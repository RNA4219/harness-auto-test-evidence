"""P1A retry aggregation with flaky detection."""

from __future__ import annotations

from typing import Any

from hate.p1a_io import _stable_hash
from hate.p1a_internal.identity import _identity_components, _normalized_canonical_test_id, _stable_mapping

SCHEMA_VERSION = "HATE/v1"


def _build_retry_aggregation(run_id: str, run_attempt: int, bundle: dict[str, Any]) -> dict[str, Any]:
    executions_by_test: dict[str, list[dict[str, Any]]] = {}
    for edge in bundle.get("edges", []):
        if edge.get("kind") != "evidenced_by":
            continue
        executions_by_test.setdefault(str(edge.get("from", "")), [])
    execution_nodes = {
        str(node.get("id", "")): node
        for node in bundle.get("nodes", [])
        if node.get("kind") == "execution_evidence"
    }
    for edge in bundle.get("edges", []):
        if edge.get("kind") != "evidenced_by":
            continue
        execution = execution_nodes.get(str(edge.get("to", "")))
        if execution:
            executions_by_test.setdefault(str(edge.get("from", "")), []).append(execution)
    aggregates: list[dict[str, Any]] = []
    test_nodes = {
        str(node.get("id", "")): node
        for node in bundle.get("nodes", [])
        if node.get("kind") == "test"
    }
    for test_node_id, executions in sorted(executions_by_test.items()):
        test_node = test_nodes.get(test_node_id, {})
        test_data = test_node.get("data", {}) if isinstance(test_node, dict) else {}
        components = _identity_components(str(test_data.get("canonical_test_id", "")), test_data)
        normalized_test_id = _normalized_canonical_test_id(components)
        matrix = _merge_matrix(components.get("matrix", {}), executions)
        matrix_group = _matrix_group_id(matrix)
        ordered_executions = sorted(executions, key=_execution_sort_key)
        statuses = [str(item.get("data", {}).get("status", "unknown")) for item in ordered_executions]
        shard_total = _shard_total(ordered_executions)
        observed_shards = sorted({
            str(item.get("data", {}).get("shard_index"))
            for item in ordered_executions
            if item.get("data", {}).get("shard_index") is not None
        })
        missing_shard = bool(shard_total and len(observed_shards) < shard_total)
        aggregate_status = "inconclusive" if missing_shard else _aggregate_status(statuses)
        aggregates.append({
            "aggregation_key": f"{normalized_test_id}:{matrix_group}:{run_attempt}",
            "test_node_id": test_node_id,
            "normalized_canonical_test_id": normalized_test_id,
            "matrix": matrix,
            "matrix_group": matrix_group,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "retry_attempts": [
                {
                    "execution_node_id": item.get("id", ""),
                    "retry_index": int(item.get("data", {}).get("retry_index", index)),
                    "status": str(item.get("data", {}).get("status", "unknown")),
                }
                for index, item in enumerate(ordered_executions)
            ],
            "shards": {
                "observed": observed_shards,
                "expected_count": shard_total,
                "missing": missing_shard,
            },
            "raw_statuses": statuses,
            "aggregate_status": aggregate_status,
            "source_refs": ["qeg-bundle.json"],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "retry_aggregation",
        "run_id": run_id,
        "run_attempt": run_attempt,
        "aggregates": aggregates,
        "summary": {
            "aggregate_count": len(aggregates),
            "flaky_count": sum(1 for item in aggregates if str(item["aggregate_status"]).startswith("flaky")),
            "inconclusive_count": sum(1 for item in aggregates if item["aggregate_status"] == "inconclusive"),
            "matrix_group_count": len({item["matrix_group"] for item in aggregates}),
            "missing_shard_count": sum(1 for item in aggregates if item["shards"]["missing"]),
        },
    }


def _merge_matrix(test_matrix: Any, executions: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, Any] = dict(test_matrix) if isinstance(test_matrix, dict) else {}
    for execution in executions:
        execution_matrix = execution.get("data", {}).get("matrix") or execution.get("data", {}).get("matrix_values") or {}
        if isinstance(execution_matrix, dict):
            matrix.update(_stable_mapping(execution_matrix))
    return _stable_mapping(matrix)


def _matrix_group_id(matrix: dict[str, Any]) -> str:
    if not matrix:
        return "matrix:default"
    return f"matrix:{_stable_hash(matrix)[:12]}"


def _execution_sort_key(execution: dict[str, Any]) -> tuple[int, str]:
    data = execution.get("data", {})
    retry_index = data.get("retry_index", data.get("attempt_index", 0))
    try:
        retry_value = int(retry_index)
    except (TypeError, ValueError):
        retry_value = 0
    return retry_value, str(execution.get("id", ""))


def _shard_total(executions: list[dict[str, Any]]) -> int:
    totals: list[int] = []
    for execution in executions:
        value = execution.get("data", {}).get("shard_total") or execution.get("data", {}).get("shard_count")
        try:
            if value is not None:
                totals.append(int(value))
        except (TypeError, ValueError):
            continue
    return max(totals) if totals else 0


def _aggregate_status(statuses: list[str]) -> str:
    if not statuses:
        return "inconclusive"
    normalized = [status.lower() for status in statuses]
    if all(status == "passed" for status in normalized):
        return "stable_passed"
    if all(status == "failed" for status in normalized):
        return "failed"
    if normalized[-1] == "passed":
        return "flaky_passed"
    if normalized[-1] == "failed":
        return "flaky_failed"
    return "inconclusive"
