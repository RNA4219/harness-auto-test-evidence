from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters.stryker import parse_stryker_file
from .p0a_io import _slug
from .p0a_records import _envelope

DEFAULT_RECENT_RUN_LIMIT = 10
MUTATION_DETECTED_STATUSES = {"killed", "timeout"}
MUTATION_COUNTED_STATUSES = {"killed", "timeout", "survived", "no_coverage"}


def _parse_stryker_mutation(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    parsed = parse_stryker_file(path)
    records: list[dict[str, Any]] = []
    for index, mutation in enumerate(parsed.get("mutations", []), start=1):
        mutation_id = str(mutation.get("mutation_id") or f"stryker-mutant-{index}")
        payload = {
            "mutation_id": mutation_id,
            "file": str(mutation.get("file", "")).replace("\\", "/"),
            "line": int(mutation.get("line") or 1),
            "status": str(mutation.get("status") or "no_coverage"),
            "mutator": str(mutation.get("mutator") or "unknown"),
            "covered_by": _string_list(mutation.get("covered_by")),
            "killed_by": _string_list(mutation.get("killed_by")),
            "sourceRef": _stable_input_source_ref(str(mutation.get("sourceRef") or ""), path, index),
        }
        records.append(
            _envelope(
                context,
                "mutation_evidence",
                f"mutation-{context['run_id']}-{context['run_attempt']}-{_slug(mutation_id)}",
                created_at,
                source_version,
                payload,
            )
        )
    return records


def _build_evidence_strength_records(
    *,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    input_dir: Path,
    test_records: list[dict[str, Any]],
    mutation_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    config = _read_optional_json(input_dir / "evidence-strength-config.json")
    recent_run_limit = _recent_run_limit(config)
    history_path = _first_existing(input_dir, ["run-history.json", "run-history.jsonl", "test-history.json", "test-history.jsonl"])
    history_statuses = _history_statuses_by_test(history_path, recent_run_limit) if history_path else {}
    current_status_by_test = {
        str(record.get("payload", {}).get("canonical_test_id", "")): str(record.get("payload", {}).get("status", "unknown"))
        for record in test_records
        if record.get("payload", {}).get("canonical_test_id")
    }
    mutation_score_by_test = _mutation_score_by_test(mutation_records)
    all_test_ids = sorted(set(current_status_by_test) | set(history_statuses) | set(mutation_score_by_test))
    if not all_test_ids:
        all_test_ids = ["unknown"]

    records: list[dict[str, Any]] = []
    for test_id in all_test_ids:
        statuses = list(history_statuses.get(test_id, []))
        current_status = current_status_by_test.get(test_id)
        if current_status in {"passed", "failed", "error"}:
            statuses.append("failed" if current_status == "error" else current_status)
        statuses = statuses[-recent_run_limit:]
        flake_score: float | str = _flake_score(statuses)
        mutation_score: float | str = mutation_score_by_test.get(test_id, "unknown")
        payload = {
            "test_id": test_id,
            "flake_score": flake_score,
            "mutation_score": mutation_score,
            "sample_size": len(statuses),
            "computed_at": created_at,
            "inputs": _strength_inputs(history_path, bool(mutation_records), bool(current_status)),
        }
        records.append(
            _envelope(
                context,
                "evidence_strength",
                f"evidence-strength-{context['run_id']}-{context['run_attempt']}-{_slug(test_id)}",
                created_at,
                source_version,
                payload,
            )
        )
    return records


def _evidence_strength_distribution(strength_records: list[dict[str, Any]]) -> dict[str, Any]:
    flake_known = [record["payload"]["flake_score"] for record in strength_records if isinstance(record.get("payload", {}).get("flake_score"), int | float)]
    mutation_known = [record["payload"]["mutation_score"] for record in strength_records if isinstance(record.get("payload", {}).get("mutation_score"), int | float)]
    return {
        "total": len(strength_records),
        "flake_known": len(flake_known),
        "flake_unknown": len(strength_records) - len(flake_known),
        "flake_nonzero": sum(1 for value in flake_known if float(value) > 0),
        "mutation_known": len(mutation_known),
        "mutation_unknown": len(strength_records) - len(mutation_known),
        "mutation_zero": sum(1 for value in mutation_known if float(value) == 0),
    }


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def _recent_run_limit(config: dict[str, Any]) -> int:
    value = config.get("recent_run_limit", config.get("recent_runs", DEFAULT_RECENT_RUN_LIMIT))
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_RECENT_RUN_LIMIT
    return max(2, parsed)


def _first_existing(input_dir: Path, names: list[str]) -> Path | None:
    for name in names:
        path = input_dir / name
        if path.exists():
            return path
    return None


def _history_statuses_by_test(path: Path, recent_run_limit: int) -> dict[str, list[str]]:
    entries = _read_history_entries(path)
    statuses: dict[str, list[str]] = {}
    for entry in entries[-recent_run_limit:]:
        for test in _tests_from_history_entry(entry):
            test_id = str(test.get("test_id") or test.get("canonical_test_id") or "")
            status = _normalized_transition_status(test.get("status") or test.get("outcome"))
            if test_id and status:
                statuses.setdefault(test_id, []).append(status)
    return statuses


def _read_history_entries(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, dict):
        runs = data.get("runs", data.get("history", []))
        return [item for item in runs if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    raise ValueError(f"{path.name} must contain a JSON object, array, or JSONL entries")


def _tests_from_history_entry(entry: dict[str, Any]) -> list[dict[str, Any]]:
    tests = entry.get("tests", entry.get("test_results", []))
    if isinstance(tests, list):
        return [item for item in tests if isinstance(item, dict)]
    test_id = entry.get("test_id") or entry.get("canonical_test_id")
    if test_id:
        return [entry]
    return []


def _normalized_transition_status(value: Any) -> str:
    status = str(value or "").lower()
    if status in {"passed", "pass", "success"}:
        return "passed"
    if status in {"failed", "fail", "failure", "error"}:
        return "failed"
    return ""


def _flake_score(statuses: list[str]) -> float | str:
    normalized = [status for status in statuses if status in {"passed", "failed"}]
    if len(normalized) < 2:
        return "unknown"
    transitions = sum(1 for left, right in zip(normalized, normalized[1:]) if left != right)
    return round(transitions / (len(normalized) - 1), 4)


def _mutation_score_by_test(mutation_records: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, int] = {}
    detected: dict[str, int] = {}
    for record in mutation_records:
        payload = record.get("payload", {})
        status = str(payload.get("status", ""))
        if status not in MUTATION_COUNTED_STATUSES:
            continue
        test_ids = set(_string_list(payload.get("covered_by")) + _string_list(payload.get("killed_by")))
        for test_id in test_ids:
            totals[test_id] = totals.get(test_id, 0) + 1
            if status in MUTATION_DETECTED_STATUSES or test_id in _string_list(payload.get("killed_by")):
                detected[test_id] = detected.get(test_id, 0) + 1
    return {test_id: round(detected.get(test_id, 0) / total, 4) for test_id, total in totals.items() if total > 0}


def _strength_inputs(history_path: Path | None, has_mutation: bool, has_current: bool) -> list[dict[str, str]]:
    inputs: list[dict[str, str]] = []
    if history_path:
        inputs.append({"kind": "run_history", "sourceRef": history_path.name})
    if has_current:
        inputs.append({"kind": "test_results", "sourceRef": "HATE-test-results.ndjson"})
    if has_mutation:
        inputs.append({"kind": "mutation", "sourceRef": "HATE-mutation.ndjson"})
    if not inputs:
        inputs.append({"kind": "unknown", "sourceRef": "none"})
    return inputs


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


def _stable_input_source_ref(value: str, path: Path, index: int) -> str:
    if not value:
        return f"{path.name}#mutant={index - 1}"
    normalized_value = value.replace("\\", "/")
    normalized_path = path.as_posix()
    if normalized_value.startswith(normalized_path):
        return path.name + normalized_value[len(normalized_path):]
    return normalized_value
