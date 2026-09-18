from __future__ import annotations

import pytest
from shadowscout.codegen.schema_inferrer import infer_pydantic_models


def test_schema_inferrer_generates_valid_pydantic_code():
    samples = [
        {
            "id": 101,
            "product-name": "Quantum GPU",
            "price": 1499.50,
            "is_available": True,
            "tags": ["hardware", "ai"],
            "optional_notes": None,
            "from": "Supplier Alpha",
        },
        {
            "id": 102,
            "product-name": "Neural TPU",
            "price": 2300.0,
            "is_available": False,
            "tags": ["hardware"],
            "optional_notes": "Pre-order only",
            "from": "Supplier Beta",
        },
    ]

    models, code_str = infer_pydantic_models(samples, model_name="ProductItem")

    assert len(models) == 1
    model = models[0]
    assert model.model_name == "ProductItem"

    # Verify code execution in dynamic namespace
    namespace: dict = {}
    exec("from pydantic import BaseModel, ConfigDict, Field\nfrom typing import Optional, List, Dict, Any, Union\n" + code_str, namespace)
    ProductItemCls = namespace["ProductItem"]

    # Instantiate model with sample data
    item1 = ProductItemCls.model_validate(samples[0])
    assert item1.id == 101
    assert getattr(item1, "product_name") == "Quantum GPU"
    assert item1.price == 1499.50
    assert getattr(item1, "from_val") == "Supplier Alpha"
