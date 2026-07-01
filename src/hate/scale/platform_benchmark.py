"""Platform benchmark fixture report for large deterministic datasets."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


DATASET_CLASSES = {
    "bench-small": {"repo_count": 10, "finding_count": 10_000, "artifact_metadata": 10_000},
    "bench-medium": {"repo_count": 100, "finding_count": 100_000, "artifact_metadata": 100_000},
    "bench-large": {"repo_count": 1000, "finding_count": 1_000_000, "artifact_metadata": 1_000_000},
}
MIN_DISTRIBUTION = {
    "critical_findings_pct": 0.05,
    "high_findings_pct": 0.15,
    "medium_findings_pct": 0.30,
    "low_findings_pct": 0.50,
    "accepted_debt_pct": 0.10,
    "expired_accepted_debt_pct": 0.02,
    "unsafe_artifact_metadata_pct": 0.01,
    "external_repo_holds_pct": 0.03,
    "stale_cache_candidates_pct": 0.05,
}
REQUIRED_METRICS = {
    "generation_time_ms",
    "store_ingest_time_ms",
    "projection_rebuild_time_ms",
    "read_model_query_p50_ms",
    "read_model_query_p95_ms",
    "read_model_query_p99_ms",
    "dashboard_view_model_generation_time_ms",
    "scheduler_lease_scan_time_ms",
    "artifact_metadata_query_time_ms",
}
REQUIRED_BUDGETS = {
    "ingest_budget_ms",
    "projection_rebuild_budget_ms",
    "read_model_p95_budget_ms",
    "dashboard_view_model_p95_budget_ms",
    "scheduler_lease_scan_budget_ms",
    "artifact_metadata_query_budget_ms",
}
REQUIRED_BASELINE = {
    "hardware_class",
    "os",
    "python_version",
    "storage_mode",
    "dataset_class",
    "seed",
    "policy_hash",
}
DEGRADATION_CODES = {
    "degraded_query",
    "partial_projection",
    "scheduler_backpressure",
    "cache_disabled",
    "artifact_metadata_only",
}


def build_platform_benchmark_report(data: dict[str, Any], report_id: str = "platform-benchmark") -> dict[str, Any]:
    """Build a deterministic platform benchmark report without materializing huge datasets."""
    dataset_class = str(data.get("dataset_class") or "bench-small")
    seed = str(data.get("seed") or "")
    requested = dict(data.get("generator_inputs") or {})
    distribution = dict(data.get("distribution") or {})
    metrics = dict(data.get("metrics") or {})
    budgets = dict(data.get("budgets") or {})
    baseline = dict(data.get("baseline") or {})
    degradations = sorted({str(item) for item in data.get("degradations", [])})
    findings: list[dict[str, Any]] = []

    counts = _resolve_counts(dataset_class, requested, findings)
    generated = _deterministic_counts(seed, counts, distribution)
    _check_distribution(generated, counts, findings)
    _check_metrics(metrics, findings)
    _check_budgets(metrics, budgets, findings)
    _check_baseline(baseline, dataset_class, seed, findings)
    _check_degradations(degradations, data, findings)

    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-benchmark-report",
        "report_id": report_id,
        "overall_status": "hold" if findings else "pass",
        "readiness_effect": "hold" if findings else "none",
        "dataset_class": dataset_class,
        "seed": seed,
        "dataset_counts": counts,
        "deterministic_hash": _stable_hash({"dataset_class": dataset_class, "seed": seed, "counts": counts, "distribution": distribution}),
        "distribution": generated,
        "metrics": metrics,
        "budgets": budgets,
        "baseline": baseline,
        "degradations": degradations,
        "findings": findings,
        "summary": {
            "repo_count": counts["repo_count"],
            "finding_count": counts["finding_count"],
            "artifact_metadata": counts["artifact_metadata"],
            "finding_count_class": _count_class(counts["finding_count"]),
            "finding_count_total": len(findings),
        },
        "sourceRefs": list(data.get("sourceRefs") or []),
    }


def _resolve_counts(dataset_class: str, requested: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, int]:
    base = dict(DATASET_CLASSES.get(dataset_class) or {})
    if not base:
        findings.append(_finding("platform_benchmark_dataset_class_unknown", {"dataset_class": dataset_class}))
        base = dict(DATASET_CLASSES["bench-small"])
    for field in ["repo_count", "finding_count", "artifact_metadata"]:
        if field in requested:
            value = requested[field]
            if isinstance(value, int) and value > 0:
                base[field] = value
            else:
                findings.append(_finding("platform_benchmark_generator_input_invalid", {"field": field}))
    return {key: int(value) for key, value in base.items()}


def _deterministic_counts(seed: str, counts: dict[str, int], distribution: dict[str, Any]) -> dict[str, int]:
    del seed
    finding_count = counts["finding_count"]
    artifact_count = counts["artifact_metadata"]
    repo_count = counts["repo_count"]
    resolved = {}
    for key, minimum in MIN_DISTRIBUTION.items():
        pct = float(distribution.get(key, minimum))
        denominator = artifact_count if key == "unsafe_artifact_metadata_pct" else repo_count if key == "external_repo_holds_pct" else finding_count
        resolved[key.replace("_pct", "")] = int(math.ceil(denominator * pct))
    return resolved


def _check_distribution(generated: dict[str, int], counts: dict[str, int], findings: list[dict[str, Any]]) -> None:
    denominators = {
        "unsafe_artifact_metadata": counts["artifact_metadata"],
        "external_repo_holds": counts["repo_count"],
    }
    for pct_key, minimum in MIN_DISTRIBUTION.items():
        count_key = pct_key.replace("_pct", "")
        denominator = denominators.get(count_key, counts["finding_count"])
        observed = generated.get(count_key, 0) / denominator if denominator else 0
        if observed < minimum:
            findings.append(_finding("platform_benchmark_distribution_below_minimum", {"distribution": count_key}))


def _check_metrics(metrics: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for metric in sorted(REQUIRED_METRICS - set(metrics)):
        findings.append(_finding("platform_benchmark_metric_missing", {"metric": metric}))


def _check_budgets(metrics: dict[str, Any], budgets: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for budget in sorted(REQUIRED_BUDGETS - set(budgets)):
        findings.append(_finding("platform_benchmark_budget_missing", {"budget": budget}))
    comparisons = [
        ("store_ingest_time_ms", "ingest_budget_ms", "degraded_query"),
        ("projection_rebuild_time_ms", "projection_rebuild_budget_ms", "partial_projection"),
        ("read_model_query_p95_ms", "read_model_p95_budget_ms", "degraded_query"),
        ("dashboard_view_model_generation_time_ms", "dashboard_view_model_p95_budget_ms", "degraded_query"),
        ("scheduler_lease_scan_time_ms", "scheduler_lease_scan_budget_ms", "scheduler_backpressure"),
        ("artifact_metadata_query_time_ms", "artifact_metadata_query_budget_ms", "artifact_metadata_only"),
    ]
    for metric, budget, degradation in comparisons:
        if _number(metrics.get(metric)) > _number(budgets.get(budget)) > 0:
            findings.append(_finding("platform_benchmark_budget_exceeded", {"metric": metric, "budget": budget, "required_degradation": degradation}))


def _check_baseline(baseline: dict[str, Any], dataset_class: str, seed: str, findings: list[dict[str, Any]]) -> None:
    for field in sorted(REQUIRED_BASELINE - set(baseline)):
        findings.append(_finding("platform_benchmark_baseline_metadata_missing", {"field": field}))
    if baseline and baseline.get("dataset_class") != dataset_class:
        findings.append(_finding("platform_benchmark_baseline_dataset_mismatch"))
    if baseline and str(baseline.get("seed")) != seed:
        findings.append(_finding("platform_benchmark_baseline_seed_mismatch"))


def _check_degradations(degradations: list[str], data: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for degradation in degradations:
        if degradation not in DEGRADATION_CODES:
            findings.append(_finding("platform_benchmark_degradation_unknown", {"degradation": degradation}))
    if degradations and data.get("claims_pass_without_scope_limit"):
        findings.append(_finding("platform_benchmark_degraded_pass_without_scope_limit"))


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _count_class(finding_count: int) -> str:
    if finding_count >= 1_000_000:
        return "million"
    if finding_count >= 100_000:
        return "hundred-thousand"
    return "small"


def _finding(code: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": code,
        "sourceRefs": [],
    }
    if extra:
        finding.update(extra)
    return finding


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
