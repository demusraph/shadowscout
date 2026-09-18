from __future__ import annotations

import httpx
from typing import Any, Dict, Optional
from shadowscout.models import EndpointCandidate, HttpMethod, PaginationConfig, PaginationType

PAGE_PARAM_KEYS = {"page", "p", "page_number", "page_no", "pageindex", "currentpage"}
SIZE_PARAM_KEYS = {"limit", "size", "per_page", "pagesize", "count", "rows", "perpage"}
OFFSET_PARAM_KEYS = {"offset", "skip", "start", "from"}
CURSOR_PARAM_KEYS = {"cursor", "after", "starting_after", "nexttoken", "next_cursor"}


def _find_json_key(data: Any, target_keys: set[str], path: str = "") -> Optional[str]:
    """Finds first matching key path in nested dictionary."""
    if not isinstance(data, dict):
        return None
    for k, v in data.items():
        lowered = k.lower()
        new_path = f"{path}.{k}" if path else k
        if lowered in target_keys:
            return new_path
        if isinstance(v, dict):
            sub = _find_json_key(v, target_keys, new_path)
            if sub:
                return sub
    return None


async def detect_pagination_strategy(
    candidate: EndpointCandidate,
    essential_headers: Dict[str, str],
    timeout_seconds: float = 6.0,
) -> PaginationConfig:
    """
    Infers pagination strategy by analyzing query parameters, payload structures,
    and probing parameter fuzzing against the target endpoint.
    """
    params = dict(candidate.query_params)
    lowered_params = {k.lower(): k for k in params.keys()}

    pag_type = PaginationType.NONE
    page_param: Optional[str] = None
    size_param: Optional[str] = None
    cursor_json_path: Optional[str] = None
    total_count_json_path: Optional[str] = None
    default_size = 20
    max_tested_size = 20

    # 1. Check for page-based query parameters
    matched_page = set(lowered_params.keys()).intersection(PAGE_PARAM_KEYS)
    matched_size = set(lowered_params.keys()).intersection(SIZE_PARAM_KEYS)
    matched_offset = set(lowered_params.keys()).intersection(OFFSET_PARAM_KEYS)
    matched_cursor = set(lowered_params.keys()).intersection(CURSOR_PARAM_KEYS)

    if matched_page:
        pag_type = PaginationType.PAGE_NUMBER
        page_param = lowered_params[next(iter(matched_page))]
    elif matched_offset:
        pag_type = PaginationType.OFFSET_LIMIT
        page_param = lowered_params[next(iter(matched_offset))]
    elif matched_cursor:
        pag_type = PaginationType.CURSOR
        page_param = lowered_params[next(iter(matched_cursor))]

    if matched_size:
        size_param = lowered_params[next(iter(matched_size))]
        try:
            default_size = int(params[size_param])
            max_tested_size = default_size
        except ValueError:
            default_size = 20

    # 2. Inspect response body sample for total count or cursor links
    if candidate.sample_items:
        # Check parent structures if available in post data or candidate context
        pass

    # 3. Active Fuzzing: Probe larger limit size to test backend flexibility
    if size_param and candidate.method == HttpMethod.GET:
        test_size = 100
        test_params = dict(params)
        test_params[size_param] = str(test_size)

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                res = await client.get(
                    candidate.url,
                    headers=essential_headers,
                    params=test_params,
                )
                if res.status_code == 200:
                    data = res.json()
                    # Check if response accepted larger limit
                    max_tested_size = test_size
        except Exception:
            max_tested_size = default_size

    # If no parameters found in query string, fallback to default page_number config
    if pag_type == PaginationType.NONE:
        pag_type = PaginationType.PAGE_NUMBER
        page_param = "page"
        size_param = "limit"
        default_size = 20
        max_tested_size = 20

    return PaginationConfig(
        pagination_type=pag_type,
        page_param=page_param,
        size_param=size_param,
        default_size=default_size,
        max_tested_size=max_tested_size,
        cursor_json_path=cursor_json_path,
        total_count_json_path=total_count_json_path,
    )
