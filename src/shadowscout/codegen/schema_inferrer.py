from __future__ import annotations

import keyword
import re
from typing import Any, Dict, List, Tuple
from shadowscout.models import InferredField, InferredModel


def _sanitize_field_name(name: str) -> Tuple[str, bool]:
    """Sanitizes field name to be a valid Python identifier. Returns (clean_name, needs_alias)."""
    clean = re.sub(r"[^0-9a-zA-Z_]", "_", name)
    if clean and clean[0].isdigit():
        clean = f"field_{clean}"
    if not clean:
        clean = "field_val"

    needs_alias = clean != name or keyword.iskeyword(clean)
    if keyword.iskeyword(clean):
        clean = f"{clean}_val"

    return clean, needs_alias


def _infer_type(values: List[Any]) -> Tuple[str, bool]:
    """Infers Python/Pydantic type from observed sample values. Returns (type_str, is_nullable)."""
    non_null_values = [v for v in values if v is not None]
    is_nullable = len(non_null_values) < len(values)

    if not non_null_values:
        return "Any | None", True

    types_seen = set(type(v) for v in non_null_values)

    if len(types_seen) == 1:
        t = next(iter(types_seen))
        if t is bool:
            type_str = "bool"
        elif t is int:
            type_str = "int"
        elif t is float:
            type_str = "float"
        elif t is str:
            type_str = "str"
        elif t is list:
            type_str = "list[Any]"
        elif t is dict:
            type_str = "dict[str, Any]"
        else:
            type_str = "Any"
    elif types_seen == {int, float}:
        type_str = "float"
    else:
        type_str = "Union[str, Any]"

    if is_nullable:
        return f"{type_str} | None", True
    return type_str, False


def infer_pydantic_models(
    sample_items: List[Dict[str, Any]],
    model_name: str = "DataItem",
) -> Tuple[List[InferredModel], str]:
    """
    Infers Pydantic V2 models from a list of observed dictionary items.
    Returns (InferredModel list, python_code_str).
    """
    if not sample_items:
        default_model = InferredModel(
            model_name=model_name,
            fields=[
                InferredField(name="raw_data", python_type="Dict[str, Any]", is_nullable=False)
            ],
        )
        code = f"""class {model_name}(BaseModel):
    raw_data: Dict[str, Any] = Field(default_factory=dict)
"""
        return [default_model], code

    # Aggregate all observed keys across sample items
    all_keys: Dict[str, List[Any]] = {}
    for item in sample_items:
        if isinstance(item, dict):
            for k, v in item.items():
                all_keys.setdefault(k, []).append(v)

    inferred_fields: List[InferredField] = []
    code_lines: List[str] = [f"class {model_name}(BaseModel):"]
    code_lines.append('    """Auto-generated Pydantic V2 model inferred by ShadowScout."""')
    code_lines.append("    model_config = ConfigDict(populate_by_name=True, extra='ignore')")
    code_lines.append("")

    for raw_key, values in all_keys.items():
        type_str, is_nullable = _infer_type(values)
        clean_name, needs_alias = _sanitize_field_name(raw_key)

        example_val = next((v for v in values if v is not None), None)
        inferred_fields.append(
            InferredField(
                name=clean_name,
                python_type=type_str,
                is_nullable=is_nullable,
                example=example_val,
                description=f"Original field: '{raw_key}'",
            )
        )

        if needs_alias:
            if is_nullable:
                code_lines.append(f"    {clean_name}: {type_str} = Field(default=None, alias='{raw_key}')")
            else:
                code_lines.append(f"    {clean_name}: {type_str} = Field(alias='{raw_key}')")
        else:
            if is_nullable:
                code_lines.append(f"    {clean_name}: {type_str} = None")
            else:
                code_lines.append(f"    {clean_name}: {type_str}")

    model = InferredModel(model_name=model_name, fields=inferred_fields)
    code_lines.append(f"\n{model_name}.model_rebuild()")
    full_code = "\n".join(code_lines) + "\n"
    return [model], full_code
