from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "HATE/v1"


def build_identity_connector_report(run_id: str, rbac_matrix: dict[str, Any]) -> dict[str, Any]:
    connectors = [
        _identity_connector("sso", "SAML/OIDC SSO", ["admin", "maintainer", "developer", "auditor", "viewer"]),
        _identity_connector("scim", "SCIM provisioning", ["admin", "maintainer", "developer", "auditor", "viewer", "service_account"]),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "identity_connector_report",
        "run_id": run_id,
        "mode": "dry_run_contract_fixture",
        "connectors": connectors,
        "dry_run_results": [
            {
                "connector_id": item["connector_id"],
                "status": "skipped_not_configured",
                "non_gating": True,
                "stable_warning_code": "HATE-EXP-001",
                "credentials_required_for_live": True,
                "credentials_present_in_fixture": False,
            }
            for item in connectors
        ],
        "identity_mapping": {
            "source_subjects": ["sso:group/platform-admins", "scim:user/auditor-fixture"],
            "role_binding_preview": [
                {"subject": "sso:group/platform-admins", "role": "admin", "scope": "org_local"},
                {"subject": "scim:user/auditor-fixture", "role": "auditor", "scope": "prj_hate"},
            ],
            "unknown_subject_default": "deny",
            "service_account_human_approval_substitute": False,
        },
        "rbac_integration": {
            "source_ref": "rbac-matrix-report.json",
            "known_roles": rbac_matrix.get("roles", []),
            "auditor_read_only_preserved": rbac_matrix.get("invariants", {}).get("auditor_read_only") is True,
            "viewer_raw_artifact_denied_preserved": rbac_matrix.get("invariants", {}).get("viewer_raw_artifact_denied") is True,
        },
        "safety": {
            "contains_connector_token": False,
            "contains_customer_private_url": False,
            "contains_idp_metadata": False,
            "external_network_required": False,
            "safe_to_share": True,
        },
        "edition_boundary": {
            "local_required": False,
            "team_required": False,
            "enterprise_available": True,
            "regulated_available": True,
        },
        "summary": {
            "connector_count": len(connectors),
            "configured_count": 0,
            "dry_run_count": len(connectors),
            "non_gating_failure_count": len(connectors),
        },
        "source_refs": [
            "docs/process/ENTERPRISE_PRODUCT_REQUIREMENTS.md",
            "docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md",
            "rbac-matrix-report.json",
        ],
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def build_enterprise_connector_report(run_id: str) -> dict[str, Any]:
    connectors = [
        _enterprise_connector("siem", "SIEM export", "audit_events", "security_monitoring"),
        _enterprise_connector("warehouse", "Data warehouse export", "aggregate_metrics", "analytics"),
        _enterprise_connector("ticketing", "Ticketing sync", "incident_and_risk_debt", "support_workflow"),
    ]
    failure_fixtures = [
        {
            "connector_id": item["connector_id"],
            "simulated_failure": "connector_unavailable",
            "stable_warning_code": "HATE-EXP-001",
            "severity": "warning",
            "non_gating": True,
            "local_artifacts_preserved": True,
            "qeg_export_preserved": True,
            "canonical_decision_unchanged": True,
        }
        for item in connectors
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "enterprise_connector_report",
        "run_id": run_id,
        "mode": "dry_run_contract_fixture",
        "connectors": connectors,
        "failure_fixtures": failure_fixtures,
        "payload_safety": {
            "raw_artifact_content_included": False,
            "customer_code_included": False,
            "connector_token_included": False,
            "pii_included": False,
            "unsafe_artifact_exported": False,
        },
        "fallback_policy": {
            "connector_failure_non_gating": True,
            "local_artifacts_preserved": True,
            "qeg_export_preserved": True,
            "retry_allowed": True,
            "manual_replay_available": True,
        },
        "summary": {
            "connector_count": len(connectors),
            "configured_count": 0,
            "dry_run_count": len(connectors),
            "failure_fixture_count": len(failure_fixtures),
        },
        "source_refs": [
            "docs/process/ENTERPRISE_PRODUCT_REQUIREMENTS.md",
            "docs/process/DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md",
            "audit-event-log.json",
            "enterprise-metrics-report.json",
            "incident-slo-report.json",
        ],
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _identity_connector(connector_id: str, display_name: str, roles: list[str]) -> dict[str, Any]:
    return {
        "connector_id": connector_id,
        "display_name": display_name,
        "connector_type": "identity",
        "live_runtime_implemented": False,
        "dry_run_supported": True,
        "optional_enterprise_connector": True,
        "mapped_roles": roles,
        "failure_policy": "non_gating_warning",
        "canonical_bundle_mutated": False,
    }


def _enterprise_connector(connector_id: str, display_name: str, payload_kind: str, purpose: str) -> dict[str, Any]:
    return {
        "connector_id": connector_id,
        "display_name": display_name,
        "connector_type": "enterprise_export",
        "payload_kind": payload_kind,
        "purpose": purpose,
        "live_runtime_implemented": False,
        "dry_run_supported": True,
        "optional_enterprise_connector": True,
        "configured": False,
        "failure_policy": "non_gating_warning",
        "canonical_bundle_mutated": False,
    }
