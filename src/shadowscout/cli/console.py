from __future__ import annotations

from typing import List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from shadowscout.models import EndpointCandidate, ScoutResult

console = Console(safe_box=True)


def print_banner() -> None:
    """Prints ASCII styling banner."""
    banner_text = """[bold cyan]SHADOWSCOUT[/bold cyan] [bold white]v0.1.0[/bold white]
[dim]Autonomous Hidden API Reverse-Engineering & High-Speed Scraper Synthesizer[/dim]"""
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def print_candidates_table(candidates: List[EndpointCandidate]) -> None:
    """Renders ranked candidate endpoints in a Rich table."""
    table = Table(title="[bold green]Discovered Candidate Endpoints[/bold green]", border_style="dim")
    table.add_column("#", justify="center", style="bold cyan")
    table.add_column("Score", justify="right")
    table.add_column("Method", justify="center", style="magenta")
    table.add_column("Endpoint Clean URL", style="white")
    table.add_column("Items", justify="right", style="yellow")
    table.add_column("Payload Key Path", style="dim")

    for idx, c in enumerate(candidates[:10], start=1):
        if c.score >= 80:
            score_str = f"[bold green]{c.score:.1f}[/bold green]"
        elif c.score >= 50:
            score_str = f"[yellow]{c.score:.1f}[/yellow]"
        else:
            score_str = f"[red]{c.score:.1f}[/red]"

        table.add_row(
            str(idx),
            score_str,
            c.method.value,
            c.clean_url,
            str(c.item_count),
            c.array_key_path or "-",
        )

    console.print(table)


def print_scout_summary(result: ScoutResult, script_path: str) -> None:
    """Prints execution summary after completing reverse engineering."""
    c = result.selected_candidate
    p = result.pruned_request

    summary_table = Table(show_header=False, border_style="green", box=None)
    summary_table.add_row("[bold cyan]Target Web Page:[/bold cyan]", result.target_url)
    summary_table.add_row("[bold cyan]Network Traffic:[/bold cyan]", f"{result.total_requests_captured} total, {result.filtered_requests_count} telemetry noise dropped")
    if c:
        summary_table.add_row("[bold cyan]Target API Discovered:[/bold cyan]", f"[bold green]{c.method.value} {c.clean_url}[/bold green]")
        summary_table.add_row("[bold cyan]Data Path:[/bold cyan]", f"'{c.array_key_path}' ({c.item_count} sample items)")
    if p:
        summary_table.add_row("[bold cyan]Ablative Header Pruning:[/bold cyan]", f"[bold yellow]{p.pruned_headers_count}[/bold yellow] useless headers stripped ({len(p.essential_headers)} essential remaining)")
    if result.pagination:
        summary_table.add_row("[bold cyan]Pagination Strategy:[/bold cyan]", f"{result.pagination.pagination_type.value} (param: '{result.pagination.page_param}')")

    summary_table.add_row("[bold cyan]Generated Scraper File:[/bold cyan]", f"[bold underline green]{script_path}[/bold underline green]")
    summary_table.add_row("[bold cyan]Verification Status:[/bold cyan]", "[bold green]PASSED (Subprocess Verified 100% Runnable)[/bold green]" if result.is_verified else "[yellow]UNVERIFIED[/yellow]")

    console.print(Panel(summary_table, title="[bold green][OK] Reverse-Engineering Complete[/bold green]", border_style="green"))
