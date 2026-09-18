from __future__ import annotations

import json
import sys
from typing import Any, Dict
from shadowscout.interceptor.browser import PlaywrightInterceptor
from shadowscout.analyzer.scorer import score_candidate_endpoints
from shadowscout.fuzzer.header_pruner import prune_request_headers
from shadowscout.fuzzer.pagination import detect_pagination_strategy
from shadowscout.codegen.template_engine import generate_standalone_scraper
from shadowscout.codegen.openapi_exporter import export_openapi_spec


async def mcp_sniff_url(url: str) -> Dict[str, Any]:
    """MCP tool: Intercepts network traffic and returns ranked candidate endpoints."""
    interceptor = PlaywrightInterceptor()
    stream = await interceptor.intercept_url(url, headless=True, interaction_seconds=3)
    candidates = score_candidate_endpoints(stream.captured_requests)

    return {
        "target_url": url,
        "total_seen": stream.total_seen,
        "noise_filtered": stream.noise_filtered,
        "candidates": [c.model_dump() for c in candidates[:5]],
    }


async def mcp_generate_scraper(url: str) -> Dict[str, Any]:
    """MCP tool: Full pipeline from SPA URL to validated Python scraper script."""
    interceptor = PlaywrightInterceptor()
    stream = await interceptor.intercept_url(url, headless=True, interaction_seconds=3)
    candidates = score_candidate_endpoints(stream.captured_requests)

    if not candidates:
        return {"error": "No structured JSON endpoint detected on the target page."}

    best = candidates[0]
    pruned = await prune_request_headers(best)
    pagination = await detect_pagination_strategy(best, pruned.essential_headers)
    scraper_code = generate_standalone_scraper(best, pruned, pagination, target_page_url=url)
    openapi_spec = export_openapi_spec(best, pruned, pagination, target_page_url=url)

    return {
        "discovered_endpoint": best.clean_url,
        "method": best.method.value,
        "score": best.score,
        "pruned_headers_count": pruned.pruned_headers_count,
        "pagination_type": pagination.pagination_type.value,
        "generated_code": scraper_code,
        "openapi_spec": openapi_spec,
    }


def run_mcp_server() -> None:
    """Entrypoint to run ShadowScout as a standard STDIO MCP server."""
    print("ShadowScout MCP Server listening on STDIO...", file=sys.stderr)
    # Stdio loop for standard MCP integration
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            # Basic JSON-RPC handler
            req_id = msg.get("id")
            method = msg.get("method")
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"status": "ready", "server": "shadowscout-mcp", "tools": ["sniff_url", "generate_scraper"]},
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as err:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(err)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
