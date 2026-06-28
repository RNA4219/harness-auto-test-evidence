from __future__ import annotations

from typing import Any

from .p2p3_io import _stable_hash

SCHEMA_VERSION = "HATE/v1"

def _build_pr_annotation_export(
    run_id: str,
    bundle: dict[str, Any],
    aete: dict[str, Any],
    alignment: dict[str, Any],
) -> dict[str, Any]:
    risk_by_id = {
        str(node.get("id", "")): node
        for node in bundle.get("nodes", [])
        if node.get("kind") == "risk"
    }
    changed_by_id = {
        str(node.get("id", "")): node
        for node in bundle.get("nodes", [])
        if node.get("kind") == "changed_code"
    }
    annotations: list[dict[str, Any]] = []
    edges = [edge for edge in bundle.get("edges", []) if isinstance(edge, dict)]
    for edge in bundle.get("edges", []):
        if edge.get("kind") != "touches":
            continue
        changed = changed_by_id.get(str(edge.get("from", "")))
        risk = risk_by_id.get(str(edge.get("to", "")))
        if not changed or not risk:
            continue
        data = changed.get("data", {})
        risk_id = str(risk.get("id", "")).removeprefix("risk:")
        severity = str(risk.get("data", {}).get("severity", "unknown"))
        evidence_refs = _evidence_refs_for_risk(str(risk.get("id", "")), edges, bundle)
        annotation_level = _annotation_level(severity, alignment)
        annotations.append({
            "annotation_id": f"pr-annotation:{run_id}:{risk_id}:{data.get('path', '')}:{data.get('start_line', '')}",
            "annotation_level": annotation_level,
            "path": data.get("path", ""),
            "start_line": data.get("start_line"),
            "end_line": data.get("end_line"),
            "start_column": 1,
            "end_column": 1,
            "risk_id": risk_id,
            "risk_label": risk.get("label", ""),
            "severity": severity,
            "message": _annotation_message(risk_id, severity, annotation_level, alignment),
            "raw_details": {
                "risk_node_id": risk.get("id", ""),
                "changed_code_node_id": changed.get("id", ""),
                "required_test_refs": evidence_refs["required_test_refs"],
                "execution_evidence_refs": evidence_refs["execution_evidence_refs"],
                "coverage_refs": evidence_refs["coverage_refs"],
                "remediation": "Review high-risk changed path and restore missing evidence before relying on this annotation as release approval.",
            },
            "aete_summary": {
                "weighted_score": aete.get("weighted_score"),
                "score_confidence": aete.get("score_confidence"),
            },
            "dq_summary": {
                "unverified_acceptance_count": alignment.get("summary", {}).get("unverified_acceptance_count", 0),
            },
            "source_refs": changed.get("sourceRefs", []),
            "publish_gate_override": False,
            "release_gate_override": False,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "pr_annotation_export",
        "run_id": run_id,
        "annotations": annotations,
        "summary": {
            "annotation_count": len(annotations),
            "high_risk_count": sum(1 for item in annotations if item["severity"] == "high"),
            "failure_annotation_count": sum(1 for item in annotations if item["annotation_level"] == "failure"),
            "warning_annotation_count": sum(1 for item in annotations if item["annotation_level"] == "warning"),
        },
        "github_pr_annotation_compatible": True,
        "annotation_source": "canonical_qeg_bundle",
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _annotation_level(severity: str, alignment: dict[str, Any]) -> str:
    if alignment.get("summary", {}).get("unverified_acceptance_count", 0):
        return "failure"
    if severity == "high":
        return "warning"
    return "notice"


def _annotation_message(risk_id: str, severity: str, level: str, alignment: dict[str, Any]) -> str:
    unverified = alignment.get("summary", {}).get("unverified_acceptance_count", 0)
    suffix = " Missing required execution evidence is visible." if unverified else " Required evidence is linked."
    return f"HATE {level}: {severity} risk {risk_id} touches this changed path.{suffix}"


def _evidence_refs_for_risk(risk_node_id: str, edges: list[dict[str, Any]], bundle: dict[str, Any]) -> dict[str, list[str]]:
    required_tests = [
        str(edge.get("to", ""))
        for edge in edges
        if edge.get("kind") == "requires_test" and edge.get("from") == risk_node_id
    ]
    executions = [
        str(edge.get("to", ""))
        for edge in edges
        if edge.get("kind") == "evidenced_by" and str(edge.get("from", "")) in required_tests
    ]
    coverage = [
        str(edge.get("from", ""))
        for edge in edges
        if edge.get("kind") == "supports" and str(edge.get("to", "")) in required_tests
    ]
    nodes = {str(node.get("id", "")): node for node in bundle.get("nodes", []) if isinstance(node, dict)}
    return {
        "required_test_refs": [
            str(nodes.get(test_id, {}).get("data", {}).get("canonical_test_id") or test_id)
            for test_id in required_tests
        ],
        "execution_evidence_refs": executions,
        "coverage_refs": [
            str(nodes.get(coverage_id, {}).get("data", {}).get("file") or coverage_id)
            for coverage_id in coverage
        ],
    }


def _build_artifact_budget_report(run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    limits = {
        "max_artifact_size_bytes": 10_000_000,
        "max_total_size_bytes": 100_000_000,
        "default_retention_days": 30,
        "public_exposure_allowed": ["none"],
    }
    artifacts = []
    for item in bundle.get("metadata", {}).get("inputArtifacts", []):
        size_bytes = int(item.get("size_bytes", 0))
        retention = item.get("retention", "profile_default")
        public_exposure = item.get("public_exposure", "none")
        over_limit_reasons = []
        if size_bytes > limits["max_artifact_size_bytes"]:
            over_limit_reasons.append("artifact_size")
        if public_exposure not in limits["public_exposure_allowed"]:
            over_limit_reasons.append("public_exposure")
        artifacts.append({
            "artifact_ref": item.get("path", ""),
            "kind": item.get("kind", ""),
            "size_bytes": size_bytes,
            "retention": retention,
            "retention_days": _retention_days(retention, limits["default_retention_days"]),
            "storage_class": item.get("storage_class", "local-fixture"),
            "public_exposure": public_exposure,
            "over_limit": bool(over_limit_reasons),
            "over_limit_reasons": over_limit_reasons,
            "budget_action": "warn_only_do_not_drop_evidence" if over_limit_reasons else "within_budget",
        })
    total_size = sum(int(item["size_bytes"]) for item in artifacts)
    by_kind: dict[str, int] = {}
    by_exposure: dict[str, int] = {}
    for artifact in artifacts:
        by_kind[str(artifact["kind"])] = by_kind.get(str(artifact["kind"]), 0) + 1
        by_exposure[str(artifact["public_exposure"])] = by_exposure.get(str(artifact["public_exposure"]), 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "artifact_budget_report",
        "run_id": run_id,
        "budget_policy": limits,
        "artifacts": artifacts,
        "summary": {
            "artifact_count": len(artifacts),
            "total_size_bytes": total_size,
            "total_over_limit": total_size > limits["max_total_size_bytes"],
            "over_limit_count": sum(1 for item in artifacts if item["over_limit"]),
            "by_kind": by_kind,
            "by_public_exposure": by_exposure,
        },
        "canonical_decision_unchanged": True,
        "evidence_dropped_for_budget": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _retention_days(retention: Any, default_days: int) -> int:
    if isinstance(retention, int):
        return retention
    text = str(retention)
    if text.endswith("d") and text[:-1].isdigit():
        return int(text[:-1])
    return default_days


def _build_attestation_report(
    run_id: str,
    bundle: dict[str, Any],
    aete: dict[str, Any],
    alignment: dict[str, Any],
) -> dict[str, Any]:
    subject_bundle = {
        "bundle_metadata": bundle.get("metadata", {}),
        "aete": aete.get("weighted_score"),
        "alignment": alignment.get("summary", {}),
    }
    subjects = [
        {
            "subject_ref": "qeg-bundle.json",
            "subject_kind": "canonical_bundle",
            "digest": _stable_hash(bundle),
            "immutable": True,
        },
        {
            "subject_ref": "aete-score.json",
            "subject_kind": "trust_score",
            "digest": _stable_hash({"weighted_score": aete.get("weighted_score"), "score_confidence": aete.get("score_confidence")}),
            "immutable": True,
        },
        {
            "subject_ref": "requirement-evidence-alignment.json",
            "subject_kind": "workflow_alignment",
            "digest": _stable_hash({"summary": alignment.get("summary", {}), "requirements": alignment.get("requirements", [])}),
            "immutable": True,
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "attestation_report",
        "run_id": run_id,
        "attestation_mode": "optional_unsigned_fixture",
        "attestation_status": "unsigned_optional",
        "subject_refs": [subject["subject_ref"] for subject in subjects],
        "subjects": subjects,
        "subject_digest": _stable_hash(subject_bundle),
        "provenance": {
            "builder": "harness-auto-test-evidence",
            "builder_version": "0.1.0-fixture",
            "build_type": "local_canonical_replay",
            "run_id": run_id,
            "source_bundle_ref": "qeg-bundle.json",
            "source_alignment_ref": "requirement-evidence-alignment.json",
            "source_trust_ref": "aete-score.json",
        },
        "signing": {
            "configured": False,
            "signature_ref": "",
            "verification_status": "not_requested",
        },
        "release_refs": {
            "release_candidate_ref": "",
            "shipyard_evidence_ref": "shipyard-run-evidence.json",
            "compliance_pack_ref": "audit-assurance-pack.json",
        },
        "immutability": {
            "canonical_bundle_immutable": True,
            "derived_attestation_mutates_canonical": False,
        },
        "local_first_precheck_dependency": False,
        "canonical_decision_unchanged": True,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _build_external_export_report(run_id: str, bundle: dict[str, Any], alignment: dict[str, Any]) -> dict[str, Any]:
    providers = [
        ("allure", "Allure", "allure-results", "local_file_bundle"),
        ("reportportal", "ReportPortal", "launch_payload", "http_api"),
        ("codecov", "Codecov", "coverage_upload", "http_api"),
        ("sonarqube", "SonarQube", "issues_and_coverage", "http_api"),
    ]
    exports = []
    for provider_id, display_name, payload_kind, transport in providers:
        exports.append({
            "provider_id": provider_id,
            "display_name": display_name,
            "enabled": False,
            "status": "skipped_not_configured",
            "payload_kind": payload_kind,
            "transport": transport,
            "source_refs": ["qeg-bundle.json", "product-readiness-report.json"],
            "derived_from_canonical_bundle": True,
            "unsafe_artifacts_excluded": True,
            "failure_policy": "non_gating_warning",
            "failure_code": "",
            "remediation": f"Configure {display_name} connector credentials before attempting live export.",
            "canonical_decision_unchanged": True,
            "precheck_decision_override": False,
            "qeg_verdict_override": False,
            "publish_gate_override": False,
            "release_gate_override": False,
        })
    failure_fixtures = [
        {
            "provider_id": provider_id,
            "simulated_failure": "connector_unavailable",
            "stable_error_code": "HATE-EXP-001",
            "severity": "warning",
            "non_gating": True,
            "canonical_decision_unchanged": True,
        }
        for provider_id, _, _, _ in providers
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "external_export_report",
        "run_id": run_id,
        "export_scope": "optional_non_gating",
        "providers": exports,
        "failure_fixtures": failure_fixtures,
        "summary": {
            "provider_count": len(exports),
            "enabled_count": sum(1 for item in exports if item["enabled"]),
            "skipped_count": sum(1 for item in exports if item["status"] == "skipped_not_configured"),
            "failure_fixture_count": len(failure_fixtures),
            "unverified_acceptance_count": alignment.get("summary", {}).get("unverified_acceptance_count", 0),
        },
        "boundaries": {
            "external_export_is_consumer": True,
            "canonical_bundle_mutated": False,
            "precheck_decision_override": False,
            "qeg_verdict_override": False,
            "product_status_override": False,
            "publish_gate_override": False,
            "release_gate_override": False,
        },
        "source_refs": ["qeg-bundle.json", "requirement-evidence-alignment.json"],
        "canonical_decision_unchanged": True,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _build_error_catalog() -> dict[str, Any]:
    errors = [
        ("HATE-E-DQ-001", "missing_commit_sha", "Provide commit_sha in github context."),
        ("HATE-E-DQ-002", "malformed_junit", "Replace malformed JUnit XML or mark adapter failure."),
        ("HATE-E-DQ-003", "missing_artifact", "Attach the referenced artifact or remove the reference."),
        ("HATE-E-EXPORT-001", "qeg_export_ineligible", "Resolve hard DQ before QEG export."),
        ("HATE-E-TRUST-001", "trust_input_missing", "Provide frozen QEG bundle and export report."),
        ("HATE-E-PRODUCT-001", "readiness_input_missing", "Provide QEG, trust, and workflow artifact directories."),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "product_error_catalog",
        "errors": [
            {"code": code, "stable_id": stable_id, "remediation": remediation, "user_facing": True}
            for code, stable_id, remediation in errors
        ],
        "source_refs": ["docs/process/PRODUCT_ERROR_TAXONOMY.md"],
        "publish_gate_override": False,
    }


def _build_enterprise_risk_debt(run_id: str, alignment: dict[str, Any]) -> dict[str, Any]:
    debts = []
    for item in alignment.get("manual_bb_bridge", []):
        debts.append({
            "debt_id": item.get("bridge_id", ""),
            "debt_type": "no_execution",
            "owner": "RNA4219",
            "risk_id": item.get("risk_id", ""),
            "age_days": 0,
            "status": "open",
            "source_refs": item.get("source_refs", []),
            "recommended_actions": ["Add automated execution evidence.", "Keep manual-bb bridge until evidence exists."],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "enterprise_risk_debt_register",
        "run_id": run_id,
        "items": debts,
        "summary": {"open_count": len(debts), "closed_count": 0},
        "publish_gate_override": False,
    }


def _build_privacy_quarantine_report(run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    refs = [str(ref) for ref in _collect_refs(bundle)]
    unsafe = [ref for ref in refs if ".." in ref.replace("\\", "/").split("/") or ref.startswith("http://")]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "privacy_quarantine_report",
        "run_id": run_id,
        "classification_policy": "fixture-safe",
        "quarantined_artifacts": [
            {"artifact_ref": ref, "reason": "unsafe reference pattern", "safe_for_summary": False}
            for ref in unsafe
        ],
        "output_policy": {
            "summary_excludes_unsafe": True,
            "qeg_export_excludes_unsafe": True,
            "diagnostic_bundle_excludes_unsafe": True,
        },
        "summary": {"unsafe_count": len(unsafe)},
        "publish_gate_override": False,
    }


def _build_hosted_read_model_index(run_id: str, source_refs: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "hosted_read_model_index",
        "run_id": run_id,
        "views": [
            {"view": "runs", "source_artifact": "qeg-bundle.json", "stale_cache_policy": "rebuild_from_canonical_bundle"},
            {"view": "evidence", "source_artifact": "workflow-evidence.jsonl", "stale_cache_policy": "rebuild_from_canonical_bundle"},
            {"view": "risk_debt", "source_artifact": "requirement-evidence-alignment.json", "stale_cache_policy": "rebuild_from_canonical_bundle"},
            {"view": "product_readiness", "source_artifact": "product-readiness-report.json", "stale_cache_policy": "rebuild_from_canonical_bundle"},
            {"view": "dashboard", "source_artifact": "dashboard-report.html", "stale_cache_policy": "rebuild_from_canonical_bundle"},
        ],
        "rbac": ["admin", "maintainer", "developer", "auditor", "viewer"],
        "source_refs": source_refs,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _collect_refs(bundle: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in bundle.get("metadata", {}).get("inputArtifacts", []):
        if item.get("path"):
            refs.append(str(item["path"]))
    for node in bundle.get("nodes", []):
        refs.extend(str(ref) for ref in node.get("sourceRefs", []))
    for edge in bundle.get("edges", []):
        refs.extend(str(ref) for ref in edge.get("traceability", {}).get("sourceRefs", []))
    return sorted(set(refs))
