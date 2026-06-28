from __future__ import annotations

from typing import Any

from .p2p3_io import _stable_hash

SCHEMA_VERSION = "HATE/v1"

REQUIRED_AUDIT_EVENTS = [
    "bundle.created",
    "bundle.exported",
    "profile.changed",
    "adapter.changed",
    "artifact.accessed",
    "artifact.quarantined",
    "riskdebt.created",
    "diagnostic.generated",
]


def build_audit_event_log(run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    bundle_digest = _stable_hash(bundle)
    commit_sha = str(bundle.get("metadata", {}).get("commitSha", "unknown"))
    profile_hash = "sha256:fixture-profile"
    events = [
        _event(1, "bundle.created", run_id, "service_account:ci", {
            "bundle_id": bundle_digest,
            "run_id": run_id,
            "commit_sha": commit_sha,
            "profile_hash": profile_hash,
        }),
        _event(2, "bundle.exported", run_id, "service_account:ci", {
            "bundle_id": bundle_digest,
            "target": "qeg",
            "status": "success",
        }),
        _event(3, "profile.changed", run_id, "user:maintainer-fixture", {
            "profile_id": "profile_fixture_default",
            "before_hash": "sha256:fixture-profile-prev",
            "after_hash": profile_hash,
            "actor": "user:maintainer-fixture",
        }),
        _event(4, "adapter.changed", run_id, "user:maintainer-fixture", {
            "adapter_id": "adapter_junit_v1",
            "version": "v1",
            "actor": "user:maintainer-fixture",
        }),
        _event(5, "artifact.accessed", run_id, "user:auditor-fixture", {
            "artifact_id": "art_summary_product_readiness",
            "actor": "user:auditor-fixture",
            "reason": "audit walkthrough fixture",
        }),
        _event(6, "artifact.quarantined", run_id, "service_account:safety-fixture", {
            "artifact_id": "art_unsafe_fixture",
            "reason": "unsafe reference pattern",
            "detector": "privacy_quarantine_fixture",
        }),
        _event(7, "riskdebt.created", run_id, "service_account:workflow-fixture", {
            "risk_id": "risk:manual-bridge-fixture",
            "source_refs": ["requirement-evidence-alignment.json"],
            "owner": "RNA4219",
        }),
        _event(8, "diagnostic.generated", run_id, "user:support-fixture", {
            "bundle_id": bundle_digest,
            "requester": "user:support-fixture",
            "redaction_status": "redacted",
        }),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "audit_event_log",
        "run_id": run_id,
        "append_only": True,
        "safe_to_share": True,
        "redaction_status": "redacted",
        "source_contracts": ["ENTERPRISE_DOMAIN_MODEL.md", "AUDIT_FIXTURE_ASSURANCE_CONTRACT.md"],
        "input_refs": ["qeg-bundle.json", "domain-model-report.json", "rbac-matrix-report.json"],
        "expected_output_refs": ["audit-event-log.json", "audit-assurance-pack.json"],
        "verification_commands": [
            "uv run pytest tests/test_p2p3.py -q",
            "uv run python -m hate product readiness ...",
        ],
        "events": events,
        "summary": {
            "event_count": len(events),
            "required_event_count": len(REQUIRED_AUDIT_EVENTS),
            "missing_required_events": sorted(set(REQUIRED_AUDIT_EVENTS) - {event["event_type"] for event in events}),
            "sequence_monotonic": _sequence_monotonic(events),
            "append_only": True,
        },
        "access_policy": {
            "auditor_read_allowed": True,
            "viewer_read_allowed": False,
            "developer_read_allowed": False,
            "raw_artifact_included": False,
        },
        "immutability": {
            "event_ids_stable": True,
            "rewrite_allowed": False,
            "delete_allowed": False,
        },
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _event(seq: int, event_type: str, run_id: str, actor: str, fields: dict[str, Any]) -> dict[str, Any]:
    event_id = f"aud_20260629_{seq:04d}"
    return {
        "event_id": event_id,
        "sequence": seq,
        "event_type": event_type,
        "run_id": run_id,
        "actor": actor,
        "occurred_at": f"2026-06-29T00:{seq:02d}:00Z",
        "fields": fields,
        "append_only": True,
        "safe_to_share": True,
    }


def _sequence_monotonic(events: list[dict[str, Any]]) -> bool:
    sequences = [int(event["sequence"]) for event in events]
    return sequences == sorted(sequences) and len(sequences) == len(set(sequences))
