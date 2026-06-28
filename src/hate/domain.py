from __future__ import annotations

from typing import Any

from .p2p3_io import _stable_hash

SCHEMA_VERSION = "HATE/v1"


def build_enterprise_domain_model(run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    """Build the P3 enterprise domain model read artifact from the canonical bundle."""
    bundle_digest = _stable_hash(bundle)
    commit_sha = str(bundle.get("metadata", {}).get("commitSha", "unknown"))
    repo_ref = str(bundle.get("metadata", {}).get("repo", "local/repository"))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "enterprise_domain_model",
        "run_id": run_id,
        "source_ref": "docs/process/ENTERPRISE_DOMAIN_MODEL.md",
        "hosted_service_required": False,
        "local_first_preserved": True,
        "entities": _domain_entities(run_id, bundle_digest, commit_sha, repo_ref),
        "relationships": _domain_relationships(run_id, bundle_digest),
        "scope_boundaries": _scope_boundaries(),
        "role_model": _role_model(),
        "classification_policy": _classification_policy(),
        "retention_links": _retention_links(),
        "audit_event_contract": _audit_event_contract(),
        "read_model_contract": {
            "derived_from_canonical_bundle": True,
            "canonical_source_preserved": True,
            "stale_cache_policy": "rebuild_from_canonical_bundle",
            "qeg_verdict_override": False,
            "precheck_decision_override": False,
        },
        "acceptance": {
            "p0_p1_local_bundle_without_org": True,
            "hosted_read_model_rebuildable_from_bundle": True,
            "scope_boundaries_explicit": True,
            "auditor_read_only": True,
            "service_account_human_approval_substitute": False,
            "artifact_classification_controls_outputs": True,
            "retention_linked_to_artifact_kind_and_classification": True,
            "audit_events_append_only": True,
        },
        "source_refs": ["qeg-bundle.json", "product-readiness-report.json", "docs/process/ENTERPRISE_DOMAIN_MODEL.md"],
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _domain_entities(run_id: str, bundle_digest: str, commit_sha: str, repo_ref: str) -> list[dict[str, Any]]:
    return [
        _entity("organization", "org_local", "optional", {"local_scope": True, "hosted_required": False}),
        _entity("workspace", "wsp_local", "optional", {"parent": "org_local", "local_scope": True}),
        _entity("project", "prj_hate", "optional", {"parent": "wsp_local", "qeg_connection_optional": True}),
        _entity("repository", "repo_local", "required", {"repo_ref": repo_ref, "commit_sha": commit_sha}),
        _entity("run", f"run_{run_id}", "required", {"run_id": run_id, "retry_scope": "attempt"}),
        _entity("attempt", f"attempt_{run_id}_1", "required", {"run_id": run_id, "attempt_index": 1}),
        _entity("evidence_bundle", f"bundle_{bundle_digest.removeprefix('sha256:')}", "required", {"digest": bundle_digest, "immutable": True}),
        _entity("profile", "profile_fixture_default", "required", {"versioned": True, "approval_substitute": False}),
    ]


def _entity(kind: str, entity_id: str, p0_p1_requirement: str, attributes: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": entity_id,
        "p0_p1_requirement": p0_p1_requirement,
        "stable_id": True,
        "attributes": attributes,
    }


def _domain_relationships(run_id: str, bundle_digest: str) -> list[dict[str, str]]:
    bundle_id = f"bundle_{bundle_digest.removeprefix('sha256:')}"
    return [
        {"from": "org_local", "to": "wsp_local", "kind": "contains"},
        {"from": "wsp_local", "to": "prj_hate", "kind": "contains"},
        {"from": "prj_hate", "to": "repo_local", "kind": "contains"},
        {"from": "repo_local", "to": f"run_{run_id}", "kind": "produces"},
        {"from": f"run_{run_id}", "to": f"attempt_{run_id}_1", "kind": "has_attempt"},
        {"from": f"attempt_{run_id}_1", "to": bundle_id, "kind": "produces"},
        {"from": "prj_hate", "to": "profile_fixture_default", "kind": "uses_profile"},
    ]


def _scope_boundaries() -> dict[str, Any]:
    return {
        "organization": {"mix_artifacts_across_orgs": False, "mix_audit_across_orgs": False},
        "workspace": {"separates_departments": True},
        "project": {"quality_unit": "product_or_repo_group"},
        "repository": {"source_control_boundary": True},
        "run_attempt": {"retry_reproducibility_boundary": True},
        "local_mapping": {
            "organization_optional": True,
            "workspace_optional": True,
            "project_optional": True,
            "default_scope": "local",
        },
    }


def _role_model() -> list[dict[str, Any]]:
    return [
        {"role": "admin", "read_only": False, "may_replace_qeg_approval": False},
        {"role": "maintainer", "read_only": False, "may_change_org_retention": False},
        {"role": "developer", "read_only": False, "may_change_profile_approval": False},
        {"role": "auditor", "read_only": True, "may_mutate_artifact": False},
        {"role": "viewer", "read_only": True, "may_access_raw_artifact": False},
        {"role": "service_account", "read_only": False, "may_replace_human_approval": False},
    ]


def _classification_policy() -> list[dict[str, Any]]:
    return [
        {"classification": "public", "summary_allowed": True, "export_allowed": True, "diagnostic_allowed": True, "default_retention_days": 180},
        {"classification": "internal", "summary_allowed": "conditional", "export_allowed": "conditional", "diagnostic_allowed": True, "default_retention_days": 90},
        {"classification": "confidential", "summary_allowed": False, "export_allowed": False, "diagnostic_allowed": False, "default_retention_days": 30},
        {"classification": "restricted", "summary_allowed": False, "export_allowed": False, "diagnostic_allowed": False, "default_retention_days": 0, "quarantine_required": True},
    ]


def _retention_links() -> list[dict[str, Any]]:
    return [
        {"artifact_kind": "canonical_json", "classification": "public", "retention_days": 180},
        {"artifact_kind": "coverage", "classification": "internal", "retention_days": 90},
        {"artifact_kind": "trace_screenshot_video", "classification": "confidential", "retention_days": 30},
        {"artifact_kind": "diagnostic_bundle", "classification": "internal", "retention_days": 14},
        {"artifact_kind": "quarantine_metadata", "classification": "restricted", "retention_days": 365},
    ]


def _audit_event_contract() -> dict[str, Any]:
    events = [
        "bundle.created",
        "bundle.exported",
        "profile.changed",
        "adapter.changed",
        "artifact.accessed",
        "artifact.quarantined",
        "riskdebt.created",
        "diagnostic.generated",
    ]
    return {
        "append_only": True,
        "required_events": events,
        "qeg_approval_substitute": False,
    }
