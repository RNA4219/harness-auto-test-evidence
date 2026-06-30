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

RELEASE_PACK_REQUIRED_REPORT_TYPES = [
    "product-readiness-report",
    "test_integrity_report",
    "artifact-safety-report",
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
        "included_reports": sorted(generated.intersection(RELEASE_REQUIRED_REPORTS)),
        "missing_required_reports": missing,
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
            "release_gate_pass_count": sum(1 for gate in gates if gate["status"] == "pass"),
            "release_gate_count": len(gates),
            "release_ready": not missing and all(gate["status"] == "pass" for gate in gates),
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


def assemble_release_candidate_pack(data: dict[str, Any]) -> dict[str, Any]:
    """Assemble a deterministic release candidate pack from required HATE reports."""

    reports = list(data.get("reports") or [])
    reports_by_type = {str(report.get("record_type")): report for report in reports}
    release_id = str(data.get("release_id") or "rc-local")
    source_version = str(data.get("source_version") or "unknown")
    required_report_types = sorted(str(item) for item in data.get("required_reports") or RELEASE_PACK_REQUIRED_REPORT_TYPES)
    report_entries = [_report_entry(report) for report in sorted(reports, key=_report_sort_key)]
    missing = [record_type for record_type in required_report_types if record_type not in reports_by_type]
    blockers: list[dict[str, Any]] = []

    for record_type in missing:
        blockers.append(_blocker("missing_required_report", "hard_dq", record_type, "Required release report is missing."))

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

    evidence_room_manifest = _evidence_room_manifest(data.get("evidence_room_artifacts") or [])
    for artifact in evidence_room_manifest["excluded_artifacts"]:
        if artifact.get("attempted_export"):
            blockers.append(_blocker(
                "quarantined_artifact_exported",
                "hard_dq",
                str(artifact.get("artifact_id") or "artifact"),
                "Unsafe or quarantined artifact attempted evidence room export.",
            ))

    qeg_refs = sorted(str(item) for item in data.get("qeg_refs") or [])
    if data.get("qeg_approval_claimed") is True:
        blockers.append(_blocker("qeg_approval_claimed", "hard_dq", "qeg", "HATE may reference QEG but cannot claim QEG approval."))

    legal_hold = _legal_hold_summary(reports)
    verdict = "blocked" if blockers else "ready"
    pack = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "release-candidate-pack",
        "release_id": release_id,
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
