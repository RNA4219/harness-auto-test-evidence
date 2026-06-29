"""HATE SCIM Connector - dry-run provisioning diff.

The connector previews user/group provisioning actions without external side
effects. Destructive actions are denied in dry-run and connector failures remain
non-gating for core HATE readiness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


DESTRUCTIVE_ACTIONS = {"delete_user", "delete_group", "purge_user", "purge_group"}


@dataclass
class SCIMDiff:
    """SCIM desired/current state diff input."""

    diff_id: str
    current_users: list[dict[str, Any]] = field(default_factory=list)
    desired_users: list[dict[str, Any]] = field(default_factory=list)
    current_groups: list[dict[str, Any]] = field(default_factory=list)
    desired_groups: list[dict[str, Any]] = field(default_factory=list)
    sourceRefs: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "scim_diff",
            "diff_id": self.diff_id,
            "current_users": self.current_users,
            "desired_users": self.desired_users,
            "current_groups": self.current_groups,
            "desired_groups": self.desired_groups,
            "sourceRefs": self.sourceRefs,
            "timestamp": self.timestamp,
        }


@dataclass
class SCIMDiffResult:
    """Dry-run SCIM provisioning preview."""

    diff_id: str
    status: str
    enabled: bool = True
    readiness_effect: str = "pass"
    simulated_actions: list[dict[str, Any]] = field(default_factory=list)
    denied_actions: list[dict[str, Any]] = field(default_factory=list)
    redacted_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    manual_review_required: bool = False
    sourceRefs: list[str] = field(default_factory=list)
    audit_event_refs: list[str] = field(default_factory=list)
    upstream_report_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "scim_diff_result",
            "diff_id": self.diff_id,
            "status": self.status,
            "enabled": self.enabled,
            "readiness_effect": self.readiness_effect,
            "simulated_actions": self.simulated_actions,
            "denied_actions": self.denied_actions,
            "redacted_diagnostics": self.redacted_diagnostics,
            "manual_review_required": self.manual_review_required,
            "sourceRefs": self.sourceRefs,
            "audit_event_refs": self.audit_event_refs,
            "upstream_report_id": self.upstream_report_id,
        }


def build_scim_diff(
    enterprise_control_report: dict[str, Any],
    connector_config: dict[str, Any] | None = None,
) -> SCIMDiffResult:
    """Build a dry-run SCIM provisioning diff from enterprise report data."""
    connector_config = connector_config or {}
    scim_data = enterprise_control_report.get("scim", {})
    enabled = bool(connector_config.get("enabled", True))
    diff_id = scim_data.get("diff_id", "")

    if not enabled:
        return SCIMDiffResult(
            diff_id=diff_id,
            status="disabled",
            enabled=False,
            readiness_effect="pass",
            redacted_diagnostics=[{
                "code": "connector_disabled",
                "message": "SCIM connector is disabled; dry-run is non-gating.",
                "severity": "info",
            }],
            sourceRefs=enterprise_control_report.get("sourceRefs", []),
            audit_event_refs=enterprise_control_report.get("audit_event_refs", []),
            upstream_report_id=enterprise_control_report.get("schema_version", "HATE/v1"),
        )

    simulated_actions: list[dict[str, Any]] = []
    denied_actions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    if connector_config.get("live_network_attempt"):
        denied_actions.append({
            "action": "live_network_call",
            "reason": "SCIM dry-run cannot perform live network calls.",
            "sourceRef": connector_config.get("sourceRef", "scim_config"),
        })
    if _contains_sensitive_text(str(connector_config)):
        diagnostics.append({
            "code": "token_redacted",
            "message": "Connector token was redacted from diagnostics.",
            "severity": "info",
        })

    current_users = {item.get("id") or item.get("userName"): item for item in scim_data.get("current_users", [])}
    desired_users = {item.get("id") or item.get("userName"): item for item in scim_data.get("desired_users", [])}
    current_groups = {item.get("id") or item.get("displayName"): item for item in scim_data.get("current_groups", [])}
    desired_groups = {item.get("id") or item.get("displayName"): item for item in scim_data.get("desired_groups", [])}

    for user_id, desired in desired_users.items():
        if user_id not in current_users:
            simulated_actions.append(_action("create_user", user_id, desired))
        elif desired != current_users[user_id]:
            simulated_actions.append(_action("update_user", user_id, desired))

    for group_id, desired in desired_groups.items():
        if group_id not in current_groups:
            simulated_actions.append(_action("create_group", group_id, desired))
        elif desired != current_groups[group_id]:
            simulated_actions.append(_action("update_group", group_id, desired))

    for action in scim_data.get("requested_actions", []):
        action_name = action.get("action", "")
        if action_name in DESTRUCTIVE_ACTIONS:
            denied_actions.append({
                "action": action_name,
                "target": action.get("target"),
                "reason": "Destructive SCIM action is denied in dry-run.",
                "sourceRef": action.get("sourceRef", ""),
            })
        else:
            simulated_actions.append({
                "action": action_name,
                "target": action.get("target"),
                "sourceRef": action.get("sourceRef", ""),
            })

    status = "preview"
    readiness_effect = "pass"
    manual_review_required = False
    if denied_actions:
        status = "denied_action"
        readiness_effect = "hold"
        manual_review_required = True
    elif diagnostics:
        status = "preview_with_diagnostics"

    return SCIMDiffResult(
        diff_id=diff_id,
        status=status,
        enabled=True,
        readiness_effect=readiness_effect,
        simulated_actions=simulated_actions,
        denied_actions=denied_actions,
        redacted_diagnostics=_redact_diagnostics(diagnostics),
        manual_review_required=manual_review_required,
        sourceRefs=enterprise_control_report.get("sourceRefs", []),
        audit_event_refs=enterprise_control_report.get("audit_event_refs", []),
        upstream_report_id=enterprise_control_report.get("schema_version", "HATE/v1"),
    )


def _action(action: str, target: str | None, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "target": target,
        "sourceRef": record.get("sourceRef", ""),
    }


def _contains_sensitive_text(value: str) -> bool:
    return bool(re.search(r"(?i)(token|bearer|client_secret|api_key|password)", value))


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
