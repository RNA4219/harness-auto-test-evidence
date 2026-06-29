from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evidence_envelope import (
    ENVELOPE_SCHEMA_VERSION,
    RECORD_KIND_SCHEMA_FILES,
    parse_timestamp,
    record_kind,
    source_refs,
    timestamp_value,
)
from .p0a_schema import _validate_schema_value


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas" / "HATE" / "v1"

SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

PAYLOAD_REQUIRED_FIELDS = {
    "test_result": {"canonical_test_id", "framework", "status", "duration_ms", "file", "identity_components", "artifacts"},
    "coverage_slice": {"format", "file", "line_hits", "branch_hits", "contexts"},
    "static_finding": {"rule_id", "severity", "file", "line", "sourceRef"},
    "contract_evidence": {"contract_id", "provider", "consumer", "interaction_id", "status", "sourceRef"},
    "mutation_evidence": {"mutation_id", "file", "line", "status", "sourceRef"},
}


@dataclass(frozen=True)
class SchemaFinding:
    code: str
    severity: str
    message: str
    sourceRef: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
        }


@dataclass(frozen=True)
class SchemaValidationResult:
    record_id: str
    record_kind: str
    schema_version: str
    schema_ref: str | None
    sourceRefs: list[str]
    accepted: bool
    findings: list[SchemaFinding]

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_kind": self.record_kind,
            "schema_version": self.schema_version,
            "schema_ref": self.schema_ref,
            "sourceRefs": self.sourceRefs,
            "accepted": self.accepted,
            "findings": [finding.as_dict() for finding in self.findings],
        }


def validate_record(record: dict[str, Any], *, schema_root: Path | None = None, source_ref: str = "record.json") -> SchemaValidationResult:
    root = schema_root or SCHEMA_ROOT
    findings: list[SchemaFinding] = []
    refs = source_refs(record)
    kind = record_kind(record) or ""
    schema_version = str(record.get("schema_version", ""))
    record_id = str(record.get("record_id", ""))
    schema_ref = RECORD_KIND_SCHEMA_FILES.get(kind)

    def reject(code: str, message: str) -> None:
        findings.append(SchemaFinding(code=code, severity="hard", message=message, sourceRef=refs[0] if refs else source_ref))

    if schema_version != ENVELOPE_SCHEMA_VERSION:
        reject("unknown_schema_version", f"unsupported schema_version: {schema_version or '<missing>'}")
    if not kind:
        reject("missing_record_kind", "record_kind or record_type is required")
    elif kind not in RECORD_KIND_SCHEMA_FILES:
        reject("unknown_record_kind", f"unknown record kind: {kind}")
    if not refs:
        reject("missing_source_ref", "sourceRef or sourceRefs is required")
    timestamp = timestamp_value(record)
    if timestamp is None:
        reject("invalid_timestamp", "collected_at or created_at is required")
    else:
        try:
            parse_timestamp(timestamp)
        except ValueError:
            reject("invalid_timestamp", f"invalid timestamp: {timestamp}")
    if _contains_secret(record):
        reject("unredacted_secret", "record contains an unredacted secret-like value")

    payload = record.get("payload")
    if not isinstance(payload, dict):
        reject("invalid_payload", "payload must be an object")
    elif kind in PAYLOAD_REQUIRED_FIELDS:
        missing = sorted(PAYLOAD_REQUIRED_FIELDS[kind].difference(payload))
        if missing:
            reject("record_kind_schema_mismatch", f"{kind} payload is missing: {', '.join(missing)}")

    if schema_ref:
        schema_path = root / schema_ref
        if not schema_path.exists():
            reject("schema_registry_missing_file", f"registered schema file missing: {schema_ref}")
        else:
            schema = _read_schema(schema_path)
            for error in _validate_schema_value(record, schema, "$"):
                code = "record_kind_schema_mismatch" if "record_type" in error or ".payload." in error else "schema_validation_error"
                reject(code, error)

    return SchemaValidationResult(
        record_id=record_id or "<missing>",
        record_kind=kind or "<missing>",
        schema_version=schema_version or "<missing>",
        schema_ref=schema_ref,
        sourceRefs=refs,
        accepted=not findings,
        findings=findings,
    )


def validate_records(records: list[dict[str, Any]], *, schema_root: Path | None = None, source_ref: str = "records.ndjson") -> list[SchemaValidationResult]:
    return [validate_record(record, schema_root=schema_root, source_ref=f"{source_ref}#line={index + 1}") for index, record in enumerate(records)]


def build_schema_validation_report(results: list[SchemaValidationResult], *, fixture_id: str = "schema-envelope") -> dict[str, Any]:
    rejection_classes: dict[str, int] = {}
    for result in results:
        for finding in result.findings:
            rejection_classes[finding.code] = rejection_classes.get(finding.code, 0) + 1
    return {
        "schema_version": "HATE/schema-validation-report/v1",
        "record_type": "schema_validation_report",
        "fixture_id": fixture_id,
        "summary": {
            "accepted": sum(1 for result in results if result.accepted),
            "rejected": sum(1 for result in results if not result.accepted),
            "rejection_classes": dict(sorted(rejection_classes.items())),
            "schema_versions": sorted({result.schema_version for result in results}),
        },
        "results": [result.as_dict() for result in results],
    }


def _read_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _contains_secret(value: Any) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_secret(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    return False
