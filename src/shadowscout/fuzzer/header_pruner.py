from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set
import httpx

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

AUTH_ERROR_KEYWORDS = {"unauthorized", "forbidden", "access denied", "invalid token", "authentication required"}


def _is_response_equivalent(baseline_res: httpx.Response, test_res: httpx.Response) -> bool:
    """
    Rigorously checks if the test response matches the baseline in status,
    content-type, body structure, and data presence (not just HTTP status code).
    """
    if test_res.status_code != baseline_res.status_code:
        return False

    base_ct = baseline_res.headers.get("content-type", "").lower()
    test_ct = test_res.headers.get("content-type", "").lower()

    if "json" in base_ct:
        if "json" not in test_ct:
            return False

        try:
            base_data = baseline_res.json()
            test_data = test_res.json()
        except Exception:
            return False

        # If both are dictionaries, check for error signals
        if isinstance(test_data, dict):
            # Check for error fields
            for err_key in ["error", "errors", "detail", "message"]:
                if err_key in test_data:
                    val_str = str(test_data[err_key]).lower()
                    if any(kw in val_str for kw in AUTH_ERROR_KEYWORDS):
                        return False

            # If baseline had keys, test_data must retain primary keys
            if isinstance(base_data, dict) and base_data:
                overlap = set(base_data.keys()).intersection(set(test_data.keys()))
                if not overlap:
                    return False

        # If baseline had a non-empty list, test must not be empty
        if isinstance(base_data, list) and len(base_data) > 0:
            if not isinstance(test_data, list) or len(test_data) == 0:
                return False

    return True


async def prune_request_headers(
    candidate: EndpointCandidate,
    timeout_seconds: float = 8.0,
) -> PrunedRequest:
    """
    Performs ablative testing on headers and cookies of an intercepted candidate endpoint.
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
    essential_cookies = dict(candidate.cookies)
    pruned_count = 0
    baseline_status = candidate.status_code

    async with httpx.AsyncClient(cookies=essential_cookies, follow_redirects=True, timeout=timeout_seconds) as client:
        # Step 1: Verify baseline request outside of Playwright
        try:
            if candidate.method == HttpMethod.POST:
                baseline_res = await client.post(
                    candidate.url,
                    headers=essential_headers,
                    params=candidate.query_params,
                    json=candidate.post_data if isinstance(candidate.post_data, (dict, list)) else None,
                    content=candidate.post_data if isinstance(candidate.post_data, str) else None,
                )
            else:
                baseline_res = await client.get(
                    candidate.url,
                    headers=essential_headers,
                    params=candidate.query_params,
                )
            baseline_status = baseline_res.status_code
        except Exception:
            # If baseline fails to connect, fallback to raw headers and cookies as essential
            return PrunedRequest(
                endpoint_url=candidate.clean_url,
                method=candidate.method,
                essential_headers=raw_headers,
                pruned_headers_count=0,
                auth_header_detected=auth_header_detected,
                cookies=essential_cookies,
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

                    # Strict semantic equivalence check (status + body + non-error)
                    if _is_response_equivalent(baseline_res, test_res):
                        essential_headers = temp_headers
                        pruned_count += 1
                except Exception:
                    continue

        # Step 3: Test if cookies can be safely pruned (or if they are required auth)
        if essential_cookies:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_seconds) as no_cookie_client:
                    if candidate.method == HttpMethod.POST:
                        no_cookie_res = await no_cookie_client.post(
                            candidate.url,
                            headers=essential_headers,
                            params=candidate.query_params,
                            json=candidate.post_data if isinstance(candidate.post_data, (dict, list)) else None,
                        )
                    else:
                        no_cookie_res = await no_cookie_client.get(
                            candidate.url,
                            headers=essential_headers,
                            params=candidate.query_params,
                        )

                    if _is_response_equivalent(baseline_res, no_cookie_res):
                        # Cookies were not required for this endpoint
                        essential_cookies = {}
            except Exception:
                pass

    return PrunedRequest(
        endpoint_url=candidate.clean_url,
        method=candidate.method,
        essential_headers=essential_headers,
        pruned_headers_count=pruned_count,
        auth_header_detected=auth_header_detected,
        cookies=essential_cookies,
        query_params=candidate.query_params,
        post_data=candidate.post_data,
        status_code=baseline_status,
        is_reproducible_outside_browser=True,
    )
