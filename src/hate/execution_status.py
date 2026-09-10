"""観測recordと、実行されたことを示す結果を区別する。"""

from __future__ import annotations

from typing import Any

OUTCOME_FIELDS = ("source_status", "wouldRun", "xfail", "xpass", "todo", "only")


def validate_execution_status(data: dict[str, Any], location: str) -> None:
    for field in ("status", "source_status"):
        if field in data and (not isinstance(data[field], str) or not data[field].strip()):
            raise ValueError(f"{location}.{field} must be a non-empty string")
    if "wouldRun" in data and type(data["wouldRun"]) is not bool:
        raise ValueError(f"{location}.wouldRun must be a boolean")


def effective_status(data: dict[str, Any]) -> str:
    if data.get("wouldRun") is True:
        return "inconclusive"
    return str(data.get("status", "unknown")).lower()


def has_execution_result(data: dict[str, Any]) -> bool:
    return effective_status(data) in {"passed", "failed", "error", "flaky"}


def outcome_declarations(data: dict[str, Any]) -> dict[str, Any]:
    fields = {field: data[field] for field in OUTCOME_FIELDS if field in data}
    if "source_status" not in fields and "status" in data and (data.get("wouldRun") is True or effective_status(data) != data["status"]):
        fields["source_status"] = data["status"]
    return fields
