from __future__ import annotations

import hashlib
import json
from typing import Any

from .expansion_runner import EXPANSION_REPORT_TYPES

SCHEMA_VERSION = "HATE/v1"

RELEASE_REQUIRED_REPORTS = [
    "product-readiness-report.json",
    "domain-model-report.json",
    "rbac-matrix-report.json",
    "audit-event-log.json",
    "retention-governance-report.json",
    "identity-connector-report.json",
    "enterprise-connector-report.json",
    "security-trust-packet.json",
    "residency-deployment-report.json",
    "commercial-contract-report.json",
    "audit-assurance-pack.json",
    "governance-portfolio-report.json",
]

CANONICAL_RELEASE_REQUIRED_REPORTS = [
    "adapter-conformance-report.json",
    "schema-validation-report.json",
    "store-replay-report.json",
    "api-contract-report.json",
    "dashboard-uat-report.json",
    "test-integrity-report.json",
    "security-quarantine-report.json",
    "enterprise-control-report.json",
    "scale-performance-report.json",
    "migration-compatibility-report.json",
    "commercial-truthfulness-report.json",
    "support-ops-report.json",
    "release-candidate-pack.json",
]

LEGACY_CANONICAL_REPORT_ALIASES = {
    "api-contract-report.json": ["hosted-read-model-index.json"],
    "dashboard-uat-report.json": ["dashboard-view-model.json", "dashboard-report.html"],
    "security-quarantine-report.json": ["privacy-quarantine-report.json"],
    "enterprise-control-report.json": [
        "domain-model-report.json",
        "rbac-matrix-report.json",
        "audit-event-log.json",
        "retention-governance-report.json",
        "identity-connector-report.json",
        "enterprise-connector-report.json",
        "residency-deployment-report.json",
    ],
    "scale-performance-report.json": ["artifact-budget-report.json", "enterprise-metrics-report.json"],
    "migration-compatibility-report.json": ["release-migration-report.json"],
    "commercial-truthfulness-report.json": ["commercial-contract-report.json"],
    "support-ops-report.json": ["support-diagnostic-bundle.json", "incident-slo-report.json"],
}

RELEASE_PACK_REQUIRED_REPORT_TYPES = [
    "product-readiness-report",
    "adapter-conformance-report",
    "schema_validation_report",
    "store_replay_report",
    "test_integrity_report",
    "security-quarantine-report",
    "safe-diagnostic-bundle",
    "store_manifest",
    "scale-performance-report",
    "api-contract-report",
    "dashboard-uat-report",
    "enterprise-control-report",
    "support-ops-report",
    "migration-compatibility-report",
    "commercial-truthfulness-report",
    *EXPANSION_REPORT_TYPES,
]


