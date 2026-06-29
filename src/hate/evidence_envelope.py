from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from .p0a_constants import SCHEMA_VERSION


ENVELOPE_SCHEMA_VERSION = SCHEMA_VERSION

RECORD_KIND_SCHEMA_FILES = {
    "test_result": "test-result.schema.json",
    "coverage_slice": "coverage-slice.schema.json",
    "static_finding": "static-finding.schema.json",
    "contract_evidence": "contract-evidence.schema.json",
    "mutation_evidence": "mutation-evidence.schema.json",
}


def record_kind(record: dict[str, Any]) -> str | None:
    value = record.get("record_kind", record.get("record_type"))
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def source_refs(record: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("sourceRef", "source_ref"):
        value = record.get(key)
        if isinstance(value, str) and value:
            refs.append(value)
    value = record.get("sourceRefs", record.get("source_refs"))
    if isinstance(value, list):
        refs.extend(str(item) for item in value if str(item))
    payload = record.get("payload")
    if isinstance(payload, dict):
        for key in ("sourceRef", "source_ref"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                refs.append(value)
        value = payload.get("sourceRefs", payload.get("source_refs"))
        if isinstance(value, list):
            refs.extend(str(item) for item in value if str(item))
    return sorted(set(refs))


def timestamp_value(record: dict[str, Any]) -> str | None:
    value = record.get("collected_at", record.get("created_at"))
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def stable_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def envelope_record(
    *,
    record_kind_value: str,
    record_id: str,
    producer: str,
    parser_version: str,
    source_ref: str,
    payload: dict[str, Any],
    collected_at: str = "2026-06-29T00:00:00Z",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "record_kind": record_kind_value,
        "record_type": record_kind_value,
        "record_id": record_id,
        "producer": producer,
        "parserVersion": parser_version,
        "sourceRef": source_ref,
        "collected_at": collected_at,
        "normalized_path_set": [],
        "diagnostics": [],
        "payload": payload,
    }
    record["source_hash"] = stable_sha256({"sourceRef": source_ref, "payload": payload})
    return record
