from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Set

STATIC_EXTENSIONS: Set[str] = {
    ".css", ".js", ".mjs", ".ts", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".wav", ".ogg", ".mp4", ".webm",
    ".wasm", ".pdf",
}

TELEMETRY_DOMAIN_PATTERNS: list[re.Pattern] = [
    re.compile(r"(^|\.)google-analytics\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)analytics\.google\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)googletagmanager\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)doubleclick\.net$", re.IGNORECASE),
    re.compile(r"(^|\.)facebook\.net$", re.IGNORECASE),
    re.compile(r"(^|\.)facebook\.com/tr(/|$)", re.IGNORECASE),
    re.compile(r"(^|\.)sentry\.io$", re.IGNORECASE),
    re.compile(r"(^|\.)datadoghq\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)mixpanel\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)segment\.(io|com)$", re.IGNORECASE),
    re.compile(r"(^|\.)amplitude\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)hotjar\.(com|io)$", re.IGNORECASE),
    re.compile(r"(^|\.)clarity\.ms$", re.IGNORECASE),
    re.compile(r"(^|\.)fullstory\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)logrocket\.io$", re.IGNORECASE),
    re.compile(r"(^|\.)tiktok\.com/api/v\d+/pixel", re.IGNORECASE),
    re.compile(r"(^|\.)cloudflareinsights\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)nr-data\.net$", re.IGNORECASE),
    re.compile(r"(^|\.)heapanalytics\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)posthog\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)stats\.wp\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)criteo\.com$", re.IGNORECASE),
]

MEDIA_CONTENT_TYPES: Set[str] = {
    "text/css",
    "text/javascript",
    "application/javascript",
    "application/x-javascript",
    "image/",
    "font/",
    "audio/",
    "video/",
}


def is_static_asset(url: str, content_type: str = "") -> bool:
    """Detects if a URL or Content-Type points to a static media asset."""
    parsed = urlparse(url)
    path = parsed.path.lower()

    for ext in STATIC_EXTENSIONS:
        if path.endswith(ext):
            return True

    if content_type:
        lowered_ct = content_type.lower()
        for media_type in MEDIA_CONTENT_TYPES:
            if media_type in lowered_ct:
                return True

    return False


def is_telemetry_or_ad(url: str) -> bool:
    """Checks if the request target matches known telemetry, analytics, or ad network patterns."""
    parsed = urlparse(url)
    host = parsed.netloc.split(":")[0].lower()
    full_target = f"{host}{parsed.path}"

    for pattern in TELEMETRY_DOMAIN_PATTERNS:
        if pattern.search(host) or pattern.search(full_target):
            return True

    # Common path cues for telemetry
    if any(cue in parsed.path.lower() for cue in ["/collect?", "/telemetry", "/analytics", "/rum", "/ping"]):
        return True

    return False


def is_noise_request(url: str, content_type: str = "") -> bool:
    """
    Master filter that returns True if the request should be discarded
    (static asset, font, CSS, ad-tracker, or healthcheck ping).
    """
    if is_telemetry_or_ad(url):
        return True
    if is_static_asset(url, content_type):
        return True
    return False
