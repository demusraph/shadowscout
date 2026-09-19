from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from shadowscout.models import CapturedRequest, EndpointCandidate


SEMANTIC_URL_PATTERNS = [
    re.compile(r"/api(/|$)", re.IGNORECASE),
    re.compile(r"/v\d+(/|$)", re.IGNORECASE),
    re.compile(r"/(products|items|catalog|listings|search|feed|inventory)(/|$)", re.IGNORECASE),
    re.compile(r"/graphql(/|$)", re.IGNORECASE),
]

TABULAR_KEY_HINTS = {
    "id", "_id", "name", "title", "price", "description", "slug", "sku",
    "created_at", "updated_at", "author", "image", "category", "rating",
    "status", "user", "email", "url", "code", "total", "amount",
}


def _find_best_array(obj: Any, current_path: str = "") -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Recursively navigates JSON structure to discover the largest array containing dictionary items.
    Returns (json_path, array_items).
    """
    best_path: Optional[str] = None
    best_items: List[Dict[str, Any]] = []

    if isinstance(obj, list):
        dict_items = [x for x in obj if isinstance(x, dict)]
        if len(dict_items) > len(best_items):
            best_path = current_path or "$"
            best_items = dict_items

    elif isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{current_path}.{key}" if current_path else key
            sub_path, sub_items = _find_best_array(value, new_path)
            if len(sub_items) > len(best_items):
                best_path = sub_path
                best_items = sub_items

    return best_path, best_items


def _is_i18n_or_config(obj: Any) -> bool:
    """Checks if a dictionary appears to be an i18n translation or frontend configuration map."""
    if not isinstance(obj, dict):
        return False
    keys = list(obj.keys())
    if not keys:
        return False
    # If majority of keys have dots and values are short strings
    dot_keys = [k for k in keys if "." in str(k)]
    if len(dot_keys) / len(keys) > 0.5:
        return True
    return False


def score_candidate_endpoints(captured_requests: List[CapturedRequest]) -> List[EndpointCandidate]:
    """
    Ranks captured requests to isolate candidate APIs carrying structured, tabular domain data.
    """
    candidates: List[EndpointCandidate] = []
    seen_clean_urls: set[str] = set()

    for req in captured_requests:
        # Require JSON response
        if not isinstance(req.response_body, (dict, list)):
            continue

        parsed_url = urlparse(req.url)
        clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        dedup_key = f"{req.method.value}:{clean_url}"
        if dedup_key in seen_clean_urls:
            continue
        seen_clean_urls.add(dedup_key)

        score = 0.0
        reasons: list[str] = []

        # HTTP Status criteria
        if req.status_code == 200:
            score += 15.0
            reasons.append("Status 200 OK")
        elif req.status_code in (201, 204):
            score += 10.0

        # Semantic URL cues
        for pattern in SEMANTIC_URL_PATTERNS:
            if pattern.search(parsed_url.path):
                score += 20.0
                reasons.append(f"Semantic API URL match ({pattern.pattern})")
                break

        # Discover structured tabular array in response body
        array_path, items = _find_best_array(req.response_body)
        item_count = len(items)

        if items:
            score += 25.0
            reasons.append(f"Contains array of {item_count} items at path '{array_path}'")

            if item_count >= 5:
                score += 15.0
            if item_count >= 15:
                score += 10.0

            # Inspect consistency and richness of keys
            first_item = items[0]
            item_keys = set(first_item.keys())
            if len(item_keys) >= 3:
                score += 15.0
                reasons.append(f"Rich tabular structure ({len(item_keys)} attributes per item)")

            matched_hints = item_keys.intersection(TABULAR_KEY_HINTS)
            if matched_hints:
                score += 15.0
                reasons.append(f"Entity domain attributes: {', '.join(sorted(matched_hints)[:4])}")

        # Check for i18n / config penalty
        if _is_i18n_or_config(req.response_body):
            score -= 40.0
            reasons.append("Penalized: i18n / UI configuration dictionary")

        # Small flat metadata penalty
        if not items and isinstance(req.response_body, dict) and len(req.response_body) < 3:
            score -= 20.0
            reasons.append("Penalized: Minimal flat metadata object")

        candidate = EndpointCandidate(
            endpoint_id=req.id,
            url=req.url,
            clean_url=clean_url,
            method=req.method,
            status_code=req.status_code,
            score=max(0.0, score),
            reason="; ".join(reasons),
            is_json=True,
            array_key_path=array_path,
            item_count=item_count,
            sample_items=items[:5],
            raw_headers=req.headers,
            cookies=req.cookies,
            query_params=req.query_params,
            post_data=req.post_data,
        )
        candidates.append(candidate)

    # Sort descending by score
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates
