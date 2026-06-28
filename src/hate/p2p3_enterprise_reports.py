from __future__ import annotations
from typing import Any

SCHEMA_VERSION = "HATE/v1"

def _build_release_migration_report(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "release_migration_report",
        "run_id": run_id,
        "release_channel": "local",
        "release_gates": ["schema-compatible", "fixture-reproducible", "no-release-override"],
        "migration_artifacts": ["product-readiness-report.json", "customer-docs-index.json"],
        "rollback_policy": "restore previous artifact bundle and schema version",
        "compatibility_matrix": [{"from": "HATE/v1", "to": "HATE/v1", "breaking": False}],
        "release_gate_override": False,
        "publish_gate_override": False,
    }

def _build_entitlement_usage_report(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "entitlement_usage_report",
        "run_id": run_id,
        "edition": "oss-local",
        "entitlements": [{"feature": "local_precheck", "status": "enabled"}, {"feature": "hosted_upload", "status": "not_configured"}],
        "usage": [{"meter": "runs", "value": 1, "limit": None}, {"meter": "artifact_bytes", "value": 0, "limit": None}],
        "over_limit_actions": ["warning", "hosted_upload_block", "connector_warning"],
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "publish_gate_override": False,
    }

def _build_customer_docs_index() -> dict[str, Any]:
    docs = ["Quickstart", "Concepts", "CLI Reference", "Schema Reference", "Security Guide", "Migration Guide", "Support Guide", "Compliance Pack"]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "customer_docs_index",
        "docs": [
            {
                "doc_id": f"doc:{name.lower().replace(' ', '-')}",
                "title": name,
                "freshness_status": "source_linked",
                "verification_status": "artifact_referenced",
            }
            for name in docs
        ],
        "overclaim_guard": "Do not claim hosted SaaS availability from local artifact readiness.",
        "publish_gate_override": False,
    }

def _build_incident_slo_report(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "incident_slo_report",
        "run_id": run_id,
        "slo_targets": [{"surface": "local_cli", "availability_target": "best_effort"}, {"surface": "hosted_api", "availability_target": "not_configured"}],
        "incident_classes": ["data_exposure", "wrong_eligibility", "evidence_corruption", "hosted_outage", "connector_degradation", "schema_adapter_regression"],
        "fixture_incidents": [
            {
                "incident_id": "INC-FIXTURE-SEV2-001",
                "severity": "sev2",
                "class": "wrong_eligibility",
                "owner": "RNA4219",
                "timeline": [{"event": "detected", "at": "fixture-time"}],
                "containment": "keep release_gate_override=false",
                "evidence_refs": ["doctor-report.json", "product-readiness-report.json"],
            }
        ],
        "publish_gate_override": False,
    }

def _build_adoption_health_report(run_id: str) -> dict[str, Any]:
    stages = ["Discover", "Prove", "Integrate", "Govern", "Scale", "Renew"]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "adoption_health_report",
        "run_id": run_id,
        "stages": [
            {"stage": stage, "owner": "RNA4219", "status": "tracked", "milestone": f"{stage.lower()}-fixture", "next_action": "review evidence refs"}
            for stage in stages
        ],
        "adoption_gaps": [{"gap_id": "adoption:hosted-runtime", "status": "not_in_local_scope", "renewal_readiness": "not_applicable"}],
        "precheck_decision_override": False,
        "publish_gate_override": False,
    }

