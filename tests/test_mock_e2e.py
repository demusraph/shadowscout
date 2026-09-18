from __future__ import annotations

import asyncio
import os
import pytest
from shadowscout.main import _run_pipeline
from shadowscout.cli.mock_server import MockServerManager


@pytest.mark.asyncio
async def test_end_to_end_mock_pipeline(tmp_path):
    server_mgr = MockServerManager(port=8899)
    mock_url = server_mgr.start()
    await asyncio.sleep(1.0)

    output_script = str(tmp_path / "test_scraper.py")
    output_openapi = str(tmp_path / "test_openapi.json")

    try:
        result = await _run_pipeline(
            url=mock_url,
            output_script=output_script,
            output_openapi=output_openapi,
            headless=True,
            interaction_seconds=3,
            verify=True,
        )

        assert result.total_requests_captured > 0
        assert len(result.candidates) >= 1
        top_cand = result.selected_candidate
        assert top_cand is not None
        assert "/api/v1/products" in top_cand.clean_url
        assert top_cand.item_count >= 5

        # Confirm script was generated on disk
        assert os.path.exists(output_script)
        assert os.path.exists(output_openapi)

        # Confirm self-verification gate passed
        assert result.is_verified is True
        assert "Items extracted:" in (result.verification_output or "")

    finally:
        server_mgr.stop()
