from __future__ import annotations

import json
from typing import List, Optional
from shadowscout.models import CapturedRequest, HttpMethod
from shadowscout.interceptor.filters import is_noise_request


class HarStream:
    """
    In-memory stream buffer for captured network traffic.
    Performs streaming noise elimination and provides query methods for candidate ranking.
    """

    def __init__(self) -> None:
        self.total_seen: int = 0
        self.noise_filtered: int = 0
        self.captured_requests: List[CapturedRequest] = []

    def record_response(
        self,
        id: str,
        url: str,
        method: str,
        status_code: int,
        headers: dict[str, str],
        query_params: dict[str, str],
        post_data: Optional[str | dict] = None,
        response_content_type: str = "",
        response_body: Optional[str | dict | list] = None,
        duration_ms: float = 0.0,
        timestamp: float = 0.0,
        cookies: Optional[dict[str, str]] = None,
    ) -> Optional[CapturedRequest]:
        """Evaluates an intercepted response; filters noise or stores candidate request."""
        self.total_seen += 1

        if is_noise_request(url, response_content_type):
            self.noise_filtered += 1
            return None

        # Parse JSON if response_body is a string and header indicates JSON
        parsed_body = response_body
        if isinstance(response_body, str) and "json" in response_content_type.lower():
            try:
                parsed_body = json.loads(response_body)
            except Exception:
                parsed_body = response_body

        req = CapturedRequest(
            id=id,
            url=url,
            method=HttpMethod(method.upper()),
            status_code=status_code,
            headers=headers,
            cookies=cookies or {},
            query_params=query_params,
            post_data=post_data,
            response_content_type=response_content_type,
            response_body=parsed_body,
            duration_ms=duration_ms,
            timestamp=timestamp,
        )
        self.captured_requests.append(req)
        return req

    def get_json_responses(self) -> List[CapturedRequest]:
        """Returns all captured requests where the response is valid structured JSON."""
        return [
            req
            for req in self.captured_requests
            if isinstance(req.response_body, (dict, list))
        ]

    def clear(self) -> None:
        """Resets the capture buffer."""
        self.total_seen = 0
        self.noise_filtered = 0
        self.captured_requests.clear()
