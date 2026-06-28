from __future__ import annotations

from typing import Any

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


def _gate(gate_id: str, name: str, evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "name": name,
        "status": "pass",
        "evidence_refs": evidence_refs,
        "release_approval_substitute": False,
    }
