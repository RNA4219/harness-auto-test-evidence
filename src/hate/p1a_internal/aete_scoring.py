"""P1A AETE dimension scoring with signal generation."""

from __future__ import annotations

from typing import Any

from hate.execution_status import has_execution_result
from hate.p1a_export_metadata import export_metadata_issues
from hate.p1a_graph import analyze_graph, has_any_source_refs
from hate.p1a_internal.doctor_report import _all_source_refs_non_empty
from hate.p1a_internal.retry_aggregation import _build_retry_aggregation
from hate.p1a_precheck import precheck_gaps, precheck_permission_issues
from hate.p1a_provenance import analyze_provenance
from hate.p1a_schema import bundle_schema_issues
from hate.p1a_scores import AETE_WEIGHTS

AETE_DIMENSIONS = list(AETE_WEIGHTS)

RUBRIC_VERSION = "aete-rubric-2026-06-28"
PROFILE_VERSION = "hate-profile-default-2026-06-28"


def _score_dimensions_with_signals(
    bundle: dict[str, Any], report: dict[str, Any], retry_aggregation: dict[str, Any] | None = None,
) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = bundle.get("nodes", [])
    edges = bundle.get("edges", [])
    metadata = bundle.get("metadata", {})
    completeness = bundle.get("completeness", {})
    provenance = analyze_provenance(bundle, report)
    has_source_refs = _all_source_refs_non_empty(nodes, edges)
    graph = analyze_graph(bundle, str(metadata.get("runId", report.get("run_id", ""))))
    has_tests = any(node.get("kind") == "test" for node in nodes)
    has_execution = any(node.get("kind") == "execution_evidence" and has_execution_result(node.get("data", {})) for node in nodes)
    has_coverage = any(node.get("kind") == "coverage" for node in nodes)
    has_context_or_branch_coverage = any(
        node.get("kind") == "coverage"
        and (node.get("data", {}).get("contexts") or node.get("data", {}).get("branch_hits"))
        for node in nodes
    )
    has_changed_code = any(node.get("kind") == "changed_code" for node in nodes)
    has_risk_edges = any(edge.get("kind") in {"touches", "requires_test"} for edge in edges)
    has_contract_or_mutation = any(node.get("kind") in {"contract_evidence", "mutation_evidence"} for node in nodes)
    has_unsupported = bool(completeness.get("unsupportedClaims") or report.get("unsupportedClaims"))
    missing_execution = bool(report.get("missing_execution"))
    if retry_aggregation is None:
        retry_aggregation = _build_retry_aggregation(
            str(metadata.get("runId", report.get("run_id", ""))),
            int(metadata.get("runAttempt", report.get("run_attempt", 1))), bundle,
        )
    aggregates = retry_aggregation["aggregates"]
    retry_summary = retry_aggregation["summary"]
    if not has_tests or retry_summary["flaky_count"] or retry_summary.get("declared_flaky_count", 0):
        determinism_score = 0
    elif missing_execution or not aggregates or retry_summary["inconclusive_count"]:
        determinism_score = 1
    elif all(item["aggregate_status"] == "stable_passed" and len(item["attempt_results"]) >= 2 for item in aggregates):
        determinism_score = 5
    else:
        determinism_score = 3
    lineage_score = 0 if not has_any_source_refs(nodes, edges) else 1
    if has_source_refs and graph.valid and graph.has_risk_test_links:
        lineage_score = 5 if graph.all_risk_tests_executed else 3
    signal_kinds = {
        node.get("kind")
        for node in nodes
        if node.get("kind") in {"execution_evidence", "coverage", "finding", "evidence_artifact", "contract_evidence", "mutation_evidence"}
        and (node.get("kind") != "execution_evidence" or has_execution_result(node.get("data", {})))
    }
    dimensions = {
        "provenance_integrity": provenance.score,
        "determinism_flakiness": determinism_score,
        "traceability_lineage": lineage_score,
        "oracle_strength": 5 if has_contract_or_mutation else 3 if has_tests and has_execution else 1,
        "change_relevance": 5 if graph.has_changed_risk_links else 1,
        "coverage_adequacy": 5 if has_context_or_branch_coverage else 3 if has_coverage else 0,
        "cross_signal_corroboration": 5 if len(signal_kinds) >= 3 else 3 if has_execution and has_coverage else 1 if signal_kinds else 0,
        "freshness_profile_conformance": 3 if not has_unsupported else 1,
    }
    signals = [
        _dimension_signal(
            "provenance_integrity",
            dimensions["provenance_integrity"],
            provenance.observed(),
            ["qeg-bundle.json", "qeg-export-report.json"],
        ),
        _dimension_signal(
            "determinism_flakiness",
            dimensions["determinism_flakiness"],
            {"has_tests": has_tests, "has_execution": has_execution, "missing_execution": missing_execution,
             "aggregate_statuses": [item["aggregate_status"] for item in aggregates],
             "flaky_count": retry_summary["flaky_count"], "declared_flaky_count": retry_summary.get("declared_flaky_count", 0),
             "inconclusive_count": retry_summary["inconclusive_count"]},
            ["qeg-bundle.json", "qeg-export-report.json"],
        ),
        _dimension_signal(
            "traceability_lineage",
            dimensions["traceability_lineage"],
            {"source_refs_complete": has_source_refs, "has_risk_edges": has_risk_edges, "has_execution": has_execution,
             "graph_integrity_ok": graph.valid, "has_risk_test_links": graph.has_risk_test_links,
             "all_risk_tests_executed": graph.all_risk_tests_executed,
             "unexecuted_risk_tests": graph.unexecuted_risk_tests},
            ["qeg-bundle.json", "evidence-map.json"],
        ),
        _dimension_signal(
            "oracle_strength",
            dimensions["oracle_strength"],
            {"has_tests": has_tests, "has_execution": has_execution, "has_contract_or_mutation": has_contract_or_mutation},
            ["qeg-bundle.json"],
        ),
        _dimension_signal(
            "change_relevance",
            dimensions["change_relevance"],
            {"has_changed_code": has_changed_code, "has_risk_edges": has_risk_edges,
             "has_changed_risk_links": graph.has_changed_risk_links},
            ["qeg-bundle.json"],
        ),
        _dimension_signal(
            "coverage_adequacy",
            dimensions["coverage_adequacy"],
            {"has_coverage": has_coverage, "has_context_or_branch_coverage": has_context_or_branch_coverage},
            ["qeg-bundle.json"],
        ),
        _dimension_signal(
            "cross_signal_corroboration",
            dimensions["cross_signal_corroboration"],
            {"signal_kinds": sorted(signal_kinds), "signal_kind_count": len(signal_kinds)},
            ["qeg-bundle.json"],
        ),
        _dimension_signal(
            "freshness_profile_conformance",
            dimensions["freshness_profile_conformance"],
            {"has_unsupported_claims": has_unsupported, "export_status": report.get("export_status", "")},
            ["qeg-export-report.json", "profile-report.json"],
        ),
    ]
    reason_refs = [
        {
            "dimension": signal["dimension"],
            "reason_ref": signal["signal_id"],
            "score": signal["score"],
            "source_refs": signal["source_refs"],
        }
        for signal in signals
    ]
    return dimensions, reason_refs, signals


