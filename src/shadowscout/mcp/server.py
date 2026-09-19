from __future__ import annotations

import asyncio
import json
import sys
import traceback
from typing import Any, Dict, List, Optional

from shadowscout.interceptor.browser import PlaywrightInterceptor
from shadowscout.analyzer.scorer import score_candidate_endpoints
from shadowscout.fuzzer.header_pruner import prune_request_headers
from shadowscout.fuzzer.pagination import detect_pagination_strategy
from shadowscout.codegen.template_engine import generate_standalone_scraper
from shadowscout.codegen.openapi_exporter import export_openapi_spec

MCP_PROTOCOL_VERSION = "2024-11-05"

TOOL_DEFINITIONS = [
    {
        "name": "sniff_url",
        "description": "Intercepts web traffic from a dynamic SPA website via Playwright CDP, drops noise, and returns ranked candidate API endpoints with tabular density scores.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The target dynamic SPA website URL (e.g. https://target-store.com/catalog)",
                },
                "interaction_seconds": {
                    "type": "integer",
                    "description": "Observation and scrolling simulation duration in seconds",
                    "default": 4,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "generate_scraper",
        "description": "Executes full autonomous reverse-engineering pipeline: intercepts SPA web traffic, isolates primary hidden API, prunes headers and cookies, detects pagination, and generates standalone Python scraper code + OpenAPI 3.1 specification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The target dynamic SPA website URL",
                },
                "interaction_seconds": {
                    "type": "integer",
                    "description": "Observation and scrolling simulation duration in seconds",
                    "default": 4,
                },
            },
            "required": ["url"],
        },
    },
]


async def mcp_sniff_url(url: str, interaction_seconds: int = 4) -> Dict[str, Any]:
    """MCP tool: Intercepts network traffic and returns ranked candidate endpoints."""
    interceptor = PlaywrightInterceptor()
    stream = await interceptor.intercept_url(url, headless=True, interaction_seconds=interaction_seconds)
    candidates = score_candidate_endpoints(stream.captured_requests)

    return {
        "target_url": url,
        "total_seen": stream.total_seen,
        "noise_filtered": stream.noise_filtered,
        "candidates": [c.model_dump() for c in candidates[:5]],
    }


async def mcp_generate_scraper(url: str, interaction_seconds: int = 4) -> Dict[str, Any]:
    """MCP tool: Full pipeline from SPA URL to validated Python scraper script."""
    interceptor = PlaywrightInterceptor()
    stream = await interceptor.intercept_url(url, headless=True, interaction_seconds=interaction_seconds)
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
        "essential_cookies_count": len(pruned.cookies),
        "pagination_type": pagination.pagination_type.value,
        "generated_code": scraper_code,
        "openapi_spec": openapi_spec,
    }


async def handle_mcp_request(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Processes a single JSON-RPC 2.0 MCP request and returns the corresponding response."""
    req_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})

    # 1. Initialization Handshake
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "shadowscout",
                    "version": "0.1.0",
                },
            },
        }

    # 2. Client initialization notification
    if method == "notifications/initialized":
        return None

    # 3. Healthcheck ping
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    # 4. Tool enumeration
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOL_DEFINITIONS,
            },
        }

    # 5. Tool execution
    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "sniff_url":
                url = args.get("url")
                if not url:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "Missing required argument 'url'"},
                    }
                seconds = int(args.get("interaction_seconds", 4))
                result = await mcp_sniff_url(url=url, interaction_seconds=seconds)

            elif tool_name == "generate_scraper":
                url = args.get("url")
                if not url:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "Missing required argument 'url'"},
                    }
                seconds = int(args.get("interaction_seconds", 4))
                result = await mcp_generate_scraper(url=url, interaction_seconds=seconds)

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2),
                        }
                    ],
                    "isError": False,
                },
            }

        except Exception as err:
            tb = traceback.format_exc()
            print(f"[!] MCP tool error in {tool_name}: {tb}", file=sys.stderr)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error executing tool: {err}\n{tb}"}],
                    "isError": True,
                },
            }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method '{method}' not found"},
    }


async def _mcp_loop() -> None:
    """Asynchronous line reader over sys.stdin."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    print("[*] ShadowScout MCP Server active on STDIO.", file=sys.stderr)

    while True:
        line_bytes = await reader.readline()
        if not line_bytes:
            break

        line = line_bytes.decode("utf-8", errors="replace").strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
            response = await handle_mcp_request(msg)
            if response is not None:
                output = json.dumps(response) + "\n"
                sys.stdout.write(output)
                sys.stdout.flush()
        except Exception as exc:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


def run_mcp_server() -> None:
    """Entrypoint to launch ShadowScout MCP Server."""
    try:
        asyncio.run(_mcp_loop())
    except (KeyboardInterrupt, SystemExit):
        pass
