"""Retention policy evaluation for enterprise control projections."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .legal_hold import evaluate_legal_hold, legal_hold_preserved


DEFAULT_RETENTION_DAYS = {
    "public": 365,
    "internal": 365,
    "confidential": 180,
    "restricted": 0,
    "regulated": 365,
}


@dataclass
class RetentionEvaluation:
    """Retention decision that never deletes evidence during evaluation."""

    resource_id: str
    resource_type: str
    retention_policy_id: str
    classification: str
    action: str
    readiness_effect: str
    reason: str
    purge_eligible_metadata_only: bool = False
    canonical_evidence_deleted: bool = False
    legal_hold_preserved: bool = True
    findings: list[dict[str, Any]] = field(default_factory=list)
    sourceRefs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "retention_policy_id": self.retention_policy_id,
            "classification": self.classification,
            "action": self.action,
            "readiness_effect": self.readiness_effect,
            "reason": self.reason,
            "purge_eligible_metadata_only": self.purge_eligible_metadata_only,
            "canonical_evidence_deleted": self.canonical_evidence_deleted,
            "legal_hold_preserved": self.legal_hold_preserved,
            "findings": self.findings,
            "sourceRefs": self.sourceRefs,
        }


def evaluate_retention_policy(
    resource: dict[str, Any],
    policy: dict[str, Any] | None = None,
    *,
    profile: str = "default",
    now: str | None = None,
    operation: str = "read",
) -> RetentionEvaluation:
    """Evaluate retention/hold state without deleting or mutating evidence."""

    policy = policy or {}
    now_dt = _parse_time(now) if now else datetime.now(timezone.utc)
    source_refs = list(resource.get("sourceRefs") or [])
    resource_id = str(resource.get("resource_id") or resource.get("bundle_id") or resource.get("artifact_id") or "")
    resource_type = str(resource.get("resource_type") or "bundle")
    classification = str(resource.get("classification") or "internal")
    policy_id = str(resource.get("retention_policy_id") or policy.get("policy_id") or "")

    if resource_type in {"bundle", "canonical_bundle"} and not policy_id:
        effect = "hard_dq" if profile in {"release", "regulated"} else "hold"
        return _evaluation(
            resource_id,
            resource_type,
            policy_id,
            classification,
            "hold",
            effect,
            "missing_retention_policy",
            source_refs,
            _finding("missing_retention_policy", effect, source_refs),
        )

    hold_eval = evaluate_legal_hold(resource, operation, profile)
    if hold_eval["readiness_effect"] == "hard_dq":
        return _evaluation(
            resource_id,
            resource_type,
            policy_id,
            classification,
            "blocked_by_legal_hold",
            "hard_dq",
            hold_eval["status"],
            source_refs,
            hold_eval["finding"],
        )

    if _migration_lost_legal_hold(resource):
        effect = "hard_dq" if profile in {"release", "regulated"} else "hold"
        return _evaluation(
            resource_id,
            resource_type,
            policy_id,
            classification,
            "hold",
            effect,
            "legal_hold_lost",
            source_refs,
            _finding("legal_hold_lost", effect, source_refs),
            legal_hold_ok=False,
        )

    expires_at = resource.get("expires_at") or _expiry_from_created_at(resource, policy, classification)
    if expires_at and _parse_time(str(expires_at)) <= now_dt:
        if (resource.get("legal_hold") or {}).get("status") == "active":
            return _evaluation(
                resource_id,
                resource_type,
                policy_id,
                classification,
                "retain",
                "pass",
                "retention_expired_but_legal_hold_active",
                source_refs,
            )
        return _evaluation(
            resource_id,
            resource_type,
            policy_id,
            classification,
            "metadata_purge_eligible",
            "soft_gap",
            "retention_expired_metadata_only",
            source_refs,
            _finding("retention_expired_metadata_only", "soft_gap", source_refs),
            purge_eligible=True,
        )

    return _evaluation(
        resource_id,
        resource_type,
        policy_id,
        classification,
        "retain",
        "pass",
        "retention_policy_valid",
        source_refs,
    )


def build_retention_legal_hold_report(
    resources: list[dict[str, Any]],
    policies: dict[str, dict[str, Any]] | None = None,
    *,
    profile: str = "default",
    now: str | None = None,
) -> dict[str, Any]:
    """Build enterprise-control-report compatible retention section."""

    policies = policies or {}
    evaluations = [
        evaluate_retention_policy(
            resource,
            policies.get(str(resource.get("retention_policy_id") or "")),
            profile=profile,
            now=now,
            operation=str(resource.get("operation") or "read"),
        ).to_dict()
        for resource in resources
    ]
    findings = [finding for item in evaluations for finding in item.get("findings", [])]
    return {
        "schema_version": "HATE/v1",
        "record_type": "enterprise-control-report",
        "connector_dry_runs": [],
        "retention_evaluations": evaluations,
        "findings": findings,
        "summary": {
            "retention_evaluation_count": len(evaluations),
            "hold_count": sum(1 for item in evaluations if item["readiness_effect"] == "hold"),
            "hard_dq_count": sum(1 for item in evaluations if item["readiness_effect"] == "hard_dq"),
            "soft_gap_count": sum(1 for item in evaluations if item["readiness_effect"] == "soft_gap"),
            "readiness_effect": _max_effect(item["readiness_effect"] for item in evaluations),
        },
        "sourceRefs": sorted({ref for item in evaluations for ref in item.get("sourceRefs", [])}),
    }


def _migration_lost_legal_hold(resource: dict[str, Any]) -> bool:
    before = resource.get("before_migration")
    after = resource.get("after_migration")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    return not legal_hold_preserved(before, after)


def _expiry_from_created_at(resource: dict[str, Any], policy: dict[str, Any], classification: str) -> str | None:
    if resource.get("expires_at"):
        return str(resource["expires_at"])
    created_at = resource.get("created_at")
    if not created_at:
        return None
    days = int(policy.get("retention_days", DEFAULT_RETENTION_DAYS.get(classification, 365)))
    if days < 1:
        return str(created_at)
    created_dt = _parse_time(str(created_at))
    return (created_dt.timestamp() + days * 86400).__str__()


def _parse_time(value: str) -> datetime:
    try:
        numeric = float(value)
    except ValueError:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.fromtimestamp(numeric, timezone.utc)


def _evaluation(
    resource_id: str,
    resource_type: str,
    policy_id: str,
    classification: str,
    action: str,
    effect: str,
    reason: str,
    source_refs: list[str],
    finding: dict[str, Any] | None = None,
    *,
    purge_eligible: bool = False,
    legal_hold_ok: bool = True,
) -> RetentionEvaluation:
    return RetentionEvaluation(
        resource_id=resource_id,
        resource_type=resource_type,
        retention_policy_id=policy_id,
        classification=classification,
        action=action,
        readiness_effect=effect,
        reason=reason,
        purge_eligible_metadata_only=purge_eligible,
        canonical_evidence_deleted=False,
        legal_hold_preserved=legal_hold_ok,
        findings=[finding] if finding else [],
        sourceRefs=source_refs,
    )


def _finding(code: str, effect: str, source_refs: list[str]) -> dict[str, Any]:
    severity = {"hard_dq": "critical", "hold": "high", "soft_gap": "medium"}.get(effect, "info")
    return {
        "code": code,
        "severity": severity,
        "message": code.replace("_", " "),
        "sourceRef": source_refs[0] if source_refs else "",
    }


def _max_effect(effects: Any) -> str:
    order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
    return max(effects, key=lambda item: order.get(item, 0), default="pass")
