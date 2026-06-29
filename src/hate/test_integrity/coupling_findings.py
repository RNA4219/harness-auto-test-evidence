"""Finding records for test coupling and oracle integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coupling_types import (
    CouplingClassification,
    CoverageClassification,
    ManualReviewClassification,
    OracleClassification,
)


@dataclass(frozen=True)
class CouplingFinding:
    """Finding for implementation-test coupling detection."""
    __test__ = False

    finding_id: str
    detector_id: str
    evidence_class: str
    triggering_records: list[str]
    source_refs: list[str]
    required_human_decision: str | None
    owner: str | None
    expiry: str | None
    readiness_effect: str
    risk_matrix_entry_ref: str | None
    reason: str
    severity: str
    profile: str
    manual_review_required: bool
    classification: CouplingClassification
    confidence: float
    affected_test_id: str
    affected_production_file: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "detector_id": self.detector_id,
            "evidence_class": self.evidence_class,
            "triggering_records": self.triggering_records,
            "sourceRefs": self.source_refs,
            "required_human_decision": self.required_human_decision,
            "owner": self.owner,
            "expiry": self.expiry,
            "readiness_effect": self.readiness_effect,
            "risk_matrix_entry_ref": self.risk_matrix_entry_ref,
            "reason": self.reason,
            "severity": self.severity,
            "profile": self.profile,
            "manual_review_required": self.manual_review_required,
            "classification": self.classification.value,
            "confidence": self.confidence,
            "affected_test_id": self.affected_test_id,
            "affected_production_file": self.affected_production_file,
        }


@dataclass(frozen=True)
class RiskOracleFinding:
    """Finding for risk without oracle detection."""
    __test__ = False

    finding_id: str
    detector_id: str
    evidence_class: str
    triggering_records: list[str]
    source_refs: list[str]
    required_human_decision: str | None
    owner: str | None
    expiry: str | None
    readiness_effect: str
    risk_matrix_entry_ref: str | None
    reason: str
    severity: str
    profile: str
    manual_review_required: bool
    risk_level: str
    oracle_classification: OracleClassification
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "detector_id": self.detector_id,
            "evidence_class": self.evidence_class,
            "triggering_records": self.triggering_records,
            "sourceRefs": self.source_refs,
            "required_human_decision": self.required_human_decision,
            "owner": self.owner,
            "expiry": self.expiry,
            "readiness_effect": self.readiness_effect,
            "risk_matrix_entry_ref": self.risk_matrix_entry_ref,
            "reason": self.reason,
            "severity": self.severity,
            "profile": self.profile,
            "manual_review_required": self.manual_review_required,
            "risk_level": self.risk_level,
            "oracle_classification": self.oracle_classification.value,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class CoverageEvidenceFinding:
    """Finding for coverage without evidence detection."""
    __test__ = False

    finding_id: str
    detector_id: str
    evidence_class: str
    triggering_records: list[str]
    source_refs: list[str]
    required_human_decision: str | None
    owner: str | None
    expiry: str | None
    readiness_effect: str
    risk_matrix_entry_ref: str | None
    reason: str
    severity: str
    profile: str
    manual_review_required: bool
    coverage_classification: CoverageClassification
    coverage_percentage: float | None
    has_executed_tests: bool
    has_oracle: bool
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "detector_id": self.detector_id,
            "evidence_class": self.evidence_class,
            "triggering_records": self.triggering_records,
            "sourceRefs": self.source_refs,
            "required_human_decision": self.required_human_decision,
            "owner": self.owner,
            "expiry": self.expiry,
            "readiness_effect": self.readiness_effect,
            "risk_matrix_entry_ref": self.risk_matrix_entry_ref,
            "reason": self.reason,
            "severity": self.severity,
            "profile": self.profile,
            "manual_review_required": self.manual_review_required,
            "coverage_classification": self.coverage_classification.value,
            "coverage_percentage": self.coverage_percentage,
            "has_executed_tests": self.has_executed_tests,
            "has_oracle": self.has_oracle,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ManualReviewRequest:
    """Request for manual review."""
    __test__ = False

    request_id: str
    risk_id: str | None
    owner: str | None
    expiry: str | None
    created_at: str
    source_refs: list[str]
    status: str
    justification: str | None
    evidence_context: list[str]
    reason: str
    blocking: bool
    required_decision: str
    classification: ManualReviewClassification
    source_ref: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "risk_id": self.risk_id,
            "owner": self.owner,
            "expiry_date": self.expiry,
            "expiry": self.expiry,
            "created_at": self.created_at,
            "source_refs": self.source_refs,
            "status": self.status,
            "justification": self.justification,
            "evidence_context": self.evidence_context,
            "reason": self.reason,
            "blocking": self.blocking,
            "required_decision": self.required_decision,
            "classification": self.classification.value,
            "sourceRef": self.source_ref,
        }
