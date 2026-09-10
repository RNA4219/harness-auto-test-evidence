"""P0bのtest-result読込時に、実行座標とrecordの形を検証する。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .execution_metadata import normalize_execution_metadata
from .execution_status import validate_execution_status
from .p0b_io import iter_ndjson
from .p0b_test_graph import IDENTITY_FIELDS
from .p0b_types import ExportError


def read_test_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    location = str(path)
    try:
        for line_number, record in iter_ndjson(path):
            location = f"{path}:{line_number}"
            payload = record.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("payload must be a JSON object")
            canonical = payload.get("canonical_test_id")
            if not isinstance(canonical, str) or not canonical.strip():
                raise ValueError("payload.canonical_test_id must be a non-empty string")
            if "record_id" in record and (not isinstance(record["record_id"], str) or not record["record_id"].strip()):
                raise ValueError("record_id must be a non-empty string")
            for field in IDENTITY_FIELDS:
                expected = dict if field in {"parameters", "params", "identity_components"} else str
                if field in payload and not isinstance(payload[field], expected):
                    raise ValueError(f"payload.{field} must be a {'JSON object' if expected is dict else 'string'}")
            normalize_execution_metadata(payload, "payload")
            validate_execution_status(payload, "payload")
            records.append(record)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ExportError(f"{location}: {exc}", exit_code=1) from exc
    return records
