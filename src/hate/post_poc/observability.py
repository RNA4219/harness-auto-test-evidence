from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


SECRET_MARKERS = ("secret=", "token=", "api_key=", "password=", "BEGIN PRIVATE KEY")


@dataclass(frozen=True)
class ObservabilityFinding:
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


def evaluate_observability_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    report = build_observability_report(
        payload.get("input", {}),
        report_id=str(payload.get("fixture_id") or "observability-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_observability_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "observability-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["observability"])
    telemetry = [_normalize_telemetry(item) for item in input_data.get("telemetry", [])]
    slo = _normalize_slo(input_data.get("slo", {}), telemetry)
    incident = _normalize_incident(input_data.get("incident", {}))
    support_pack = _normalize_support_pack(input_data.get("support_pack", {}), telemetry, incident)
    findings = _findings_for(telemetry, slo, incident, support_pack, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "observability-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "runtime_telemetry_events": telemetry,
        "slo_burn_rate_report": slo,
        "incident_lifecycle_record": incident,
        "post_incident_evidence_pack": support_pack,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "telemetry_event_count": len(telemetry),
            "alert_status": slo["alert_status"],
            "incident_state": incident["incident_state"],
            "owner": incident["owner"],
            "support_bundle_safe": support_pack["support_bundle_safe"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_incident_response_packet(
    input_data: dict[str, Any],
    *,
    packet_id: str = "incident-response-packet",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["incident-response-packet"])
    report = (
        input_data
        if input_data.get("record_type") == "observability-report"
        else build_observability_report(input_data, report_id=f"{packet_id}:observability", source_refs=source_refs)
    )
    slo = dict(report.get("slo_burn_rate_report", {}))
    incident = dict(report.get("incident_lifecycle_record", {}))
    support_pack = dict(report.get("post_incident_evidence_pack", {}))
    actions = _incident_actions_for(slo, incident, support_pack)
    findings = _incident_packet_findings(report, actions, source_refs[0])
    packet = {
        "schema_version": "HATE/v1",
        "record_type": "incident-response-packet",
        "packet_id": packet_id,
        **productization_envelope(input_data, report_id=packet_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "incident_id": incident.get("incident_id", ""),
        "correlation_id": slo.get("correlation_id", ""),
        "owner": incident.get("owner", ""),
        "severity": incident.get("severity", ""),
        "actions": actions,
        "support_pack": support_pack,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "action_count": len(actions),
            "blocked_action_count": sum(1 for action in actions if action["status"] == "blocked"),
            "finding_count": len(findings),
            "support_bundle_safe": support_pack.get("support_bundle_safe", False),
            "ready_for_response": not findings and all(action["status"] == "ready" for action in actions),
        },
        "sourceRefs": sorted(set(source_refs + list(report.get("sourceRefs", [])))),
    }
    return apply_productization_contract_tree(packet, source_refs=source_refs)


def write_incident_response_packet(packet: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    apply_productization_contract_tree(packet, source_refs=list(packet.get("sourceRefs", [])))
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "incident-response-packet-artifact",
        **productization_envelope(packet, report_id=f"{packet.get('packet_id') or 'incident-response-packet'}:artifact", source_refs=list(packet.get("sourceRefs", []))),
        "readiness_effect": str(packet.get("readiness_effect") or "none"),
        "artifact_path": str(path),
        "action_count": len(packet.get("actions", [])),
        "sourceRefs": list(packet.get("sourceRefs", [])),
    }


def _incident_actions_for(
    slo: dict[str, Any],
    incident: dict[str, Any],
    support_pack: dict[str, Any],
) -> list[dict[str, Any]]:
    active = incident.get("incident_state") not in {"none", ""}
    return [
        _incident_action("correlate_evidence", bool(slo.get("correlation_id")), "Correlate telemetry, SLO, incident, and support evidence."),
        _incident_action("route_alert", bool(slo.get("alert_route_ref")) or slo.get("alert_status") == "ok", "Route firing/breached SLO to an alert destination."),
        _incident_action("assign_owner", bool(incident.get("owner")) or not active, "Assign owner for active incident response."),
        _incident_action("capture_timeline", bool(incident.get("timeline_refs")) or not active, "Capture incident timeline references."),
        _incident_action("capture_decision", bool(incident.get("decision_ref")) or not active, "Capture incident decision reference."),
        _incident_action("export_safe_support_pack", bool(support_pack.get("support_bundle_safe") and support_pack.get("redaction_report_ref")), "Export only redacted, safe support bundle."),
        _incident_action("post_incident_review", bool(incident.get("post_incident_review_ref")) or incident.get("incident_state") not in {"closed", "resolved"}, "Closed/resolved incidents require post-incident review."),
    ]


def _incident_action(action_id: str, ready: bool, description: str) -> dict[str, Any]:
    return {
        "record_type": "incident-response-action",
        "action_id": action_id,
        "status": "ready" if ready else "blocked",
        "description": description,
        "required": True,
    }


def _incident_packet_findings(
    report: dict[str, Any],
    actions: list[dict[str, Any]],
    source_ref: str,
) -> list[ObservabilityFinding]:
    findings = [
        _finding("incident_response_action_blocked", f"Incident response action blocked: {action['action_id']}.", source_ref)
        for action in actions
        if action["status"] == "blocked"
    ]
    if report.get("findings"):
        findings.append(_finding("incident_response_blocked_by_observability_findings", "Incident response packet cannot be ready while observability findings remain.", source_ref))
    return findings


def _normalize_telemetry(raw: dict[str, Any]) -> dict[str, Any]:
    event = dict(raw or {})
    return {
        "record_type": "runtime-telemetry-event",
        "signal": str(event.get("signal") or "metrics"),
        "correlation_id": str(event.get("correlation_id") or ""),
        "run_id": str(event.get("run_id") or ""),
        "tenant_id": str(event.get("tenant_id") or ""),
        "service_name": str(event.get("service_name") or ""),
        "metric_name": str(event.get("metric_name") or ""),
        "log_message": str(event.get("log_message") or ""),
        "trace_id": str(event.get("trace_id") or ""),
        "alert_route_ref": str(event.get("alert_route_ref") or ""),
        "redaction_report_ref": str(event.get("redaction_report_ref") or ""),
    }


def _normalize_slo(raw: dict[str, Any], telemetry: list[dict[str, Any]]) -> dict[str, Any]:
    slo = dict(raw or {})
    sample = telemetry[0] if telemetry else {}
    return {
        "record_type": "slo-burn-rate-report",
        "correlation_id": str(slo.get("correlation_id") or sample.get("correlation_id") or ""),
        "run_id": str(slo.get("run_id") or sample.get("run_id") or ""),
        "tenant_id": str(slo.get("tenant_id") or sample.get("tenant_id") or ""),
        "service_name": str(slo.get("service_name") or sample.get("service_name") or ""),
        "metric_name": str(slo.get("metric_name") or sample.get("metric_name") or ""),
        "slo_id": str(slo.get("slo_id") or ""),
        "burn_rate": _float(slo.get("burn_rate"), 0.0),
        "alert_status": str(slo.get("alert_status") or "ok"),
        "alert_route_ref": str(slo.get("alert_route_ref") or sample.get("alert_route_ref") or ""),
    }


def _normalize_incident(raw: dict[str, Any]) -> dict[str, Any]:
    incident = dict(raw or {})
    return {
        "record_type": "incident-lifecycle-record",
        "incident_id": str(incident.get("incident_id") or ""),
        "incident_state": str(incident.get("incident_state") or "none"),
        "owner": str(incident.get("owner") or ""),
        "severity": str(incident.get("severity") or ""),
        "timeline_refs": [str(item) for item in incident.get("timeline_refs", [])],
        "decision_ref": str(incident.get("decision_ref") or ""),
        "post_incident_review_ref": str(incident.get("post_incident_review_ref") or ""),
    }


def _normalize_support_pack(
    raw: dict[str, Any],
    telemetry: list[dict[str, Any]],
    incident: dict[str, Any],
) -> dict[str, Any]:
    pack = dict(raw or {})
    return {
        "record_type": "post-incident-evidence-pack",
        "support_pack_id": str(pack.get("support_pack_id") or "support-pack"),
        "incident_id": str(pack.get("incident_id") or incident["incident_id"]),
        "evidence_refs": [str(item) for item in pack.get("evidence_refs", [])],
        "support_bundle_safe": bool(pack.get("support_bundle_safe", True)),
        "redaction_report_ref": str(pack.get("redaction_report_ref") or _first_redaction(telemetry)),
    }


def _findings_for(
    telemetry: list[dict[str, Any]],
    slo: dict[str, Any],
    incident: dict[str, Any],
    support_pack: dict[str, Any],
    source_ref: str,
) -> list[ObservabilityFinding]:
    findings: list[ObservabilityFinding] = []
    if not telemetry or any(not event["correlation_id"] for event in telemetry) or not slo["correlation_id"]:
        findings.append(_finding("observability_correlation_id_missing", "Telemetry, SLO, and incident evidence require correlation_id.", source_ref))
    if any(_contains_secret(event["log_message"]) for event in telemetry) or not support_pack["support_bundle_safe"]:
        findings.append(_finding("observability_raw_secret_log", "Raw secret logs are denied before support bundle export.", source_ref))
    if slo["alert_status"] in {"firing", "breached"} and not slo["alert_route_ref"]:
        findings.append(_finding("observability_alert_route_missing", "SLO breach requires an alert route.", source_ref))
    if slo["burn_rate"] > 1.0 or slo["alert_status"] in {"firing", "breached"}:
        findings.append(_finding("observability_slo_breach", "SLO burn-rate breach is active.", source_ref))
    if incident["incident_state"] not in {"none", "closed", "resolved"} and not incident["owner"]:
        findings.append(_finding("incident_owner_missing", "Active incidents require an owner.", source_ref))
    if incident["incident_state"] in {"closed", "resolved"} and not incident["post_incident_review_ref"]:
        findings.append(_finding("incident_review_missing", "Closed incidents require a post-incident review reference.", source_ref))
    if incident["incident_state"] not in {"none"} and (not incident["timeline_refs"] or not incident["decision_ref"]):
        findings.append(_finding("incident_review_missing", "Incident evidence requires timeline and decision references.", source_ref))
    if support_pack["evidence_refs"] and not support_pack["redaction_report_ref"]:
        findings.append(_finding("observability_raw_secret_log", "Support evidence pack requires redaction report.", source_ref))
    return findings


def _first_redaction(telemetry: list[dict[str, Any]]) -> str:
    for event in telemetry:
        if event["redaction_report_ref"]:
            return event["redaction_report_ref"]
    return ""


def _contains_secret(value: str) -> bool:
    lower = value.lower()
    return any(marker.lower() in lower for marker in SECRET_MARKERS)


def _finding(code: str, message: str, source_ref: str) -> ObservabilityFinding:
    return ObservabilityFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
