"""Packaged HATE-bridge/v1 schema loading and validation."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class BridgeValidationError(ValueError):
    pass


def load_bridge_schema(name: str) -> dict[str, Any]:
    resource = files("hate").joinpath("_schemas", "HATE-bridge", "v1", f"{name}.schema.json")
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        fallback = Path(__file__).resolve().parents[3] / "schemas" / "HATE-bridge" / "v1" / f"{name}.schema.json"
        if fallback.is_file():
            return json.loads(fallback.read_text(encoding="utf-8"))
        raise BridgeValidationError(f"packaged bridge schema is missing: {name}") from exc


def validate_bridge_record(record: Any, schema_name: str) -> None:
    schema = load_bridge_schema(schema_name)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(record), key=lambda item: list(item.absolute_path))
    if errors:
        detail = "; ".join(error.message for error in errors[:5])
        raise BridgeValidationError(f"{schema_name} schema validation failed: {detail}")
