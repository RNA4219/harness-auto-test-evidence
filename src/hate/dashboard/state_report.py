"""Dashboard state report evaluation for HATE-GAP-008."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_STATES = {"ready", "loading", "empty", "stale", "error", "unauthorized", "high-volume", "partial", "quarantined"}
REQUIRED_VIEWS = {
    "run_overview",
    "risk_graph",
    "risk_coverage",
    "evidence_graph",
    "adapter_health",
    "artifact_detail",
    "artifact_safety",
    "manual_review_queue",
    "release_pack",
    "support_triage",
}


@dataclass(frozen=True)
class DashboardStateFinding:
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


def evaluate_dashboard_state_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_dashboard_state_report(input_data, source_refs=[payload.get("fixture_id", "fixture")])
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_dashboard_state_report(
    input_data: dict[str, Any],
    *,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    view_states = _normalize_view_states(input_data)
    findings = _findings_for(input_data, view_states)
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "dashboard-state-report",
        "report_id": str(input_data.get("report_id") or "dashboard-state-report"),
        "view_states": view_states,
        "required_views": sorted(REQUIRED_VIEWS),
        "required_states": sorted(REQUIRED_STATES),
        "findings": [finding.to_dict() for finding in findings],
        "status": status,
        "readiness_effect": "hold" if findings else "none",
        "sourceRefs": sorted(set((source_refs or []) + _source_refs(view_states))),
    }


def _normalize_view_states(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_states = input_data.get("view_states")
    if isinstance(raw_states, list):
        return [_normalize_state(item) for item in raw_states if isinstance(item, dict)]

    return [_normalize_state({
        "view": input_data.get("view", "run_overview"),
        "state": input_data.get("state", "ready"),
        "rbac": input_data.get("rbac", "allowed"),
        "sourceRefs": input_data.get("sourceRefs", ["dashboard-state-fixture"]),
        "required_actions": input_data.get("required_actions", ["inspect_source_refs"]),
        "forbidden_content": input_data.get("forbidden_content", []),
        "visible_sourceRefs": input_data.get("visible_sourceRefs", True),
        "product_ready_badge": input_data.get("product_ready_badge", False),
        "hard_dq_count": input_data.get("hard_dq_count", 0),
        "missing_report_count": input_data.get("missing_report_count", 0),
        "restricted_path_visible": input_data.get("restricted_path_visible", False),
        "raw_secret_visible": input_data.get("raw_secret_visible", False),
        "severity_color_only": input_data.get("severity_color_only", False),
    })]


def _normalize_state(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "view": str(raw.get("view", "run_overview")),
        "state": str(raw.get("state", "ready")),
        "rbac": str(raw.get("rbac", "allowed")),
        "sourceRefs": sorted({str(item) for item in raw.get("sourceRefs", [])}),
        "required_actions": sorted({str(item) for item in raw.get("required_actions", [])}),
        "forbidden_content": sorted({str(item) for item in raw.get("forbidden_content", [])}),
        "visible_sourceRefs": bool(raw.get("visible_sourceRefs", True)),
        "product_ready_badge": bool(raw.get("product_ready_badge", False)),
        "hard_dq_count": int(raw.get("hard_dq_count", 0) or 0),
        "missing_report_count": int(raw.get("missing_report_count", 0) or 0),
        "restricted_path_visible": bool(raw.get("restricted_path_visible", False)),
        "raw_secret_visible": bool(raw.get("raw_secret_visible", False)),
        "severity_color_only": bool(raw.get("severity_color_only", False)),
    }


def _findings_for(input_data: dict[str, Any], view_states: list[dict[str, Any]]) -> list[DashboardStateFinding]:
    findings: list[DashboardStateFinding] = []
    required_views = set(input_data.get("required_views", []))
    if required_views:
        observed = {state["view"] for state in view_states}
        missing = sorted(required_views - observed)
        if missing:
            findings.append(_finding(
                "dashboard_required_view_missing",
                f"Dashboard state report is missing required views: {', '.join(missing)}",
                "dashboard-state-manifest",
            ))

    for state in view_states:
        source_ref = _state_source_ref(state)
        if state["rbac"] == "denied":
            findings.append(_finding(
                "dashboard_rbac_denied_state_required",
                "RBAC denied dashboard state must render as unauthorized without restricted details.",
                source_ref,
            ))
        if not state["sourceRefs"] or not state["visible_sourceRefs"]:
            findings.append(_finding(
                "dashboard_source_refs_missing",
                "Dashboard state must expose sourceRefs for the upstream report evidence.",
                source_ref,
            ))
        if not state["required_actions"] and state["state"] in {"empty", "error", "stale", "unauthorized"}:
            findings.append(_finding(
                "dashboard_action_missing",
                "Blocking or empty dashboard state must include an actionable next step.",
                source_ref,
            ))
        if state["product_ready_badge"] and (state["hard_dq_count"] > 0 or state["missing_report_count"] > 0):
            findings.append(_finding(
                "dashboard_product_ready_overclaim",
                "Product-ready badge is forbidden when hard DQ or missing reports are present.",
                source_ref,
            ))
        if state["restricted_path_visible"] or state["raw_secret_visible"]:
            findings.append(_finding(
                "dashboard_restricted_content_visible",
                "Dashboard state must not expose restricted paths or raw secrets.",
                source_ref,
            ))
        if state["severity_color_only"]:
            findings.append(_finding(
                "dashboard_severity_color_only",
                "Severity must not be represented by color alone.",
                source_ref,
            ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> DashboardStateFinding:
    severity = "high"
    if code in {"dashboard_restricted_content_visible", "dashboard_product_ready_overclaim"}:
        severity = "critical"
    return DashboardStateFinding(code=code, severity=severity, message=message, sourceRef=source_ref)


def _source_refs(view_states: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for state in view_states:
        refs.extend(state["sourceRefs"])
    return refs


def _state_source_ref(state: dict[str, Any]) -> str:
    if state["sourceRefs"]:
        return state["sourceRefs"][0]
    return f"dashboard-state:{state['view']}:{state['state']}"
