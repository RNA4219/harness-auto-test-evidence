"""Escaped defect ingest adapter for QEG optional evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

VALID_ID_PREFIXES = ("rand:", "ctg:", "mbb:", "hate:", "qeg:")


def load_escaped_defects(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load and normalize escaped defect records from generic JSON or CSV."""
    raw_records = _read_raw_records(path)
    defects: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_records):
        defect, record_claims = _normalize_record(raw, index)
        defects.append(defect)
        claims.extend(record_claims)
    return defects, claims


def find_escaped_defects_path(fixture_dir: Path) -> Path | None:
    for name in ("escaped-defects.json", "escaped-defects.csv"):
        path = fixture_dir / name
        if path.exists():
            return path
    return None


def _read_raw_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        records = data.get("defects") or data.get("escaped_defects") or data.get("items")
        if isinstance(records, list):
            return [record for record in records if isinstance(record, dict)]
        return [data]
    if isinstance(data, list):
        return [record for record in data if isinstance(record, dict)]
    return []


def _normalize_record(raw: dict[str, Any], index: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw_defect_id = str(raw.get("defect_id") or raw.get("id") or raw.get("key") or f"defect-{index + 1}")
    defect_id = _normalize_hate_id(raw_defect_id, "defect")
    requirement_ids = _split_refs(
        raw.get("affected_requirement_ids")
        or raw.get("requirement_ids")
        or raw.get("requirements")
        or []
    )
    risk_ids = _split_refs(
        raw.get("affected_risk_ids")
        or raw.get("risk_ids")
        or raw.get("risks")
        or []
    )
    release_ref = str(raw.get("release_ref") or raw.get("release") or raw.get("verdict_ref") or "").strip()
    defect = {
        "defect_id": defect_id,
        "detected_at": str(raw.get("detected_at") or raw.get("created_at") or raw.get("detected") or "").strip(),
        "severity": str(raw.get("severity") or raw.get("priority") or "unknown").strip().lower(),
        "affected_requirement_ids": requirement_ids,
        "affected_risk_ids": risk_ids,
        "release_ref": release_ref,
    }
    claims: list[dict[str, Any]] = []
    invalid_refs = [
        ref
        for ref in [*requirement_ids, *risk_ids, release_ref]
        if ref and not _has_valid_prefix(ref)
    ]
    if invalid_refs:
        claims.append({
            "defect_id": defect_id,
            "refs": invalid_refs,
            "reason": "escaped defect id resolution failed",
        })
    if not release_ref:
        claims.append({
            "defect_id": defect_id,
            "reason": "escaped defect release_ref missing",
        })
    return defect, claims


def _normalize_hate_id(value: str, kind: str) -> str:
    value = value.strip()
    if _has_valid_prefix(value):
        return value
    return f"hate:{kind}/{value}"


def _split_refs(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        normalized = value.replace(";", ",")
        return [item.strip() for item in normalized.split(",") if item.strip()]
    return []


def _has_valid_prefix(value: str) -> bool:
    return value.startswith(VALID_ID_PREFIXES)
