"""Tests for P2/P3 product readiness advisory artifacts."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from hate.p2p3 import generate_product_readiness, make_product_read_model_handler, query_product_read_model
from hate.p2p3_readiness import _build_evaluation_score
from hate.store import ingest_local_store, query_local_store, read_history_index


def test_p2p3_generates_product_readiness_artifacts(tmp_path: Path) -> None:
    """P2/P3 emits PRG coverage and enterprise safety artifacts."""
    bundle = Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    workflow_dir = Path("fixtures/golden/p1b-workflow-minimal/expected")
    out_dir = tmp_path / "product-output"

    result = generate_product_readiness(
        bundle_path=bundle,
        trust_dir=trust_dir,
        workflow_dir=workflow_dir,
        out_dir=out_dir,
    )

    assert result["product_status"] == "go"
    assert result["prg_coverage"] == "7/7"
    assert result["publish_gate_override"] is False
    assert "product-readiness-report.json" in result["generated"]
    assert "enterprise-metrics-report.json" in result["generated"]
    required_artifacts = {
        "pr-annotation-export.json",
        "artifact-budget-report.json",
        "attestation-report.json",
        "external-export-report.json",
        "product-error-catalog.json",
        "enterprise-risk-debt-register.json",
        "privacy-quarantine-report.json",
        "hosted-read-model-index.json",
        "domain-model-report.json",
        "rbac-matrix-report.json",
        "identity-connector-report.json",
        "enterprise-connector-report.json",
        "audit-event-log.json",
        "retention-governance-report.json",
        "release-migration-report.json",
        "entitlement-usage-report.json",
        "incident-slo-report.json",
        "adoption-health-report.json",
        "security-trust-packet.json",
        "residency-deployment-report.json",
        "roadmap-decision-record.json",
        "accessibility-localization-report.json",
        "commercial-contract-report.json",
        "audit-assurance-pack.json",
        "release-candidate-pack.json",
        "dashboard-report.html",
        "dashboard-view-model.json",
    }
    assert required_artifacts.issubset(set(result["generated"]))

    readiness = json.loads((out_dir / "product-readiness-report.json").read_text())
    assert readiness["record_type"] == "product_readiness_report"
    assert readiness["summary"]["overall_status"] == "go"
    assert readiness["summary"]["live_saas_required"] is False
    assert readiness["summary"]["required_artifact_count"] >= 20
    assert readiness["summary"]["evaluation_score"] == 77.5
    assert readiness["summary"]["evaluation_confidence"] == "medium"
    assert readiness["summary"]["go_label_is_advisory"] is True
    assert readiness["summary"]["degraded_by_doctor_findings"] is False
    assert readiness["summary"]["degraded_by_unverified_acceptance"] is False
    assert readiness["evaluation"]["method"] == "gate_capped_evidence_score_v2"
    assert readiness["evaluation"]["go_label_is_advisory"] is True
    assert readiness["evaluation"]["release_approval"] is False
    assert readiness["evaluation"]["raw_score"] == 77.5
    assert readiness["evaluation"]["cap_score"] == 79
    assert readiness["evaluation"]["addition_total"] == 82.5
    assert readiness["evaluation"]["penalty_total"] == 5
    assert readiness["evaluation"]["interpretation"] == "usable_with_review"
    assert any(item["cap_id"] == "uncalibrated_aete" for item in readiness["evaluation"]["caps"])
    assert {item["component_id"] for item in readiness["evaluation"]["additions"]} == {
        "aete_weighted_score",
        "product_readiness_gate_coverage",
        "required_artifact_completeness",
        "workflow_acceptance",
        "doctor_hygiene",
    }
    assert any(item["component_id"] == "uncalibrated_aete" and item["points"] == 5 for item in readiness["evaluation"]["penalties"])
    assert readiness["boundaries"]["qeg_gate_override"] is False
    assert readiness["boundaries"]["hosted_saas_claim"] is False
    assert [gate["gate_id"] for gate in readiness["product_readiness_gates"]] == [
        "PRG-0", "PRG-1", "PRG-2", "PRG-3", "PRG-4", "PRG-5", "PRG-6",
    ]

    hosted = json.loads((out_dir / "hosted-read-model-index.json").read_text())
    assert all(view["stale_cache_policy"] == "rebuild_from_canonical_bundle" for view in hosted["views"])
    assert any(view["view"] == "dashboard" for view in hosted["views"])

    domain_model = json.loads((out_dir / "domain-model-report.json").read_text())
    assert domain_model["record_type"] == "enterprise_domain_model"
    assert domain_model["hosted_service_required"] is False
    assert domain_model["local_first_preserved"] is True
    assert {entity["kind"] for entity in domain_model["entities"]} >= {
        "organization", "workspace", "project", "repository", "run", "attempt", "evidence_bundle", "profile",
    }
    assert domain_model["scope_boundaries"]["local_mapping"]["default_scope"] == "local"
    assert next(role for role in domain_model["role_model"] if role["role"] == "auditor")["read_only"] is True
    assert next(role for role in domain_model["role_model"] if role["role"] == "service_account")["may_replace_human_approval"] is False
    restricted = next(item for item in domain_model["classification_policy"] if item["classification"] == "restricted")
    assert restricted["diagnostic_allowed"] is False
    assert restricted["quarantine_required"] is True
    assert any(item["artifact_kind"] == "diagnostic_bundle" and item["retention_days"] == 14 for item in domain_model["retention_links"])
    assert domain_model["audit_event_contract"]["append_only"] is True
    assert "diagnostic.generated" in domain_model["audit_event_contract"]["required_events"]
    assert domain_model["read_model_contract"]["canonical_source_preserved"] is True
    assert domain_model["acceptance"]["p0_p1_local_bundle_without_org"] is True
    assert domain_model["acceptance"]["artifact_classification_controls_outputs"] is True
    assert domain_model["qeg_verdict_override"] is False

    rbac = json.loads((out_dir / "rbac-matrix-report.json").read_text())
    assert rbac["record_type"] == "rbac_matrix_report"
    assert {"admin", "maintainer", "developer", "auditor", "viewer", "service_account", "security_reviewer"}.issubset(set(rbac["roles"]))
    assert rbac["invariants"]["auditor_read_only"] is True
    assert rbac["invariants"]["viewer_raw_artifact_denied"] is True
    assert rbac["invariants"]["developer_audit_log_denied"] is True
    assert rbac["invariants"]["service_account_human_approval_substitute"] is False
    assert rbac["invariants"]["qeg_approval_not_reimplemented"] is True
    assert rbac["invariants"]["least_privilege_default_deny"] is True
    matrix = {
        (item["role"], item["resource"], item["action"]): item["decision"]
        for item in rbac["matrix"]
    }
    assert matrix[("viewer", "artifacts", "read_raw")] == "deny"
    assert matrix[("developer", "audit-events", "read")] == "deny"
    assert matrix[("auditor", "audit-events", "read")] == "allow"
    assert matrix[("auditor", "profiles", "write")] == "deny"
    assert matrix[("service_account", "audit-events", "append")] == "allow"
    artifact_mapping = next(item for item in rbac["read_model_mapping"] if item["read_model_resource"] == "artifacts")
    assert artifact_mapping["viewer_allowed"] is False
    assert artifact_mapping["auditor_allowed"] is True

    identity_connector = json.loads((out_dir / "identity-connector-report.json").read_text())
    assert identity_connector["record_type"] == "identity_connector_report"
    assert identity_connector["mode"] == "dry_run_contract_fixture"
    assert {item["connector_id"] for item in identity_connector["connectors"]} == {"sso", "scim"}
    assert all(item["dry_run_supported"] is True for item in identity_connector["connectors"])
    assert all(item["failure_policy"] == "non_gating_warning" for item in identity_connector["connectors"])
    assert all(item["canonical_bundle_mutated"] is False for item in identity_connector["connectors"])
    assert identity_connector["summary"]["configured_count"] == 0
    assert identity_connector["summary"]["non_gating_failure_count"] == 2
    assert all(item["non_gating"] is True for item in identity_connector["dry_run_results"])
    assert all(item["credentials_present_in_fixture"] is False for item in identity_connector["dry_run_results"])
    assert identity_connector["identity_mapping"]["unknown_subject_default"] == "deny"
    assert identity_connector["identity_mapping"]["service_account_human_approval_substitute"] is False
    assert identity_connector["rbac_integration"]["auditor_read_only_preserved"] is True
    assert identity_connector["rbac_integration"]["viewer_raw_artifact_denied_preserved"] is True
    assert identity_connector["safety"]["contains_connector_token"] is False
    assert identity_connector["safety"]["contains_customer_private_url"] is False
    assert identity_connector["safety"]["external_network_required"] is False
    assert identity_connector["edition_boundary"]["local_required"] is False
    assert identity_connector["precheck_decision_override"] is False

    enterprise_connector = json.loads((out_dir / "enterprise-connector-report.json").read_text())
    assert enterprise_connector["record_type"] == "enterprise_connector_report"
    assert {item["connector_id"] for item in enterprise_connector["connectors"]} == {"siem", "warehouse", "ticketing"}
    assert all(item["dry_run_supported"] is True for item in enterprise_connector["connectors"])
    assert all(item["failure_policy"] == "non_gating_warning" for item in enterprise_connector["connectors"])
    assert all(item["configured"] is False for item in enterprise_connector["connectors"])
    assert enterprise_connector["summary"]["failure_fixture_count"] == 3
    assert all(item["stable_warning_code"] == "HATE-EXP-001" for item in enterprise_connector["failure_fixtures"])
    assert all(item["non_gating"] is True for item in enterprise_connector["failure_fixtures"])
    assert all(item["qeg_export_preserved"] is True for item in enterprise_connector["failure_fixtures"])
    assert enterprise_connector["payload_safety"]["raw_artifact_content_included"] is False
    assert enterprise_connector["payload_safety"]["connector_token_included"] is False
    assert enterprise_connector["payload_safety"]["unsafe_artifact_exported"] is False
    assert enterprise_connector["fallback_policy"]["connector_failure_non_gating"] is True
    assert enterprise_connector["fallback_policy"]["local_artifacts_preserved"] is True
    assert enterprise_connector["qeg_verdict_override"] is False

    audit_log = json.loads((out_dir / "audit-event-log.json").read_text())
    assert audit_log["record_type"] == "audit_event_log"
    assert audit_log["append_only"] is True
    assert audit_log["safe_to_share"] is True
    assert audit_log["summary"]["event_count"] == 8
    assert audit_log["summary"]["missing_required_events"] == []
    assert audit_log["summary"]["sequence_monotonic"] is True
    assert audit_log["access_policy"]["auditor_read_allowed"] is True
    assert audit_log["access_policy"]["viewer_read_allowed"] is False
    assert audit_log["immutability"]["rewrite_allowed"] is False
    event_types = {event["event_type"] for event in audit_log["events"]}
    assert event_types == {
        "bundle.created",
        "bundle.exported",
        "profile.changed",
        "adapter.changed",
        "artifact.accessed",
        "artifact.quarantined",
        "riskdebt.created",
        "diagnostic.generated",
    }
    by_type = {event["event_type"]: event["fields"] for event in audit_log["events"]}
    assert {"bundle_id", "run_id", "commit_sha", "profile_hash"}.issubset(by_type["bundle.created"])
    assert {"bundle_id", "target", "status"}.issubset(by_type["bundle.exported"])
    assert {"profile_id", "before_hash", "after_hash", "actor"}.issubset(by_type["profile.changed"])
    assert {"adapter_id", "version", "actor"}.issubset(by_type["adapter.changed"])
    assert {"artifact_id", "actor", "reason"}.issubset(by_type["artifact.accessed"])
    assert {"artifact_id", "reason", "detector"}.issubset(by_type["artifact.quarantined"])
    assert {"risk_id", "source_refs", "owner"}.issubset(by_type["riskdebt.created"])
    assert {"bundle_id", "requester", "redaction_status"}.issubset(by_type["diagnostic.generated"])
    assert audit_log["qeg_verdict_override"] is False

    retention = json.loads((out_dir / "retention-governance-report.json").read_text())
    assert retention["record_type"] == "retention_governance_report"
    assert retention["policy_scope"] == "metadata_policy_not_system_of_record"
    classes = {item["classification"]: item for item in retention["classification_policies"]}
    assert classes["public"]["retention_days"] == 180
    assert classes["internal"]["retention_days"] == 90
    assert classes["confidential"]["retention_days"] == 30
    assert classes["restricted"]["delete_action"] == "quarantine_metadata_only"
    assert all(item["final_retention_control"] == "delegated_to_qeg_or_connected_storage" for item in retention["classification_policies"])
    assert retention["legal_hold"]["supported"] is True
    assert retention["legal_hold"]["delete_allowed_while_on_hold"] is False
    assert retention["legal_hold"]["canonical_bundle_mutated"] is False
    assert retention["legal_hold"]["qeg_retention_reimplemented"] is False
    assert retention["customer_export_delete"]["export_metadata_only"] is True
    assert retention["customer_export_delete"]["raw_artifact_deletion_delegated"] is True
    request_decisions = {item["request_type"]: item["decision"] for item in retention["request_fixtures"]}
    assert request_decisions["customer_export"] == "allow_metadata_only"
    assert request_decisions["customer_delete"] == "defer_to_system_of_record"
    assert request_decisions["legal_hold"] == "hold_metadata_and_block_delete"
    assert all(item["canonical_bundle_mutated"] is False for item in retention["artifact_actions"])
    assert retention["summary"]["legal_hold_blocks_delete"] is True
    assert retention["qeg_verdict_override"] is False

    dashboard = (out_dir / "dashboard-report.html").read_text()
    assert "HATE Product Readiness Dashboard" in dashboard
    assert "Canonical artifact readiness: go" in dashboard
    assert "override QEG or Shipyard gates" in dashboard

    dashboard_vm = json.loads((out_dir / "dashboard-view-model.json").read_text())
    assert dashboard_vm["record_type"] == "dashboard_view_model"
    assert [view["view_id"] for view in dashboard_vm["required_views"]] == [
        "overview", "risk_matrix", "evidence_map", "artifact_budget", "readiness_trend",
    ]
    assert dashboard_vm["required_views"][0]["cards"][0]["card_id"] == "product_status"
    assert len(dashboard_vm["required_views"][1]["rows"]) == 2
    assert dashboard_vm["required_views"][2]["summary"]["test_count"] == 2
    assert dashboard_vm["cache"]["stale_cache"] is False
    assert dashboard_vm["boundaries"]["qeg_verdict_override"] is False
    assert dashboard_vm["boundaries"]["publish_gate_override"] is False

    pr_annotation = json.loads((out_dir / "pr-annotation-export.json").read_text())
    assert pr_annotation["summary"]["high_risk_count"] == 2
    assert pr_annotation["summary"]["warning_annotation_count"] == 2
    assert pr_annotation["github_pr_annotation_compatible"] is True
    assert pr_annotation["annotations"][0]["aete_summary"]["weighted_score"] == 0.65
    first_annotation = pr_annotation["annotations"][0]
    assert first_annotation["annotation_id"].startswith("pr-annotation:1001:")
    assert first_annotation["annotation_level"] == "warning"
    assert first_annotation["message"].startswith("HATE warning: high risk")
    assert first_annotation["start_column"] == 1
    assert first_annotation["end_column"] == 1
    assert first_annotation["raw_details"]["required_test_refs"]
    assert first_annotation["raw_details"]["execution_evidence_refs"]
    assert first_annotation["raw_details"]["coverage_refs"]
    assert first_annotation["publish_gate_override"] is False

    budget = json.loads((out_dir / "artifact-budget-report.json").read_text())
    assert budget["summary"]["artifact_count"] >= 4
    assert budget["summary"]["over_limit_count"] == 0
    assert budget["budget_policy"]["max_artifact_size_bytes"] == 10_000_000
    assert budget["summary"]["by_public_exposure"]["none"] == budget["summary"]["artifact_count"]
    assert all("retention_days" in artifact for artifact in budget["artifacts"])
    assert all(artifact["budget_action"] == "within_budget" for artifact in budget["artifacts"])
    assert budget["canonical_decision_unchanged"] is True
    assert budget["evidence_dropped_for_budget"] is False

    attestation = json.loads((out_dir / "attestation-report.json").read_text())
    assert attestation["attestation_mode"] == "optional_unsigned_fixture"
    assert attestation["attestation_status"] == "unsigned_optional"
    assert len(attestation["subjects"]) == 3
    assert all(subject["digest"].startswith("sha256:") for subject in attestation["subjects"])
    assert attestation["provenance"]["build_type"] == "local_canonical_replay"
    assert attestation["provenance"]["source_bundle_ref"] == "qeg-bundle.json"
    assert attestation["signing"]["configured"] is False
    assert attestation["signing"]["verification_status"] == "not_requested"
    assert attestation["release_refs"]["shipyard_evidence_ref"] == "shipyard-run-evidence.json"
    assert attestation["immutability"]["canonical_bundle_immutable"] is True
    assert attestation["canonical_decision_unchanged"] is True
    assert attestation["local_first_precheck_dependency"] is False

    external_export = json.loads((out_dir / "external-export-report.json").read_text())
    assert external_export["record_type"] == "external_export_report"
    assert {item["provider_id"] for item in external_export["providers"]} == {
        "allure", "reportportal", "codecov", "sonarqube",
    }
    assert all(item["failure_policy"] == "non_gating_warning" for item in external_export["providers"])
    assert external_export["summary"]["provider_count"] == 4
    assert external_export["summary"]["failure_fixture_count"] == 4
    assert all(item["stable_error_code"] == "HATE-EXP-001" for item in external_export["failure_fixtures"])
    assert all(item["non_gating"] is True for item in external_export["failure_fixtures"])
    assert external_export["boundaries"]["canonical_bundle_mutated"] is False
    assert external_export["boundaries"]["precheck_decision_override"] is False
    assert external_export["boundaries"]["qeg_verdict_override"] is False
    assert external_export["boundaries"]["product_status_override"] is False
    assert external_export["canonical_decision_unchanged"] is True
    assert external_export["publish_gate_override"] is False

    errors = json.loads((out_dir / "product-error-catalog.json").read_text())
    assert {item["code"] for item in errors["errors"]} >= {"HATE-E-DQ-001", "HATE-E-PRODUCT-001"}

    risk_debt = json.loads((out_dir / "enterprise-risk-debt-register.json").read_text())
    assert risk_debt["summary"]["open_count"] == 0

    quarantine = json.loads((out_dir / "privacy-quarantine-report.json").read_text())
    assert quarantine["output_policy"]["diagnostic_bundle_excludes_unsafe"] is True

    release = json.loads((out_dir / "release-migration-report.json").read_text())
    assert release["compatibility_matrix"][0]["breaking"] is False

    entitlement = json.loads((out_dir / "entitlement-usage-report.json").read_text())
    assert entitlement["precheck_decision_override"] is False
    assert entitlement["qeg_verdict_override"] is False

    metrics = json.loads((out_dir / "enterprise-metrics-report.json").read_text())
    assert metrics["privacy_boundary"]["contains_customer_code"] is False
    assert len(metrics["metrics"]) >= 7

    incident = json.loads((out_dir / "incident-slo-report.json").read_text())
    assert "wrong_eligibility" in incident["incident_classes"]

    adoption = json.loads((out_dir / "adoption-health-report.json").read_text())
    assert [stage["stage"] for stage in adoption["stages"]] == ["Discover", "Prove", "Integrate", "Govern", "Scale", "Renew"]

    trust = json.loads((out_dir / "security-trust-packet.json").read_text())
    assert trust["contains_customer_code"] is False
    assert trust["contains_secret"] is False
    assert trust["contains_pii"] is False
    assert trust["contains_unsafe_artifact"] is False
    assert trust["security_review_record"]["status"] == "conditional"
    assert trust["security_review_record"]["trust_packet_refs"]
    assert trust["security_review_record"]["expiry_at"] == "2026-12-29T00:00:00Z"
    assert trust["security_review_record"]["open_findings"][0]["severity"] == "high"
    assert trust["security_review_record"]["open_findings"][0]["owner"] == "RNA4219"
    assert trust["security_review_record"]["open_findings"][0]["due_date"] == "2026-07-28"
    assert trust["security_review_record"]["open_findings"][0]["mitigation"]
    assert {"data-flow.md", "security-controls.json", "sbom.json", "vulnerability-report.json", "subprocessors.md"}.issubset(set(trust["trust_packet_refs"]))
    assert len(trust["control_mapping"]) >= 10
    assert all(item["source_refs"] for item in trust["control_mapping"])
    assert all(item["evidence_refs"] for item in trust["control_mapping"])
    assert trust["privacy_summary"]["contains_customer_code"] is False
    assert len(trust["sbom"]["components"]) >= 2
    assert trust["vulnerability_report"]["critical_open_count"] == 0
    assert trust["vulnerability_report"]["high_open_count"] == 0
    assert trust["vulnerability_report"]["open_findings"][0]["severity"] == "medium"
    assert trust["vulnerability_report"]["open_findings"][0]["owner"] == "RNA4219"
    assert trust["vulnerability_report"]["open_findings"][0]["due_date"] == "2026-07-28"
    assert trust["vulnerability_report"]["connected_to_incident_response"] is True
    assert all(item["customer_data_sent"] is False for item in trust["subprocessors"])
    assert trust["freshness"]["sbom"] == "fixture_current"
    assert trust["attestation_summary"]["provenance_available"] is True
    assert trust["qeg_gate_policy_override"] is False
    assert trust["qeg_approval_override"] is False
    assert trust["qeg_verdict_override"] is False

    residency = json.loads((out_dir / "residency-deployment-report.json").read_text())
    assert all(mode["canonical_replay_preserved"] for mode in residency["deployment_modes"])
    assert {mode["mode"] for mode in residency["deployment_modes"]} == {
        "local_only", "ci_attached", "hosted_read_model", "private_tenant", "customer_managed", "air_gapped_export",
    }
    assert all(mode["p0a_local_first_preserved"] is True for mode in residency["deployment_modes"])
    assert all(mode["evidence_eligibility_depends_on_region"] is False for mode in residency["deployment_modes"])
    assert residency["residency_profile"]["allowed_regions"] == ["us", "eu", "jp"]
    assert residency["residency_profile"]["data_classes"]["artifact_content"] == "not_uploaded"
    assert residency["residency_profile"]["key_management"]["mode"] == "customer_managed"
    assert residency["residency_profile"]["network"]["public_ingress"] is False
    routing = {item["class"]: item for item in residency["data_class_routing"]}
    assert routing["read_model"]["rebuildable_from_canonical"] is True
    assert routing["artifact_content"]["hosted_default"] is False
    assert routing["security_review_packet"]["customer_code_included"] is False
    assert residency["connectivity_controls"]["egress_allowlist_required_for_connectors"] is True
    assert residency["connectivity_controls"]["artifact_fetch_ssrf_metadata_ip_block"] is True
    assert residency["connectivity_controls"]["air_gapped_export_has_checksum_and_offline_docs"] is True
    recovery = {item["asset"]: item for item in residency["backup_recovery"]}
    assert recovery["hosted_read_model"]["backup"] == "rebuild_from_canonical_bundle"
    assert recovery["audit_metadata"]["recovery_expectation"] == "restore_without_rewriting_record_ids"
    assert residency["summary"]["customer_source_code_hosted_by_default"] is False
    assert residency["summary"]["air_gapped_supported"] is True
    assert residency["qeg_verdict_override"] is False

    roadmap = json.loads((out_dir / "roadmap-decision-record.json").read_text())
    assert roadmap["customer_facing_available_claim"] is False

    accessibility = json.loads((out_dir / "accessibility-localization-report.json").read_text())
    assert accessibility["translated_schema_fields"] is False

    commercial = json.loads((out_dir / "commercial-contract-report.json").read_text())
    assert commercial["unsupported_available_claims"] == 0
    assert commercial["record_type"] == "commercial_contract_report"
    assert commercial["source_contract"] == "LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md"
    assert commercial["summary"]["commitment_count"] == 3
    assert commercial["summary"]["unsupported_available_claims"] == 0
    assert all(item["source_refs"] for item in commercial["commercial_commitment_register"])
    assert all(item["source_contracts"] for item in commercial["commercial_commitment_register"])
    assert all(item["owner"] == "RNA4219" for item in commercial["commercial_commitment_register"])
    assert all(item["verification_refs"] for item in commercial["commercial_commitment_register"])
    by_commitment = {
        item["commitment_id"]: item
        for item in commercial["commercial_commitment_register"]
    }
    assert by_commitment["COM-LOCAL-ARTIFACTS-001"]["status"] == "implemented"
    assert by_commitment["COM-HOSTED-RUNTIME-001"]["status"] == "proposed"
    assert by_commitment["COM-UNSUPPORTED-RUNTIME-CLAIM-001"]["status"] == "unsupported"
    assert all(
        item["available_claim"] is False
        for item in commercial["procurement_response_index"]
        if item["response_status"] in {"planned", "unsupported"}
    )
    assert commercial["contract_exceptions"][0]["owner"] == "RNA4219"
    assert commercial["contract_exceptions"][0]["expiry_at"] == "2026-12-31"
    assert commercial["contract_exceptions"][0]["risk"] == "overcommit_risk"
    assert commercial["contract_exceptions"][0]["workaround"]
    assert commercial["contract_exceptions"][0]["linked_roadmap_item"] == "roadmap:hosted-runtime"
    assert commercial["safety"]["contains_customer_source_code"] is False
    assert commercial["safety"]["contains_secret"] is False
    assert commercial["safety"]["contains_pii"] is False
    assert commercial["safety"]["contains_unsafe_artifact"] is False
    assert commercial["qeg_verdict_override"] is False

    assurance = json.loads((out_dir / "audit-assurance-pack.json").read_text())
    assert assurance["safe_to_share"] is True
    assert "product-readiness-report.json" in assurance["expected_output_refs"]
    assert "dashboard-report.html" in assurance["expected_output_refs"]
    assert assurance["audit_fixture_manifest"]["record_type"] == "audit_fixture_manifest"
    assert assurance["audit_fixture_manifest"]["source_contracts"]
    assert assurance["audit_fixture_manifest"]["input_refs"]
    assert assurance["audit_fixture_manifest"]["expected_output_refs"]
    assert assurance["audit_fixture_manifest"]["verification_commands"]
    assert assurance["audit_fixture_manifest"]["safe_to_share"] is True
    assert assurance["audit_fixture_manifest"]["redaction_status"] == "redacted"
    assert assurance["auditor_walkthrough"]["recalculates_expected_output"] is True
    assert assurance["auditor_walkthrough"]["canonical_evidence_mutated"] is False
    assert len(assurance["expected_output_index"]) == len(assurance["expected_output_refs"])
    assert all(item["status"] == "pass" for item in assurance["verification_log"])
    assert all("auditor" in item["access_policy"] for item in assurance["evidence_room_index"])
    assert all(item["safe_to_share"] is True for item in assurance["evidence_room_index"])
    assert all(item["contains_unsafe_artifact"] is False for item in assurance["evidence_room_index"])
    assert assurance["audit_finding_register"][0]["status"] == "open"
    assert assurance["audit_finding_register"][0]["owner"] == "RNA4219"
    assert assurance["audit_finding_register"][0]["due_date"] == "2026-07-28"
    assert assurance["audit_finding_register"][0]["source_refs"]
    assert assurance["assurance_summary"]["open_finding_count"] == 1
    assert assurance["assurance_summary"]["limitations_disclosed"] is True
    assert assurance["safety"]["contains_customer_source_code"] is False
    assert assurance["safety"]["contains_secret"] is False
    assert assurance["safety"]["contains_pii"] is False
    assert assurance["safety"]["contains_unsafe_artifact"] is False
    assert assurance["qeg_verdict_override"] is False

    release_pack = json.loads((out_dir / "release-candidate-pack.json").read_text())
    assert release_pack["record_type"] == "release_candidate_pack"
    assert release_pack["release_candidate_id"] == "rc-1001-fixture"
    assert release_pack["missing_required_reports"] == []
    assert release_pack["summary"]["missing_required_report_count"] == 0
    assert release_pack["summary"]["release_ready"] is True
    assert {gate["gate_id"] for gate in release_pack["release_gates"]} == {
        "RG-1", "RG-2", "RG-3", "RG-4", "RG-5", "RG-6", "RG-7", "RG-8",
    }
    assert all(gate["status"] == "pass" for gate in release_pack["release_gates"])
    assert all(gate["evidence_refs"] for gate in release_pack["release_gates"])
    assert all(gate["release_approval_substitute"] is False for gate in release_pack["release_gates"])
    assert release_pack["compatibility_matrix"]["schema_versions"] == ["HATE/v1"]
    assert release_pack["compatibility_matrix"]["supported_until"] == "2026-12-31"
    assert "rollback_instructions" in release_pack["release_notes"]
    assert release_pack["rollback"]["canonical_bundle_immutable"] is True
    assert release_pack["rollback"]["old_bundle_destroyed"] is False
    assert release_pack["rollback"]["unsupported_future_schema_safe_reject"] is True
    assert release_pack["qeg_verdict_override"] is False

    support = json.loads((out_dir / "support-diagnostic-bundle.json").read_text())
    assert support["safe_to_share"] is True
    assert "unsafe_artifact" in support["excluded"]
    assert support["support_use"] == "initial_triage_and_reproduction"
    assert support["hate_version"]
    assert support["schema_registry_version"] == "HATE/v1"
    assert support["sanitized_command"]["full_environment_variables_included"] is False
    assert support["safety_checks"]["contains_customer_code"] is False
    assert support["safety_checks"]["contains_raw_artifact_content"] is False
    assert support["safety_checks"]["contains_secret"] is False
    assert support["safety_checks"]["contains_pii"] is False
    assert support["safety_checks"]["contains_unsafe_artifact"] is False
    assert support["safety_checks"]["contains_customer_private_url"] is False
    assert support["safety_checks"]["safe_for_support_share"] is True
    assert support["adapter_registry_summary"]["source_ref"] == "adapter-conformance-report.json"
    assert support["capability_manifest_summary"]["live_saas_required"] is False
    assert support["dq_summary"]["missing_input_artifact_count"] == 0
    assert support["qeg_compatibility_summary"]["canonical_source_preserved"] is True
    assert support["qeg_compatibility_summary"]["qeg_verdict_override"] is False
    assert support["environment_policy"]["external_connector_tokens_included"] is False
    assert support["precheck_decision_override"] is False
    assert support["qeg_verdict_override"] is False

    telemetry = json.loads((out_dir / "privacy-telemetry-report.json").read_text())
    assert telemetry["safety_check"] == "pass"
    assert "customer_code" in telemetry["prohibited_signals"]

    shipyard = json.loads((out_dir / "shipyard-run-evidence.json").read_text())
    assert shipyard["shipyard_state_override"] is False
    assert shipyard["publish_gate_override"] is False
    assert "audit-assurance-pack.json" in shipyard["attached_artifacts"]


def test_p2p3_cli_product_readiness(tmp_path: Path) -> None:
    """CLI `hate product readiness` generates expected product artifacts."""
    out_dir = tmp_path / "product-cli-output"
    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "product", "readiness",
            "--bundle", "fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json",
            "--trust", "fixtures/golden/p1a-trust-minimal/expected",
            "--workflow", "fixtures/golden/p1b-workflow-minimal/expected",
            "--out", str(out_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["product_status"] == "go"
    assert output["prg_coverage"] == "7/7"
    assert (out_dir / "product-readiness-report.json").exists()


def test_p2p3_degrades_to_hold_when_input_artifact_is_missing(tmp_path: Path) -> None:
    """Missing expected input artifacts downgrade product readiness to hold."""
    bundle = Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json")
    trust_dir = tmp_path / "trust"
    workflow_dir = tmp_path / "workflow"
    shutil.copytree(Path("fixtures/golden/p1a-trust-minimal/expected"), trust_dir)
    shutil.copytree(Path("fixtures/golden/p1b-workflow-minimal/expected"), workflow_dir)
    (workflow_dir / "workflow-docs-stale.json").unlink()

    out_dir = tmp_path / "product-hold-output"
    result = generate_product_readiness(
        bundle_path=bundle,
        trust_dir=trust_dir,
        workflow_dir=workflow_dir,
        out_dir=out_dir,
    )

    readiness = json.loads((out_dir / "product-readiness-report.json").read_text())
    assert result["product_status"] == "hold"
    assert result["prg_coverage"] == "3/7"
    assert readiness["summary"]["degraded_by_input_artifacts"] is True
    assert readiness["summary"]["evaluation_score"] < 77.5
    assert readiness["summary"]["evaluation_confidence"] == "medium"
    assert any(item["component_id"] == "missing_input_artifacts" and item["points"] > 0 for item in readiness["evaluation"]["penalties"])
    assert readiness["evaluation"]["score"] <= 49
    assert readiness["evaluation"]["cap_score"] == 49
    assert any(item["cap_id"] == "missing_input_artifacts" for item in readiness["evaluation"]["caps"])
    assert readiness["evidence_summary"]["missing_input_artifacts"][0]["artifact_ref"] == "workflow-docs-stale.json"


def test_p2p3_evaluation_caps_prevent_easy_additive_scores() -> None:
    """Risk gates cap the score even when positive evidence components are high."""
    evaluation = _build_evaluation_score(
        aete={"weighted_score": 1.0, "calibration_status": "calibrated", "score_confidence": "high"},
        gates=[
            {"status": "pass"},
            {"status": "covered_by_fixture"},
            {"status": "covered_by_fixture"},
            {"status": "covered_by_artifact"},
            {"status": "covered_by_artifact"},
            {"status": "covered_by_artifact"},
            {"status": "covered_by_artifact"},
        ],
        generated_refs=[
            "pr-annotation-export.json",
            "artifact-budget-report.json",
            "attestation-report.json",
            "external-export-report.json",
            "product-error-catalog.json",
            "enterprise-risk-debt-register.json",
            "privacy-quarantine-report.json",
            "hosted-read-model-index.json",
            "domain-model-report.json",
            "rbac-matrix-report.json",
            "identity-connector-report.json",
            "enterprise-connector-report.json",
            "audit-event-log.json",
            "retention-governance-report.json",
            "release-migration-report.json",
            "entitlement-usage-report.json",
            "incident-slo-report.json",
            "adoption-health-report.json",
            "security-trust-packet.json",
            "residency-deployment-report.json",
            "roadmap-decision-record.json",
            "accessibility-localization-report.json",
            "commercial-contract-report.json",
            "audit-assurance-pack.json",
            "release-candidate-pack.json",
            "dashboard-report.html",
            "dashboard-view-model.json",
        ],
        input_gaps=[],
        doctor_findings=1,
        unverified_acceptance=2,
        workflow_acceptance={"verdict": "accepted"},
    )

    assert evaluation["raw_score"] > evaluation["score"]
    assert evaluation["score"] == 69
    assert evaluation["cap_score"] == 69
    assert {cap["cap_id"] for cap in evaluation["caps"]} >= {
        "doctor_findings_present",
        "unverified_acceptance_present",
    }
    assert evaluation["interpretation"] == "material_gaps"


def test_p2p3_hosted_read_model_query_envelope() -> None:
    """Local read model query returns the hosted API response envelope."""
    readiness_dir = Path("fixtures/golden/p2p3-product-readiness-minimal/expected")

    envelope = query_product_read_model(
        readiness_dir=readiness_dir,
        resource="product-readiness",
        request_id="req_test",
    )

    assert envelope["schema_version"] == "HATE/v1"
    assert envelope["request_id"] == "req_test"
    assert envelope["errors"] == []
    assert envelope["pagination"]["next_cursor"] is None
    assert envelope["data"]["path"] == "/v1/product-readiness"
    assert envelope["data"]["canonical_source_preserved"] is True
    assert envelope["data"]["release_gate_override"] is False
    assert envelope["source"]["record_id"] == "product_readiness_report"


def test_p2p3_cli_product_query() -> None:
    """CLI `hate product query` exposes hosted read model envelopes."""
    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "product", "query",
            "--readiness", "fixtures/golden/p2p3-product-readiness-minimal/expected",
            "--resource", "risk-debt",
            "--request-id", "req_cli",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["request_id"] == "req_cli"
    assert output["data"]["path"] == "/v1/risk-debt"
    assert output["errors"] == []


def test_p2_hosted_read_model_filter_stale_and_rbac_contract() -> None:
    """Hosted read model envelope preserves filters, stale cache, pagination, and RBAC errors."""
    readiness_dir = Path("fixtures/golden/p2p3-product-readiness-minimal/expected")

    filtered = query_product_read_model(
        readiness_dir=readiness_dir,
        resource="risk-debt",
        request_id="req_filter",
        role="auditor",
        filters={"status": "open"},
        stale_cache=True,
        cursor="cursor_001",
    )

    assert filtered["request_id"] == "req_filter"
    assert filtered["errors"] == []
    assert filtered["pagination"]["next_cursor"] == "cursor_001"
    assert filtered["data"]["role"] == "auditor"
    assert filtered["data"]["filters"] == {"status": "open"}
    assert filtered["data"]["stale_cache"] is True
    assert filtered["data"]["canonical_source_preserved"] is True
    assert filtered["data"]["attributes"]["summary"]["filter_status"] == "open"

    forbidden = query_product_read_model(
        readiness_dir=readiness_dir,
        resource="artifacts",
        request_id="req_forbidden",
        role="viewer",
    )

    assert forbidden["data"] == {}
    assert forbidden["errors"][0]["code"] == "HATE-E-PRODUCT-QUERY-403"
    assert forbidden["errors"][0]["http_status"] == 403
    assert forbidden["errors"][0]["category"] == "SEC"
    assert "remediation" in forbidden["errors"][0]


def test_p2_cli_product_query_filter_and_rbac() -> None:
    """CLI product query exposes hosted read model filter and RBAC contract."""
    filtered = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "product", "query",
            "--readiness", "fixtures/golden/p2p3-product-readiness-minimal/expected",
            "--resource", "risk-debt",
            "--request-id", "req_cli_filter",
            "--role", "auditor",
            "--filter", "status=open",
            "--stale-cache",
            "--cursor", "cursor_cli",
        ],
        capture_output=True,
        text=True,
    )
    assert filtered.returncode == 0
    filtered_output = json.loads(filtered.stdout)
    assert filtered_output["pagination"]["next_cursor"] == "cursor_cli"
    assert filtered_output["data"]["filters"] == {"status": "open"}
    assert filtered_output["data"]["stale_cache"] is True

    forbidden = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "product", "query",
            "--readiness", "fixtures/golden/p2p3-product-readiness-minimal/expected",
            "--resource", "artifacts",
            "--role", "viewer",
        ],
        capture_output=True,
        text=True,
    )
    assert forbidden.returncode == 0
    forbidden_output = json.loads(forbidden.stdout)
    assert forbidden_output["errors"][0]["code"] == "HATE-E-PRODUCT-QUERY-403"

    audit = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "product", "query",
            "--readiness", "fixtures/golden/p2p3-product-readiness-minimal/expected",
            "--resource", "audit-events",
            "--role", "auditor",
        ],
        capture_output=True,
        text=True,
    )
    assert audit.returncode == 0
    audit_output = json.loads(audit.stdout)
    assert audit_output["data"]["attributes"]["record_type"] == "audit_event_log"
    assert audit_output["data"]["attributes"]["summary"]["missing_required_events"] == []


def test_p2p3_http_read_model_endpoint() -> None:
    """HTTP read model endpoint returns REST API-compatible envelope."""
    readiness_dir = Path("fixtures/golden/p2p3-product-readiness-minimal/expected")
    handler = make_product_read_model_handler(readiness_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/product-readiness", timeout=5) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert payload["schema_version"] == "HATE/v1"
    assert payload["data"]["path"] == "/v1/product-readiness"
    assert payload["data"]["canonical_source_preserved"] is True
    assert payload["errors"] == []


def test_p2_http_read_model_endpoint_filter_and_forbidden_status() -> None:
    """HTTP handler maps query params to filters and stable RBAC status codes."""
    readiness_dir = Path("fixtures/golden/p2p3-product-readiness-minimal/expected")
    handler = make_product_read_model_handler(readiness_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/v1/risk-debt?role=auditor&filter.status=open&stale_cache=true&cursor=next_1",
            timeout=5,
        ) as response:
            assert response.status == 200
            filtered = json.loads(response.read().decode("utf-8"))
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/artifacts?role=viewer", timeout=5)
            raise AssertionError("viewer artifacts request should be forbidden")
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
            forbidden = json.loads(exc.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert filtered["pagination"]["next_cursor"] == "next_1"
    assert filtered["data"]["filters"] == {"status": "open"}
    assert filtered["data"]["stale_cache"] is True
    assert forbidden["errors"][0]["code"] == "HATE-E-PRODUCT-QUERY-403"


def test_p2_local_store_ingests_and_reloads_run_bundle_and_risk_debt(tmp_path: Path) -> None:
    """P2 local store can reload run manifest, canonical bundle, history, and risk debt."""
    store_dir = tmp_path / ".hate"
    bundle = Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json")
    readiness_dir = Path("fixtures/golden/p2p3-product-readiness-minimal/expected")

    result = ingest_local_store(
        store_dir=store_dir,
        bundle_path=bundle,
        readiness_dir=readiness_dir,
    )

    assert result["store_status"] == "success"
    assert result["run_id"] == "1001"
    assert result["history_count"] == 1
    assert (store_dir / "history-index.json").exists()
    assert (store_dir / "runs" / "1001" / "qeg-bundle.json").exists()

    history = read_history_index(store_dir)
    assert history["record_type"] == "local_store_history_index"
    assert history["summary"]["latest_run_id"] == "1001"
    assert history["summary"]["resources"] == ["run", "bundle", "risk-debt", "product-readiness", "manifest", "history"]
    assert history["publish_gate_override"] is False

    run_query = query_local_store(store_dir, resource="run")
    assert run_query["resource"] == "run"
    assert run_query["run_id"] == "1001"
    assert run_query["data"]["record_type"] == "local_store_manifest"
    assert run_query["data"]["boundaries"]["canonical_source_preserved"] is True

    bundle_query = query_local_store(store_dir, resource="bundle", run_id="1001")
    assert bundle_query["data"]["metadata"]["runId"] == "1001"
    assert bundle_query["canonical_source_preserved"] is True

    risk_query = query_local_store(store_dir, resource="risk-debt")
    assert risk_query["data"]["record_type"] == "enterprise_risk_debt_register"
    assert risk_query["data"]["summary"]["open_count"] == 0
    assert risk_query["publish_gate_override"] is False


def test_p2_cli_store_ingest_query_and_history(tmp_path: Path) -> None:
    """CLI store commands persist and reload local history resources."""
    store_dir = tmp_path / ".hate-cli"
    ingest = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "store", "ingest",
            "--store", str(store_dir),
            "--bundle", "fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json",
            "--readiness", "fixtures/golden/p2p3-product-readiness-minimal/expected",
        ],
        capture_output=True,
        text=True,
    )
    assert ingest.returncode == 0
    ingest_output = json.loads(ingest.stdout)
    assert ingest_output["run_id"] == "1001"
    assert ingest_output["history_count"] == 1

    query = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "store", "query",
            "--store", str(store_dir),
            "--resource", "risk-debt",
        ],
        capture_output=True,
        text=True,
    )
    assert query.returncode == 0
    query_output = json.loads(query.stdout)
    assert query_output["resource"] == "risk-debt"
    assert query_output["data"]["summary"]["open_count"] == 0

    history = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "store", "history",
            "--store", str(store_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert history.returncode == 0
    history_output = json.loads(history.stdout)
    assert history_output["summary"]["run_count"] == 1
    assert history_output["summary"]["latest_run_id"] == "1001"
