"""Data models for test integrity findings - HATE-PG-004A.

Test integrity signals detect markers and flags that indicate incomplete
or potentially compromised test execution evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class IntegritySignalType(Enum):
    """Types of test integrity signals."""
    SKIP_DETECTED = "test_skip_detected"
    XFAIL_DETECTED = "test_xfail_detected"
    ONLY_DETECTED = "test_only_detected"
    TODO_DETECTED = "test_todo_detected"
    MOCK_ABUSE_DETECTED = "mock_abuse_detected"
    ASSERTION_QUALITY = "assertion_quality"


# Severity levels per PRODUCT_GRADE_IMPLEMENTATION_SPEC
SEVERITY_LEVELS = ("low", "medium", "high", "critical")

# Readiness effects per product-grade spec
READINESS_EFFECTS = ("pass", "soft_gap", "hold", "blocked")

# Signal severity matrix by profile and marker
# Based on PRODUCT_GRADE_IMPLEMENTATION_SPEC.md lines 387-451
SIGNAL_SEVERITY_MATRIX = {
    # skip: warning in default, hold in high/critical risk areas, block in release if high/critical
    IntegritySignalType.SKIP_DETECTED: {
        "default": {"severity": "low", "effect": "soft_gap"},
        "strict": {"severity": "medium", "effect": "soft_gap"},
        "release": {"severity": "medium", "effect": "hold"},
        "product": {"severity": "medium", "effect": "hold"},
    },
    # xfail: warning in default, hold if missing issue_ref or expiry
    IntegritySignalType.XFAIL_DETECTED: {
        "default": {"severity": "low", "effect": "soft_gap"},
        "strict": {"severity": "medium", "effect": "soft_gap"},
        "release": {"severity": "medium", "effect": "hold"},
        "product": {"severity": "medium", "effect": "hold"},
    },
    # only: hard DQ in release/product, warning in default/strict
    IntegritySignalType.ONLY_DETECTED: {
        "default": {"severity": "low", "effect": "soft_gap"},
        "strict": {"severity": "medium", "effect": "soft_gap"},
        "release": {"severity": "high", "effect": "blocked"},
        "product": {"severity": "high", "effect": "blocked"},
    },
    # todo: warning in default, block in release if not mitigated
    IntegritySignalType.TODO_DETECTED: {
        "default": {"severity": "low", "effect": "soft_gap"},
        "strict": {"severity": "medium", "effect": "soft_gap"},
        "release": {"severity": "high", "effect": "blocked"},
        "product": {"severity": "medium", "effect": "hold"},
    },
    # mock_abuse: soft_gap at boundary with oracle, hard_dq replacing behavior under test
    IntegritySignalType.MOCK_ABUSE_DETECTED: {
        "default": {"severity": "medium", "effect": "soft_gap"},
        "strict": {"severity": "medium", "effect": "conditional"},
        "release": {"severity": "high", "effect": "blocked"},
        "product": {"severity": "high", "effect": "blocked"},
    },
    # assertion_quality: soft_gap for non-risk, hold for required risk without oracle
    IntegritySignalType.ASSERTION_QUALITY: {
        "default": {"severity": "low", "effect": "soft_gap"},
        "strict": {"severity": "medium", "effect": "conditional"},
        "release": {"severity": "high", "effect": "blocked"},
        "product": {"severity": "high", "effect": "blocked"},
    },
}

# Debt types for test integrity
DEBT_TYPES = (
    "missing_execution",
    "integrity_skip",
    "integrity_xfail",
    "integrity_todo",
    "mock_abuse",
    "assertion_weak",
    "no_oracle",
)

# Debt statuses
DEBT_STATUSES = ("open", "acknowledged", "mitigated", "accepted", "closed", "stale")

# Marker kinds for canonical finding field
MARKER_KINDS = ("skip", "xfail", "only", "todo", "mock_abuse", "assertion_quality")

# Detector ID for skip/focus/todo detector
DETECTOR_ID_SKIP_FOCUS = "hate.pg004a.skip_focus_todo_detector"


@dataclass(frozen=True)
class IntegrityFinding:
    """A finding representing a detected test integrity signal.

    Per HATE-PG-004A task packet canonical fields:
    - finding_id: unique identifier for this finding
    - detector_id: identifier of the detector that produced this finding
    - severity: low, medium, high, critical
    - profile: the profile context when this finding was generated
    - affected_test_id: the canonical test ID affected
    - marker_kind: skip, xfail, only, todo, mock_abuse, assertion_quality
    - reason: human-readable explanation
    - owner: the owner if specified, or None
    - expiry: expiry date if specified, or None
    - sourceRef: primary source reference
    - readiness_effect: blocked, hold, soft_gap, pass
    - suggested_manual_review_action: suggested remediation

    Compatibility aliases (for 004B and existing tests):
    - signal_id: alias for marker_kind with "test_" prefix and "_detected" suffix
    - affected_refs: alias for [affected_test_id]
    - product_effect: alias for readiness_effect
    - recommended_action: alias for suggested_manual_review_action
    - source_refs: alias for [sourceRef]
    """
    # Canonical fields (task packet required)
    finding_id: str
    detector_id: str
    severity: str
    profile: str
    affected_test_id: str
    marker_kind: str
    reason: str
    owner: str | None
    expiry: str | None
    sourceRef: str
    readiness_effect: str
    suggested_manual_review_action: str

    # Avoid pytest collection warning
    __test__ = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize to dict with both canonical and compatibility fields."""
        return {
            # Canonical fields
            "finding_id": self.finding_id,
            "detector_id": self.detector_id,
            "severity": self.severity,
            "profile": self.profile,
            "affected_test_id": self.affected_test_id,
            "marker_kind": self.marker_kind,
            "reason": self.reason,
            "owner": self.owner,
            "expiry": self.expiry,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
            "suggested_manual_review_action": self.suggested_manual_review_action,
            # Compatibility aliases (signal_id format)
            "signal_id": f"test_{self.marker_kind}_detected",
            "affected_refs": [self.affected_test_id],
            "product_effect": self.readiness_effect,
            "recommended_action": self.suggested_manual_review_action,
            "sourceRefs": [self.sourceRef],
        }


