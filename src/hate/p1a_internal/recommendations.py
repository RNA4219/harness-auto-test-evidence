"""P1A reason tree and recommendations."""

from __future__ import annotations

from typing import Any

from hate.p1a_export_metadata import export_metadata_issues
from hate.p1a_precheck import precheck_gaps, precheck_permission_issues
from hate.p1a_schema import bundle_schema_issues

SCHEMA_VERSION = "HATE/v1"


def _build_reason_tree(bundle: dict[str, Any], report: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    if mode in {"why-excluded", "why-score-changed"}:
        for index, issue in enumerate(bundle_schema_issues(bundle), start=1):
            reasons.append({
                "reason_id": f"reason:bundle_schema:{index}", "category": "schema", "summary": issue["message"],
                "evidence_status": "ineligible", "blocking": True, **issue, "children": [],
            })
    for index, issue in enumerate(export_metadata_issues(bundle, report), start=1):
        blocking = issue["severity"] == "high"
        if mode != "why-score-changed" and mode != ("why-excluded" if blocking else "why-soft-gap"):
            continue
        reasons.append({
            "reason_id": f"reason:export:{index}", "category": "export", "summary": issue["message"],
            "evidence_status": "ineligible" if blocking else "soft_gap", "blocking": blocking,
            **issue, "children": [],
        })
    if mode in {"why-excluded", "why-score-changed"}:
        for index, issue in enumerate(precheck_permission_issues(bundle), start=1):
            reasons.append({
                "reason_id": f"reason:precheck_permission:{index}", "category": "precheck",
                "summary": issue["message"], "evidence_status": "ineligible", "blocking": True,
                **issue, "children": [],
            })
    if mode in {"why-soft-gap", "why-score-changed"}:
        for index, gap in enumerate(precheck_gaps(bundle), start=1):
            reasons.append({
                "reason_id": f"reason:precheck:{index}", "category": "precheck",
                "summary": gap["message"], "evidence_status": "soft_gap",
                **gap, "children": [],
            })
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
    if gap_id in {"bundle_schema", "all"}:
        for index, issue in enumerate(bundle_schema_issues(bundle), start=1):
            recommendations.append({
                "recommendation_id": f"recommend:bundle_schema:{index}", "gap_id": "bundle_schema",
                "blocking": True, **issue,
                "recommended_actions": ["Resolve the reported bundle schema violation and regenerate the bundle from valid source inputs."],
                "recommended_manual_layer": "spec-clarification", "related_source_refs": issue["source_refs"],
            })
    for index, issue in enumerate(export_metadata_issues(bundle, report), start=1):
        if gap_id not in {"export_metadata", "all", issue["issue"]}:
            continue
        recommendations.append({
            "recommendation_id": f"recommend:export:{index}", "gap_id": "export_metadata",
            "blocking": issue["severity"] == "high", **issue,
            "recommended_actions": [
                "Review the original bundle purpose, export status, and schema validation evidence.",
                "Resolve the reported restriction or evidence gap and regenerate the export from corrected inputs.",
            ],
            "recommended_manual_layer": "spec-clarification", "related_source_refs": issue["source_refs"],
        })
    if gap_id in {"precheck", "precheck_permission", "all"}:
        for index, issue in enumerate(precheck_permission_issues(bundle), start=1):
            recommendations.append({
                "recommendation_id": f"recommend:precheck_permission:{index}",
                "gap_id": "precheck_permission", "blocking": True, **issue,
                "recommended_actions": [
                    "Inspect the original precheck record and resolve each reported permission condition.",
                    "Regenerate precheck and QEG export from corrected evidence; retain the original denial for diagnosis.",
                ],
                "recommended_manual_layer": "spec-clarification", "related_source_refs": issue["source_refs"],
            })
    for index, gap in enumerate(precheck_gaps(bundle), start=1):
        declared_id = gap["gap"].get("gap_id") if gap["gap"] is not None else None
        if gap_id not in {"precheck", "all"} and gap_id != declared_id:
            continue
        recommendations.append({
            "recommendation_id": f"recommend:precheck:{index}", "gap_id": "precheck", **gap,
            "recommended_actions": [
                "Review the original precheck reasons and the declared gap details.",
                "Attach the missing evidence or context, then regenerate precheck and QEG export.",
            ],
            "recommended_manual_layer": "spec-clarification", "related_source_refs": gap["source_refs"],
        })
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
