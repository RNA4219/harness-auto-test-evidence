"""P1A AETE dimension scoring with signal generation."""

from __future__ import annotations

from typing import Any

from hate.p1a_internal.doctor_report import _all_source_refs_non_empty

AETE_DIMENSIONS = [
    "provenance_integrity",
    "determinism_flakiness",
    "traceability_lineage",
    "oracle_strength",
    "change_relevance",
    "coverage_adequacy",
    "cross_signal_corroboration",
    "freshness_profile_conformance",
]

RUBRIC_VERSION = "aete-rubric-2026-06-28"
PROFILE_VERSION = "hate-profile-default-2026-06-28"


def _score_dimensions_with_signals(bundle: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = bundle.get("nodes", [])
    edges = bundle.get("edges", [])
    metadata = bundle.get("metadata", {})
    completeness = bundle.get("completeness", {})
    has_run = bool(metadata.get("runId") and metadata.get("createdAt") and report.get("commit_sha"))
    has_source_refs = _all_source_refs_non_empty(nodes, edges)
    has_tests = any(node.get("kind") == "test" for node in nodes)
    has_execution = any(node.get("kind") == "execution_evidence" for node in nodes)
    has_coverage = any(node.get("kind") == "coverage" for node in nodes)
    has_context_or_branch_coverage = any(
        node.get("kind") == "coverage"
        and (node.get("data", {}).get("contexts") or node.get("data", {}).get("branch_hits"))
        for node in nodes
    )
    has_changed_code = any(node.get("kind") == "changed_code" for node in nodes)
    has_risk_edges = any(edge.get("kind") in {"touches", "requires_test"} for edge in edges)
    has_contract_or_mutation = any(node.get("kind") in {"contract_evidence", "mutation_evidence"} for node in nodes)
    has_artifact_hash = any(node.get("kind") == "evidence_artifact" and node.get("data", {}).get("sha256") for node in nodes)
    has_unsupported = bool(completeness.get("unsupportedClaims") or report.get("unsupportedClaims"))
    missing_execution = bool(report.get("missing_execution"))
    signal_kinds = {
        node.get("kind")
        for node in nodes
        if node.get("kind") in {"execution_evidence", "coverage", "finding", "evidence_artifact", "contract_evidence", "mutation_evidence"}
    }
    dimensions = {
        "provenance_integrity": 5 if has_run and has_artifact_hash else 3 if has_run else 1 if metadata.get("runId") else 0,
        "determinism_flakiness": 3 if has_tests and has_execution and not missing_execution else 1 if has_tests else 0,
        "traceability_lineage": 5 if has_source_refs and has_risk_edges and has_execution else 3 if has_source_refs and has_risk_edges else 1,
        "oracle_strength": 5 if has_contract_or_mutation else 3 if has_tests and has_execution else 1,
        "change_relevance": 5 if has_changed_code and has_risk_edges else 1,
        "coverage_adequacy": 5 if has_context_or_branch_coverage else 3 if has_coverage else 0,
        "cross_signal_corroboration": 5 if len(signal_kinds) >= 3 else 3 if has_execution and has_coverage else 1 if signal_kinds else 0,
        "freshness_profile_conformance": 3 if not has_unsupported else 1,
    }
    signals = [
        _dimension_signal(
            "provenance_integrity",
            dimensions["provenance_integrity"],
            {
                "has_run_id": bool(metadata.get("runId")),
                "has_created_at": bool(metadata.get("createdAt")),
                "has_commit_sha": bool(report.get("commit_sha")),
                "has_artifact_hash": has_artifact_hash,
            },
            ["qeg-bundle.json", "qeg-export-report.json"],
        ),
        _dimension_signal(
            "determinism_flakiness",
            dimensions["determinism_flakiness"],
            {"has_tests": has_tests, "has_execution": has_execution, "missing_execution": missing_execution},
            ["qeg-bundle.json", "qeg-export-report.json"],
        ),
        _dimension_signal(
            "traceability_lineage",
            dimensions["traceability_lineage"],
            {"source_refs_complete": has_source_refs, "has_risk_edges": has_risk_edges, "has_execution": has_execution},
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
            {"has_changed_code": has_changed_code, "has_risk_edges": has_risk_edges},
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


def _score_confidence(completeness: dict[str, Any], report: dict[str, Any]) -> str:
    if report.get("missing_execution") or completeness.get("unsupportedClaims"):
        return "medium"
    if completeness.get("partial"):
        return "medium"
    return "high"