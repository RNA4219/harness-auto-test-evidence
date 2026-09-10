"""保存manifestと入力メタデータを、配布スキーマを正本として検証する。"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from hate.schema_resources import read_schema


@cache
def _validator() -> Draft202012Validator:
    return Draft202012Validator(read_schema("store-manifest.schema.json"), format_checker=FormatChecker())


def manifest_errors(data: Any) -> list[dict[str, Any]]:
    """外部参照のないstoreスキーマを検証し、項目と理由を返す。"""
    errors = [
        {"issue": "invalid_manifest", "field": ".".join(map(str, error.absolute_path)), "error": error.message}
        for error in _validator().iter_errors(data)
    ]
    if not errors:
        try:
            json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, RecursionError) as exc:
            errors.append({"issue": "invalid_manifest", "field": "", "error": f"manifest cannot be serialized: {exc}"})
    return errors
