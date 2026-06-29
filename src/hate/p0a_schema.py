from __future__ import annotations

import hashlib
import json
import mimetypes
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .p0a_constants import REDACTION_STATUS, SCHEMA_VERSION, SOURCE_TOOL
from .p0a_io import (
    _artifact_kind,
    _dq,
    _file_sha256,
    _read_optional_json,
    _slug,
    _stable_sha256,
    _stable_source_ref,
    _to_posix,
)
def _schema_validation_hits(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    seen_hits: set[tuple[str, str, str]] = set()
    flattened: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, list):
            flattened.extend(item for item in record if isinstance(item, dict))
        elif isinstance(record, dict) and "record_type" in record:
            flattened.append(record)
        elif not isinstance(record, dict):
            hits.append(_dq("HATE-DQ-015", "schema validation failed: generated record is not an object", "generated-record"))
    for record in flattened:
        schema_name = _schema_name_for_generated_record(record)
        if not schema_name:
            continue
        schema = _load_hate_schema(schema_name)
        for error in _validate_schema_value(record, schema, "$"):
            hit = _dq("HATE-DQ-015", f"schema validation failed: {error}", _schema_source_ref(record, schema_name))
            key = (hit["code"], hit["message"], hit["source_ref"])
            if key in seen_hits:
                continue
            seen_hits.add(key)
            hits.append(hit)
    return hits

def _schema_name_for_generated_record(record: dict[str, Any]) -> str | None:
    record_type = record.get("record_type")
    if record_type == "run":
        return "run.schema.json"
    if record_type == "test_result":
        return "test-result.schema.json"
    if record_type == "coverage_slice":
        return "coverage-slice.schema.json"
    if record_type == "precheck_decision":
        return "precheck-decision.schema.json"
    if record_type == "audit_record":
        return "audit-record.schema.json"
    if "artifacts" in record and record.get("schema_version") == SCHEMA_VERSION:
        return "artifact-manifest.schema.json"
    return None

def _schema_source_ref(record: dict[str, Any], schema_name: str) -> str:
    if schema_name == "artifact-manifest.schema.json":
        return "artifact-manifest.json"
    record_type = str(record.get("record_type") or "generated-record")
    return {
        "run": "HATE-run.json",
        "test_result": "HATE-test-results.ndjson",
        "coverage_slice": "HATE-coverage.ndjson",
        "precheck_decision": "precheck-decision.json",
        "audit_record": "record.json",
    }.get(record_type, "generated-record")

def _load_hate_schema(name: str) -> dict[str, Any]:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "HATE" / "v1" / name
    with schema_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a JSON object")
    return data

def _validate_schema_value(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    if "allOf" in schema:
        for item in schema["allOf"]:
            if not isinstance(item, dict):
                continue
            if "$ref" in item:
                item = _load_hate_schema(str(item["$ref"]))
            errors.extend(_validate_schema_value(value, item, path))
        return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']!r}")
    expected_type = schema.get("type")
    if expected_type and not _schema_type_matches(value, str(expected_type)):
        errors.append(f"{path} must be {expected_type}")
        return errors
    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path} length must be at least {min_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and not re.match(pattern, value):
            errors.append(f"{path} must match {pattern}")
    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, int | float) and value < minimum:
            errors.append(f"{path} must be >= {minimum}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for field in required:
                if isinstance(field, str) and field not in value:
                    errors.append(f"{path}.{field} is required")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for field, subschema in properties.items():
                if field in value and isinstance(subschema, dict):
                    errors.extend(_validate_schema_value(value[field], subschema, f"{path}.{field}"))
        additional = schema.get("additionalProperties", True)
        if isinstance(additional, dict):
            known = set(properties) if isinstance(properties, dict) else set()
            for field, item in value.items():
                if field not in known:
                    errors.extend(_validate_schema_value(item, additional, f"{path}.{field}"))
        elif additional is False and isinstance(properties, dict):
            unknown = sorted(set(value).difference(properties))
            if unknown:
                errors.append(f"{path} has unknown fields: {', '.join(unknown)}")
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_validate_schema_value(item, item_schema, f"{path}[{index}]"))
    return errors

def _schema_type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int | float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True