def build_release_candidate_pack(run_id: str, generated_refs: list[str]) -> dict[str, Any]:
    generated = set(generated_refs)
    missing = [ref for ref in RELEASE_REQUIRED_REPORTS if ref not in generated]
    canonical_coverage = _canonical_report_coverage(generated)
    gates = [
        _gate("RG-1", "Schema", ["product-readiness-report.json"]),
        _gate("RG-2", "Fixture", ["audit-assurance-pack.json"]),
        _gate("RG-3", "Adapter", ["rbac-matrix-report.json"]),
        _gate("RG-4", "Replay", ["audit-assurance-pack.json"]),
        _gate("RG-5", "QEG", ["product-readiness-report.json"]),
        _gate("RG-6", "Security", ["security-trust-packet.json", "privacy-quarantine-report.json"]),
        _gate("RG-7", "Docs", ["customer-docs-index.json", "commercial-contract-report.json"]),
        _gate("RG-8", "Rollback", ["release-migration-report.json"]),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "release_candidate_pack",
        "run_id": run_id,
        "release_candidate_id": f"rc-{run_id}-fixture",
        "channel": "preview",
        "required_reports": RELEASE_REQUIRED_REPORTS,
        "canonical_required_reports": CANONICAL_RELEASE_REQUIRED_REPORTS,
        "included_reports": sorted(generated.intersection(RELEASE_REQUIRED_REPORTS)),
        "missing_required_reports": missing,
        "canonical_report_mapping": canonical_coverage["mapping"],
        "missing_canonical_reports": canonical_coverage["missing"],
        "release_gates": gates,
        "compatibility_matrix": {
            "cli_version": "0.1.0-fixture",
            "schema_versions": ["HATE/v1"],
            "adapter_sdk_versions": ["1.x-fixture"],
            "qeg_export_versions": ["QEG/v1"],
            "profile_versions": ["default/v1"],
            "supported_until": "2026-12-31",
        },
        "release_notes": {
            "summary": "Local artifact release candidate fixture.",
            "breaking_changes": [],
            "deprecated_fields": [],
            "migration_steps": [],
            "known_issues": ["Hosted runtime evidence is not claimed by this release candidate."],
            "security_notes": ["Security trust packet fixture is included."],
            "artifact_safety_changes": ["Unsafe artifacts remain excluded from public outputs."],
            "qeg_compatibility": "QEG/v1 fixture compatible",
            "rollback_instructions": "Restore previous artifact bundle; canonical bundles are immutable.",
        },
        "rollback": {
            "canonical_bundle_immutable": True,
            "old_bundle_destroyed": False,
            "unsupported_future_schema_safe_reject": True,
            "migration_dry_run_available": True,
            "rollback_note_ref": "release-migration-report.json",
        },
        "summary": {
            "required_report_count": len(RELEASE_REQUIRED_REPORTS),
            "included_required_report_count": len(RELEASE_REQUIRED_REPORTS) - len(missing),
            "missing_required_report_count": len(missing),
            "missing_canonical_report_count": len(canonical_coverage["missing"]),
            "release_gate_pass_count": sum(1 for gate in gates if gate["status"] == "pass"),
            "release_gate_count": len(gates),
            "release_ready": not missing and all(gate["status"] == "pass" for gate in gates),
            "canonical_product_grade_ready": not canonical_coverage["missing"],
        },
        "source_refs": [
            "RELEASE_MIGRATION_POLICY.md",
            "IMPLEMENTATION_ROADMAP_CHECKLIST.md",
            "product-readiness-report.json",
        ],
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _canonical_report_coverage(generated: set[str]) -> dict[str, Any]:
    mapping = []
    missing = []
    for canonical_ref in CANONICAL_RELEASE_REQUIRED_REPORTS:
        aliases = LEGACY_CANONICAL_REPORT_ALIASES.get(canonical_ref, [])
        observed = [ref for ref in [canonical_ref, *aliases] if ref in generated]
        covered = bool(observed)
        mapping.append(
            {
                "canonical_report": canonical_ref,
                "covered": covered,
                "observed_refs": sorted(observed),
                "legacy_aliases": aliases,
            }
        )
        if not covered:
            missing.append(canonical_ref)
    return {"mapping": mapping, "missing": missing}


def assemble_release_candidate_pack(data: dict[str, Any]) -> dict[str, Any]:
    """Assemble a deterministic release candidate pack from required HATE reports."""

    reports = list(data.get("reports") or [])
    reports_by_type = {str(report.get("record_type")): report for report in reports}
    reports_by_id = {str(report.get("report_id") or report.get("id") or report.get("record_type")): report for report in reports}
    release_id = str(data.get("release_id") or "rc-local")
    source_version = str(data.get("source_version") or "unknown")
    required_specs = _required_report_specs(data.get("required_reports") or RELEASE_PACK_REQUIRED_REPORT_TYPES)
    required_report_types = sorted(spec["report_id"] for spec in required_specs)
    report_entries = [_report_entry(report) for report in sorted(reports, key=_report_sort_key)]
    missing_specs = [
        spec for spec in required_specs
        if spec["report_id"] not in reports_by_type and spec["report_id"] not in reports_by_id
    ]
    missing = [
        _missing_report_entry(spec) if spec["structured"] else spec["report_id"]
        for spec in missing_specs
    ]
    blockers: list[dict[str, Any]] = []

    for spec in missing_specs:
        blockers.append(_blocker("missing_required_report", "hard_dq", spec["report_id"], "Required release report is missing."))

    for spec in required_specs:
        report = reports_by_type.get(spec["report_id"]) or reports_by_id.get(spec["report_id"])
        if report and spec["hash"]:
            actual_hash = str(report.get("report_hash") or _stable_hash(report))
            if actual_hash != spec["hash"]:
                blockers.append(_blocker("stale_required_report_hash", "hard_dq", spec["report_id"], "Required report hash is stale or does not match expected input."))

    for report in sorted(reports, key=_report_sort_key):
        record_type = str(report.get("record_type") or "")
        effect = _report_readiness_effect(report)
        if effect == "hard_dq":
            blockers.append(_blocker("dependency_hard_dq", "hard_dq", record_type, "Required dependency has hard_dq readiness."))
        if _has_open_manual_review(report):
            blockers.append(_blocker("open_manual_review", "hard_dq", record_type, "Open manual review blocks release candidate pack."))
        if record_type == "commercial-truthfulness-report" and _has_unsupported_commercial_claim(report):
            blockers.append(_blocker(
                "unsupported_commercial_claim",
                "hard_dq",
                record_type,
                "Unsupported commercial claim is not release eligible.",
            ))
        if record_type == "migration-compatibility-report" and _has_migration_hard_dq(report):
            blockers.append(_blocker("migration_compatibility_hard_dq", "hard_dq", record_type, "Migration compatibility report contains a hard DQ."))
        if _legal_hold_lost(report):
            blockers.append(_blocker("legal_hold_lost", "hard_dq", record_type, "Legal hold or protected metadata was lost or mutated."))

    evidence_room_manifest = _evidence_room_manifest(data.get("evidence_room_artifacts") or [])
    for artifact in evidence_room_manifest["excluded_artifacts"]:
        if artifact.get("attempted_export"):
            blockers.append(_blocker(
                "unsafe_artifact_included",
                "hard_dq",
                str(artifact.get("artifact_id") or "artifact"),
                "Unsafe artifact was included or requested for evidence room output.",
            ))
            blockers.append(_blocker(
                "quarantined_artifact_exported",
                "hard_dq",
                str(artifact.get("artifact_id") or "artifact"),
                "Unsafe or quarantined artifact attempted evidence room export.",
            ))

    qeg_refs = _qeg_refs(data.get("qeg_refs") or {})
    if qeg_refs["validate_status"] == "failed":
        blockers.append(_blocker("qeg_validate_failed", "hard_dq", "qeg", "QEG validate failed."))
    if qeg_refs["import_status"] == "failed":
        blockers.append(_blocker("qeg_import_failed", "hard_dq", "qeg", "QEG import failed."))
    if data.get("qeg_approval_claimed") is True:
        blockers.append(_blocker("qeg_approval_claimed", "hard_dq", "qeg", "HATE may reference QEG but cannot claim QEG approval."))

    legal_hold = _legal_hold_summary(reports)
    verdict = "blocked" if blockers else "ready"
    pack = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "release-candidate-pack",
        "release_id": release_id,
        "release_candidate_id": release_id,
        "source_version": source_version,
        "required_reports": required_report_types,
        "reports": report_entries,
        "missing_required_reports": missing,
        "verdict": verdict,
        "readiness_effect": "hard_dq" if blockers else "pass",
        "blockers": blockers,
        "manual_review_state": _manual_review_state(reports),
        "commercial_claim_state": _commercial_claim_state(reports_by_type.get("commercial-truthfulness-report")),
        "qeg_refs": qeg_refs,
        "qeg_approval_claimed": False,
        "evidence_room_manifest": evidence_room_manifest,
        "legal_hold": legal_hold,
        "sign_off": {
            "status": "blocked" if blockers else str(data.get("sign_off", {}).get("status") or "pending"),
            "owner": str(data.get("sign_off", {}).get("owner") or ""),
            "sourceRefs": sorted(str(item) for item in data.get("sign_off", {}).get("sourceRefs", [])),
        },
        "summary": {
            "required_report_count": len(required_report_types),
            "included_required_report_count": len(required_report_types) - len(missing),
            "missing_required_report_count": len(missing),
            "blocker_count": len(blockers),
            "hard_dq_count": sum(1 for blocker in blockers if blocker["readiness_effect"] == "hard_dq"),
            "release_ready": not blockers,
        },
        "sourceRefs": sorted({ref for report in report_entries for ref in report["sourceRefs"]}),
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }
    pack["pack_hash"] = _stable_hash({key: value for key, value in pack.items() if key != "pack_hash"})
    return pack


