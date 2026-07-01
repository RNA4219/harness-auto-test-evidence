"""Platform dashboard wireframe conformance report."""

from __future__ import annotations

import json
from typing import Any


REQUIRED_VIEWS = {
    "portfolio_overview",
    "repo_detail",
    "run_detail",
    "findings_queue",
    "risk_debt_board",
    "manual_review_queue",
    "policy_drift",
    "scheduler_status",
    "artifact_quarantine",
}
REQUIRED_VIEW_FIELDS = {
    "view_id",
    "scope",
    "generated_at",
    "stale",
    "permissions",
    "summary",
    "items",
    "selected_item",
    "sourceRefs",
    "redactions",
    "errors",
}
COMMON_LAYOUT = {
    "header",
    "summary_metrics",
    "filter_bar",
    "primary_table_or_timeline",
    "detail_panel",
    "sourceRefs_panel",
    "unsafe_redaction_notices",
}
STATE_BEHAVIORS = {
    "loading": {"stable_skeleton", "no_fake_counts"},
    "empty": {"no_data_reason", "next_action"},
    "partial": {"missing_resource_list", "stale_marker"},
    "stale": {"age", "source", "rebuild_action"},
    "permission_denied": {"denial_reason", "restricted_body_hidden"},
    "unsafe_hidden": {"redaction_reason", "approval_path"},
    "degraded": {"performance_budget_exceeded", "reduced_data_mode"},
}
VISUAL_REQUIRED = {
    "stable_table_labels",
    "distinct_non_ready_states",
    "score_breakdown_visible",
    "sourceRefs_reachable",
    "unsafe_body_never_rendered",
    "keyboard_focus_order_complete",
    "mobile_critical_information_preserved",
}


def build_platform_dashboard_wireframe_report(
    data: dict[str, Any],
    report_id: str = "platform-dashboard-wireframe",
) -> dict[str, Any]:
    """Validate dashboard view composition and visual acceptance metadata."""
    views = [dict(item) for item in data.get("views", [])]
    required_views = set(data.get("required_views") or REQUIRED_VIEWS)
    visual_acceptance = set(data.get("visual_acceptance", []))
    findings: list[dict[str, Any]] = []
    view_reports = [_view_report(view, findings) for view in views]
    _check_inventory(view_reports, required_views, findings)
    _check_visual_acceptance(visual_acceptance, findings)
    _check_unsafe_body_not_rendered(views, findings)

    source_refs = _report_source_refs(data, view_reports, findings)
    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-dashboard-wireframe-report",
        "report_id": report_id,
        "overall_status": "hold" if findings else "pass",
        "readiness_effect": "hold" if findings else "none",
        "view_inventory": view_reports,
        "state_matrix": _state_matrix_summary(views),
        "visual_acceptance": sorted(visual_acceptance),
        "findings": findings,
        "summary": {
            "view_count": len(views),
            "required_view_count": len(required_views),
            "covered_view_count": len({item["view_id"] for item in view_reports}),
            "finding_count": len(findings),
        },
        "sourceRefs": source_refs,
    }


def _view_report(view: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    view_id = str(view.get("view_id") or "")
    missing_fields = sorted(REQUIRED_VIEW_FIELDS - set(view))
    missing_layout = sorted(COMMON_LAYOUT - set(view.get("layout", [])))
    state = str(view.get("state") or "ready")
    behaviors = set(view.get("state_behaviors", []))
    missing_behaviors = sorted(STATE_BEHAVIORS.get(state, set()) - behaviors)
    source_refs = list(view.get("sourceRefs") or [])
    columns = list(view.get("columns") or [])

    if missing_fields:
        findings.append(_finding("dashboard_wireframe_view_model_field_missing", {"view_id": view_id, "missing_fields": missing_fields}))
    if missing_layout:
        findings.append(_finding("dashboard_wireframe_layout_region_missing", {"view_id": view_id, "missing_layout": missing_layout}))
    if missing_behaviors:
        findings.append(_finding("dashboard_wireframe_state_behavior_missing", {"view_id": view_id, "state": state, "missing_behaviors": missing_behaviors}))
    if not source_refs:
        findings.append(_finding("dashboard_wireframe_source_refs_missing", {"view_id": view_id}))
    if any(not str(column.get("label") or "") for column in columns if isinstance(column, dict)):
        findings.append(_finding("dashboard_wireframe_table_label_missing", {"view_id": view_id}))
    if view.get("recomputes_readiness"):
        findings.append(_finding("dashboard_wireframe_recomputes_readiness", {"view_id": view_id}))

    return {
        "view_id": view_id,
        "state": state,
        "scope": view.get("scope", ""),
        "stale": bool(view.get("stale", False)),
        "missing_fields": missing_fields,
        "missing_layout": missing_layout,
        "missing_state_behaviors": missing_behaviors,
        "sourceRefs": source_refs,
    }


def _check_inventory(view_reports: list[dict[str, Any]], required_views: set[str], findings: list[dict[str, Any]]) -> None:
    present = {item["view_id"] for item in view_reports}
    for view_id in sorted(required_views - present):
        findings.append(_finding("dashboard_wireframe_required_view_missing", {"view_id": view_id}))


def _check_visual_acceptance(visual_acceptance: set[str], findings: list[dict[str, Any]]) -> None:
    for item in sorted(VISUAL_REQUIRED - visual_acceptance):
        findings.append(_finding("dashboard_wireframe_visual_acceptance_missing", {"acceptance": item}))


def _check_unsafe_body_not_rendered(views: list[dict[str, Any]], findings: list[dict[str, Any]]) -> None:
    for view in views:
        serialized = json.dumps(view, sort_keys=True)
        if "unsafe_artifact_body" in serialized or "SECRET_SHOULD_NOT_RENDER" in serialized:
            findings.append(_finding("dashboard_wireframe_unsafe_body_rendered", {"view_id": str(view.get("view_id") or "")}))


def _state_matrix_summary(views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "state": state,
            "covered": any(str(view.get("state") or "ready") == state for view in views),
            "required_behaviors": sorted(behaviors),
        }
        for state, behaviors in STATE_BEHAVIORS.items()
    ]


def _finding(code: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": code,
        "sourceRefs": [],
    }
    if extra:
        finding.update(extra)
    return finding


def _report_source_refs(
    data: dict[str, Any],
    view_reports: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[str]:
    refs: list[str] = [str(ref) for ref in data.get("sourceRefs", []) if str(ref)]
    for view in view_reports:
        refs.extend(str(ref) for ref in view.get("sourceRefs", []) if str(ref))
    for finding in findings:
        refs.extend(str(ref) for ref in finding.get("sourceRefs", []) if str(ref))
    return sorted(set(refs))
