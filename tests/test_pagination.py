from __future__ import annotations

import pytest
import httpx
from shadowscout.fuzzer.pagination import detect_pagination_strategy
from shadowscout.fuzzer.header_pruner import prune_request_headers
from shadowscout.models import EndpointCandidate, HttpMethod, PaginationType


@pytest.mark.asyncio
async def test_pagination_post_endpoint_probed_with_post(monkeypatch):
    """FIX #5: Ensures that candidate with POST method is probed using POST with payload."""
    recorded_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            200,
            json={"items": [{"id": 1}], "next_cursor": "cur_123"},
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def mock_client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_client_factory)

    candidate = EndpointCandidate(
        endpoint_id="c-post-1",
        url="https://api.example.com/search",
        clean_url="https://api.example.com/search",
        method=HttpMethod.POST,
        status_code=200,
        raw_headers={"authorization": "Bearer token"},
        post_data={"query": "laptop", "limit": 20},
    )

    pag_config = await detect_pagination_strategy(
        candidate=candidate,
        essential_headers={"authorization": "Bearer token"},
        timeout_seconds=2.0,
    )

    assert len(recorded_requests) == 1
    assert recorded_requests[0].method == "POST"
    assert pag_config.pagination_type == PaginationType.CURSOR
    assert pag_config.cursor_json_path == "next_cursor"


@pytest.mark.asyncio
async def test_write_endpoints_guard_limits_requests(monkeypatch):
    """FIX #1: Ensures write endpoints (POST) do not receive repeated probing (>1 request)."""
    recorded_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            200,
            json={"status": "created", "id": 999},
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def mock_client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_client_factory)

    candidate = EndpointCandidate(
        endpoint_id="c-order-1",
        url="https://api.example.com/orders",
        clean_url="https://api.example.com/orders",
        method=HttpMethod.POST,
        status_code=201,
        raw_headers={
            "authorization": "Bearer token",
            "sec-ch-ua": '"Chromium";v="124"',
            "accept-language": "en-US",
        },
        post_data={"item_id": 42, "qty": 1},
    )

    # 1. Header pruning MUST make 0 requests for POST
    pruned = await prune_request_headers(candidate, timeout_seconds=2.0)
    assert len(recorded_requests) == 0
    assert pruned.is_reproducible_outside_browser is False

    # 2. Pagination detection may make at most 1 cursor probe request
    pag_config = await detect_pagination_strategy(
        candidate=candidate,
        essential_headers=pruned.essential_headers,
        timeout_seconds=2.0,
    )

    # Total requests across both phases must not exceed 1 request
    assert len(recorded_requests) <= 1


@pytest.mark.asyncio
async def test_put_patch_delete_skip_all_probing(monkeypatch):
    """FIX #1: PUT/PATCH/DELETE endpoints skip all probing completely (0 requests)."""
    recorded_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: httpx.AsyncClient(transport=transport, *a, **kw))

    for m in [HttpMethod.PUT, HttpMethod.PATCH, HttpMethod.DELETE]:
        candidate = EndpointCandidate(
            endpoint_id=f"c-{m.value}",
            url="https://api.example.com/item/1",
            clean_url="https://api.example.com/item/1",
            method=m,
            status_code=200,
        )
        pruned = await prune_request_headers(candidate, timeout_seconds=1.0)
        assert pruned.is_reproducible_outside_browser is False

        await detect_pagination_strategy(candidate, pruned.essential_headers, timeout_seconds=1.0)

    # Zero requests across all PUT/PATCH/DELETE operations
    assert len(recorded_requests) == 0