def _score_dimensions(bundle: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    dimensions, reason_refs, _signals = _score_dimensions_with_signals(bundle, report)
    return dimensions, reason_refs


def _dimension_signal(dimension: str, score: int, observed: dict[str, Any], source_refs: list[str]) -> dict[str, Any]:
    return {
        "signal_id": f"signal:{dimension}:{score}",
        "dimension": dimension,
        "score": score,
        "observed": observed,
        "rationale": _dimension_rationale(dimension, score),
        "source_refs": source_refs,
    }


def _dimension_rationale(dimension: str, score: int) -> str:
    labels = {
        0: "required signal is absent",
        1: "only weak or incomplete signal is present",
        3: "required signal is present at the base trust level",
        5: "strong corroborating signal is present",
    }
    return f"{dimension} score {score}: {labels.get(score, 'profile-specific signal score')}"


def _score_confidence(
    completeness: dict[str, Any], report: dict[str, Any], *, bundle: dict[str, Any] | None = None,
    retry_aggregation: dict[str, Any] | None = None,
) -> str:
    export_issues = export_metadata_issues(bundle or {}, report)
    if bundle is not None and (analyze_provenance(bundle, report).issues or precheck_permission_issues(bundle)
                               or bundle_schema_issues(bundle)):
        return "low"
    if any(issue["severity"] == "high" for issue in export_issues):
        return "low"
    if export_issues:
        return "medium"
    if bundle is not None and precheck_gaps(bundle):
        return "medium"
    if bundle is not None and retry_aggregation is None:
        metadata = bundle.get("metadata", {})
        retry_aggregation = _build_retry_aggregation(
            str(metadata.get("runId", report.get("run_id", ""))),
            int(metadata.get("runAttempt", report.get("run_attempt", 1))), bundle,
        )
    if retry_aggregation is not None and retry_aggregation["summary"]["inconclusive_count"]:
        return "medium"
    gaps = ("partial", "unsupportedClaims", "excludedArtifacts", "parserFailures")
    if (report.get("missing_execution") or report.get("unsupportedClaims") or report.get("excludedArtifacts")
            or any(source.get(field) for source in (completeness, report.get("completeness", {})) for field in gaps)):
        return "medium"
    return "high"