def _build_security_trust_packet(run_id: str) -> dict[str, Any]:
    trust_packet_refs = [
        "data-flow.md",
        "security-controls.json",
        "privacy-summary.md",
        "subprocessors.md",
        "sbom.json",
        "vulnerability-report.json",
        "pen-test-summary.md",
        "attestation-summary.json",
        "deletion-export-policy.md",
        "support-security-escalation.md",
    ]
    control_mapping = [
        {"control_area": "Access control", "source_refs": ["SECURITY_REVIEW_TRUST_CONTRACT.md"], "evidence_refs": ["rbac-matrix-report.json", "audit-event-log.json"]},
        {"control_area": "Data protection", "source_refs": ["PRIVACY_QUARANTINE_CONTRACT.md"], "evidence_refs": ["privacy-quarantine-report.json", "retention-governance-report.json"]},
        {"control_area": "Change management", "source_refs": ["SECURITY_REVIEW_TRUST_CONTRACT.md"], "evidence_refs": ["release-migration-report.json"]},
        {"control_area": "Incident management", "source_refs": ["SLO_INCIDENT_RESPONSE_CONTRACT.md"], "evidence_refs": ["incident-slo-report.json"]},
        {"control_area": "Vulnerability management", "source_refs": ["SECURITY_REVIEW_TRUST_CONTRACT.md"], "evidence_refs": ["security-trust-packet.json"]},
        {"control_area": "Logging / monitoring", "source_refs": ["ENTERPRISE_DOMAIN_MODEL.md"], "evidence_refs": ["audit-event-log.json"]},
        {"control_area": "Supplier management", "source_refs": ["SECURITY_REVIEW_TRUST_CONTRACT.md"], "evidence_refs": ["identity-connector-report.json", "enterprise-connector-report.json"]},
        {"control_area": "Business continuity", "source_refs": ["DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md"], "evidence_refs": ["residency-deployment-report.json"]},
        {"control_area": "Evidence integrity", "source_refs": ["SECURITY_REVIEW_TRUST_CONTRACT.md"], "evidence_refs": ["attestation-report.json", "domain-model-report.json"]},
        {"control_area": "Secure development", "source_refs": ["ADAPTER_SDK_CONTRACT.md"], "evidence_refs": ["adapter-conformance-report.json"]},
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "security_trust_packet",
        "run_id": run_id,
        "source_contract": "SECURITY_REVIEW_TRUST_CONTRACT.md",
        "scope": ["local_cli", "artifact_generation", "hosted_read_model_contract", "enterprise_connector_contract"],
        "security_review_record": {
            "review_id": "SEC-REV-20260629-001",
            "customer_id": "fixture-customer",
            "scope": ["hosted_read_model", "artifact_storage", "github_action", "enterprise_connectors"],
            "requested_at": "2026-06-29T00:00:00Z",
            "status": "conditional",
            "trust_packet_refs": trust_packet_refs,
            "control_mappings": [item["control_area"] for item in control_mapping],
            "open_findings": [
                {
                    "finding_id": "SEC-FIXTURE-HIGH-001",
                    "severity": "high",
                    "status": "tracked",
                    "owner": "RNA4219",
                    "due_date": "2026-07-28",
                    "affected_surface": "hosted_read_model_contract",
                    "customer_exposure": "none_fixture_only",
                    "mitigation": "Keep hosted runtime claims disabled until runtime evidence exists.",
                    "source_refs": ["MANUAL_BB_GATE_FULL_IMPLEMENTATION.md"],
                }
            ],
            "assumptions": ["Local artifact packet does not claim hosted SaaS runtime availability."],
            "expiry_at": "2026-12-29T00:00:00Z",
            "owner": "RNA4219",
        },
        "trust_packet_refs": trust_packet_refs,
        "data_flow": {
            "inputs": ["qeg-bundle.json", "aete-score.json", "workflow-evidence.jsonl"],
            "storage": ["local output directory", "optional hosted read model cache"],
            "outputs": ["product-readiness-report.json", "security-trust-packet.json"],
            "external_transfers": ["optional enterprise connector dry-run only"],
            "raw_artifact_exported": False,
        },
        "control_mapping": control_mapping,
        "privacy_summary": {
            "classification_refs": ["domain-model-report.json", "retention-governance-report.json"],
            "redaction_refs": ["support-diagnostic-bundle.json"],
            "quarantine_refs": ["privacy-quarantine-report.json"],
            "contains_customer_code": False,
            "contains_secret": False,
            "contains_pii": False,
            "contains_unsafe_artifact": False,
        },
        "sbom": {
            "format": "fixture-sbom",
            "components": [
                {"name": "harness-auto-test-evidence", "type": "application", "version": "0.1.0-fixture"},
                {"name": "python-stdlib", "type": "runtime", "version": "fixture"},
            ],
            "third_party_runtime_dependencies": [],
            "freshness_status": "fixture_current",
        },
        "vulnerability_report": {
            "open_findings": [
                {
                    "finding_id": "VULN-FIXTURE-MEDIUM-001",
                    "severity": "medium",
                    "status": "tracked",
                    "owner": "RNA4219",
                    "due_date": "2026-07-28",
                    "affected_surface": "dependency_scanning_fixture",
                    "customer_exposure": "none_fixture_only",
                    "mitigation": "Run dependency scan before release candidate packaging.",
                }
            ],
            "critical_open_count": 0,
            "high_open_count": 0,
            "freshness_status": "fixture_current",
            "connected_to_incident_response": True,
            "connected_to_release_policy": True,
        },
        "subprocessors": [
            {"name": "GitHub Actions", "purpose": "optional CI execution", "configured": False, "customer_data_sent": False},
            {"name": "DashScope GLM", "purpose": "optional delegated implementation", "configured": False, "customer_data_sent": False},
        ],
        "freshness": {
            "data_flow": "fixture_current",
            "security_controls": "fixture_current",
            "sbom": "fixture_current",
            "vulnerability_report": "fixture_current",
            "subprocessors": "fixture_current",
            "privacy_summary": "fixture_current",
        },
        "attestation_summary": {
            "source_ref": "attestation-report.json",
            "signed": False,
            "provenance_available": True,
        },
        "deletion_export_policy_ref": "retention-governance-report.json",
        "support_security_escalation_ref": "incident-slo-report.json",
        "contains_customer_code": False,
        "contains_secret": False,
        "contains_pii": False,
        "contains_unsafe_artifact": False,
        "qeg_gate_policy_override": False,
        "qeg_waiver_override": False,
        "qeg_approval_override": False,
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }

def _build_residency_deployment_report(run_id: str) -> dict[str, Any]:
    mode_specs = [
        ("local_only", "customer_machine", "none", "customer"),
        ("ci_attached", "ci_workspace_artifact_store", "hate_cli_action", "customer"),
        ("hosted_read_model", "customer_approved_bundle_refs", "hosted_dashboard_api", "shared"),
        ("private_tenant", "dedicated_tenant_storage", "managed_hosted_control", "provider"),
        ("customer_managed", "customer_cloud_storage", "limited_managed_control", "customer"),
        ("air_gapped_export", "offline_bundle", "offline_validation", "customer"),
    ]
    modes = [item[0] for item in mode_specs]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "residency_deployment_report",
        "run_id": run_id,
        "deployment_modes": [
            {
                "mode": mode,
                "data_plane": data_plane,
                "control_plane": control_plane,
                "owner": owner,
                "canonical_replay_preserved": True,
                "p0a_local_first_preserved": True,
                "evidence_eligibility_depends_on_region": False,
                "residual_risk": "hosted_optional" if mode in {"hosted_read_model", "private_tenant"} else "customer_controlled",
            }
            for mode, data_plane, control_plane, owner in mode_specs
        ],
        "residency_profile": {
            "profile_id": "residency-fixture-001",
            "deployment_mode": "hosted_read_model",
            "allowed_regions": ["us", "eu", "jp"],
            "disallowed_regions": [],
            "data_classes": {
                "canonical_bundle": "customer_controlled",
                "read_model": "hosted_allowed",
                "artifact_content": "not_uploaded",
                "telemetry": "aggregate_only",
            },
            "key_management": {"mode": "customer_managed", "rotation_days": 90},
            "network": {"public_ingress": False, "private_link": True, "ip_allowlist": True},
        },
        "data_class_routing": [
            {"class": "canonical_bundle", "default_route": "customer_controlled", "allowed_modes": modes, "raw_content_hosted": False},
            {"class": "read_model", "default_route": "hosted_if_enabled", "allowed_modes": ["hosted_read_model", "private_tenant", "customer_managed"], "rebuildable_from_canonical": True},
            {"class": "artifact_content", "default_route": "local_or_customer_storage", "allowed_modes": ["local_only", "ci_attached", "customer_managed", "air_gapped_export"], "hosted_default": False},
            {"class": "artifact_metadata", "default_route": "hosted_if_enabled", "allowed_modes": modes, "hash_size_classification_only": True},
            {"class": "telemetry", "default_route": "off_or_aggregate", "allowed_modes": modes, "prohibited_signals_blocked": True},
            {"class": "support_bundle", "default_route": "explicit_export", "allowed_modes": ["local_only", "customer_managed", "air_gapped_export"], "privacy_checks_required": True},
            {"class": "audit_log", "default_route": "tenant_or_org_scope", "allowed_modes": modes, "append_only": True},
            {"class": "security_review_packet", "default_route": "redacted_export", "allowed_modes": modes, "customer_code_included": False},
        ],
        "connectivity_controls": {
            "private_networking_supported": True,
            "egress_allowlist_required_for_connectors": True,
            "ingress_requires_rbac_and_network_policy": True,
            "artifact_fetch_ssrf_metadata_ip_block": True,
            "connector_scoped_credentials": True,
            "air_gapped_export_has_checksum_and_offline_docs": True,
        },
        "backup_recovery": [
            {"asset": "hosted_read_model", "backup": "rebuild_from_canonical_bundle", "recovery_expectation": "rebuild_preferred"},
            {"asset": "entitlement_manifest", "backup": "tenant_config", "recovery_expectation": "restore_with_audit_event"},
            {"asset": "audit_metadata", "backup": "immutable_append_only_target", "recovery_expectation": "restore_without_rewriting_record_ids"},
            {"asset": "customer_docs_index", "backup": "repo_release_artifact", "recovery_expectation": "regenerate_from_docs_source"},
            {"asset": "trust_packet_index", "backup": "release_artifact", "recovery_expectation": "regenerate_from_source_contracts"},
            {"asset": "telemetry_aggregate", "backup": "optional", "recovery_expectation": "loss_does_not_affect_evidence"},
        ],
        "summary": {
            "deployment_mode_count": len(modes),
            "hosted_read_model_rebuildable": True,
            "customer_source_code_hosted_by_default": False,
            "unsafe_artifact_hosted_by_default": False,
            "air_gapped_supported": True,
        },
        "source_refs": ["DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md"],
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }

def _build_roadmap_decision_report(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "roadmap_decision_record",
        "run_id": run_id,
        "roadmap_items": [
            {"item_id": "roadmap:hosted-runtime", "status": "planned", "personas": ["Platform Admin"], "acceptance_refs": ["AC-HATE-P3-ENTERPRISE"], "source_refs": ["ENTERPRISE_PRODUCT_REQUIREMENTS.md"]},
            {"item_id": "roadmap:local-artifacts", "status": "implemented", "personas": ["Developer", "QA Lead"], "acceptance_refs": ["AC-HATE-P3-ENTERPRISE"], "source_refs": ["product-readiness-report.json"]},
        ],
        "decision_rationale": "Local artifact readiness is implemented before hosted runtime expansion.",
        "customer_facing_available_claim": False,
        "publish_gate_override": False,
    }

def _build_accessibility_localization_report(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "accessibility_localization_report",
        "run_id": run_id,
        "surfaces": [
            {"surface": "cli_summary", "target": "text", "violations": [], "color_only_status": False},
            {"surface": "customer_docs", "target": "wcag-structure", "violations": [], "color_only_status": False},
        ],
        "message_catalog": [{"message_id": "product.readiness.status", "stable_identifier": True, "locale_fallback": "en"}],
        "translated_schema_fields": False,
        "publish_gate_override": False,
    }
