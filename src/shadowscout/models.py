from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"


class PaginationType(str, Enum):
    NONE = "none"
    PAGE_NUMBER = "page_number"        # ?page=1 or ?p=1
    OFFSET_LIMIT = "offset_limit"      # ?offset=0&limit=20
    CURSOR = "cursor"                  # ?cursor=xyz or ?after=xyz
    GRAPHQL = "graphql"                # { "variables": { "page": 1 } }


class PaginationConfig(BaseModel):
    pagination_type: PaginationType = PaginationType.NONE
    page_param: Optional[str] = None
    size_param: Optional[str] = None
    default_size: int = 20
    max_tested_size: int = 20
    cursor_json_path: Optional[str] = None
    total_count_json_path: Optional[str] = None


class CapturedRequest(BaseModel):
    id: str
    url: str
    method: HttpMethod
    status_code: int
    headers: Dict[str, str] = Field(default_factory=dict)
    cookies: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, str] = Field(default_factory=dict)
    post_data: Optional[Any] = None
    response_content_type: str = ""
    response_body: Optional[Any] = None
    duration_ms: float = 0.0
    timestamp: float = 0.0


class EndpointCandidate(BaseModel):
    endpoint_id: str
    url: str
    clean_url: str
    method: HttpMethod
    status_code: int
    score: float = 0.0
    reason: str = ""
    is_json: bool = True
    array_key_path: Optional[str] = None
    item_count: int = 0
    sample_items: List[Dict[str, Any]] = Field(default_factory=list)
    raw_headers: Dict[str, str] = Field(default_factory=dict)
    cookies: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, str] = Field(default_factory=dict)
    post_data: Optional[Any] = None


class PrunedRequest(BaseModel):
    endpoint_url: str
    method: HttpMethod
    essential_headers: Dict[str, str] = Field(default_factory=dict)
    pruned_headers_count: int = 0
    auth_header_detected: Optional[str] = None
    cookies: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, str] = Field(default_factory=dict)
    post_data: Optional[Any] = None
    status_code: int = 200
    is_reproducible_outside_browser: bool = True


class InferredField(BaseModel):
    name: str
    python_type: str
    is_nullable: bool = False
    example: Any = None
    description: Optional[str] = None


class InferredModel(BaseModel):
    model_name: str
    fields: List[InferredField] = Field(default_factory=list)


class ScoutResult(BaseModel):
    target_url: str
    total_requests_captured: int
    filtered_requests_count: int
    candidates: List[EndpointCandidate] = Field(default_factory=list)
    selected_candidate: Optional[EndpointCandidate] = None
    pruned_request: Optional[PrunedRequest] = None
    pagination: Optional[PaginationConfig] = None
    inferred_models: List[InferredModel] = Field(default_factory=list)
    generated_scraper_code: Optional[str] = None
    openapi_spec: Optional[Dict[str, Any]] = None
    is_verified: bool = False
    verification_output: Optional[str] = None
