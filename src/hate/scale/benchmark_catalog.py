"""Benchmark catalog fixture evaluation for HATE-GAP-018."""

from __future__ import annotations

from typing import Any

from .performance_budget import evaluate_performance_budget


REPO_CLASS_SHAPES = {
    "small": {"tests": 1_000, "coverage_records": 50_000, "artifact_metadata": 1_000, "graph_nodes": 5_000, "graph_edges": 20_000},
    "medium": {"tests": 25_000, "coverage_records": 1_000_000, "artifact_metadata": 25_000, "graph_nodes": 100_000, "graph_edges": 400_000},
    "large": {"tests": 100_000, "coverage_records": 10_000_000, "artifact_metadata": 100_000, "graph_nodes": 500_000, "graph_edges": 2_000_000},
    "monorepo": {"tests": 250_000, "coverage_records": 25_000_000, "artifact_metadata": 250_000, "graph_nodes": 1_000_000, "graph_edges": 4_000_000},
}


def evaluate_benchmark_catalog_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_benchmark_catalog_report(
        input_data,
        scenario_id=str(payload.get("fixture_id") or "benchmark-catalog-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": "hold" if report["readiness_effect"] in {"hold", "hard_dq"} else "pass",
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": "hold" if report["readiness_effect"] in {"hold", "hard_dq"} else "none",
        "report": report,
    }


def build_benchmark_catalog_report(
    input_data: dict[str, Any],
    *,
    scenario_id: str = "benchmark-catalog",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    budget_input = _to_performance_budget_input(input_data, scenario_id, source_refs)
    report = evaluate_performance_budget(budget_input)
    extra_findings = _catalog_findings(input_data, report)
    _escalate_fixture_budget_exceeded(input_data, report)
    if extra_findings:
        report["findings"].extend(extra_findings)
        report["readiness_effect"] = _worst_effect([report["readiness_effect"]] + [item["readiness_effect"] for item in extra_findings])
        report["overall_status"] = "blocked" if report["readiness_effect"] == "hard_dq" else "hold"
    report["benchmark_catalog"] = {
        "repo_class": str(input_data.get("repo_class") or "medium"),
        "duration_seconds": float(input_data.get("duration_seconds", 0) or 0),
        "budget_seconds": float(input_data.get("budget_seconds", 0) or 0),
        "manifest_only_large_fixture": bool(input_data.get("manifest_only_large_fixture", True)),
        "streaming_or_chunked": bool(input_data.get("streaming_or_chunked", True)),
    }
    return report


def _escalate_fixture_budget_exceeded(input_data: dict[str, Any], report: dict[str, Any]) -> None:
    duration = float(input_data.get("duration_seconds", 0) or 0)
    budget = float(input_data.get("budget_seconds", 0) or 0)
    if not budget or duration <= budget:
        return
    for finding in report["findings"]:
        if finding.get("code") == "performance_budget_exceeded":
            finding["readiness_effect"] = "hold"
            finding["severity"] = "hold"
            break
    report["readiness_effect"] = _worst_effect([report["readiness_effect"], "hold"])
    report["overall_status"] = "hold"


def _to_performance_budget_input(
    input_data: dict[str, Any],
    scenario_id: str,
    source_refs: list[str] | None,
) -> dict[str, Any]:
    repo_class = str(input_data.get("repo_class") or "medium")
    duration_seconds = float(input_data.get("duration_seconds", 0) or 0)
    budget_seconds = float(input_data.get("budget_seconds", 0) or 0)
    observed_ms = int(duration_seconds * 1000)
    budget_ms = int(budget_seconds * 1000)
    dataset_shape = dict(REPO_CLASS_SHAPES.get(repo_class, REPO_CLASS_SHAPES["medium"]))
    dataset_shape.update({key: int(value) for key, value in input_data.get("dataset_shape", {}).items()})
    estimated = {
        "peak_memory_mb": int(input_data.get("peak_memory_mb", 512)),
        "input_bytes": int(input_data.get("input_bytes", 0)),
        "archive_entries": int(input_data.get("archive_entries", 0)),
        "pagination_tested": bool(input_data.get("pagination_tested", repo_class in {"medium", "large", "monorepo"})),
        "cache_invalidation_tested": bool(input_data.get("cache_invalidation_tested", True)),
        "pairwise_comparisons": int(input_data.get("pairwise_comparisons", 0)),
    }
    return {
        "scenario_id": scenario_id,
        "profile": str(input_data.get("profile") or "default"),
        "dataset_shape": dataset_shape,
        "observed_ms": {
            "ingest": observed_ms,
            "validation": min(observed_ms, 120_000),
            "graph_build": min(observed_ms, 180_000),
            "store_index": min(observed_ms, 90_000),
            "replay": min(observed_ms, 120_000),
            "report_generation": min(observed_ms, 60_000),
        },
        "thresholds_ms": {"ingest": budget_ms or 300_000},
        "estimated_counters": estimated,
        "sourceRefs": list(source_refs or input_data.get("sourceRefs") or ["performance-benchmark"]),
    }


def _catalog_findings(input_data: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    repo_class = str(input_data.get("repo_class") or "medium")
    source_ref = report["sourceRefs"][0] if report.get("sourceRefs") else "performance-benchmark"
    if repo_class not in REPO_CLASS_SHAPES:
        findings.append(_finding("performance_unknown_repo_class", "hold", f"Unknown benchmark repo class: {repo_class}", source_ref))
    if report["pagination"]["required"] and not report["pagination"]["tested"]:
        findings.append(_finding("performance_pagination_not_tested", "hold", "Large benchmark requires pagination evidence.", source_ref))
    if not report["staleness"]["cache_invalidation_tested"]:
        findings.append(_finding("performance_cache_invalidation_not_tested", "hold", "Benchmark requires cache invalidation evidence.", source_ref))
    if repo_class in {"large", "monorepo"} and not bool(input_data.get("manifest_only_large_fixture", True)):
        findings.append(_finding("performance_large_raw_fixture_committed", "hard_dq", "Large fixtures must be compact generator manifests, not raw committed outputs.", source_ref))
    if not bool(input_data.get("streaming_or_chunked", True)):
        findings.append(_finding("performance_unbounded_processing", "hard_dq", "Large parser/coverage operations must be streaming or chunked.", source_ref))
    return findings


def _finding(code: str, effect: str, message: str, source_ref: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "critical" if effect == "hard_dq" else "high",
        "readiness_effect": effect,
        "message": message,
        "operation": "benchmark_catalog",
        "sourceRef": source_ref,
        "details": {},
    }


def _worst_effect(effects: list[str]) -> str:
    order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
    return max(effects, key=lambda item: order[item])
