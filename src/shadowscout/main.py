from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Optional
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from shadowscout.cli.console import (
    console,
    print_banner,
    print_candidates_table,
    print_scout_summary,
)
from shadowscout.cli.mock_server import MockServerManager
from shadowscout.cli.validator import verify_generated_code
from shadowscout.interceptor.browser import PlaywrightInterceptor
from shadowscout.analyzer.scorer import score_candidate_endpoints
from shadowscout.fuzzer.header_pruner import prune_request_headers
from shadowscout.fuzzer.pagination import detect_pagination_strategy
from shadowscout.codegen.template_engine import generate_standalone_scraper
from shadowscout.codegen.openapi_exporter import export_openapi_spec
from shadowscout.models import ScoutResult

app = typer.Typer(
    name="shadowscout",
    help="Autonomous Hidden API Reverse-Engineering & High-Speed Scraper Synthesizer",
    add_completion=False,
)


async def _run_pipeline(
    url: str,
    output_script: str = "scraper.py",
    output_openapi: Optional[str] = None,
    headless: bool = True,
    interaction_seconds: int = 4,
    verify: bool = True,
) -> ScoutResult:
    """Core asynchronous execution pipeline of ShadowScout."""
    with Progress(
        SpinnerColumn(spinner_name="line"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Network Interception
        t1 = progress.add_task(f"[cyan]Navigating to {url} and sniffing traffic...", total=None)
        interceptor = PlaywrightInterceptor()
        stream = await interceptor.intercept_url(
            url=url,
            headless=headless,
            interaction_seconds=interaction_seconds,
        )
        progress.update(t1, description=f"[green]Captured {stream.total_seen} requests ({stream.noise_filtered} telemetry dropped)")

        # Step 2: Payload Analysis & Candidate Ranking
        t2 = progress.add_task("[cyan]Ranking candidate endpoints via tabular density heuristic...", total=None)
        candidates = score_candidate_endpoints(stream.captured_requests)
        progress.update(t2, description=f"[green]Ranked {len(candidates)} candidate API endpoints")

        if not candidates:
            console.print("[bold red][!] No structured JSON API detected on the target page.[/bold red]")
            return ScoutResult(
                target_url=url,
                total_requests_captured=stream.total_seen,
                filtered_requests_count=stream.noise_filtered,
                candidates=[],
            )

        best_candidate = candidates[0]

        # Step 3: Header Ablation & Minimization
        t3 = progress.add_task(f"[cyan]Testing header ablation on {best_candidate.clean_url}...", total=None)
        pruned = await prune_request_headers(best_candidate)
        progress.update(t3, description=f"[green]Pruned {pruned.pruned_headers_count} non-essential headers")

        # Step 4: Pagination & Fuzzing Detection
        t4 = progress.add_task("[cyan]Detecting pagination strategy & probing limits...", total=None)
        pagination = await detect_pagination_strategy(best_candidate, pruned.essential_headers)
        progress.update(t4, description=f"[green]Pagination strategy: {pagination.pagination_type.value}")

        # Step 5: Code Synthesis
        t5 = progress.add_task(f"[cyan]Synthesizing standalone scraper to {output_script}...", total=None)
        scraper_code = generate_standalone_scraper(
            candidate=best_candidate,
            pruned=pruned,
            pagination=pagination,
            target_page_url=url,
        )

        with open(output_script, "w", encoding="utf-8") as f:
            f.write(scraper_code)

        openapi_spec = None
        if output_openapi:
            openapi_spec = export_openapi_spec(
                candidate=best_candidate,
                pruned=pruned,
                pagination=pagination,
                target_page_url=url,
            )
            with open(output_openapi, "w", encoding="utf-8") as f:
                json.dump(openapi_spec, f, indent=2)

        progress.update(t5, description=f"[green]Synthesized scraper in '{output_script}'")

        # Step 6: Subprocess Self-Verification Gate
        is_verified = False
        verification_output = None
        if verify:
            t6 = progress.add_task("[cyan]Executing subprocess verification gate...", total=None)
            is_verified, verification_output = verify_generated_code(output_script)
            if is_verified:
                progress.update(t6, description="[bold green]Subprocess verification: PASSED (100% Runnable)")
            else:
                progress.update(t6, description="[bold red]Subprocess verification: FAILED")

    result = ScoutResult(
        target_url=url,
        total_requests_captured=stream.total_seen,
        filtered_requests_count=stream.noise_filtered,
        candidates=candidates,
        selected_candidate=best_candidate,
        pruned_request=pruned,
        pagination=pagination,
        generated_scraper_code=scraper_code,
        openapi_spec=openapi_spec,
        is_verified=is_verified,
        verification_output=verification_output,
    )

    return result


@app.command()
def sniff(
    url: str = typer.Argument(..., help="The target dynamic SPA web page URL"),
    output: str = typer.Option("scraper.py", "-o", "--output", help="Path to save synthesized Python scraper"),
    openapi: Optional[str] = typer.Option(None, "--openapi", help="Path to export OpenAPI 3.1 specification JSON"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode"),
    interaction_seconds: int = typer.Option(4, "-t", "--time", help="Interaction and scrolling observation time in seconds"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Run automated subprocess verification gate"),
) -> None:
    """
    Reverse-engineers a dynamic web page, isolates hidden APIs, and generates a zero-browser scraper.
    """
    print_banner()
    result = asyncio.run(
        _run_pipeline(
            url=url,
            output_script=output,
            output_openapi=openapi,
            headless=headless,
            interaction_seconds=interaction_seconds,
            verify=verify,
        )
    )

    if result.candidates:
        print_candidates_table(result.candidates)
        print_scout_summary(result, script_path=output)


@app.command()
def demo(
    output: str = typer.Option("demo_scraper.py", "-o", "--output", help="Output path for demo scraper"),
    port: int = typer.Option(8765, "--port", help="Port for the mock server"),
) -> None:
    """
    Runs an instant zero-config interactive demo using an embedded mock SPA e-commerce store.
    """
    print_banner()
    console.print(f"[bold yellow]Starting embedded mock SPA server on port {port}...[/bold yellow]")

    server_mgr = MockServerManager(port=port)
    mock_url = server_mgr.start()
    time.sleep(1.0)

    try:
        console.print(f"[green]Mock SPA running at {mock_url}[/green]")
        result = asyncio.run(
            _run_pipeline(
                url=mock_url,
                output_script=output,
                output_openapi="demo_openapi.json",
                headless=True,
                interaction_seconds=3,
                verify=True,
            )
        )

        if result.candidates:
            print_candidates_table(result.candidates)
            print_scout_summary(result, script_path=output)
            console.print(f"\n[bold cyan]Run the generated scraper yourself:[/bold cyan]")
            console.print(f"[white]python {output} --pages 2 -o products.jsonl[/white]\n")
    finally:
        server_mgr.stop()


@app.command()
def mcp() -> None:
    """
    Launches ShadowScout as a Model Context Protocol (MCP) server over STDIO.
    """
    from shadowscout.mcp.server import run_mcp_server
    run_mcp_server()


if __name__ == "__main__":
    app()