def _required_report_specs(raw_required: list[Any]) -> list[dict[str, Any]]:
    specs = []
    for item in raw_required:
        if isinstance(item, dict):
            report_id = str(item.get("report_id") or item.get("record_type") or item.get("id") or "")
            if report_id:
                specs.append({
                    "report_id": report_id,
                    "path": str(item.get("path") or ""),
                    "hash": str(item.get("hash") or item.get("report_hash") or ""),
                    "required_for_stage": str(item.get("required_for_stage") or ""),
                    "structured": True,
                })
        else:
            report_id = str(item)
            specs.append({
                "report_id": report_id,
                "path": "",
                "hash": "",
                "required_for_stage": "",
                "structured": False,
            })
    return sorted(specs, key=lambda spec: spec["report_id"])


def _missing_report_entry(spec: dict[str, Any]) -> dict[str, str]:
    return {
        "report_id": spec["report_id"],
        "path": spec["path"],
        "required_for_stage": spec["required_for_stage"],
    }


def _gate(gate_id: str, name: str, evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "name": name,
        "status": "pass",
        "evidence_refs": evidence_refs,
        "release_approval_substitute": False,
    }


def _report_entry(report: dict[str, Any]) -> dict[str, Any]:
    record_type = str(report.get("record_type") or "")
    report_id = str(report.get("report_id") or report.get("id") or record_type)
    return {
        "record_type": record_type,
        "report_id": report_id,
        "report_hash": str(report.get("report_hash") or _stable_hash(report)),
        "readiness_effect": _report_readiness_effect(report),
        "sourceRefs": sorted(str(item) for item in report.get("sourceRefs") or report.get("source_refs") or []),
        "legal_hold": bool(report.get("legal_hold") or report.get("legal_hold_active")),
    }


