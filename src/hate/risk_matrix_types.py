"""Types and policy constants for risk coverage matrix evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


EVIDENCE_CLASSES = {
    "executable_oracle",
    "static_finding",
    "contract_check",
    "mutation_score",
    "coverage_only",
    "manual_review",
}

GAP_CLASSES = {
    "missing_execution",
    "missing_oracle",
    "missing_contract",
    "missing_review",
    "coverage_gap",
    "oracle_weak",
    "no_oracle",
    "unsupported_claim",
    "blocked_by_static_finding",
}

READINESS_EFFECTS = {
    "blocked",
    "hold",
    "soft_gap",
    "pass",
}

SEVERITY_LEVELS = {"low", "medium", "high", "critical"}

SEVERITY_AGING_DAYS = {
    "low": 30,
    "medium": 14,
    "high": 7,
    "critical": 1,
}

DEBT_TYPES = {
    "missing_execution",
    "coverage_gap",
    "flaky_unresolved",
    "matrix_gap",
    "artifact_unsafe",
    "manual_required",
    "contract_gap",
    "mutation_gap",
    "static_unresolved",
    "traceability_gap",
}

DEBT_STATUSES = {
    "open",
    "acknowledged",
    "mitigated",
    "accepted",
    "closed",
    "stale",
}


def _compute_age_days(created_at: str, now: str) -> int:
    """Compute age in days from created_at timestamp to now."""

    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
        delta = current - created
        return max(0, int(delta.total_seconds() / 86400))
    except (ValueError, TypeError):
        return 0


def _required_evidence_for_severity(severity: str) -> list[str]:
    """Determine required evidence classes based on severity."""

    if severity == "critical":
        return ["executable_oracle", "contract_check"]
    if severity == "high":
        return ["executable_oracle", "manual_review"]
    if severity == "medium":
        return ["coverage_only", "manual_review"]
    return ["coverage_only"]


@dataclass(frozen=True)
class RiskCoverageEntry:
    risk_id: str
    severity: str
    evidence_class: str | None
    oracle_strength: float
    gap_class: str | None
    readiness_effect: str
    sourceRefs: list[str]
    requirement_refs: list[str]
    required_evidence_classes: list[str]
    observed_evidence_classes: list[str]
    owner: str | None
    due_date: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "severity": self.severity,
            "evidence_class": self.evidence_class,
            "oracle_strength": self.oracle_strength,
            "gap_class": self.gap_class,
            "readiness_effect": self.readiness_effect,
            "sourceRefs": self.sourceRefs,
            "requirement_refs": self.requirement_refs,
            "required_evidence_classes": self.required_evidence_classes,
            "observed_evidence_classes": self.observed_evidence_classes,
            "owner": self.owner,
            "due_date": self.due_date,
        }


@dataclass(frozen=True)
class RiskDebtItem:
    risk_debt_id: str
    debt_type: str
    severity: str
    status: str
    risk_id: str
    owner: str | None
    created_at: str
    last_seen_at: str
    age_days: int
    source_refs: list[str]
    recommended_actions: list[str]
    blocking_profile: list[str]
    expiry_date: str | None = None
    justification: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result = {
            "risk_debt_id": self.risk_debt_id,
            "debt_type": self.debt_type,
            "severity": self.severity,
            "status": self.status,
            "risk_id": self.risk_id,
            "owner": self.owner,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "age_days": self.age_days,
            "source_refs": self.source_refs,
            "recommended_actions": self.recommended_actions,
            "blocking_profile": self.blocking_profile,
        }
        if self.expiry_date is not None:
            result["expiry_date"] = self.expiry_date
        if self.justification is not None:
            result["justification"] = self.justification
        return result
