from __future__ import annotations

import httpx
from typing import Dict, List, Optional, Set
from shadowscout.models import EndpointCandidate, HttpMethod, PrunedRequest

IGNORED_PSEUDO_HEADERS: Set[str] = {
    ":authority", ":method", ":path", ":scheme", "host", "content-length",
}

CANDIDATE_HEADERS_TO_PRUNE: List[str] = [
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
    "sec-fetch-user",
    "priority",
    "cache-control",
    "pragma",
    "accept-language",
    "dnt",
    "upgrade-insecure-requests",
]

AUTH_HEADER_HINTS: Set[str] = {
    "authorization",
    "x-api-key",
    "x-csrf-token",
    "x-xsrf-token",
    "apikey",
    "token",
    "session-id",
}


async def prune_request_headers(
    candidate: EndpointCandidate,
    timeout_seconds: float = 8.0,
) -> PrunedRequest:
    """
    Performs ablative testing on headers of an intercepted candidate endpoint.
    Drops non-essential telemetry/browser headers to deliver a minimal viable HTTP request.
    """
    raw_headers = {
        k.lower(): v
        for k, v in candidate.raw_headers.items()
        if k.lower() not in IGNORED_PSEUDO_HEADERS
    }

    auth_header_detected: Optional[str] = None
    for h in raw_headers:
        if h in AUTH_HEADER_HINTS:
            auth_header_detected = h
            break

    # Standard headers we always ensure exist if not present
    if "user-agent" not in raw_headers:
        raw_headers["user-agent"] = "ShadowScout/0.1.0"
    if "accept" not in raw_headers:
        raw_headers["accept"] = "application/json, text/plain, */*"

    essential_headers = dict(raw_headers)
    pruned_count = 0
    baseline_status = candidate.status_code

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_seconds) as client:
        # Step 1: Verify baseline request outside of Playwright
        try:
            if candidate.method == HttpMethod.POST:
                res = await client.post(
                    candidate.url,
                    headers=essential_headers,
                    params=candidate.query_params,
                    json=candidate.post_data if isinstance(candidate.post_data, (dict, list)) else None,
                    content=candidate.post_data if isinstance(candidate.post_data, str) else None,
                )
            else:
                res = await client.get(
                    candidate.url,
                    headers=essential_headers,
                    params=candidate.query_params,
                )
            baseline_status = res.status_code
        except Exception:
            # If baseline fails to connect, fallback to raw headers as essential
            return PrunedRequest(
                endpoint_url=candidate.clean_url,
                method=candidate.method,
                essential_headers=raw_headers,
                pruned_headers_count=0,
                auth_header_detected=auth_header_detected,
                cookies={},
                query_params=candidate.query_params,
                post_data=candidate.post_data,
                status_code=candidate.status_code,
                is_reproducible_outside_browser=False,
            )

        # Step 2: Ablation pass on non-essential browser headers
        for test_header in CANDIDATE_HEADERS_TO_PRUNE:
            if test_header in essential_headers:
                temp_headers = dict(essential_headers)
                del temp_headers[test_header]

                try:
                    if candidate.method == HttpMethod.POST:
                        test_res = await client.post(
                            candidate.url,
                            headers=temp_headers,
                            params=candidate.query_params,
                            json=candidate.post_data if isinstance(candidate.post_data, (dict, list)) else None,
                        )
                    else:
                        test_res = await client.get(
                            candidate.url,
                            headers=temp_headers,
                            params=candidate.query_params,
                        )

                    # If dropping this header retains identical status code, safely discard it
                    if test_res.status_code == baseline_status:
                        essential_headers = temp_headers
                        pruned_count += 1
                except Exception:
                    continue

    return PrunedRequest(
        endpoint_url=candidate.clean_url,
        method=candidate.method,
        essential_headers=essential_headers,
        pruned_headers_count=pruned_count,
        auth_header_detected=auth_header_detected,
        cookies={},
        query_params=candidate.query_params,
        post_data=candidate.post_data,
        status_code=baseline_status,
        is_reproducible_outside_browser=True,
    )
