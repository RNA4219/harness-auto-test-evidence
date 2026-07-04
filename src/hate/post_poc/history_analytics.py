from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


METRIC_NAMES = [
    "flake_rate",
    "evidence_freshness",
    "debt_age",
    "repo_health_score",
    "baseline_drift",
    "regression_cluster_count",
    "manual_review_latency",
]


@dataclass(frozen=True)
class HistoryFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_history_analytics_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_history_analytics_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "history-analytics-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_history_analytics_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "history-analytics-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["history-analytics"])
    query = _normalize_query(input_data.get("query", input_data))
    samples = [_normalize_sample(sample) for sample in input_data.get("samples", [])]
    excluded = [_normalize_exclusion(item) for item in input_data.get("excluded", [])]
    trend_window, metrics = _build_trend_window(query, samples, excluded)
    findings = _findings_for_query(query, samples, excluded, metrics, source_refs[0])

    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "history-analytics-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "query": query,
        "trend_window": trend_window,
        "result": {
            "record_type": "history-analytics-result",
            "metrics": metrics,
            "sample_count": len(samples),
            "excluded_count": len(excluded),
            "exclusion_reasons": sorted({item["reason"] for item in excluded if item["reason"]}),
            "sourceRefs": source_refs,
        },
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "metric_count": len(metrics),
            "sample_count": len(samples),
            "excluded_count": len(excluded),
            "finding_count": len(findings),
            "aggregation_level": query["aggregation_level"],
            "performance_budget_ms": query["performance_budget_ms"],
            "actual_runtime_ms": query["actual_runtime_ms"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_history_materialization_plan(
    input_data: dict[str, Any],
    *,
    plan_id: str = "history-materialization-plan",
    previous_manifest: dict[str, Any] | None = None,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["history-materialization"])
    query = _normalize_query(input_data.get("query", input_data))
    samples = [_normalize_sample(sample) for sample in input_data.get("samples", [])]
    excluded = [_normalize_exclusion(item) for item in input_data.get("excluded", [])]
    previous_entries = {
        str(entry.get("cache_key")): entry
        for entry in (previous_manifest or {}).get("entries", [])
        if entry.get("cache_key")
    }
    entries = [_materialization_entry(query, sample, previous_entries) for sample in samples]
    current_keys = {entry["cache_key"] for entry in entries}
    dropped_entries = [
        _dropped_materialization_entry(entry)
        for cache_key, entry in previous_entries.items()
        if cache_key not in current_keys
    ]
    all_entries = entries + dropped_entries
    findings = _findings_for_materialization_plan(query, samples, excluded, all_entries, source_refs[0])
    plan = {
        "schema_version": "HATE/v1",
        "record_type": "history-materialization-plan",
        "plan_id": plan_id,
        **productization_envelope(input_data, report_id=plan_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "query_fingerprint": _stable_digest({
            "window_start": query["window_start"],
            "window_end": query["window_end"],
            "repo_filter": query["repo_filter"],
            "suite_filter": query["suite_filter"],
            "aggregation_level": query["aggregation_level"],
            "required_metrics": query["required_metrics"],
        }),
        "incremental": {
            "record_type": "history-incremental-materialization",
            "strategy": "sample-fingerprint",
            "reused_count": sum(1 for entry in all_entries if entry["materialization_action"] == "reuse"),
            "recompute_count": sum(1 for entry in all_entries if entry["materialization_action"] == "recompute"),
            "drop_count": sum(1 for entry in all_entries if entry["materialization_action"] == "drop"),
            "excluded_count": len(excluded),
            "sourceRefs": source_refs,
        },
        "entries": all_entries,
        "excluded": excluded,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "entry_count": len(all_entries),
            "sample_count": len(samples),
            "finding_count": len(findings),
            "reused_count": sum(1 for entry in all_entries if entry["materialization_action"] == "reuse"),
            "recompute_count": sum(1 for entry in all_entries if entry["materialization_action"] == "recompute"),
            "drop_count": sum(1 for entry in all_entries if entry["materialization_action"] == "drop"),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(plan, source_refs=source_refs)


def write_history_materialization_manifest(plan: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "history-materialization-manifest",
        "plan_id": str(plan.get("plan_id") or ""),
        **productization_envelope(plan, report_id=str(plan.get("plan_id") or "history-materialization-manifest"), source_refs=list(plan.get("sourceRefs", []))),
        "readiness_effect": str(plan.get("readiness_effect") or "none"),
        "query_fingerprint": str(plan.get("query_fingerprint") or ""),
        "entries": [
            {
                "record_type": "history-materialization-entry",
                "cache_key": entry["cache_key"],
                "sample_id": entry["sample_id"],
                "repo_id": entry["repo_id"],
                "suite_id": entry["suite_id"],
                "sample_fingerprint": entry["sample_fingerprint"],
                "materialized_ref": entry["materialized_ref"],
                "sourceRefs": list(entry.get("sourceRefs") or [entry.get("sourceRef") or entry["sample_id"]]),
            }
            for entry in plan.get("entries", [])
            if entry.get("materialization_action") != "drop"
        ],
        "sourceRefs": list(plan.get("sourceRefs", [])),
    }
    apply_productization_contract_tree(manifest, source_refs=manifest["sourceRefs"])
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "history-materialization-manifest-artifact",
        **productization_envelope(manifest, report_id=f"{manifest['plan_id']}:artifact", source_refs=manifest["sourceRefs"]),
        "readiness_effect": manifest["readiness_effect"],
        "artifact_path": str(path),
        "entry_count": len(manifest["entries"]),
        "sourceRefs": manifest["sourceRefs"],
    }


def _materialization_entry(
    query: dict[str, Any],
    sample: dict[str, Any],
    previous_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sample_fingerprint = _stable_digest({
        "run_id": sample["run_id"],
        "repo_id": sample["repo_id"],
        "suite_id": sample["suite_id"],
        "run_started_at": sample["run_started_at"],
        "test_count": sample["test_count"],
        "flake_count": sample["flake_count"],
        "evidence_age_days": sample["evidence_age_days"],
        "debt_age_days": sample["debt_age_days"],
        "repo_health_score": sample["repo_health_score"],
        "baseline_score": sample["baseline_score"],
        "current_score": sample["current_score"],
        "regression_clusters": sample["regression_clusters"],
        "manual_review_latency_hours": sample["manual_review_latency_hours"],
    })
    cache_key = _stable_digest({
        "aggregation_level": query["aggregation_level"],
        "repo_id": sample["repo_id"],
        "suite_id": sample["suite_id"],
        "run_id": sample["run_id"],
    })
    previous = previous_entries.get(cache_key)
    can_reuse = bool(previous and previous.get("sample_fingerprint") == sample_fingerprint and previous.get("materialized_ref"))
    materialized_ref = str(previous.get("materialized_ref")) if can_reuse else f"history-cache://{cache_key}"
    return {
        "record_type": "history-materialization-entry",
        "sample_id": sample["run_id"],
        "repo_id": sample["repo_id"],
        "suite_id": sample["suite_id"],
        "cache_key": cache_key,
        "sample_fingerprint": sample_fingerprint,
        "materialization_action": "reuse" if can_reuse else "recompute",
        "materialized_ref": materialized_ref,
        "sourceRef": sample["sourceRef"],
    }


def _dropped_materialization_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "history-materialization-entry",
        "sample_id": str(entry.get("sample_id") or ""),
        "repo_id": str(entry.get("repo_id") or ""),
        "suite_id": str(entry.get("suite_id") or ""),
        "cache_key": str(entry.get("cache_key") or ""),
        "sample_fingerprint": str(entry.get("sample_fingerprint") or ""),
        "materialization_action": "drop",
        "materialized_ref": str(entry.get("materialized_ref") or ""),
        "sourceRef": str(entry.get("sourceRef") or entry.get("sample_id") or "previous-manifest"),
    }


def _findings_for_materialization_plan(
    query: dict[str, Any],
    samples: list[dict[str, Any]],
    excluded: list[dict[str, str]],
    entries: list[dict[str, Any]],
    source_ref: str,
) -> list[HistoryFinding]:
    findings: list[HistoryFinding] = []
    if len(samples) < query["min_sample_count"]:
        findings.append(_finding("history_window_too_small", "Incremental plan sample_count is below min_sample_count.", source_ref))
    if any(sample["data_age_days"] > query["stale_after_days"] for sample in samples):
        findings.append(_finding("history_stale_data", "Incremental plan includes stale samples.", source_ref))
    if any(not entry["cache_key"] or not entry["sample_fingerprint"] for entry in entries):
        findings.append(_finding("history_materialization_key_missing", "Materialization entries require cache_key and sample_fingerprint.", source_ref))
    if excluded and not all(item["reason"] for item in excluded):
        findings.append(_finding("history_metric_source_missing", "Excluded samples require exclusion reasons.", source_ref))
    return findings


def _normalize_query(raw: dict[str, Any]) -> dict[str, Any]:
    query = dict(raw or {})
    return {
        "record_type": "history-analytics-query",
        "window_start": str(query.get("window_start") or ""),
        "window_end": str(query.get("window_end") or ""),
        "repo_filter": str(query.get("repo_filter") or "*"),
        "suite_filter": str(query.get("suite_filter") or "*"),
        "aggregation_level": str(query.get("aggregation_level") or "repo"),
        "performance_budget_ms": int(query.get("performance_budget_ms") or 1000),
        "actual_runtime_ms": int(query.get("actual_runtime_ms") or 0),
        "min_sample_count": int(query.get("min_sample_count") or 2),
        "stale_after_days": int(query.get("stale_after_days") or 14),
        "required_metrics": [str(item) for item in query.get("required_metrics", METRIC_NAMES)],
    }


def _normalize_sample(raw: dict[str, Any]) -> dict[str, Any]:
    sample = dict(raw or {})
    return {
        "run_id": str(sample.get("run_id") or ""),
        "repo_id": str(sample.get("repo_id") or ""),
        "suite_id": str(sample.get("suite_id") or ""),
        "run_started_at": str(sample.get("run_started_at") or ""),
        "test_count": int(sample.get("test_count") or 0),
        "flake_count": int(sample.get("flake_count") or 0),
        "evidence_age_days": float(sample.get("evidence_age_days") or 0),
        "debt_age_days": float(sample.get("debt_age_days") or 0),
        "repo_health_score": _optional_float(sample.get("repo_health_score")),
        "baseline_score": _optional_float(sample.get("baseline_score")),
        "current_score": _optional_float(sample.get("current_score")),
        "regression_clusters": int(sample.get("regression_clusters") or 0),
        "unexplained_regression_clusters": int(sample.get("unexplained_regression_clusters") or 0),
        "manual_review_latency_hours": float(sample.get("manual_review_latency_hours") or 0),
        "data_age_days": float(sample.get("data_age_days") or sample.get("evidence_age_days") or 0),
        "sourceRef": str(sample.get("sourceRef") or sample.get("run_id") or "sample"),
    }


def _normalize_exclusion(raw: dict[str, Any]) -> dict[str, str]:
    item = dict(raw or {})
    return {
        "sample_id": str(item.get("sample_id") or ""),
        "reason": str(item.get("reason") or "unknown"),
        "sourceRef": str(item.get("sourceRef") or item.get("sample_id") or "excluded"),
    }


def _build_trend_window(
    query: dict[str, Any],
    samples: list[dict[str, Any]],
    excluded: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics = _compute_metrics(samples)
    trend_window = {
        "record_type": "history-trend-window",
        "window_start": query["window_start"],
        "window_end": query["window_end"],
        "repo_filter": query["repo_filter"],
        "suite_filter": query["suite_filter"],
        "aggregation_level": query["aggregation_level"],
        "sample_count": len(samples),
        "excluded_count": len(excluded),
        "exclusion_reasons": sorted({item["reason"] for item in excluded if item["reason"]}),
        "performance_budget_ms": query["performance_budget_ms"],
        "sourceRefs": [sample["sourceRef"] for sample in samples],
    }
    return trend_window, metrics


def _compute_metrics(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {}

    total_tests = sum(sample["test_count"] for sample in samples)
    total_flakes = sum(sample["flake_count"] for sample in samples)
    evidence_age = _average(sample["evidence_age_days"] for sample in samples)
    drift_values = [
        abs(sample["current_score"] - sample["baseline_score"])
        for sample in samples
        if sample["current_score"] is not None and sample["baseline_score"] is not None
    ]
    health_values = [
        sample["repo_health_score"]
        for sample in samples
        if sample["repo_health_score"] is not None
    ]
    return {
        "flake_rate": round(total_flakes / total_tests, 4) if total_tests else None,
        "evidence_freshness": round(max(0.0, 1.0 - (evidence_age / 30.0)), 4),
        "debt_age": round(_average(sample["debt_age_days"] for sample in samples), 2),
        "repo_health_score": round(_average(health_values), 4) if health_values else None,
        "baseline_drift": round(_average(drift_values), 4) if drift_values else None,
        "regression_cluster_count": sum(sample["regression_clusters"] for sample in samples),
        "manual_review_latency": round(
            _average(sample["manual_review_latency_hours"] for sample in samples),
            2,
        ),
    }


def _findings_for_query(
    query: dict[str, Any],
    samples: list[dict[str, Any]],
    excluded: list[dict[str, str]],
    metrics: dict[str, Any],
    source_ref: str,
) -> list[HistoryFinding]:
    findings: list[HistoryFinding] = []
    if len(samples) < query["min_sample_count"]:
        findings.append(_finding(
            "history_window_too_small",
            "Trend query sample_count is below min_sample_count.",
            source_ref,
        ))
    if query["actual_runtime_ms"] > query["performance_budget_ms"]:
        findings.append(_finding(
            "history_query_budget_exceeded",
            "Trend query exceeded performance_budget_ms.",
            source_ref,
        ))
    if any(sample["data_age_days"] > query["stale_after_days"] for sample in samples):
        findings.append(_finding(
            "history_stale_data",
            "Trend query includes samples older than stale_after_days.",
            source_ref,
        ))

    missing_metrics = [
        metric for metric in query["required_metrics"]
        if metric not in metrics or metrics.get(metric) is None
    ]
    if missing_metrics:
        findings.append(_finding(
            "history_metric_source_missing",
            f"Trend query is missing metric sources: {', '.join(missing_metrics)}.",
            source_ref,
        ))

    unexplained = sum(sample["unexplained_regression_clusters"] for sample in samples)
    if unexplained:
        findings.append(_finding(
            "history_regression_cluster_unexplained",
            "Regression clusters require explanatory sourceRefs before pass.",
            source_ref,
        ))

    if excluded and not any(item["reason"] for item in excluded):
        findings.append(_finding(
            "history_metric_source_missing",
            "Excluded samples require exclusion reasons.",
            source_ref,
        ))
    return findings


def _average(values: Any) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return sum(items) / len(items)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _stable_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finding(code: str, message: str, source_ref: str) -> HistoryFinding:
    return HistoryFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
