from __future__ import annotations

import asyncio
import time
import uuid
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from shadowscout.interceptor.har_stream import HarStream
from shadowscout.models import CapturedRequest

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class PlaywrightInterceptor:
    """
    Automated browser driver that navigates dynamic Single Page Applications (SPAs),
    triggers user interaction events, and sniffs network communications.
    """

    def __init__(self, har_stream: Optional[HarStream] = None) -> None:
        self.stream = har_stream or HarStream()

    async def intercept_url(
        self,
        url: str,
        headless: bool = True,
        interaction_seconds: int = 4,
        on_request_captured: Optional[Callable[[CapturedRequest], None]] = None,
    ) -> HarStream:
        """
        Launches browser, intercepts all network traffic, simulates scrolls and pagination clicks,
        and returns the captured HarStream.
        """
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                ],
            )
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = await context.new_page()

            async def handle_response(response):
                try:
                    req = response.request
                    req_url = req.url
                    method = req.method
                    headers = await req.all_headers()
                    post_data = req.post_data
                    status = response.status
                    content_type = response.headers.get("content-type", "")

                    # Extract query parameters
                    parsed = urlparse(req_url)
                    query_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

                    # Extract response body safely
                    body = None
                    if "json" in content_type.lower():
                        try:
                            body = await response.json()
                        except Exception:
                            body = await response.text()
                    elif any(text_type in content_type.lower() for text_type in ["text/html", "text/plain"]):
                        # Only take small text bodies
                        try:
                            body = await response.text()
                            if len(body) > 200_000:
                                body = body[:200_000]
                        except Exception:
                            body = None

                    # Extract request cookies
                    req_cookies = {}
                    cookie_header = headers.get("cookie", "")
                    if cookie_header:
                        for part in cookie_header.split(";"):
                            if "=" in part:
                                ck, cv = part.strip().split("=", 1)
                                req_cookies[ck.strip()] = cv.strip()

                    captured = self.stream.record_response(
                        id=str(uuid.uuid4())[:8],
                        url=req_url,
                        method=method,
                        status_code=status,
                        headers=headers,
                        query_params=query_params,
                        post_data=post_data,
                        response_content_type=content_type,
                        response_body=body,
                        duration_ms=0.0,
                        timestamp=time.time(),
                        cookies=req_cookies,
                    )
                    if captured and on_request_captured:
                        on_request_captured(captured)

                except Exception:
                    # Ignore closed frames / transient abort errors
                    pass

            page.on("response", handle_response)

            try:
                # Navigate to the target page with a reasonable timeout
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(1.5)

                # Proactive user interaction simulation
                await self._simulate_interactions(page, interaction_seconds)

                # Persist full browser session cookies to all captured requests
                try:
                    cookies_list = await context.cookies()
                    session_cookies = {c["name"]: c["value"] for c in cookies_list}
                    for req in self.stream.captured_requests:
                        for ck, cv in session_cookies.items():
                            req.cookies.setdefault(ck, cv)
                except Exception:
                    pass

            except Exception as e:
                # Capture whatever we got even if networkidle timed out
                pass
            finally:
                await context.close()
                await browser.close()

        return self.stream

    async def _simulate_interactions(self, page, duration_seconds: int) -> None:
        """Simulates realistic human scrolling and pagination interactions."""
        start_time = time.time()

        # Step 1: Smooth downward scrolls to trigger dynamic lazy load
        while time.time() - start_time < (duration_seconds / 2):
            try:
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8);")
                await asyncio.sleep(0.5)
            except Exception:
                break

        # Step 2: Attempt to detect and click pagination or 'Load More' buttons
        pagination_selectors = [
            "button:has-text('Load More')",
            "button:has-text('More')",
            "button:has-text('Next')",
            "button:has-text('Muat')",
            "button:has-text('Selanjutnya')",
            "[aria-label*='Next' i]",
            "[aria-label*='page 2' i]",
            "a:has-text('Next')",
            "a:has-text('2')",
        ]

        for selector in pagination_selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=500):
                    await element.click(timeout=1000)
                    await asyncio.sleep(1.0)
                    break
            except Exception:
                continue

        # Final short wait to settle in-flight network requests
        await asyncio.sleep(1.0)
