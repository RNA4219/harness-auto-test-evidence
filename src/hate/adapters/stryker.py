"""Stryker mutation evidence parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["parse_stryker_file"]

VALID_STATUSES = {
    "killed",
    "survived",
    "timeout",
    "no_coverage",
    "ignored",
    "compile_error",
    "runtime_error",
}


def parse_stryker_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    entries = _read_json_or_ndjson(source)
    mutations: list[dict[str, Any]] = []
    for entry_index, entry in enumerate(entries):
        if entry.get("record_type") == "mutation_evidence":
            mutations.append(_from_hate_record(entry, source, entry_index))
            continue
        mutants = entry.get("mutants") or entry.get("mutations") or []
        if isinstance(mutants, dict):
            mutants = list(mutants.values())
        for mutant_index, mutant in enumerate(mutants):
            mutations.append(_from_mutant(mutant, source, f"entry={entry_index}/mutant={mutant_index}"))
    return {"mutations": mutations, "parser_diagnostics": [], "sourceRef": str(source)}


def _from_hate_record(entry: dict[str, Any], source: Path, index: int) -> dict[str, Any]:
    payload = entry.get("payload", {})
    status = _status(payload.get("status"))
    return {
        "mutation_id": payload.get("mutation_id") or payload.get("mutant_id") or payload.get("id"),
        "file": _normalize_path(str(payload.get("file", ""))),
        "line": int(payload.get("start_line") or payload.get("line") or 0),
        "status": status,
        "mutator": payload.get("mutator", ""),
        "covered_by": payload.get("covered_by", []),
        "killed_by": payload.get("killed_by", []),
        "score": payload.get("score"),
        "sourceRef": f"{source}#line={index + 1}",
    }


def _from_mutant(mutant: dict[str, Any], source: Path, pointer: str) -> dict[str, Any]:
    status = _status(mutant.get("status"))
    location = mutant.get("location", {})
    start = location.get("start", {}) if isinstance(location, dict) else {}
    return {
        "mutation_id": mutant.get("id"),
        "file": _normalize_path(str(mutant.get("file") or mutant.get("sourceFilePath") or "")),
        "line": int(mutant.get("line") or start.get("line") or 0),
        "status": status,
        "mutator": mutant.get("mutator") or mutant.get("mutatorName", ""),
        "covered_by": mutant.get("coveredBy") or mutant.get("covered_by", []),
        "killed_by": mutant.get("killedBy") or mutant.get("killed_by", []),
        "score": mutant.get("score"),
        "sourceRef": f"{source}#{pointer}",
    }


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
    raise ValueError("Stryker input must be JSON object, array, or NDJSON")


def _status(value: Any) -> str:
    normalized = str(value or "").replace("-", "_").lower()
    aliases = {
        "killed": "killed",
        "survived": "survived",
        "timeout": "timeout",
        "no_coverage": "no_coverage",
        "nocoverage": "no_coverage",
        "compileerror": "compile_error",
        "compile_error": "compile_error",
        "runtimeerror": "runtime_error",
        "runtime_error": "runtime_error",
        "ignored": "ignored",
    }
    status = aliases.get(normalized, normalized)
    if status not in VALID_STATUSES:
        raise ValueError(f"unknown mutant status: {value}")
    return status


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")
