"""保存形式の版情報を、初期化・書込・復元より前に検証する。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from jsonschema import FormatChecker

from .json_io import strict_json_loads
from .models import LocalStoreError

STORE_SCHEMA_VERSION = "HATE/v1"
STORE_VERSION = "1.0.0"
_FORMATS = FormatChecker()


class StoreVersionError(LocalStoreError):
    """未対応・不正な版情報を残して、そのストアの操作を止める。"""


def new_store_version(root: Path, producer_version: str) -> dict[str, Any]:
    path = root / "store-version.json"
    try:
        if not isinstance(producer_version, str) or not producer_version.strip():
            raise ValueError("producer_version must be a non-blank string")
        producer_version.encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise StoreVersionError(
            "Invalid store producer metadata", "validate_store_version", path,
            [{"issue": "invalid_store_version", "field": "producer_version", "error": str(exc)}],
        ) from exc
    return {
        "schema_version": STORE_SCHEMA_VERSION, "store_version": STORE_VERSION,
        "created_at": datetime.now(UTC).isoformat(), "producer_version": producer_version,
    }


def validate_store_version(root: Path) -> dict[str, Any] | None:
    """既存markerを検証する。markerのない新規・従来ストアは通常の初期化を許す。"""
    path = root / "store-version.json"
    try:
        data = strict_json_loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise StoreVersionError(
            f"Store version could not be read: {exc}", "validate_store_version", path,
            [{"issue": "invalid_store_version", "error": str(exc)}],
        ) from exc
    findings: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        findings.append({"issue": "invalid_store_version", "field": "", "error": "store version must be an object"})
    else:
        for name in ("schema_version", "store_version", "created_at", "producer_version"):
            value = data.get(name)
            if not isinstance(value, str) or not value.strip():
                findings.append({"issue": "invalid_store_version", "field": name, "error": "non-blank string required"})
        for name, supported in (("schema_version", STORE_SCHEMA_VERSION), ("store_version", STORE_VERSION)):
            if isinstance(data.get(name), str) and data[name] != supported:
                findings.append({"issue": "unsupported_store_version", "field": name, "actual": data[name], "supported": supported})
        if isinstance(data.get("created_at"), str) and not _FORMATS.conforms(data["created_at"], "date-time"):
            findings.append({"issue": "invalid_store_version", "field": "created_at", "error": "date-time with timezone required"})
    if findings:
        raise StoreVersionError("Store version is invalid or unsupported", "validate_store_version", path, findings)
    return cast(dict[str, Any], data)
