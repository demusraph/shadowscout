from __future__ import annotations

import asyncio
import pytest
from shadowscout.codegen.template_engine import (
    generate_standalone_scraper,
    extract_cursor_from_payload,
    AuthenticationExpiredError,
)
from shadowscout.models import (
    EndpointCandidate,
    HttpMethod,
    PaginationConfig,
    PaginationType,
    PrunedRequest,
)


def _make_dummy_candidate():
    candidate = EndpointCandidate(
        endpoint_id="c-test",
        url="https://api.example.com/v1/items",
        clean_url="https://api.example.com/v1/items",
        method=HttpMethod.GET,
        status_code=200,
        sample_items=[{"id": 1, "name": "Item 1"}],
        raw_headers={"authorization": "Bearer test-token"},
    )
    pruned = PrunedRequest(
        endpoint_url="https://api.example.com/v1/items",
        method=HttpMethod.GET,
        essential_headers={"authorization": "Bearer test-token"},
        pruned_headers_count=2,
        auth_header_detected="authorization",
        status_code=200,
        is_reproducible_outside_browser=True,
    )
    pagination = PaginationConfig(
        pagination_type=PaginationType.PAGE_NUMBER,
        page_param="page",
        size_param="limit",
        default_size=20,
    )
    return candidate, pruned, pagination


def test_template_includes_concurrency_and_semaphore():
    """FIX #3: Verify that template generates bounded concurrency with asyncio.Semaphore and --concurrency."""
    candidate, pruned, pagination = _make_dummy_candidate()
    code = generate_standalone_scraper(candidate, pruned, pagination)

    assert "asyncio.Semaphore" in code
    assert "--concurrency" in code
    assert "-c" in code
    assert "concurrency: int = 5" in code


def test_template_detects_auth_token_expiry_on_401():
    """FIX #4: Verify that 401/403 triggers AuthenticationExpiredError with actionable instructions."""
    candidate, pruned, pagination = _make_dummy_candidate()
    code = generate_standalone_scraper(candidate, pruned, pagination)

    assert "AuthenticationExpiredError" in code
    assert "resp.status_code in (401, 403)" in code
    assert "The authorization token, session cookie, or API key has expired" in code


def test_cursor_extractor_skips_non_scalar_values():
    """FIX #6(b): Verify extract_cursor_from_payload returns None when cursor is a dict/list."""
    # When cursor field is a nested dict or list, it must NOT convert it to str("{...}")
    payload_dict_cursor = {
        "items": [],
        "next_cursor": {"nested_key": "not_a_scalar"},
    }
    assert extract_cursor_from_payload(payload_dict_cursor, None) is None
    assert extract_cursor_from_payload(payload_dict_cursor, "next_cursor") is None

    payload_list_cursor = {
        "items": [],
        "next_cursor": [1, 2, 3],
    }
    assert extract_cursor_from_payload(payload_list_cursor, None) is None

    # Valid scalar values should be extracted cleanly
    payload_scalar_str = {"items": [], "next_cursor": "cursor_token_xyz"}
    assert extract_cursor_from_payload(payload_scalar_str, None) == "cursor_token_xyz"

    payload_scalar_int = {"items": [], "next_cursor": 12345}
    assert extract_cursor_from_payload(payload_scalar_int, None) == "12345"


@pytest.mark.asyncio
async def test_generated_code_no_silent_data_drop(capsys):
    """FIX #2(b): Verify generated scraper execution does not silently drop items when types vary."""
    candidate, pruned, pagination = _make_dummy_candidate()
    code = generate_standalone_scraper(candidate, pruned, pagination)

    # Verify fallback handling code is present
    assert "ScrapedItem.model_construct" in code
    assert "validation_failures" in code
    assert "failed strict validation and were preserved via fallback" in code

    # Execute generated code in isolated namespace
    namespace: dict = {}
    exec(code, namespace)

    DirectScraper = namespace["DirectScraper"]
    ScrapedItem = namespace["ScrapedItem"]

    scraper = DirectScraper()

    # Mock fetch_page to return an item that violates strict inferred schema
    # (e.g. string for integer id, or unexpected structure)
    async def mock_fetch_page(client, page_num, limit_size, cursor=None):
        if page_num == 1:
            return [{"id": "INVALID_NON_INT_STRING", "name": "Item 2"}], None
        return [], None

    scraper.fetch_page = mock_fetch_page

    items = await scraper.run(max_pages=1)
    captured = capsys.readouterr()

    # The item must NOT be dropped!
    assert len(items) == 1
    # Check that warning was logged to stderr
    assert "failed strict validation and were preserved" in captured.err
