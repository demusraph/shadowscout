from __future__ import annotations

import json
from typing import Any, Dict, List
from shadowscout.models import EndpointCandidate, PaginationConfig, PaginationType, PrunedRequest
from shadowscout.codegen.schema_inferrer import infer_pydantic_models


def generate_standalone_scraper(
    candidate: EndpointCandidate,
    pruned: PrunedRequest,
    pagination: PaginationConfig,
    target_page_url: str = "",
) -> str:
    """
    Synthesizes a production-ready, standalone Python scraper script using httpx and Pydantic.
    Operates 100% without a headless browser at native HTTP speed.
    """
    # 1. Infer Pydantic model code
    _, pydantic_code = infer_pydantic_models(candidate.sample_items, model_name="ScrapedItem")

    # 2. Serialize parameters, cookies, and headers cleanly
    headers_repr = json.dumps(pruned.essential_headers, indent=4)
    cookies_repr = json.dumps(pruned.cookies, indent=4)
    params_repr = json.dumps(pruned.query_params, indent=4)
    post_data_repr = json.dumps(pruned.post_data, indent=4) if pruned.post_data else "None"
    array_path_repr = repr(candidate.array_key_path)
    cursor_path_repr = repr(pagination.cursor_json_path)

    # 3. Construct script template
    script = f'''#!/usr/bin/env python3
"""
Autonomous High-Speed Scraper synthesized by ShadowScout.
Target Origin: {target_page_url or candidate.clean_url}
Discovered API: {candidate.clean_url}
Method: {candidate.method.value}
Generated without browser dependencies for maximum throughput and reliability.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import httpx
from pydantic import BaseModel, ConfigDict, Field

# ==============================================================================
# Inferred Data Schema (Pydantic V2)
# ==============================================================================
{pydantic_code}

# ==============================================================================
# Scraper Implementation
# ==============================================================================
API_ENDPOINT = {repr(candidate.clean_url)}
METHOD = {repr(candidate.method.value)}
ESSENTIAL_HEADERS = {headers_repr}
ESSENTIAL_COOKIES = {cookies_repr}
DEFAULT_QUERY_PARAMS = {params_repr}
POST_DATA = {post_data_repr}
ARRAY_KEY_PATH = {array_path_repr}
CURSOR_JSON_PATH = {cursor_path_repr}

PAGINATION_TYPE = {repr(pagination.pagination_type.value)}
PAGE_PARAM = {repr(pagination.page_param)}
SIZE_PARAM = {repr(pagination.size_param)}
DEFAULT_SIZE = {pagination.default_size}


def extract_items_from_payload(payload: Any, path: Optional[str]) -> List[Dict[str, Any]]:
    """Recursively resolves array path inside response payload."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict) or not path:
        return []

    curr = payload
    parts = path.strip("$.").split(".")
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            break

    if isinstance(curr, list):
        return [x for x in curr if isinstance(x, dict)]
    return []


def extract_cursor_from_payload(payload: Any, path: Optional[str]) -> Optional[str]:
    """Extracts next cursor value from payload using configured path or common heuristics."""
    if not isinstance(payload, dict):
        return None

    if path:
        curr = payload
        parts = path.strip("$.").split(".")
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            else:
                curr = None
                break
        if curr is not None:
            return str(curr)

    # Heuristic fallback for common cursor field names
    for candidate_key in ["next_cursor", "nextCursor", "end_cursor", "cursor", "next_page_token", "nextToken"]:
        if candidate_key in payload and payload[candidate_key]:
            return str(payload[candidate_key])
        if "page_info" in payload and isinstance(payload["page_info"], dict):
            if candidate_key in payload["page_info"] and payload["page_info"][candidate_key]:
                return str(payload["page_info"][candidate_key])

    return None


class DirectScraper:
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    async def fetch_page(
        self,
        client: httpx.AsyncClient,
        page_num: int,
        limit_size: int,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetches a single page with exponential retry on 429 or server errors. Returns (items, next_cursor)."""
        params = dict(DEFAULT_QUERY_PARAMS)

        if PAGINATION_TYPE == "page_number" and PAGE_PARAM:
            params[PAGE_PARAM] = str(page_num)
        elif PAGINATION_TYPE == "offset_limit" and PAGE_PARAM:
            offset = (page_num - 1) * limit_size
            params[PAGE_PARAM] = str(offset)
        elif PAGINATION_TYPE == "cursor" and PAGE_PARAM and cursor:
            params[PAGE_PARAM] = cursor

        if SIZE_PARAM:
            params[SIZE_PARAM] = str(limit_size)

        for attempt in range(3):
            try:
                if METHOD == "POST":
                    resp = await client.post(
                        API_ENDPOINT,
                        headers=ESSENTIAL_HEADERS,
                        params=params,
                        json=POST_DATA,
                        timeout=self.timeout,
                    )
                else:
                    resp = await client.get(
                        API_ENDPOINT,
                        headers=ESSENTIAL_HEADERS,
                        params=params,
                        timeout=self.timeout,
                    )

                if resp.status_code == 200:
                    payload = resp.json()
                    items = extract_items_from_payload(payload, ARRAY_KEY_PATH)
                    next_cursor = extract_cursor_from_payload(payload, CURSOR_JSON_PATH)
                    return items, next_cursor
                elif resp.status_code == 429:
                    # Rate limit encountered; back off
                    wait_time = (attempt + 1) * 2.0
                    print(f"[!] Rate limited (429). Retrying in {{wait_time}}s...", file=sys.stderr)
                    await asyncio.sleep(wait_time)
                else:
                    print(f"[!] HTTP error {{resp.status_code}} on page {{page_num}}", file=sys.stderr)
                    break
            except Exception as exc:
                print(f"[!] Network exception (attempt {{attempt + 1}}): {{exc}}", file=sys.stderr)
                await asyncio.sleep(1.0)

        return [], None

    async def run(
        self,
        max_pages: int = 5,
        limit_size: int = DEFAULT_SIZE,
        delay_seconds: float = 0.2,
    ) -> List[ScrapedItem]:
        """Runs the scraping loop, handles cursor advancement, and validates items against ScrapedItem model."""
        all_items: List[ScrapedItem] = []
        current_cursor: Optional[str] = None

        async with httpx.AsyncClient(cookies=ESSENTIAL_COOKIES, follow_redirects=True) as client:
            for page in range(1, max_pages + 1):
                raw_items, next_cursor = await self.fetch_page(
                    client, page_num=page, limit_size=limit_size, cursor=current_cursor
                )
                if not raw_items:
                    print(f"[*] Completed or empty page reached at page {{page}}.")
                    break

                for item_dict in raw_items:
                    try:
                        validated = ScrapedItem.model_validate(item_dict)
                        all_items.append(validated)
                    except Exception:
                        # Continue even if single item fails strict schema
                        pass

                print(f"[+] Page {{page}}: Extracted {{len(raw_items)}} items (Total: {{len(all_items)}})")

                # Advance cursor for cursor-based pagination
                if PAGINATION_TYPE == "cursor":
                    if not next_cursor or next_cursor == current_cursor:
                        print(f"[*] Cursor exhausted or reached end of stream at page {{page}}.")
                        break
                    current_cursor = next_cursor

                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)

        return all_items


def save_records(items: List[ScrapedItem], output_path: str) -> None:
    """Exports validated records to JSONL, CSV, or JSON."""
    if not items:
        print("[!] No records to save.", file=sys.stderr)
        return

    data = [item.model_dump(by_alias=True) for item in items]

    if output_path.endswith(".csv"):
        fieldnames = list(data[0].keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                # Flatten any nested structures to strings for CSV compatibility
                flat_row = {{k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in row.items()}}
                writer.writerow(flat_row)
    elif output_path.endswith(".json"):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:  # Default to .jsonl
        with open(output_path, "w", encoding="utf-8") as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + "\\n")

    print(f"[OK] Saved {{len(data)}} records to '{{output_path}}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="High-Speed Standalone API Scraper")
    parser.add_argument("-p", "--pages", type=int, default=5, help="Maximum number of pages to scrape")
    parser.add_argument("-l", "--limit", type=int, default=DEFAULT_SIZE, help="Batch limit per request")
    parser.add_argument("-o", "--output", type=str, default="scraped_data.jsonl", help="Output file path (.jsonl, .json, .csv)")
    parser.add_argument("--test-run", action="store_true", help="Runs single page test with limit 5 for verification")

    args = parser.parse_args()

    max_pages = 1 if args.test_run else args.pages
    batch_size = 5 if args.test_run else args.limit

    scraper = DirectScraper()
    items = asyncio.run(scraper.run(max_pages=max_pages, limit_size=batch_size))

    if args.test_run:
        print(f"=== TEST RUN VERIFICATION ===")
        print(f"Items extracted: {{len(items)}}")
        if items:
            sample = items[0].model_dump()
            print(f"Sample item keys: {{list(sample.keys())}}")
        sys.exit(0 if len(items) > 0 else 1)

    save_records(items, args.output)


if __name__ == "__main__":
    main()
'''
    return script