# Alias for backward compatibility with existing code
TestIntegrityFinding = IntegrityFinding


@dataclass(frozen=True)
class IntegrityRiskDebt:
    """Risk debt entry generated from test integrity findings.

    Non-clean accepted/hold cases must generate risk debt entries.
    """
    debt_id: str
    debt_type: str
    severity: str
    status: str
    test_id: str
    marker: str
    owner: str | None
    created_at: str
    last_seen_at: str
    age_days: int
    source_refs: list[str]
    recommended_actions: list[str]
    blocking_profile: list[str]
    justification: str | None = None
    expiry_date: str | None = None

    # Avoid pytest collection warning
    __test__ = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "debt_id": self.debt_id,
            "debt_type": self.debt_type,
            "severity": self.severity,
            "status": self.status,
            "test_id": self.test_id,
            "marker": self.marker,
            "owner": self.owner,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "age_days": self.age_days,
            "source_refs": self.source_refs,
            "recommended_actions": self.recommended_actions,
            "blocking_profile": self.blocking_profile,
            "justification": self.justification,
            "expiry_date": self.expiry_date,
        }


@dataclass(frozen=True)
class AntiEvasionMatch:
    """Detection of anti-evasion patterns (renamed wrappers, etc.).

    Per PRODUCT_GRADE_IMPLEMENTATION_SPEC.md anti-evasion rules:
    - Framework-specific markers like it.only, fit, fdescribe
    - pytest -k narrowing, @pytest.mark.skip decorators
    - Production branch coupling detection
    """
    pattern: str
    test_id: str
    framework: str
    source_ref: str

    # Avoid pytest collection warning
    __test__ = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "test_id": self.test_id,
            "framework": self.framework,
            "sourceRef": self.source_ref,
        }