"""P1A retry aggregation with flaky detection."""

from __future__ import annotations

from collections import Counter
from typing import Any

from hate.execution_status import OUTCOME_FIELDS, effective_status
from hate.p1a_internal.identity import _identity_components, _normalized_canonical_test_id, _stable_mapping
from hate.p1a_io import _stable_hash

SCHEMA_VERSION = "HATE/v1"


def _build_retry_aggregation(run_id: str, run_attempt: int, bundle: dict[str, Any]) -> dict[str, Any]:
    aggregates = [_aggregate_group(run_id, run_attempt, group) for group in _execution_groups(bundle)]
    issues = [{**issue, "aggregation_key": item["aggregation_key"], "test_node_ids": item["test_node_ids"]}
              for item in aggregates for issue in item["issues"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "retry_aggregation",
        "run_id": run_id,
        "run_attempt": run_attempt,
        "aggregates": aggregates,
        "issues": issues,
        "summary": {
            "aggregate_count": len(aggregates),
            "flaky_count": sum(1 for item in aggregates if str(item["aggregate_status"]).startswith("flaky")),
            "declared_flaky_count": sum(1 for item in aggregates if item["declared_flaky"]),
            "inconclusive_count": sum(1 for item in aggregates if item["aggregate_status"] == "inconclusive"),
            "matrix_group_count": len({item["matrix_group"] for item in aggregates}),
            "missing_shard_count": sum(1 for item in aggregates if item["shards"]["missing"]),
            "issue_count": len(issues),
        },
    }


def _execution_groups(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = bundle.get("nodes", [])
    counts = Counter(node.get("id", "") for node in nodes)
    unique = {node["id"]: node for node in nodes if node.get("id", "").strip() and counts[node["id"]] == 1}
    tests = {node_id: node for node_id, node in unique.items() if node.get("kind") == "test"}
    executions = {node_id: node for node_id, node in unique.items() if node.get("kind") == "execution_evidence"}
    links: dict[str, set[str]] = {node_id: set() for node_id in tests}
    for edge in bundle.get("edges", []):
        if edge.get("kind") == "evidenced_by" and edge.get("from") in tests and edge.get("to") in executions:
            links[edge["from"]].add(edge["to"])
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for test_id, test in sorted(tests.items()):
        data = test.get("data", {})
        components = _identity_components(str(data.get("canonical_test_id", "")), data)
        canonical = (_normalized_canonical_test_id(components) if all(components[key] for key in ("framework", "file", "name"))
                     else f"test-node:{test_id}")
        linked: list[dict[str, Any] | None] = [executions[node_id] for node_id in sorted(links[test_id])] or [None]
        for execution in linked:
            matrix = _merge_matrix(components["matrix"], [execution] if execution is not None else [])
            key = canonical, _matrix_group_id(matrix)
            group = groups.setdefault(key, {"canonical": canonical, "matrix": matrix, "matrix_group": key[1],
                                            "test_ids": set(), "executions": {}})
            group["test_ids"].add(test_id)
            if execution is not None:
                group["executions"][execution["id"]] = execution
    return [groups[key] for key in sorted(groups)]


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"issue": code, "message": message, **details}


def _aggregate_group(run_id: str, run_attempt: int, group: dict[str, Any]) -> dict[str, Any]:
    executions = sorted(group["executions"].values(), key=_execution_sort_key)
    totals = {item["data"].get("shard_total", item["data"].get("shard_count")) for item in executions
              if "shard_total" in item.get("data", {}) or "shard_count" in item.get("data", {})}
    shard_total = _shard_total(executions)
    sharded = bool(totals) or any("shard_index" in item.get("data", {}) for item in executions)
    issues: list[dict[str, Any]] = []
    if not executions:
        issues.append(_issue("missing_execution_evidence", "test has no unambiguous linked execution evidence"))
    if len(totals) > 1:
        issues.append(_issue("conflicting_shard_totals", "execution records disagree on the expected shard count"))
    elif sharded and not totals:
        issues.append(_issue("unknown_shard_total", "shard indices do not declare the expected shard count"))
    by_retry: dict[int, list[dict[str, Any]]] = {}
    for execution in executions:
        by_retry.setdefault(_execution_sort_key(execution)[0], []).append(execution)
    indices = sorted(by_retry)
    if indices and (indices[0] != 0 or len(indices) != indices[-1] + 1):
        issues.append(_issue("retry_sequence_gap", "retry history must cover every index from zero to the final attempt"))
    declared_retry_count = max((item["data"].get("retry_count", 0) for item in executions), default=0)
    if declared_retry_count and (not indices or indices[-1] < declared_retry_count):
        issues.append(_issue("reported_retry_history_missing", "reported retries are not fully represented by execution history",
                             retry_count=declared_retry_count))
    attempts = []
    for retry_index in indices:
        attempt, attempt_issues = _attempt_result(retry_index, by_retry[retry_index], shard_total, sharded)
        attempts.append(attempt)
        issues.extend(attempt_issues)
    status = "inconclusive" if issues else _aggregate_status([item["status"] for item in attempts])
    declared_flaky = any(item.get("data", {}).get("flaky") is True for item in executions)
    if declared_flaky and not status.startswith("flaky"):
        issues.append(_issue("declared_flaky_without_mixed_history", "input declares flaky but available history does not establish both failure and success"))
        status = "inconclusive"
    if status.startswith("flaky"):
        issues.append(_issue("flaky_execution", "complete retry history contains both failure and success"))
    test_ids = sorted(group["test_ids"])
    return {
        "aggregation_key": f"{group['canonical']}:{group['matrix_group']}:{run_attempt}",
        "test_node_id": test_ids[0], "test_node_ids": test_ids,
        "normalized_canonical_test_id": group["canonical"], "matrix": group["matrix"], "matrix_group": group["matrix_group"],
        "run_id": run_id, "run_attempt": run_attempt,
        "declared_flaky": declared_flaky, "declared_retry_count": declared_retry_count,
        "retry_attempts": [{"execution_node_id": item["id"], "retry_index": _execution_sort_key(item)[0],
                            "shard_index": item.get("data", {}).get("shard_index"),
                            "status": str(item.get("data", {}).get("status", "unknown")),
                            **{field: item["data"][field] for field in ("flaky", "retry_count", *OUTCOME_FIELDS) if field in item.get("data", {})}}
                           for item in executions],
        "attempt_results": attempts,
        "shards": {"observed": [str(index) for index in sorted({item["data"]["shard_index"] for item in executions
                                                               if "shard_index" in item.get("data", {})})],
                   "expected_count": shard_total, "missing": any(item["missing_shard"] for item in attempts)},
        "raw_statuses": [str(item.get("data", {}).get("status", "unknown")) for item in executions],
        "aggregate_status": status, "issues": issues, "source_refs": ["qeg-bundle.json"],
    }


def _attempt_result(
    retry_index: int, executions: list[dict[str, Any]], shard_total: int, sharded: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    shards = [item.get("data", {}).get("shard_index") for item in executions]
    if len(set(shards)) != len(shards):
        issues.append(_issue("duplicate_retry_shard", "multiple execution nodes occupy the same retry and shard",
                             retry_index=retry_index))
    if sharded and any(index is None for index in shards):
        issues.append(_issue("missing_shard_index", "sharded execution has no shard index", retry_index=retry_index))
    if shard_total and any(index is not None and index >= shard_total for index in shards):
        issues.append(_issue("shard_index_out_of_range", "shard index must be between zero and expected count minus one",
                             retry_index=retry_index))
    valid_shards = {index for index in shards if index is not None and 0 <= index < shard_total}
    missing = bool(shard_total and len(valid_shards) < shard_total)
    if missing:
        issues.append(_issue("missing_shards", "retry attempt does not contain all expected shards", retry_index=retry_index,
                             missing_count=shard_total - len(valid_shards)))
    statuses = [effective_status(item.get("data", {})) for item in executions]
    unexecuted = [item["id"] for item in executions if item.get("data", {}).get("wouldRun") is True]
    if unexecuted:
        issues.append(_issue("test_not_executed", "test was collected as runnable but was not executed",
                             retry_index=retry_index, execution_node_ids=unexecuted))
    elif any(status not in {"passed", "failed", "error"} for status in statuses):
        issues.append(_issue("incomplete_execution_status", "execution status does not establish pass or failure",
                             retry_index=retry_index))
    status = "inconclusive" if issues else "failed" if any(value in {"failed", "error"} for value in statuses) else "passed"
    return {"retry_index": retry_index, "status": status, "missing_shard": missing,
            "execution_node_ids": [item["id"] for item in executions]}, issues


def _merge_matrix(test_matrix: Any, executions: list[dict[str, Any]]) -> dict[str, Any]:
    base: dict[str, Any] = dict(test_matrix) if isinstance(test_matrix, dict) else {}
    matrices = []
    for execution in executions:
        execution_matrix = execution.get("data", {}).get("matrix") or execution.get("data", {}).get("matrix_values") or {}
        if isinstance(execution_matrix, dict):
            matrices.append(_stable_mapping({**base, **execution_matrix}))
    if matrices and any(matrix != matrices[0] for matrix in matrices):
        raise ValueError("executions span multiple matrix groups")
    return matrices[0] if matrices else _stable_mapping(base)


def _matrix_group_id(matrix: dict[str, Any]) -> str:
    if not matrix:
        return "matrix:default"
    return f"matrix:{_stable_hash(matrix)[:12]}"


def _execution_sort_key(execution: dict[str, Any]) -> tuple[int, str]:
    data = execution.get("data", {})
    retry_index = data.get("retry_index", data.get("attempt_index", 0))
    return int(retry_index), str(execution.get("id", ""))


def _shard_total(executions: list[dict[str, Any]]) -> int:
    totals: set[int] = set()
    for execution in executions:
        value = execution.get("data", {}).get("shard_total", execution.get("data", {}).get("shard_count"))
        if value is not None:
            totals.add(int(value))
    return next(iter(totals)) if len(totals) == 1 else 0


def _aggregate_status(statuses: list[str]) -> str:
    if not statuses:
        return "inconclusive"
    normalized = ["failed" if status.lower() == "error" else status.lower() for status in statuses]
    if any(status not in {"passed", "failed"} for status in normalized):
        return "inconclusive"
    if all(status == "passed" for status in normalized):
        return "stable_passed"
    if all(status == "failed" for status in normalized):
        return "failed"
    if normalized[-1] == "passed":
        return "flaky_passed"
    if normalized[-1] == "failed":
        return "flaky_failed"
    return "inconclusive"
