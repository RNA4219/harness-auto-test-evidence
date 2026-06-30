"""Notification delivery evaluation for HATE-GAP-030."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NotificationFinding:
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


def evaluate_notification_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_notification_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "notification-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_notification_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "notification-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["notification"])
    notification_config = _normalize_notification_config(input_data.get("notification_config", input_data))
    findings = _findings_for(notification_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "notification-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "notification_config": notification_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "event_taxonomy_defined": notification_config["event_taxonomy_defined"],
            "signing_enabled": notification_config["signing_enabled"],
            "retry_schedule_defined": notification_config["retry_schedule_defined"],
            "dead_letter_state_defined": notification_config["dead_letter_state_defined"],
            "tenant_scoped_delivery": notification_config["tenant_scoped_delivery"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_notification_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    return {
        "event_taxonomy_defined": bool(config.get("event_taxonomy_defined", False)),
        "signing_enabled": bool(config.get("signing_enabled", False)),
        "retry_schedule_defined": bool(config.get("retry_schedule_defined", False)),
        "dedupe_enabled": bool(config.get("dedupe_enabled", False)),
        "dead_letter_state_defined": bool(config.get("dead_letter_state_defined", False)),
        "tenant_scoped_delivery": bool(config.get("tenant_scoped_delivery", False)),
        "webhook_url": str(config.get("webhook_url") or ""),
        "signature_verified": bool(config.get("signature_verified", False)),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[NotificationFinding]:
    findings: list[NotificationFinding] = []
    if not config["event_taxonomy_defined"]:
        findings.append(_finding(
            "notification_event_taxonomy_missing",
            "Notification delivery requires event taxonomy definition.",
            source_ref,
        ))
    if not config["signing_enabled"]:
        findings.append(_finding(
            "notification_unsigned_webhook_denied",
            "Unsigned webhook delivery is denied for security.",
            source_ref,
        ))
    if not config["retry_schedule_defined"]:
        findings.append(_finding(
            "notification_retry_schedule_missing",
            "Notification delivery requires retry schedule.",
            source_ref,
        ))
    if not config["dedupe_enabled"]:
        findings.append(_finding(
            "notification_dedupe_missing",
            "Notification delivery requires dedupe support.",
            source_ref,
        ))
    if not config["dead_letter_state_defined"]:
        findings.append(_finding(
            "notification_dead_letter_missing",
            "Notification delivery requires dead-letter state handling.",
            source_ref,
        ))
    if not config["tenant_scoped_delivery"]:
        findings.append(_finding(
            "notification_tenant_scope_missing",
            "Notification delivery requires tenant scoped delivery.",
            source_ref,
        ))
    if config["webhook_url"] and not config["signature_verified"]:
        findings.append(_finding(
            "notification_webhook_signature_invalid",
            "Webhook signature verification failed.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> NotificationFinding:
    return NotificationFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )