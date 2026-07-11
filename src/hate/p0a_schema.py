from __future__ import annotations

import re
from typing import Any

from .p0a_constants import SCHEMA_VERSION
from .p0a_io import (
    _dq,
)
from .schema_resources import read_schema, validate_schema_instance


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
    if record_type == "mutation_evidence":
        return "mutation-evidence.schema.json"
    if record_type == "evidence_strength":
        return "evidence-strength.schema.json"
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
        "mutation_evidence": "HATE-mutation.ndjson",
        "evidence_strength": "HATE-evidence-strength.ndjson",
        "precheck_decision": "precheck-decision.json",
        "audit_record": "record.json",
    }.get(record_type, "generated-record")

def _load_hate_schema(name: str) -> dict[str, Any]:
    return read_schema(name)

def _validate_schema_value(value: Any, schema: dict[str, Any], path: str, _root_schema: dict[str, Any] | None = None) -> list[str]:
    del _root_schema
    return [_format_jsonschema_error(error, path) for error in validate_schema_instance(value, schema)]

def _format_jsonschema_error(error: Any, root_path: str) -> str:
    suffix = "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
    location = f"{root_path}{suffix}"
    if error.validator == "required":
        match = re.match(r"'([^']+)' is a required property", error.message)
        if match:
            return f"{location}.{match.group(1)} is required"
    if error.validator == "pattern":
        return f"{location} must match {error.validator_value}"
    if error.validator == "enum":
        return f"{location} must be one of {error.validator_value!r}"
    if error.validator == "const":
        return f"{location} must equal {error.validator_value!r}"
    if error.validator == "type":
        return f"{location} must be {error.validator_value}"
    if error.validator == "minimum":
        return f"{location} must be >= {error.validator_value}"
    if error.validator == "maximum":
        return f"{location} must be <= {error.validator_value}"
    return f"{location}: {error.message}"

def _schema_type_matches(value: Any, expected_type: str) -> bool:
    """Backward-compatible helper retained for p0a_support consumers."""
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
