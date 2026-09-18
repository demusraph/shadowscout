from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlparse
from shadowscout.models import EndpointCandidate, PaginationConfig, PrunedRequest
from shadowscout.codegen.schema_inferrer import infer_pydantic_models


def export_openapi_spec(
    candidate: EndpointCandidate,
    pruned: PrunedRequest,
    pagination: PaginationConfig,
    target_page_url: str = "",
) -> Dict[str, Any]:
    """
    Generates an OpenAPI 3.1 specification for the reverse-engineered hidden API.
    """
    parsed = urlparse(candidate.clean_url)
    base_server = f"{parsed.scheme}://{parsed.netloc}"
    path_name = parsed.path or "/"

    models, _ = infer_pydantic_models(candidate.sample_items, model_name="ScrapedItem")
    main_model = models[0] if models else None

    # Construct JSON Schema properties from inferred fields
    properties: Dict[str, Any] = {}
    for f in (main_model.fields if main_model else []):
        field_type = "string"
        if "int" in f.python_type:
            field_type = "integer"
        elif "float" in f.python_type:
            field_type = "number"
        elif "bool" in f.python_type:
            field_type = "boolean"
        elif "List" in f.python_type:
            field_type = "array"
        elif "Dict" in f.python_type:
            field_type = "object"

        properties[f.name] = {
            "type": field_type,
            "description": f.description,
        }

    # Prepare parameter specs
    parameters: list[Dict[str, Any]] = []

    # Query parameters
    for param_name, sample_val in pruned.query_params.items():
        parameters.append({
            "name": param_name,
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
            "example": sample_val,
        })

    # Auth headers if detected
    if pruned.auth_header_detected:
        parameters.append({
            "name": pruned.auth_header_detected,
            "in": "header",
            "required": True,
            "schema": {"type": "string"},
            "description": "Required authentication credential token",
        })

    method_key = candidate.method.value.lower()

    spec: Dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": f"Reverse-Engineered API: {parsed.netloc}",
            "version": "1.0.0",
            "description": (
                f"Automatically reverse-engineered by ShadowScout.\n"
                f"Source Web Page: {target_page_url or base_server}\n"
                f"Discovered Endpoint: {candidate.clean_url}"
            ),
        },
        "servers": [{"url": base_server}],
        "paths": {
            path_name: {
                method_key: {
                    "summary": f"Extract domain data from {parsed.path}",
                    "operationId": f"get_{parsed.path.strip('/').replace('/', '_') or 'root'}",
                    "parameters": parameters,
                    "responses": {
                        "200": {
                            "description": "Successful extraction of structured domain data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "items": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": properties,
                                                },
                                            }
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }

    return spec
