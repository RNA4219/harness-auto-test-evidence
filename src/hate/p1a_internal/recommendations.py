"""P1A reason tree and recommendations."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "HATE/v1"


def _build_reason_tree(bundle: dict[str, Any], report: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    if mode == "why-soft-gap":
        for index, gap in enumerate(report.get("missing_execution", []), start=1):
            reasons.append({
                "reason_id": f"reason:soft_gap:{index}",
                "category": "missing_execution",
                "summary": gap.get("reason", "missing execution"),
                "risk_id": gap.get("risk_id", ""),
                "expected_test_ref": gap.get("expected_test_ref", ""),
                "evidence_status": "missing",
                "source_refs": ["qeg-export-report.json"],
                "children": [
                    {
                        "reason_id": f"reason:soft_gap:{index}:risk",
                        "summary": "High-risk changed path requires execution evidence.",
                        "source_refs": _source_refs_for_risk(bundle, gap.get("risk_id", "")),
                    }
                ],
            })
    elif mode == "why-excluded":
        for index, artifact in enumerate(report.get("excludedArtifacts", []), start=1):
            reasons.append({
                "reason_id": f"reason:excluded:{index}",
                "category": "artifact_safety",
                "summary": artifact.get("reason", "artifact excluded"),
                "artifact_id": artifact.get("artifact_id", ""),
                "evidence_status": "excluded",
                "source_refs": ["qeg-export-report.json"],
                "children": [],
            })
    else:
        completeness = bundle.get("completeness", {})
        reasons.append({
            "reason_id": "reason:score:completeness",
            "category": "aete_score",
            "summary": "AETE score follows bundle completeness and visible unsupported claims.",
            "score": completeness.get("score"),
            "partial": completeness.get("partial"),
            "source_refs": ["qeg-bundle.json", "qeg-export-report.json"],
            "children": [
                {
                    "reason_id": "reason:score:unsupported",
                    "summary": f"Unsupported claims: {len(completeness.get('unsupportedClaims', []))}",
                    "source_refs": ["qeg-export-report.json"],
                }
            ],
        })
    return reasons


def _build_recommendations(bundle: dict[str, Any], report: dict[str, Any], gap_id: str) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    if gap_id in {"missing_execution", "all"}:
        for index, gap in enumerate(report.get("missing_execution", []), start=1):
            recommendations.append({
                "recommendation_id": f"recommend:missing_execution:{index}",
                "gap_id": "missing_execution",
                "risk_id": gap.get("risk_id", ""),
                "expected_test_ref": gap.get("expected_test_ref", ""),
                "recommended_actions": [
                    "Add or restore automated execution evidence for the expected test.",
                    "If automation is not available, create a manual-bb bridge review.",
                    "Keep the risk debt open until evidence is attached.",
                ],
                "recommended_test_layer": "unit",
                "recommended_manual_layer": "manual-scripted",
                "source_refs": ["qeg-export-report.json", "risk-debt-register.json", "manual-bb-bridge-requests.jsonl"],
                "related_source_refs": _source_refs_for_risk(bundle, gap.get("risk_id", "")),
            })
    if gap_id in {"artifact_safety", "all"}:
        for index, artifact in enumerate(report.get("excludedArtifacts", []), start=1):
            recommendations.append({
                "recommendation_id": f"recommend:artifact_safety:{index}",
                "gap_id": "artifact_safety",
                "artifact_id": artifact.get("artifact_id", ""),
                "recommended_actions": [
                    "Replace the unsafe artifact with a redacted artifact reference.",
                    "Run artifact safety checks before adding it to QEG evidence.",
                ],
                "recommended_manual_layer": "spec-clarification",
                "source_refs": ["qeg-export-report.json"],
                "related_source_refs": [],
            })
    return recommendations


def _source_refs_for_risk(bundle: dict[str, Any], risk_id: str) -> list[str]:
    target_id = f"risk:{risk_id}"
    refs: list[str] = []
    for node in bundle.get("nodes", []):
        if node.get("id") == target_id:
            refs.extend(str(ref) for ref in node.get("sourceRefs", []))
    for edge in bundle.get("edges", []):
        if edge.get("from") == target_id or edge.get("to") == target_id:
            refs.extend(str(ref) for ref in edge.get("traceability", {}).get("sourceRefs", []))
    return sorted(set(refs))


def _build_summary(aete_score: dict[str, Any], doctor_report: dict[str, Any]) -> str:
    return "\n".join([
        "# P1a Trust Summary",
        "",
        f"- Run: `{aete_score['run_id']}` attempt `{aete_score['run_attempt']}`",
        f"- Weighted score: `{aete_score['weighted_score']:.3f}`",
        f"- Score confidence: `{aete_score['score_confidence']}`",
        f"- Calibration: `{aete_score['calibration_status']}`",
        f"- Doctor findings: {doctor_report['summary']['finding_count']}",
        "",
        "HATE trust hardening is advisory evidence only.",
        "`publish_gate_override=false` and `release_gate_override=false`.",
        "",
    ])