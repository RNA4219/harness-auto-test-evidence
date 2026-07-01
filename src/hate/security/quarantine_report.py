"""Product-grade security quarantine report builder."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .export_filter import filter_for_export
from .summary_filter import filter_for_summary


READINESS_ORDER = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
PUBLIC_SURFACES = {"public", "external_export", "qeg_export", "diagnostic_bundle", "support_bundle", "summary"}
UNSAFE_REDACTION_STATES = {"pending", "failed"}


def build_security_quarantine_report(input_data: dict[str, Any]) -> dict[str, Any]:
    """Build security-quarantine-report from artifact safety and surface filter results."""

    artifact_reports = list(input_data.get("artifact_safety_reports") or [])
    artifacts = list(input_data.get("artifacts") or _artifacts_from_safety_reports(artifact_reports))
    surfaces = list(input_data.get("surfaces") or ["summary", "qeg_export", "diagnostic_bundle", "external_export"])
    profile = str(input_data.get("profile") or "product")

    artifact_results = [_artifact_result(report, artifacts) for report in artifact_reports]
    safety_findings = _findings_from_artifact_results(artifact_results)
    surface_checks: list[dict[str, Any]] = []
    surface_findings: list[dict[str, Any]] = []

    for surface in surfaces:
        surface_name = str(surface)
        summary_report = filter_for_summary(artifacts, _summary_surface(surface_name))
        export_report = filter_for_export(artifacts, _export_surface(surface_name), profile=profile)
        check = {
            "surface": surface_name,
            "summary_visible_artifact_ids": [item["artifact_id"] for item in summary_report["visible_artifacts"]],
            "summary_hidden_artifact_ids": [item["artifact_id"] for item in summary_report["hidden_artifacts"]],
            "export_allowed_artifact_ids": [item["artifact_id"] for item in export_report["allowed_artifacts"]],
            "export_excluded_artifact_ids": [item["artifact_id"] for item in export_report["excluded_artifacts"]],
            "export_hold_artifact_ids": [item["artifact_id"] for item in export_report["hold_artifacts"]],
            "export_ready": bool(export_report["export_ready"]),
            "readiness_effect": _max_effect(summary_report["readiness_effect"], export_report["readiness_effect"]),
            "sourceRefs": ["security/summary_filter.py:filter_for_summary", "security/export_filter.py:filter_for_export"],
        }
        surface_checks.append(check)
        surface_findings.extend(_surface_findings(surface_name, artifacts, check))

    findings = safety_findings + surface_findings
    readiness_effect = _max_effect(*(finding["readiness_effect"] for finding in findings))
    status = "pass" if readiness_effect == "pass" else "hold"
    source_refs = sorted(
        {
            *input_data.get("sourceRefs", []),
            *[ref for result in artifact_results for ref in result.get("sourceRefs", [])],
            "docs/process/PRIVACY_QUARANTINE_CONTRACT.md",
            "docs/process/DATA_RETENTION_LEGAL_REQUIREMENTS.md",
        }
    )

    return {
        "schema_version": "HATE/v1",
        "record_type": "security-quarantine-report",
        "report_id": str(input_data.get("report_id") or "security-quarantine-report"),
        "profile": profile,
        "artifact_results": artifact_results,
        "surface_checks": surface_checks,
        "findings": findings,
        "status": status,
        "readiness_effect": readiness_effect,
        "sourceRefs": source_refs,
        "summary": {
            "artifact_count": len(artifacts),
            "artifact_report_count": len(artifact_reports),
            "surface_count": len(surface_checks),
            "finding_count": len(findings),
            "quarantined_count": sum(1 for item in artifact_results if item["quarantine_status"] == "quarantined"),
            "redaction_pending_or_failed_count": sum(
                1 for item in artifact_results if item["redaction_status"] in UNSAFE_REDACTION_STATES
            ),
        },
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def _artifact_result(report: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    artifact_id = str(report.get("artifact_id") or "unknown")
    manifest = _find_artifact_manifest(artifact_id, artifacts)
    quarantine_required = bool(report.get("quarantine_required", False))
    redaction_required = bool(report.get("redaction_required", False))
    manifest_quarantine = str(manifest.get("quarantine_status") or "")
    manifest_redaction = str(manifest.get("redaction_status") or "")
    quarantine_status = manifest_quarantine or ("quarantined" if quarantine_required else "none")
    redaction_status = manifest_redaction or ("pending" if redaction_required else "not_required")

    return {
        "artifact_id": artifact_id,
        "classification": str(manifest.get("classification") or _classification_for_report(report)),
        "quarantine_required": quarantine_required,
        "quarantine_status": quarantine_status,
        "redaction_required": redaction_required,
        "redaction_status": redaction_status,
        "safe_for_summary": bool(manifest.get("safe_for_summary", not quarantine_required)),
        "finding_types": sorted({str(finding.get("finding_type")) for finding in report.get("findings", [])}),
        "readiness_effect": str(report.get("readiness_effect") or "pass"),
        "sourceRefs": list(report.get("sourceRefs") or []),
    }


def _artifacts_from_safety_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for report in reports:
        quarantine_required = bool(report.get("quarantine_required", False))
        redaction_required = bool(report.get("redaction_required", False))
        artifacts.append(
            {
                "artifact_id": str(report.get("artifact_id") or "unknown"),
                "classification": _classification_for_report(report),
                "quarantine_status": "quarantined" if quarantine_required else "none",
                "redaction_status": "pending" if redaction_required else "not_required",
                "safe_for_summary": not quarantine_required,
                "readiness_effect": str(report.get("readiness_effect") or "pass"),
            }
        )
    return artifacts


def _find_artifact_manifest(artifact_id: str, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    for artifact in artifacts:
        if str(artifact.get("artifact_id")) == artifact_id:
            return artifact
    return {}


def _classification_for_report(report: dict[str, Any]) -> str:
    if report.get("quarantine_required") or report.get("redaction_required"):
        return "restricted"
    return "public"


def _findings_from_artifact_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for result in results:
        artifact_id = result["artifact_id"]
        source_ref = _first_source_ref(result)
        if result["quarantine_required"] and result["quarantine_status"] != "quarantined":
            findings.append(
                _finding(
                    "security_quarantine_decision_missing",
                    "critical",
                    f"Artifact {artifact_id} requires quarantine but is not quarantined.",
                    source_ref,
                    "hard_dq",
                    artifact_id,
                    "quarantine",
                )
            )
        if result["redaction_required"] and result["redaction_status"] in {"not_required", "pending", "failed"}:
            findings.append(
                _finding(
                    "security_quarantine_redaction_not_complete",
                    "high",
                    f"Artifact {artifact_id} requires completed redaction before public or diagnostic exposure.",
                    source_ref,
                    "hold" if result["redaction_status"] == "pending" else "hard_dq",
                    artifact_id,
                    "complete_redaction",
                )
            )
        if result["readiness_effect"] == "hard_dq":
            findings.append(
                _finding(
                    "security_quarantine_artifact_hard_dq",
                    "critical",
                    f"Artifact {artifact_id} has hard_dq safety findings.",
                    source_ref,
                    "hard_dq",
                    artifact_id,
                    "keep_quarantined",
                )
            )
    return findings


def _surface_findings(surface: str, artifacts: list[dict[str, Any]], check: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    visible = set(check["summary_visible_artifact_ids"])
    exported = set(check["export_allowed_artifact_ids"])
    public_like = surface in PUBLIC_SURFACES
    for artifact in artifacts:
        artifact_id = str(artifact.get("artifact_id") or "unknown")
        quarantine_status = str(artifact.get("quarantine_status") or "none")
        redaction_status = str(artifact.get("redaction_status") or "not_required")
        classification = str(artifact.get("classification") or "internal")
        unsafe = quarantine_status == "quarantined" or redaction_status in UNSAFE_REDACTION_STATES
        if unsafe and artifact_id in visible:
            findings.append(
                _finding(
                    "security_quarantine_unsafe_artifact_visible",
                    "critical",
                    f"Unsafe artifact {artifact_id} is visible on {surface}.",
                    f"surface:{surface}",
                    "hard_dq",
                    artifact_id,
                    "hide_from_surface",
                )
            )
        if unsafe and artifact_id in exported:
            findings.append(
                _finding(
                    "security_quarantine_unsafe_artifact_exported",
                    "critical",
                    f"Unsafe artifact {artifact_id} is exported on {surface}.",
                    f"surface:{surface}",
                    "hard_dq",
                    artifact_id,
                    "exclude_from_export",
                )
            )
        if public_like and classification in {"confidential", "restricted"} and artifact_id in exported:
            findings.append(
                _finding(
                    "security_quarantine_restricted_artifact_exported",
                    "critical",
                    f"Restricted artifact {artifact_id} is exported on public-like surface {surface}.",
                    f"surface:{surface}",
                    "hard_dq",
                    artifact_id,
                    "restrict_surface",
                )
            )
    return findings


def _summary_surface(surface: str) -> str:
    if surface == "external_export":
        return "public"
    if surface in {"qeg_export", "diagnostic_bundle", "support_bundle"}:
        return "qeg" if surface == "qeg_export" else "support"
    return surface


def _export_surface(surface: str) -> str:
    if surface == "public":
        return "external_export"
    return surface


def _first_source_ref(result: dict[str, Any]) -> str:
    refs = result.get("sourceRefs") or []
    return str(refs[0]) if refs else f"artifact:{result['artifact_id']}"


def _finding(
    code: str,
    severity: str,
    message: str,
    source_ref: str,
    readiness_effect: str,
    artifact_id: str,
    required_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "sourceRef": source_ref,
        "readiness_effect": readiness_effect,
        "artifact_id": artifact_id,
        "required_action": required_action,
    }


def _max_effect(*effects: str) -> str:
    if not effects:
        return "pass"
    return max(effects, key=lambda effect: READINESS_ORDER.get(effect, 0))
