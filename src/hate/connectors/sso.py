"""HATE SSO Connector - Dry-run SSO mapping projection.

SSO mapping projects groups/roles/claims without live network calls.
Missing mapping or unsupported claim produces hold/manual review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class SSOMapping:
    """SSO group/role/claim mapping.

    Dry-run projection - no live network calls.
    """

    mapping_id: str
    provider: str
    groups: list[dict[str, Any]] = field(default_factory=list)
    roles: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    sourceRefs: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to SSO mapping dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "sso_mapping",
            "mapping_id": self.mapping_id,
            "provider": self.provider,
            "groups": self.groups,
            "roles": self.roles,
            "claims": self.claims,
            "sourceRefs": self.sourceRefs,
            "timestamp": self.timestamp,
        }


@dataclass
class SSOMappingResult:
    """Result of SSO mapping projection.

    Holds status and any missing/unsupported claims.
    """

    mapping_id: str
    status: str  # "mapped", "missing_claim", "unsupported_claim"
    mapped_groups: list[str] = field(default_factory=list)
    mapped_roles: list[str] = field(default_factory=list)
    mapped_claims: list[str] = field(default_factory=list)
    missing_claims: list[dict[str, Any]] = field(default_factory=list)
    unsupported_claims: list[dict[str, Any]] = field(default_factory=list)
    manual_review_required: bool = False
    readiness_effect: str = "pass"
    configuration_status: str = "valid"
    enabled: bool = True
    simulated_actions: list[dict[str, Any]] = field(default_factory=list)
    denied_actions: list[dict[str, Any]] = field(default_factory=list)
    redacted_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    audit_event_refs: list[str] = field(default_factory=list)
    hold_reason: str = ""
    sourceRefs: list[str] = field(default_factory=list)
    upstream_report_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to result dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "sso_mapping_result",
            "mapping_id": self.mapping_id,
            "status": self.status,
            "mapped_groups": self.mapped_groups,
            "mapped_roles": self.mapped_roles,
            "mapped_claims": self.mapped_claims,
            "missing_claims": self.missing_claims,
            "unsupported_claims": self.unsupported_claims,
            "manual_review_required": self.manual_review_required,
            "readiness_effect": self.readiness_effect,
            "configuration_status": self.configuration_status,
            "enabled": self.enabled,
            "simulated_actions": self.simulated_actions,
            "denied_actions": self.denied_actions,
            "redacted_diagnostics": self.redacted_diagnostics,
            "audit_event_refs": self.audit_event_refs,
            "hold_reason": self.hold_reason,
            "sourceRefs": self.sourceRefs,
            "upstream_report_id": self.upstream_report_id,
        }


def build_sso_mapping(
    enterprise_control_report: dict[str, Any],
    mapping_config: dict[str, Any],
) -> SSOMappingResult:
    """Build SSO mapping result from enterprise control report.

    Dry-run projection - no live network calls.
    Missing mapping or unsupported claim produces hold/manual review.
    """
    sso_data = enterprise_control_report.get("sso_mapping", {})
    enabled = bool(mapping_config.get("enabled", True))
    config_claims = set(mapping_config.get("supported_claims", []))
    config_groups = set(mapping_config.get("supported_groups", []))
    config_roles = set(mapping_config.get("supported_roles", []))

    diagnostics: list[dict[str, Any]] = []
    denied_actions: list[dict[str, Any]] = []
    simulated_actions: list[dict[str, Any]] = []

    if not enabled:
        return SSOMappingResult(
            mapping_id=sso_data.get("mapping_id", ""),
            status="disabled",
            manual_review_required=False,
            readiness_effect="pass",
            configuration_status="disabled",
            enabled=False,
            redacted_diagnostics=[{
                "code": "connector_disabled",
                "message": "SSO connector is disabled; dry-run is non-gating.",
                "severity": "info",
            }],
            sourceRefs=enterprise_control_report.get("sourceRefs", []),
            upstream_report_id=enterprise_control_report.get("schema_version", "HATE/v1"),
        )

    issuer = mapping_config.get("issuer", "")
    audience = mapping_config.get("audience", "")
    if not _valid_issuer(issuer):
        diagnostics.append({
            "code": "invalid_issuer",
            "message": "SSO issuer must be an https URL.",
            "severity": "hold",
        })
    if not audience:
        diagnostics.append({
            "code": "missing_audience",
            "message": "SSO audience is required for dry-run validation.",
            "severity": "hold",
        })
    if mapping_config.get("live_network_attempt"):
        denied_actions.append({
            "action": "live_network_validation",
            "reason": "SSO connector dry-run cannot perform live network calls.",
            "sourceRef": mapping_config.get("sourceRef", "sso_config"),
        })
    if _contains_secret(str(mapping_config)):
        diagnostics.append({
            "code": "secret_redacted",
            "message": "Connector secret/token was redacted from diagnostics.",
            "severity": "info",
        })

    # Extract claims, groups, roles from report
    claims = sso_data.get("claims", [])
    groups = sso_data.get("groups", [])
    roles = sso_data.get("roles", [])

    mapped_claims = []
    mapped_groups = []
    mapped_roles = []
    missing_claims = []
    unsupported_claims = []

    # Process claims
    for claim in claims:
        claim_name = claim.get("name", "")
        if claim_name in config_claims:
            mapped_claims.append(claim_name)
            simulated_actions.append({
                "action": "map_claim",
                "claim": claim_name,
                "sourceRef": claim.get("sourceRef", ""),
            })
        else:
            unsupported_claims.append({
                "claim_name": claim_name,
                "reason": f"Claim '{claim_name}' not in supported claims config",
                "sourceRef": claim.get("sourceRef", ""),
            })

    # Check for missing required claims
    required_claims = mapping_config.get("required_claims", [])
    for required in required_claims:
        if required not in mapped_claims:
            missing_claims.append({
                "claim_name": required,
                "reason": f"Required claim '{required}' not present in SSO data",
                "sourceRef": sso_data.get("sourceRef", ""),
            })

    # Process groups
    for group in groups:
        group_name = group.get("name", "")
        if group_name in config_groups:
            mapped_groups.append(group_name)
            simulated_actions.append({
                "action": "map_group",
                "group": group_name,
                "sourceRef": group.get("sourceRef", ""),
            })
        else:
            # Groups not in config are informational, not blocking
            pass

    # Process roles
    for role in roles:
        role_name = role.get("name", "")
        if role_name in config_roles:
            mapped_roles.append(role_name)
            simulated_actions.append({
                "action": "map_role",
                "role": role_name,
                "sourceRef": role.get("sourceRef", ""),
            })
        else:
            # Roles not in config are informational
            pass

    # Determine status
    status = "mapped"
    manual_review_required = False
    hold_reason = ""

    configuration_status = "valid"
    readiness_effect = "pass"

    if diagnostics or denied_actions:
        status = "invalid_config"
        manual_review_required = True
        readiness_effect = "hold"
        configuration_status = "invalid"
        hold_reason = "SSO connector dry-run configuration requires review"

    if missing_claims:
        status = "missing_claim"
        manual_review_required = True
        readiness_effect = "hold"
        configuration_status = "incomplete"
        hold_reason = f"Missing required claims: {[c['claim_name'] for c in missing_claims]}"

    if unsupported_claims:
        status = "unsupported_claim"
        manual_review_required = True
        readiness_effect = "hold"
        configuration_status = "unsupported"
        hold_reason = f"Unsupported claims: {[c['claim_name'] for c in unsupported_claims]}"

    return SSOMappingResult(
        mapping_id=sso_data.get("mapping_id", ""),
        status=status,
        mapped_groups=mapped_groups,
        mapped_roles=mapped_roles,
        mapped_claims=mapped_claims,
        missing_claims=missing_claims,
        unsupported_claims=unsupported_claims,
        manual_review_required=manual_review_required,
        readiness_effect=readiness_effect,
        configuration_status=configuration_status,
        enabled=enabled,
        simulated_actions=simulated_actions,
        denied_actions=denied_actions,
        redacted_diagnostics=_redact_diagnostics(diagnostics),
        audit_event_refs=enterprise_control_report.get("audit_event_refs", []),
        hold_reason=hold_reason,
        sourceRefs=enterprise_control_report.get("sourceRefs", []),
        upstream_report_id=enterprise_control_report.get("schema_version", "HATE/v1"),
    )


def _valid_issuer(value: str) -> bool:
    return bool(value and value.startswith("https://") and " " not in value)


def _contains_secret(value: str) -> bool:
    return bool(re.search(r"(?i)(secret|token|bearer|client_secret|api_key)", value))


def _redact_diagnostics(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    redacted = []
    for item in diagnostics:
        clean = {}
        for key, value in item.items():
            if isinstance(value, str):
                clean[key] = re.sub(
                    r"(?i)(secret|token|bearer|client_secret|api_key)[^,\s'}]*",
                    "[REDACTED]",
                    value,
                )
            else:
                clean[key] = value
        redacted.append(clean)
    return redacted
