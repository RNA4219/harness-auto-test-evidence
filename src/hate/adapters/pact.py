"""Pact contract evidence parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["parse_pact_file"]


def parse_pact_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    entries = _read_json_or_ndjson(source)
    contracts: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if entry.get("record_type") == "contract_evidence":
            contracts.append(_from_hate_record(entry, source, index))
            continue
        contracts.extend(_from_pact_json(entry, source, index))
    return {"contracts": contracts, "parser_diagnostics": [], "sourceRef": str(source)}


def _from_hate_record(entry: dict[str, Any], source: Path, index: int) -> dict[str, Any]:
    payload = entry.get("payload", {})
    interaction_id = payload.get("interaction_id") or payload.get("interaction") or payload.get("verification_id")
    if not interaction_id:
        raise ValueError("Pact contract evidence missing interaction id")
    return {
        "contract_id": payload.get("contract_id") or interaction_id,
        "provider": payload.get("provider", "unknown"),
        "consumer": payload.get("consumer", "unknown"),
        "interaction_id": interaction_id,
        "status": _status(payload.get("status")),
        "pact_version": payload.get("pact_version") or payload.get("pact_specification_version", "unknown"),
        "failure_class": payload.get("failure_class") or ("provider_verification_failed" if _status(payload.get("status")) == "failed" else None),
        "required": bool(payload.get("required", False)),
        "sourceRef": f"{source}#line={index + 1}",
    }


def _from_pact_json(entry: dict[str, Any], source: Path, index: int) -> list[dict[str, Any]]:
    provider = _name(entry.get("provider"))
    consumer = _name(entry.get("consumer"))
    version = str(entry.get("pact_version") or entry.get("pactVersion") or entry.get("metadata", {}).get("pactSpecification", {}).get("version", "unknown"))
    items = entry.get("results") or entry.get("interactions") or []
    contracts: list[dict[str, Any]] = []
    for item_index, item in enumerate(items):
        interaction_id = item.get("interaction_id") or item.get("id") or item.get("description")
        if not interaction_id:
            raise ValueError("Pact interaction missing interaction id")
        status = _status(item.get("status") or item.get("result") or ("failed" if item.get("error") else "passed"))
        contracts.append(
            {
                "contract_id": item.get("contract_id") or f"pact-{provider}-{consumer}-{interaction_id}",
                "provider": _name(item.get("provider")) if item.get("provider") else provider,
                "consumer": _name(item.get("consumer")) if item.get("consumer") else consumer,
                "interaction_id": interaction_id,
                "status": status,
                "pact_version": item.get("pact_version") or version,
                "failure_class": item.get("failure_class") or ("provider_verification_failed" if status == "failed" else None),
                "required": bool(item.get("required", True)),
                "sourceRef": f"{source}#entry={index}/interaction={item_index}",
            }
        )
    return contracts


def _read_json_or_ndjson(source: Path) -> list[dict[str, Any]]:
    text = source.read_text(encoding="utf-8").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    raise ValueError("Pact input must be JSON object, array, or NDJSON")


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name", "unknown"))
    return str(value or "unknown")


def _status(value: Any) -> str:
    normalized = str(value or "passed").lower()
    if normalized in {"pass", "passed", "success", "ok"}:
        return "passed"
    if normalized in {"fail", "failed", "failure", "error"}:
        return "failed"
    return normalized