def _report_sort_key(report: dict[str, Any]) -> tuple[str, str]:
    return (str(report.get("record_type") or ""), str(report.get("report_id") or report.get("id") or ""))


def _report_readiness_effect(report: dict[str, Any]) -> str:
    candidates = [
        report.get("readiness_effect"),
        report.get("verdict"),
        report.get("status"),
        (report.get("summary") or {}).get("readiness_effect"),
        (report.get("summary") or {}).get("overall_status"),
    ]
    lowered = {str(item).lower() for item in candidates if item is not None}
    if lowered & {"hard_dq", "blocked", "fail", "failed"}:
        return "hard_dq"
    if lowered & {"hold", "pending"}:
        return "hold"
    if lowered & {"soft_gap", "warning"}:
        return "soft_gap"
    return "pass"


def _has_open_manual_review(report: dict[str, Any]) -> bool:
    summary = report.get("summary") or {}
    return bool(
        report.get("manual_review_state") in {"open", "pending", "required"}
        or summary.get("open_manual_review_count", 0)
        or summary.get("manual_review_required_count", 0)
    )


def _has_unsupported_commercial_claim(report: dict[str, Any]) -> bool:
    summary = report.get("summary") or {}
    if summary.get("unsupported_claim_count", 0) and _report_readiness_effect(report) != "pass":
        return True
    return any(
        claim.get("release_eligible") is False and claim.get("declared_status") in {"unsupported", "planned", "candidate"}
        for claim in report.get("claims", [])
    )


def _has_migration_hard_dq(report: dict[str, Any]) -> bool:
    if _report_readiness_effect(report) == "hard_dq":
        return True
    decision = str(report.get("compatibility_decision") or report.get("compatibility_class") or "").lower()
    if decision in {"hard_dq", "blocked", "unsupported"}:
        return True
    return any(
        str(finding.get("readiness_effect") or "").lower() == "hard_dq"
        for finding in report.get("findings", [])
        if isinstance(finding, dict)
    )


