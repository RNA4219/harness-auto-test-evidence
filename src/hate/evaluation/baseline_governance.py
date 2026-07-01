"""Baseline governance reducer for real-repo evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


EVENT_TYPES = {"proposed", "approved", "frozen", "expired", "revoked", "superseded"}


def build_real_repo_baseline_governance_report(
    data: dict[str, Any],
    report_id: str = "real-repo-baseline-governance",
    *,
    today: str | None = None,
) -> dict[str, Any]:
    """Build a baseline governance report from append-only baseline events."""
    events = [_normalize_event(event) for event in data.get("events", []) if isinstance(event, dict)]
    projection = _reduce_events(events, today=today or _today())
    findings = _findings_for_projection(projection)
    can_use = not findings and projection["status"] == "approved"
    if projection["frozen"]:
        can_use = can_use and not projection["replacement_pending"]
    return {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-baseline-governance-report",
        "report_id": report_id,
        "baseline_id": projection["baseline_id"],
        "repo_id": projection["repo_id"],
        "suite_id": projection["suite_id"],
        "baseline_run_id": projection["baseline_run_id"],
        "status": projection["status"],
        "frozen": projection["frozen"],
        "can_use_for_regression": can_use,
        "implementation_readiness_proof": projection["ownership_scope"] != "external",
        "projection": projection,
        "findings": findings,
        "summary": {
            "event_count": len(events),
            "finding_count": len(findings),
            "approved": projection["status"] == "approved",
            "expired": projection["status"] == "expired",
            "revoked": projection["status"] == "revoked",
        },
        "sourceRefs": list(data.get("sourceRefs") or ["fixtures/platform/evaluation/baseline-governance/fixture.json"]),
    }


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    event_type = str(event.get("event_type") or "")
    if event_type not in EVENT_TYPES:
        event_type = "invalid"
    return {
        "schema_version": str(event.get("schema_version") or "HATE/v1"),
        "record_type": "real-repo-baseline-event",
        "baseline_id": str(event.get("baseline_id") or ""),
        "repo_id": str(event.get("repo_id") or ""),
        "suite_id": str(event.get("suite_id") or "default"),
        "baseline_run_id": str(event.get("baseline_run_id") or ""),
        "event_type": event_type,
        "actor": str(event.get("actor") or ""),
        "reason": str(event.get("reason") or ""),
        "approved_by": str(event.get("approved_by") or ""),
        "expires_at": str(event.get("expires_at") or ""),
        "policy_hash": str(event.get("policy_hash") or ""),
        "ownership_scope": str(event.get("ownership_scope") or "owned"),
        "sourceRefs": list(event.get("sourceRefs") or []),
    }


def _reduce_events(events: list[dict[str, Any]], *, today: str) -> dict[str, Any]:
    projection = {
        "baseline_id": "",
        "repo_id": "",
        "suite_id": "default",
        "baseline_run_id": "",
        "status": "missing",
        "frozen": False,
        "replacement_pending": False,
        "actor": "",
        "reason": "",
        "approved_by": "",
        "expires_at": "",
        "policy_hash": "",
        "ownership_scope": "owned",
        "last_event_type": "",
    }
    for event in events:
        for key in ("baseline_id", "repo_id", "suite_id", "baseline_run_id", "actor", "reason", "approved_by", "expires_at", "policy_hash", "ownership_scope"):
            if event.get(key):
                projection[key] = event[key]
        event_type = event["event_type"]
        projection["last_event_type"] = event_type
        if event_type == "proposed":
            projection["status"] = "proposed"
        elif event_type == "approved":
            projection["status"] = "approved"
        elif event_type == "frozen":
            projection["frozen"] = True
        elif event_type == "expired":
            projection["status"] = "expired"
        elif event_type == "revoked":
            projection["status"] = "revoked"
        elif event_type == "superseded":
            projection["status"] = "superseded"
            projection["replacement_pending"] = False
    if projection["status"] == "approved" and projection["expires_at"] and projection["expires_at"] < today:
        projection["status"] = "expired"
    if projection["frozen"] and projection["status"] == "approved" and projection["last_event_type"] not in {"frozen", "approved", "superseded"}:
        projection["replacement_pending"] = True
    return projection


def _findings_for_projection(projection: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not projection["baseline_id"] or projection["status"] == "missing":
        findings.append(_finding("baseline_missing", "Baseline event history is missing."))
    if projection["status"] == "proposed":
        findings.append(_finding("baseline_unapproved", "Proposed baseline cannot be used for regression comparison."))
    if projection["status"] == "expired":
        findings.append(_finding("baseline_expired", "Expired baseline cannot hide regressions."))
    if projection["status"] == "revoked":
        findings.append(_finding("baseline_revoked", "Revoked baseline cannot be used for regression comparison."))
    if projection["status"] == "superseded":
        findings.append(_finding("baseline_superseded", "Superseded baseline cannot be used as current baseline."))
    if projection["frozen"] and projection["last_event_type"] == "approved":
        findings.append(_finding("baseline_frozen_replacement_missing_supersede", "Frozen baseline replacement requires superseded event and reviewer reason."))
    if projection["ownership_scope"] == "external":
        findings.append(_finding("baseline_external_not_readiness_proof", "External repo baseline cannot prove HATE implementation readiness."))
    return findings


def _finding(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": message,
    }


def _today() -> str:
    return datetime.now(UTC).date().isoformat()
