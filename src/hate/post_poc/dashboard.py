from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


ROUTES = {
    "/dashboard/portfolio",
    "/dashboard/repos/:repo_id",
    "/dashboard/findings",
    "/dashboard/debt",
    "/dashboard/manual-review",
    "/dashboard/policies",
    "/dashboard/audit",
}
UI_STATES = {
    "loading",
    "empty",
    "partial",
    "stale",
    "permission_denied",
    "unsafe_artifact_hidden",
    "action_pending",
    "action_failed",
    "loaded",
}
ACTION_TYPES = {
    "assign_owner",
    "change_due_date",
    "request_manual_review",
    "accept_debt",
    "revoke_debt",
    "resolve_debt",
    "propose_baseline",
    "trigger_rerun",
    "export_safe_report",
}


@dataclass(frozen=True)
class DashboardFinding:
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


def evaluate_dashboard_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_dashboard_interaction_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "dashboard-interaction-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_dashboard_interaction_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "dashboard-interaction-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["dashboard-interaction"])
    session = _normalize_session(input_data.get("session", {}))
    routes = [_normalize_route(route) for route in input_data.get("routes", [])]
    actions = [_normalize_action(action) for action in input_data.get("actions", [])]
    findings = _findings_for(session, routes, actions, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "dashboard-interaction-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "session_view": session,
        "route_states": routes,
        "action_intents": actions,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "route_count": len(routes),
            "action_intent_count": len(actions),
            "finding_count": len(findings),
            "permission_denied_count": sum(1 for route in routes if route["ui_state"] == "permission_denied"),
            "unsafe_hidden_count": sum(1 for route in routes if route["ui_state"] == "unsafe_artifact_hidden"),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def render_dashboard_static_html(report: dict[str, Any]) -> str:
    """Render a local, read-only dashboard evidence page from canonical records."""
    session = report.get("session_view", {})
    routes = list(report.get("route_states", []))
    actions = list(report.get("action_intents", []))
    findings = list(report.get("findings", []))
    summary = report.get("summary", {})
    status = str(report.get("overall_status") or "unknown")
    status_class = "pass" if status == "pass" else "hold"
    rows = "\n".join(_route_html_row(route) for route in routes)
    action_rows = "\n".join(_action_html_row(action) for action in actions) or _empty_row("No pending action intents.", 5)
    finding_rows = "\n".join(_finding_html_row(finding) for finding in findings) or _empty_row("No dashboard findings.", 4)
    return "\n".join([
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <title>HATE Dashboard Evidence</title>",
        "  <style>",
        "    body { font-family: system-ui, sans-serif; margin: 24px; color: #202124; background: #f8fafc; }",
        "    header, section { max-width: 1180px; margin: 0 auto 20px; }",
        "    header { display: flex; justify-content: space-between; gap: 16px; align-items: start; }",
        "    h1 { font-size: 24px; margin: 0 0 8px; }",
        "    h2 { font-size: 18px; margin: 0 0 10px; }",
        "    .pill { display: inline-block; padding: 4px 10px; border-radius: 999px; font-weight: 700; }",
        "    .pass { background: #dff7e7; color: #146c2e; }",
        "    .hold { background: #fff2cc; color: #7a4c00; }",
        "    .denied, .unsafe { color: #8a1f11; font-weight: 700; }",
        "    .muted { color: #5f6b7a; }",
        "    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }",
        "    .metric { background: white; border: 1px solid #d9e2ec; padding: 12px; border-radius: 8px; }",
        "    table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #d9e2ec; }",
        "    th, td { text-align: left; padding: 10px; border-bottom: 1px solid #e6edf3; vertical-align: top; }",
        "    th { background: #eef3f8; font-size: 13px; }",
        "    code { overflow-wrap: anywhere; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <header>",
        "    <div>",
        "      <h1>HATE Dashboard Evidence</h1>",
        f"      <div class=\"muted\">Report: <code>{escape(str(report.get('report_id') or ''))}</code></div>",
        f"      <div class=\"muted\">Actor: <code>{escape(str(session.get('actor') or ''))}</code> / Role: <code>{escape(str(session.get('role') or ''))}</code></div>",
        "    </div>",
        f"    <span class=\"pill {status_class}\">{escape(status.upper())}</span>",
        "  </header>",
        "  <section class=\"grid\">",
        _metric("Routes", summary.get("route_count", len(routes))),
        _metric("Actions", summary.get("action_intent_count", len(actions))),
        _metric("Permission Denied", summary.get("permission_denied_count", 0)),
        _metric("Unsafe Hidden", summary.get("unsafe_hidden_count", 0)),
        "  </section>",
        "  <section>",
        "    <h2>Route States</h2>",
        "    <table>",
        "      <thead><tr><th>Route</th><th>State</th><th>RBAC</th><th>Read Model</th><th>Canonical Verdict</th><th>Safety</th></tr></thead>",
        f"      <tbody>{rows}</tbody>",
        "    </table>",
        "  </section>",
        "  <section>",
        "    <h2>Action Intents</h2>",
        "    <table>",
        "      <thead><tr><th>Intent</th><th>Action</th><th>Actor</th><th>Target</th><th>Status</th></tr></thead>",
        f"      <tbody>{action_rows}</tbody>",
        "    </table>",
        "  </section>",
        "  <section>",
        "    <h2>Findings</h2>",
        "    <table>",
        "      <thead><tr><th>Code</th><th>Severity</th><th>Effect</th><th>Source</th></tr></thead>",
        f"      <tbody>{finding_rows}</tbody>",
        "    </table>",
        "  </section>",
        "</body>",
        "</html>",
    ])


def write_dashboard_static_html(report: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard_static_html(report), encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "dashboard-static-html-artifact",
        **productization_envelope(report, report_id=f"{report.get('report_id') or 'dashboard'}:artifact", source_refs=list(report.get("sourceRefs", []))),
        "readiness_effect": str(report.get("readiness_effect") or "none"),
        "artifact_path": str(path),
        "source_report_id": str(report.get("report_id") or ""),
        "overall_status": report.get("overall_status", "hold"),
        "sourceRefs": list(report.get("sourceRefs", [])),
    }


def _route_html_row(route: dict[str, Any]) -> str:
    state = str(route.get("ui_state") or "")
    rbac = str(route.get("rbac_decision") or "")
    safety = "unsafe body redacted" if state == "unsafe_artifact_hidden" else "body not rendered"
    safety_class = "unsafe" if state == "unsafe_artifact_hidden" else "muted"
    if state == "permission_denied":
        safety = "restricted view"
        safety_class = "denied"
    return "".join([
        "<tr>",
        f"<td><code>{escape(str(route.get('route') or ''))}</code></td>",
        f"<td>{escape(state)}</td>",
        f"<td>{escape(rbac)}</td>",
        f"<td><code>{escape(str(route.get('read_model_ref') or ''))}</code></td>",
        f"<td><code>{escape(str(route.get('canonical_verdict_ref') or ''))}</code></td>",
        f"<td class=\"{safety_class}\">{escape(safety)}</td>",
        "</tr>",
    ])


def _action_html_row(action: dict[str, Any]) -> str:
    return "".join([
        "<tr>",
        f"<td><code>{escape(str(action.get('intent_id') or ''))}</code></td>",
        f"<td>{escape(str(action.get('action_type') or ''))}</td>",
        f"<td><code>{escape(str(action.get('actor') or ''))}</code></td>",
        f"<td><code>{escape(str(action.get('target_ref') or ''))}</code></td>",
        f"<td>{escape(str(action.get('intent_status') or ''))}</td>",
        "</tr>",
    ])


def _finding_html_row(finding: dict[str, Any]) -> str:
    return "".join([
        "<tr>",
        f"<td><code>{escape(str(finding.get('code') or ''))}</code></td>",
        f"<td>{escape(str(finding.get('severity') or ''))}</td>",
        f"<td>{escape(str(finding.get('readiness_effect') or ''))}</td>",
        f"<td><code>{escape(str(finding.get('sourceRef') or ''))}</code></td>",
        "</tr>",
    ])


def _metric(label: str, value: Any) -> str:
    return f"    <div class=\"metric\"><strong>{escape(label)}</strong><br>{escape(str(value))}</div>"


def _empty_row(message: str, colspan: int) -> str:
    return f"<tr><td colspan=\"{colspan}\" class=\"muted\">{escape(message)}</td></tr>"


def _normalize_session(raw: dict[str, Any]) -> dict[str, Any]:
    session = dict(raw or {})
    return {
        "record_type": "dashboard-session-view",
        "session_id": str(session.get("session_id") or ""),
        "actor": str(session.get("actor") or ""),
        "role": str(session.get("role") or ""),
        "tenant_id": str(session.get("tenant_id") or ""),
        "authenticated": bool(session.get("authenticated", False)),
        "sourceRefs": [str(item) for item in session.get("sourceRefs", [])],
    }


def _normalize_route(raw: dict[str, Any]) -> dict[str, Any]:
    route = dict(raw or {})
    return {
        "record_type": "dashboard-route-state",
        "route": str(route.get("route") or ""),
        "ui_state": str(route.get("ui_state") or route.get("state") or "loading"),
        "read_model_ref": str(route.get("read_model_ref") or ""),
        "rbac_decision": str(route.get("rbac_decision") or "allowed"),
        "canonical_verdict_ref": str(route.get("canonical_verdict_ref") or ""),
        "recomputed_verdict": bool(route.get("recomputed_verdict", False)),
        "unsafe_artifact_body_visible": bool(route.get("unsafe_artifact_body_visible", False)),
        "raw_connector_payload_visible": bool(route.get("raw_connector_payload_visible", False)),
        "hidden_reason": str(route.get("hidden_reason") or ""),
        "sourceRefs": [str(item) for item in route.get("sourceRefs", [])],
    }


def _normalize_action(raw: dict[str, Any]) -> dict[str, Any]:
    action = dict(raw or {})
    return {
        "record_type": "dashboard-action-intent",
        "intent_id": str(action.get("intent_id") or ""),
        "action_type": str(action.get("action_type") or ""),
        "actor": str(action.get("actor") or ""),
        "target_ref": str(action.get("target_ref") or ""),
        "idempotency_key": str(action.get("idempotency_key") or ""),
        "intent_status": str(action.get("intent_status") or "pending"),
        "sourceRefs": [str(item) for item in action.get("sourceRefs", [])],
    }


def _findings_for(
    session: dict[str, Any],
    routes: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    source_ref: str,
) -> list[DashboardFinding]:
    findings: list[DashboardFinding] = []
    if not session["authenticated"]:
        findings.append(_finding("dashboard_session_unauthenticated", "Dashboard session requires authentication.", source_ref))

    route_names = {route["route"] for route in routes}
    if "/dashboard/portfolio" not in route_names:
        findings.append(_finding("dashboard_route_missing", "Dashboard portfolio route is required.", source_ref))

    for route in routes:
        route_ref = route["sourceRefs"][0] if route["sourceRefs"] else source_ref
        if route["route"] not in ROUTES:
            findings.append(_finding("dashboard_route_missing", f"Unsupported dashboard route: {route['route']}.", route_ref))
        if route["ui_state"] not in UI_STATES:
            findings.append(_finding("dashboard_state_unknown", f"Unsupported dashboard UI state: {route['ui_state']}.", route_ref))
        if not route["read_model_ref"]:
            findings.append(_finding("dashboard_read_model_missing", "Dashboard route requires canonical read_model_ref.", route_ref))
        if not route["sourceRefs"]:
            findings.append(_finding("dashboard_source_refs_missing", "Dashboard route requires sourceRefs.", route_ref))
        if route["ui_state"] == "permission_denied" and route["rbac_decision"] != "denied":
            findings.append(_finding("dashboard_rbac_denied_state_required", "Permission denied route requires denied RBAC decision.", route_ref))
        if route["rbac_decision"] == "denied" and route["ui_state"] != "permission_denied":
            findings.append(_finding("dashboard_rbac_denied_state_required", "Denied RBAC decision must render permission_denied state.", route_ref))
        if route["ui_state"] == "unsafe_artifact_hidden" and not route["hidden_reason"]:
            findings.append(_finding("dashboard_unsafe_hidden_reason_missing", "Unsafe hidden state requires hidden_reason.", route_ref))
        if route["recomputed_verdict"] or not route["canonical_verdict_ref"]:
            findings.append(_finding("dashboard_recomputed_verdict", "Dashboard must use canonical verdict refs and not recompute readiness.", route_ref))
        if route["unsafe_artifact_body_visible"] or route["raw_connector_payload_visible"]:
            findings.append(_finding("dashboard_unsafe_body_visible", "Dashboard must not render unsafe artifact bodies or raw connector payloads.", route_ref))

    for action in actions:
        action_ref = action["sourceRefs"][0] if action["sourceRefs"] else source_ref
        if action["action_type"] not in ACTION_TYPES:
            findings.append(_finding("dashboard_action_unknown", f"Unsupported dashboard action: {action['action_type']}.", action_ref))
        if not action["intent_id"] or not action["actor"] or not action["target_ref"] or not action["idempotency_key"] or not action["sourceRefs"]:
            findings.append(_finding("dashboard_action_intent_missing", "Dashboard action must produce auditable intent with actor, target, idempotency, and sourceRefs.", action_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> DashboardFinding:
    return DashboardFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