def _legal_hold_lost(report: dict[str, Any]) -> bool:
    summary = report.get("summary") or {}
    if report.get("legal_hold_lost") or report.get("protected_metadata_mutated"):
        return True
    if summary.get("legal_hold_preserved") is False or summary.get("protected_metadata_preserved") is False:
        return True
    return any(
        str(finding.get("code") or "") in {
            "legal_hold_lost",
            "protected_metadata_mutated",
            "platform_store_migration_legal_hold_lost",
            "platform_store_migration_raw_access_audit_removed",
        }
        for finding in report.get("findings", [])
        if isinstance(finding, dict)
    )


def _qeg_refs(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return {
            "validate_ref": str(raw.get("validate_ref") or ""),
            "import_ref": str(raw.get("import_ref") or ""),
            "gate_ref": str(raw.get("gate_ref") or ""),
            "record_ref": str(raw.get("record_ref") or ""),
            "validate_status": str(raw.get("validate_status") or "pass"),
            "import_status": str(raw.get("import_status") or "pass"),
            "gate_status": str(raw.get("gate_status") or "not_claimed"),
            "approval_claimed": False,
        }
    refs = sorted(str(item) for item in raw or [])
    return {
        "validate_ref": refs[0] if len(refs) > 0 else "",
        "import_ref": refs[1] if len(refs) > 1 else "",
        "gate_ref": refs[2] if len(refs) > 2 else "",
        "record_ref": refs[3] if len(refs) > 3 else "",
        "validate_status": "pass",
        "import_status": "pass",
        "gate_status": "not_claimed",
        "approval_claimed": False,
    }


def _manual_review_state(reports: list[dict[str, Any]]) -> dict[str, Any]:
    open_refs = [
        str(report.get("report_id") or report.get("record_type"))
        for report in reports
        if _has_open_manual_review(report)
    ]
    return {
        "status": "open" if open_refs else "closed",
        "open_refs": sorted(open_refs),
    }


def _commercial_claim_state(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"status": "missing", "unsupported_claim_count": 0, "release_eligible_claim_count": 0}
    summary = report.get("summary") or {}
    unsupported = int(summary.get("unsupported_claim_count", 0) or 0)
    release_eligible = int(summary.get("release_eligible_claim_count", 0) or 0)
    return {
        "status": "blocked" if _has_unsupported_commercial_claim(report) else "ready",
        "unsupported_claim_count": unsupported,
        "release_eligible_claim_count": release_eligible,
    }


def _evidence_room_manifest(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for artifact in sorted(artifacts, key=lambda item: str(item.get("artifact_id") or "")):
        artifact_id = str(artifact.get("artifact_id") or "")
        unsafe = bool(
            artifact.get("contains_unsafe_artifact")
            or artifact.get("contains_secret")
            or artifact.get("contains_pii")
            or artifact.get("quarantine_status") == "quarantined"
            or artifact.get("safe_to_share") is False
        )
        entry = {
            "artifact_id": artifact_id,
            "artifact_hash": str(artifact.get("artifact_hash") or _stable_hash(artifact)),
            "sourceRefs": sorted(str(item) for item in artifact.get("sourceRefs") or []),
        }
        if unsafe:
            excluded.append({
                **entry,
                "reason": "unsafe_or_quarantined",
                "attempted_export": bool(artifact.get("include_in_evidence_room")),
            })
        else:
            included.append({**entry, "safe_to_share": True})
    return {
        "included_artifacts": included,
        "excluded_artifacts": excluded,
        "unsafe_artifact_excluded_count": len(excluded),
    }


def _legal_hold_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    held = sorted(
        str(report.get("report_id") or report.get("record_type"))
        for report in reports
        if report.get("legal_hold") or report.get("legal_hold_active")
    )
    return {
        "preserved": True,
        "held_report_refs": held,
    }


def _blocker(code: str, effect: str, ref: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "readiness_effect": effect,
        "ref": ref,
        "message": message,
    }


def _stable_hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
