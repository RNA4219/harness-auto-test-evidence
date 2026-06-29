"""HATE Ops Connectors - dry-run SIEM/warehouse/ticketing projections.

Enterprise connectors preview export/sync actions without external side effects.
Connector failures remain non-gating for core HATE readiness and must not override
precheck/product verdicts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


DESTRUCTIVE_EXPORT_ACTIONS = {"purge_events", "delete_all_metrics", "reset_tickets", "export_raw_artifact"}
UNSAFE_EXPORT_FIELDS = {"raw_artifact_content", "raw_artifact_path", "quarantined_artifact", "unsafe_artifact"}


@dataclass
class OpsConnectorResult:
    """Dry-run ops connector preview."""

    connector_id: str
    mode: str
    status: str
    enabled: bool = True
    readiness_effect: str = "pass"
    simulated_actions: list[dict[str, Any]] = field(default_factory=list)
    denied_actions: list[dict[str, Any]] = field(default_factory=list)
    redacted_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    payload_kind: str = ""
    provider: str = ""
    configuration_status: str = "configured"
    entitlement_status: str = "available"
    audit_event_refs: list[str] = field(default_factory=list)
    sourceRefs: list[str] = field(default_factory=list)
    upstream_report_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "ops_connector_result",
            "connector_id": self.connector_id,
            "mode": self.mode,
            "status": self.status,
            "enabled": self.enabled,
            "readiness_effect": self.readiness_effect,
            "simulated_actions": self.simulated_actions,
            "denied_actions": self.denied_actions,
            "redacted_diagnostics": self.redacted_diagnostics,
            "payload_kind": self.payload_kind,
            "provider": self.provider,
            "configuration_status": self.configuration_status,
            "entitlement_status": self.entitlement_status,
            "audit_event_refs": self.audit_event_refs,
            "sourceRefs": self.sourceRefs,
            "upstream_report_id": self.upstream_report_id,
        }


def build_ops_connector(
    enterprise_control_report: dict[str, Any],
    connector_type: str,
    connector_config: dict[str, Any] | None = None,
) -> OpsConnectorResult:
    """Build a dry-run ops connector projection from enterprise report data.

    Args:
        enterprise_control_report: Upstream enterprise control report
        connector_type: One of "siem", "warehouse", "ticketing"
        connector_config: Optional connector configuration

    Returns:
        OpsConnectorResult with dry-run preview
    """
    connector_config = connector_config or {}
    enabled = bool(connector_config.get("enabled", True))

    # Map connector_type to report key
    report_key = {
        "siem": "siem_export",
        "warehouse": "warehouse_export",
        "ticketing": "ticketing_sync",
        "support": "support_bundle",
    }.get(connector_type)

    if not report_key:
        return OpsConnectorResult(
            connector_id="unknown",
            mode=connector_type,
            status="invalid_config",
            enabled=False,
            readiness_effect="hold",
            redacted_diagnostics=[{
                "code": "invalid_connector_type",
                "message": f"Unknown connector type: {connector_type}",
                "severity": "error",
            }],
            sourceRefs=enterprise_control_report.get("sourceRefs", []),
        )

    connector_data = enterprise_control_report.get(report_key, {})
    connector_id = connector_data.get("connector_id", f"{connector_type}-default")
    provider = connector_data.get("provider", connector_config.get("provider", ""))
    payload_kind = connector_data.get("payload_kind", "")

    if not enabled:
        return OpsConnectorResult(
            connector_id=connector_id,
            mode=connector_type,
            status="disabled",
            enabled=False,
            readiness_effect="pass",
            payload_kind=payload_kind,
            provider=provider,
            configuration_status="disabled",
            redacted_diagnostics=[{
                "code": "connector_disabled",
                "message": f"{connector_type.upper()} connector is disabled; dry-run is non-gating.",
                "severity": "info",
            }],
            sourceRefs=enterprise_control_report.get("sourceRefs", []),
            upstream_report_id=enterprise_control_report.get("schema_version", "HATE/v1"),
        )

    simulated_actions: list[dict[str, Any]] = []
    denied_actions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    # Check for live network attempts
    if connector_config.get("live_network_attempt"):
        denied_actions.append({
            "action": "live_network_call",
            "reason": f"{connector_type.upper()} dry-run cannot perform live network calls.",
            "sourceRef": connector_config.get("sourceRef", f"{connector_type}_config"),
        })

    # Check for sensitive data
    if _contains_sensitive_text(str(connector_config) + str(connector_data)):
        diagnostics.append({
            "code": "token_redacted",
            "message": "Connector token was redacted from diagnostics.",
            "severity": "info",
        })

    if _contains_unsafe_export(connector_data):
        denied_actions.append({
            "action": "unsafe_artifact_export",
            "target": connector_data.get("connector_id", connector_id),
            "reason": "Unsafe/quarantined/raw artifact content is excluded from connector exports.",
            "sourceRef": connector_data.get("sourceRef", ""),
        })
        diagnostics.append({
            "code": "unsafe_artifact_export_blocked",
            "message": "Unsafe artifact export was blocked before connector payload generation.",
            "severity": "critical",
        })

    # Check for destructive actions
    for action in connector_data.get("requested_actions", []):
        action_name = action.get("action", "")
        if action_name in DESTRUCTIVE_EXPORT_ACTIONS:
            denied_actions.append({
                "action": action_name,
                "target": action.get("target"),
                "reason": f"Destructive {connector_type} action is denied in dry-run.",
                "sourceRef": action.get("sourceRef", ""),
            })
        else:
            simulated_actions.append({
                "action": action_name,
                "target": action.get("target"),
                "sourceRef": action.get("sourceRef", ""),
            })

    # Handle connector errors
    if connector_data.get("error"):
        diagnostics.append({
            "code": "connector_error",
            "message": f"{connector_type.upper()} connector error: {connector_data['error']}",
            "severity": "warning",
            "non_gating": True,
        })

    # Build preview action for payload
    if payload_kind and not connector_data.get("error"):
        preview_data = connector_data.get("events_preview") or \
                       connector_data.get("metrics_preview") or \
                       connector_data.get("tickets_preview") or \
                       connector_data.get("support_bundle_preview")
        if preview_data:
            simulated_actions.append({
                "action": f"export_{payload_kind}",
                "preview_count": len(preview_data),
                "sourceRef": connector_data.get("sourceRef", ""),
            })

    # Determine status and readiness effect
    status = "preview"
    readiness_effect = "pass"

    if connector_data.get("error"):
        status = "failure_preview"
        readiness_effect = "non_gating_failure"
    elif any(item.get("action") == "unsafe_artifact_export" for item in denied_actions):
        status = "unsafe_export_blocked"
        readiness_effect = "hard_dq"
    elif denied_actions:
        status = "denied_action"
        readiness_effect = "hold"
    elif diagnostics:
        status = "preview_with_diagnostics"

    return OpsConnectorResult(
        connector_id=connector_id,
        mode=connector_type,
        status=status,
        enabled=True,
        readiness_effect=readiness_effect,
        simulated_actions=simulated_actions,
        denied_actions=denied_actions,
        redacted_diagnostics=_redact_diagnostics(diagnostics),
        payload_kind=payload_kind,
        provider=provider,
        configuration_status="configured",
        entitlement_status="available",
        audit_event_refs=enterprise_control_report.get("audit_event_refs", []),
        sourceRefs=enterprise_control_report.get("sourceRefs", []) + [connector_data.get("sourceRef", "")],
        upstream_report_id=enterprise_control_report.get("schema_version", "HATE/v1"),
    )


def build_ops_connector_report(
    enterprise_control_report: dict[str, Any],
    connector_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build combined ops connector report for all enterprise connectors.

    Returns a report with all three ops connectors (siem, warehouse, ticketing)
    with non-gating failure policy enforcement.
    """
    connector_config = connector_config or {}

    siem_result = build_ops_connector(enterprise_control_report, "siem", connector_config.get("siem"))
    warehouse_result = build_ops_connector(enterprise_control_report, "warehouse", connector_config.get("warehouse"))
    ticketing_result = build_ops_connector(enterprise_control_report, "ticketing", connector_config.get("ticketing"))

    connectors = [
        siem_result.to_dict(),
        warehouse_result.to_dict(),
        ticketing_result.to_dict(),
    ]

    non_gating_count = sum(
        1 for c in connectors
        if c.get("readiness_effect") in ("pass", "non_gating_failure")
    )

    return {
        "schema_version": "HATE/v1",
        "record_type": "ops_connector_report",
        "run_id": enterprise_control_report.get("report_id", ""),
        "mode": "dry_run_contract_fixture",
        "connectors": connectors,
        "summary": {
            "connector_count": 3,
            "enabled_count": sum(1 for c in connectors if c.get("enabled")),
            "non_gating_count": non_gating_count,
            "failure_count": sum(1 for c in connectors if c.get("status") == "failure_preview"),
        },
        "safety": {
            "contains_connector_token": False,
            "live_network_required": False,
            "payload_safe": True,
        },
        "boundaries": {
            "canonical_bundle_mutated": False,
            "precheck_decision_override": False,
            "qeg_verdict_override": False,
            "release_gate_override": False,
        },
        "sourceRefs": enterprise_control_report.get("sourceRefs", []),
    }


def _contains_sensitive_text(value: str) -> bool:
    return bool(re.search(r"(?i)(token|bearer|client_secret|api_key|password)", value))


def _contains_unsafe_export(connector_data: dict[str, Any]) -> bool:
    if any(field in connector_data for field in UNSAFE_EXPORT_FIELDS):
        return True
    serialized = str(connector_data)
    return bool(re.search(r"(?i)(quarantined|raw_artifact|unsafe_artifact|private_key|secret_value)", serialized))


def _redact_diagnostics(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    redacted = []
    for item in diagnostics:
        clean = {}
        for key, value in item.items():
            if isinstance(value, str):
                clean[key] = re.sub(
                    r"(?i)(token|bearer|client_secret|api_key|password)[^,\s'}]*",
                    "[REDACTED]",
                    value,
                )
            else:
                clean[key] = value
        redacted.append(clean)
    return redacted
