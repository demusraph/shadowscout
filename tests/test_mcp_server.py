from __future__ import annotations

import pytest
from shadowscout.mcp.server import handle_mcp_request


@pytest.mark.asyncio
async def test_mcp_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    }
    resp = await handle_mcp_request(req)
    assert resp is not None
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == "shadowscout"
    assert "tools" in resp["result"]["capabilities"]


@pytest.mark.asyncio
async def test_mcp_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = await handle_mcp_request(req)
    assert resp is not None
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "sniff_url" in tool_names
    assert "generate_scraper" in tool_names


@pytest.mark.asyncio
async def test_mcp_tools_call_missing_arg():
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "sniff_url",
            "arguments": {},
        },
    }
    resp = await handle_mcp_request(req)
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_mcp_unknown_method():
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "invalid/method",
        "params": {},
    }
    resp = await handle_mcp_request(req)
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32601
