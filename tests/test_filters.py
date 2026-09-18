from __future__ import annotations

import pytest
from shadowscout.interceptor.filters import is_noise_request, is_static_asset, is_telemetry_or_ad


def test_static_asset_filtering():
    assert is_static_asset("https://example.com/static/style.css") is True
    assert is_static_asset("https://example.com/assets/app.min.js") is True
    assert is_static_asset("https://example.com/logo.svg") is True
    assert is_static_asset("https://example.com/fonts/inter.woff2") is True
    assert is_static_asset("https://example.com/avatar.png") is True

    # Legitimate API URLs should NOT be static assets
    assert is_static_asset("https://example.com/api/v1/products") is False
    assert is_static_asset("https://example.com/graphql") is False


def test_telemetry_filtering():
    assert is_telemetry_or_ad("https://www.google-analytics.com/g/collect?v=2") is True
    assert is_telemetry_or_ad("https://analytics.google.com/g/collect") is True
    assert is_telemetry_or_ad("https://connect.facebook.net/en_US/fbevents.js") is True
    assert is_telemetry_or_ad("https://o123456.ingest.sentry.io/api/123/envelope/") is True
    assert is_telemetry_or_ad("https://browser-intake-datadoghq.com/api/v2/rum") is True
    assert is_telemetry_or_ad("https://api.mixpanel.com/track") is True
    assert is_telemetry_or_ad("https://static.hotjar.com/c/hotjar-123.js") is True
    assert is_telemetry_or_ad("https://analytics.tiktok.com/api/v2/pixel") is True

    # Non-telemetry endpoints
    assert is_telemetry_or_ad("https://example.com/api/v1/users") is False
    assert is_telemetry_or_ad("https://store.target.com/catalog/search?q=laptop") is False


def test_master_noise_filter():
    assert is_noise_request("https://google-analytics.com/collect") is True
    assert is_noise_request("https://cdn.example.com/bundle.js") is True
    assert is_noise_request("https://api.example.com/items", content_type="application/json") is False
