"""Dashboard UAT report aggregation for HATE-PG-008."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_CHECKS = {
    "view_model_fixtures",
    "schema_validation",
    "redaction",
    "pagination",
    "source_ref_traceability",
}


@dataclass(frozen=True)
class DashboardUATFinding:
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


def build_dashboard_uat_report(
    input_data: dict[str, Any],
    *,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    checks = _normalize_checks(input_data)
    findings = _findings_for(input_data, checks)
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "dashboard-uat-report",
        "report_id": str(input_data.get("report_id") or "dashboard-uat-report"),
        "view_model_results": _normalize_results(input_data.get("view_model_results", [])),
        "checks": checks,
        "state_report_refs": sorted({str(item) for item in input_data.get("state_report_refs", [])}),
        "manual_uat_refs": sorted({str(item) for item in input_data.get("manual_uat_refs", [])}),
        "findings": [finding.to_dict() for finding in findings],
        "status": status,
        "readiness_effect": "hold" if findings else "none",
        "sourceRefs": sorted(set((source_refs or []) + _source_refs(input_data, checks))),
    }


def _normalize_checks(input_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = input_data.get("checks", {})
    checks: dict[str, dict[str, Any]] = {}
    for check_id in sorted(REQUIRED_CHECKS | set(raw if isinstance(raw, dict) else {})):
        data = raw.get(check_id, {}) if isinstance(raw, dict) else {}
        if not isinstance(data, dict):
            data = {}
        checks[check_id] = {
            "check_id": check_id,
            "status": str(data.get("status") or "not_run"),
            "sourceRefs": sorted({str(item) for item in data.get("sourceRefs", [])}),
            "details": str(data.get("details") or ""),
        }
    return checks


def _normalize_results(raw: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        results.append({
            "fixture_id": str(item.get("fixture_id") or "unknown"),
            "view": str(item.get("view") or "unknown"),
            "status": str(item.get("status") or "not_run"),
            "sourceRefs": sorted({str(ref) for ref in item.get("sourceRefs", [])}),
        })
    return sorted(results, key=lambda item: (item["fixture_id"], item["view"]))


def _findings_for(input_data: dict[str, Any], checks: dict[str, dict[str, Any]]) -> list[DashboardUATFinding]:
    findings: list[DashboardUATFinding] = []
    for check_id in sorted(REQUIRED_CHECKS):
        check = checks.get(check_id, {"status": "not_run", "sourceRefs": []})
        status = check["status"]
        source_ref = _first_ref(check, f"dashboard-uat:{check_id}")
        if status in {"not_run", "blocked"}:
            findings.append(_finding(
                "dashboard_uat_required_check_not_run",
                f"Dashboard UAT required check did not pass: {check_id}",
                source_ref,
            ))
        elif status == "fail":
            findings.append(_finding(
                "dashboard_uat_required_check_failed",
                f"Dashboard UAT required check failed: {check_id}",
                source_ref,
            ))

    for result in _normalize_results(input_data.get("view_model_results", [])):
        if result["status"] != "pass":
            findings.append(_finding(
                "dashboard_uat_view_model_fixture_failed",
                f"Dashboard view model fixture did not pass: {result['fixture_id']}",
                _first_ref(result, f"dashboard-fixture:{result['fixture_id']}"),
            ))

    if not input_data.get("state_report_refs"):
        findings.append(_finding(
            "dashboard_uat_state_report_missing",
            "Dashboard UAT report must reference dashboard-state-report evidence.",
            "dashboard-uat-report.json",
        ))
    if input_data.get("raw_unsafe_artifact_visible") is True:
        findings.append(_finding(
            "dashboard_uat_unsafe_artifact_visible",
            "Dashboard UAT must prove raw unsafe artifacts are not visible.",
            "dashboard-uat-report.json",
            severity="critical",
        ))
    if input_data.get("product_ready_badge_with_missing_report") is True:
        findings.append(_finding(
            "dashboard_uat_product_ready_overclaim",
            "Dashboard UAT blocks product-ready badge when required reports are missing.",
            "dashboard-uat-report.json",
            severity="critical",
        ))
    return findings


def _finding(code: str, message: str, source_ref: str, *, severity: str = "high") -> DashboardUATFinding:
    return DashboardUATFinding(code=code, severity=severity, message=message, sourceRef=source_ref)


def _first_ref(item: dict[str, Any], fallback: str) -> str:
    refs = item.get("sourceRefs", [])
    if isinstance(refs, list) and refs:
        return str(refs[0])
    return fallback


def _source_refs(input_data: dict[str, Any], checks: dict[str, dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    refs.extend(str(item) for item in input_data.get("state_report_refs", []))
    refs.extend(str(item) for item in input_data.get("manual_uat_refs", []))
    for check in checks.values():
        refs.extend(check["sourceRefs"])
    for result in _normalize_results(input_data.get("view_model_results", [])):
        refs.extend(result["sourceRefs"])
    return refs
