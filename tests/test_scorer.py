from __future__ import annotations

import pytest
from shadowscout.analyzer.scorer import score_candidate_endpoints
from shadowscout.models import CapturedRequest, HttpMethod


def test_scorer_identifies_tabular_data():
    product_req = CapturedRequest(
        id="req-1",
        url="https://store.example.com/api/v1/products?page=1",
        method=HttpMethod.GET,
        status_code=200,
        headers={"content-type": "application/json"},
        query_params={"page": "1"},
        response_content_type="application/json",
        response_body={
            "status": "success",
            "items": [
                {"id": 1, "name": "Laptop", "price": 999.0, "sku": "LP-01", "stock": 10},
                {"id": 2, "name": "Mouse", "price": 49.0, "sku": "MS-02", "stock": 50},
                {"id": 3, "name": "Keyboard", "price": 89.0, "sku": "KB-03", "stock": 30},
                {"id": 4, "name": "Monitor", "price": 299.0, "sku": "MN-04", "stock": 15},
                {"id": 5, "name": "Headphones", "price": 79.0, "sku": "HD-05", "stock": 25},
            ],
        },
    )

    i18n_req = CapturedRequest(
        id="req-2",
        url="https://store.example.com/locales/en.json",
        method=HttpMethod.GET,
        status_code=200,
        headers={"content-type": "application/json"},
        query_params={},
        response_content_type="application/json",
        response_body={
            "nav.home": "Home",
            "nav.catalog": "Catalog",
            "btn.submit": "Submit",
            "btn.cancel": "Cancel",
            "footer.copyright": "2026 Store",
        },
    )

    candidates = score_candidate_endpoints([product_req, i18n_req])

    assert len(candidates) >= 1
    top_candidate = candidates[0]
    assert top_candidate.endpoint_id == "req-1"
    assert top_candidate.score >= 60.0
    assert top_candidate.item_count == 5
    assert top_candidate.array_key_path == "items"
