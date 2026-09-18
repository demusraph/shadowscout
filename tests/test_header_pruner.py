from __future__ import annotations

import pytest
from shadowscout.fuzzer.header_pruner import prune_request_headers
from shadowscout.models import EndpointCandidate, HttpMethod


@pytest.mark.asyncio
async def test_header_pruner_detects_auth():
    candidate = EndpointCandidate(
        endpoint_id="c-1",
        url="https://api.example.com/data",
        clean_url="https://api.example.com/data",
        method=HttpMethod.GET,
        status_code=200,
        raw_headers={
            ":authority": "api.example.com",
            "authorization": "Bearer token_secret_123",
            "sec-ch-ua": '"Chromium";v="124"',
            "accept-language": "en-US,en;q=0.9",
        },
    )

    # Since api.example.com won't connect in local unit tests, it should fallback safely
    pruned = await prune_request_headers(candidate, timeout_seconds=1.0)
    assert pruned.auth_header_detected == "authorization"
    assert ":authority" not in pruned.essential_headers
