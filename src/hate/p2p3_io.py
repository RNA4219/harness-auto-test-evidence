from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "HATE/v1"

class ProductError(Exception):
    message: str
    exit_code: int = 1

    def __init__(self, message: str, exit_code: int = 1) -> None:
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)

def _api_envelope(
    request_id: str,
    data: dict[str, Any],
    errors: list[dict[str, Any]],
    source: dict[str, Any],
    next_cursor: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "data": data,
        "errors": errors,
        "pagination": {"next_cursor": next_cursor},
        "source": source,
    }


def _stable_ref(path: Path) -> str:
    value = path.resolve().as_posix()
    marker = "fixtures/golden/"
    if marker in value:
        return "fixture:/" + value.split(marker, 1)[1]
    try:
        return "workspace:/" + path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return "path:/" + path.name


def _missing_conformance_report() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "adapter_conformance",
        "summary": {
            "overall_status": "missing",
            "check_count": 0,
            "covered_categories": [],
        },
        "checks": [],
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _read_optional_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return _read_json(path)


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ProductError(f"required JSON artifact not found: {path}", exit_code=2)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ProductError(f"{path.name} must contain a JSON object", exit_code=1)
    return data


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + __import__("hashlib").sha256(payload.encode("utf-8")).hexdigest()
