"""Security models for artifact safety detection - HATE-PG-005A.

Data structures and enums for security findings, severity levels,
and readiness effects per PRIVACY_QUARANTINE_CONTRACT.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class SafetySignalType(str, Enum):
    """Signal types for artifact safety detection."""

    # Core detector signals
    SECRET_DETECTED = "secret_detected"
    PII_DETECTED = "pii_detected"
    UNSAFE_PATH_DETECTED = "unsafe_path_detected"
    EXTERNAL_URL_DETECTED = "external_url_detected"
    ARCHIVE_OR_BINARY_RISK = "archive_or_binary_risk"

    # Effect signals
    REDACTION_REQUIRED = "redaction_required"
    QUARANTINE_REQUIRED = "quarantine_required"

    # Sub-classifications for secrets
    SECRET_API_KEY = "secret_api_key"
    SECRET_PRIVATE_KEY = "secret_private_key"
    SECRET_TOKEN = "secret_token"
    SECRET_PASSWORD = "secret_password"

    # Sub-classifications for PII
    PII_EMAIL = "pii_email"
    PII_PHONE = "pii_phone"
    PII_ADDRESS = "pii_address"
    PII_USER_ID = "pii_user_id"
    PII_NAME = "pii_name"

    # Sub-classifications for paths
    PATH_ABSOLUTE = "path_absolute"
    PATH_HOME_DIR = "path_home_dir"
    PATH_WINDOWS_DRIVE = "path_windows_drive"
    PATH_TRAVERSAL = "path_traversal"
    PATH_TEMP_PRIVATE = "path_temp_private"
    PATH_UNC = "path_unc"

    # Sub-classifications for URLs
    URL_EXTERNAL = "url_external"
    URL_WEBHOOK = "url_webhook"
    URL_SIGNED = "url_signed"
    URL_CLOUD_STORAGE = "url_cloud_storage"
    URL_METADATA_IP = "url_metadata_ip"
    URL_LOCALHOST = "url_localhost"

    # Sub-classifications for archives/binary
    ARCHIVE_NO_MANIFEST = "archive_no_manifest"
    ARCHIVE_EXCESSIVE_SIZE = "archive_excessive_size"
    ARCHIVE_NESTED = "archive_nested"
    BINARY_BLOB = "binary_blob"
    BASE64_OPAQUE = "base64_opaque"


class Severity(str, Enum):
    """Severity levels for security findings."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReadinessEffect(str, Enum):
    """Readiness effects for security findings per PRIVACY_QUARANTINE_CONTRACT.md."""
    PASS = "pass"
    SOFT_GAP = "soft_gap"
    HOLD = "hold"
    HARD_DQ = "hard_dq"
    CONDITIONAL = "conditional"


class QuarantineAction(str, Enum):
    """Quarantine action types."""
    NONE = "none"
    QUARANTINE = "quarantine"
    REDACT = "redact"
    BLOCK = "block"
    REVIEW_REQUIRED = "review_required"


class AllowlistContext(str, Enum):
    """Allowlist contexts for fake/test secrets."""
    TEST_FIXTURE = "test_fixture"
    SYNTHETIC_PII = "synthetic_pii"
    EXAMPLE_VALUE = "example_value"
    PLACEHOLDER = "placeholder"
    DOCUMENTATION = "documentation"


# Severity levels per signal type
SEVERITY_LEVELS: dict[SafetySignalType, Severity] = {
    # Secrets - critical by default
    SafetySignalType.SECRET_DETECTED: Severity.CRITICAL,
    SafetySignalType.SECRET_API_KEY: Severity.CRITICAL,
    SafetySignalType.SECRET_PRIVATE_KEY: Severity.CRITICAL,
    SafetySignalType.SECRET_TOKEN: Severity.HIGH,
    SafetySignalType.SECRET_PASSWORD: Severity.CRITICAL,

    # PII - high by default
    SafetySignalType.PII_DETECTED: Severity.HIGH,
    SafetySignalType.PII_EMAIL: Severity.HIGH,
    SafetySignalType.PII_PHONE: Severity.HIGH,
    SafetySignalType.PII_ADDRESS: Severity.MEDIUM,
    SafetySignalType.PII_USER_ID: Severity.MEDIUM,
    SafetySignalType.PII_NAME: Severity.LOW,

    # Paths - medium to high
    SafetySignalType.UNSAFE_PATH_DETECTED: Severity.HIGH,
    SafetySignalType.PATH_ABSOLUTE: Severity.MEDIUM,
    SafetySignalType.PATH_HOME_DIR: Severity.HIGH,
    SafetySignalType.PATH_WINDOWS_DRIVE: Severity.MEDIUM,
    SafetySignalType.PATH_TRAVERSAL: Severity.HIGH,
    SafetySignalType.PATH_TEMP_PRIVATE: Severity.MEDIUM,
    SafetySignalType.PATH_UNC: Severity.HIGH,

    # URLs - medium to high
    SafetySignalType.EXTERNAL_URL_DETECTED: Severity.MEDIUM,
    SafetySignalType.URL_EXTERNAL: Severity.MEDIUM,
    SafetySignalType.URL_WEBHOOK: Severity.HIGH,
    SafetySignalType.URL_SIGNED: Severity.HIGH,
    SafetySignalType.URL_CLOUD_STORAGE: Severity.MEDIUM,
    SafetySignalType.URL_METADATA_IP: Severity.HIGH,
    SafetySignalType.URL_LOCALHOST: Severity.HIGH,

    # Archives/binary - medium to high
    SafetySignalType.ARCHIVE_OR_BINARY_RISK: Severity.MEDIUM,
    SafetySignalType.ARCHIVE_NO_MANIFEST: Severity.MEDIUM,
    SafetySignalType.ARCHIVE_EXCESSIVE_SIZE: Severity.HIGH,
    SafetySignalType.ARCHIVE_NESTED: Severity.HIGH,
    SafetySignalType.BINARY_BLOB: Severity.MEDIUM,
    SafetySignalType.BASE64_OPAQUE: Severity.MEDIUM,

    # Effect signals inherit from source
    SafetySignalType.REDACTION_REQUIRED: Severity.HIGH,
    SafetySignalType.QUARANTINE_REQUIRED: Severity.HIGH,
}


# Readiness effects per signal type
READINESS_EFFECTS: dict[SafetySignalType, ReadinessEffect] = {
    # Secrets - hard DQ unless allowlisted
    SafetySignalType.SECRET_DETECTED: ReadinessEffect.HARD_DQ,
    SafetySignalType.SECRET_API_KEY: ReadinessEffect.HARD_DQ,
    SafetySignalType.SECRET_PRIVATE_KEY: ReadinessEffect.HARD_DQ,
    SafetySignalType.SECRET_TOKEN: ReadinessEffect.HARD_DQ,
    SafetySignalType.SECRET_PASSWORD: ReadinessEffect.HARD_DQ,

    # PII - hard DQ or hold
    SafetySignalType.PII_DETECTED: ReadinessEffect.HARD_DQ,
    SafetySignalType.PII_EMAIL: ReadinessEffect.HARD_DQ,
    SafetySignalType.PII_PHONE: ReadinessEffect.HARD_DQ,
    SafetySignalType.PII_ADDRESS: ReadinessEffect.HOLD,
    SafetySignalType.PII_USER_ID: ReadinessEffect.HOLD,
    SafetySignalType.PII_NAME: ReadinessEffect.SOFT_GAP,

    # Paths - hold or soft_gap
    SafetySignalType.UNSAFE_PATH_DETECTED: ReadinessEffect.HOLD,
    SafetySignalType.PATH_ABSOLUTE: ReadinessEffect.SOFT_GAP,
    SafetySignalType.PATH_HOME_DIR: ReadinessEffect.HARD_DQ,
    SafetySignalType.PATH_WINDOWS_DRIVE: ReadinessEffect.SOFT_GAP,
    SafetySignalType.PATH_TRAVERSAL: ReadinessEffect.HARD_DQ,
    SafetySignalType.PATH_TEMP_PRIVATE: ReadinessEffect.HOLD,
    SafetySignalType.PATH_UNC: ReadinessEffect.HARD_DQ,

    # URLs - hold
    SafetySignalType.EXTERNAL_URL_DETECTED: ReadinessEffect.HOLD,
    SafetySignalType.URL_EXTERNAL: ReadinessEffect.HOLD,
    SafetySignalType.URL_WEBHOOK: ReadinessEffect.HARD_DQ,
    SafetySignalType.URL_SIGNED: ReadinessEffect.HARD_DQ,
    SafetySignalType.URL_CLOUD_STORAGE: ReadinessEffect.HOLD,
    SafetySignalType.URL_METADATA_IP: ReadinessEffect.HARD_DQ,
    SafetySignalType.URL_LOCALHOST: ReadinessEffect.HARD_DQ,

    # Archives/binary - hold
    SafetySignalType.ARCHIVE_OR_BINARY_RISK: ReadinessEffect.HOLD,
    SafetySignalType.ARCHIVE_NO_MANIFEST: ReadinessEffect.HOLD,
    SafetySignalType.ARCHIVE_EXCESSIVE_SIZE: ReadinessEffect.HARD_DQ,
    SafetySignalType.ARCHIVE_NESTED: ReadinessEffect.HARD_DQ,
    SafetySignalType.BINARY_BLOB: ReadinessEffect.SOFT_GAP,
    SafetySignalType.BASE64_OPAQUE: ReadinessEffect.HOLD,

    # Effect signals
    SafetySignalType.REDACTION_REQUIRED: ReadinessEffect.HOLD,
    SafetySignalType.QUARANTINE_REQUIRED: ReadinessEffect.HARD_DQ,
}


# Signal severity matrix for profile-based effects
SIGNAL_SEVERITY_MATRIX: dict[str, dict[SafetySignalType, tuple[Severity, ReadinessEffect]]] = {
    "default": {
        # Secrets always critical/DQ
        SafetySignalType.SECRET_DETECTED: (Severity.CRITICAL, ReadinessEffect.HARD_DQ),
        SafetySignalType.PII_DETECTED: (Severity.HIGH, ReadinessEffect.HOLD),
        SafetySignalType.UNSAFE_PATH_DETECTED: (Severity.MEDIUM, ReadinessEffect.SOFT_GAP),
        SafetySignalType.EXTERNAL_URL_DETECTED: (Severity.MEDIUM, ReadinessEffect.HOLD),
        SafetySignalType.ARCHIVE_OR_BINARY_RISK: (Severity.MEDIUM, ReadinessEffect.HOLD),
    },
    "strict": {
        # All signals elevated
        SafetySignalType.SECRET_DETECTED: (Severity.CRITICAL, ReadinessEffect.HARD_DQ),
        SafetySignalType.PII_DETECTED: (Severity.CRITICAL, ReadinessEffect.HARD_DQ),
        SafetySignalType.UNSAFE_PATH_DETECTED: (Severity.HIGH, ReadinessEffect.HOLD),
        SafetySignalType.EXTERNAL_URL_DETECTED: (Severity.HIGH, ReadinessEffect.HARD_DQ),
        SafetySignalType.ARCHIVE_OR_BINARY_RISK: (Severity.HIGH, ReadinessEffect.HOLD),
    },
    "release": {
        # Release profile - stricter than default
        SafetySignalType.SECRET_DETECTED: (Severity.CRITICAL, ReadinessEffect.HARD_DQ),
        SafetySignalType.PII_DETECTED: (Severity.CRITICAL, ReadinessEffect.HARD_DQ),
        SafetySignalType.UNSAFE_PATH_DETECTED: (Severity.HIGH, ReadinessEffect.HARD_DQ),
        SafetySignalType.EXTERNAL_URL_DETECTED: (Severity.HIGH, ReadinessEffect.HARD_DQ),
        SafetySignalType.ARCHIVE_OR_BINARY_RISK: (Severity.HIGH, ReadinessEffect.HOLD),
    },
    "product": {
        # Product profile - maximum strictness
        SafetySignalType.SECRET_DETECTED: (Severity.CRITICAL, ReadinessEffect.HARD_DQ),
        SafetySignalType.PII_DETECTED: (Severity.CRITICAL, ReadinessEffect.HARD_DQ),
        SafetySignalType.UNSAFE_PATH_DETECTED: (Severity.CRITICAL, ReadinessEffect.HARD_DQ),
        SafetySignalType.EXTERNAL_URL_DETECTED: (Severity.HIGH, ReadinessEffect.HARD_DQ),
        SafetySignalType.ARCHIVE_OR_BINARY_RISK: (Severity.HIGH, ReadinessEffect.HARD_DQ),
    },
}


# Allowlist contexts - these are safe when properly tagged
ALLOWLIST_CONTEXTS: dict[AllowlistContext, set[SafetySignalType]] = {
    AllowlistContext.TEST_FIXTURE: {
        SafetySignalType.SECRET_DETECTED,
        SafetySignalType.SECRET_API_KEY,
        SafetySignalType.SECRET_TOKEN,
    },
    AllowlistContext.SYNTHETIC_PII: {
        SafetySignalType.PII_DETECTED,
        SafetySignalType.PII_EMAIL,
        SafetySignalType.PII_PHONE,
        SafetySignalType.PII_NAME,
        SafetySignalType.PII_USER_ID,
    },
    AllowlistContext.EXAMPLE_VALUE: {
        SafetySignalType.SECRET_DETECTED,
        SafetySignalType.PII_DETECTED,
    },
    AllowlistContext.PLACEHOLDER: {
        SafetySignalType.SECRET_DETECTED,
        SafetySignalType.SECRET_PASSWORD,
        SafetySignalType.SECRET_TOKEN,
    },
    AllowlistContext.DOCUMENTATION: {
        SafetySignalType.SECRET_DETECTED,
        SafetySignalType.PII_DETECTED,
    },
}


@dataclass
class SafetyFinding:
    """Base class for safety findings."""

    finding_id: str
    detector_id: str
    signal_type: SafetySignalType
    severity: Severity
    confidence: float
    reason: str
    source_ref: str
    readiness_effect: ReadinessEffect
    redaction_hint: str | None = None
    quarantine_action: QuarantineAction = QuarantineAction.NONE
    allowlist_ref: str | None = None
    policy_refs: list[str] = field(default_factory=list)
    span: dict[str, int] | None = None  # {start_line, end_line, start_col, end_col}
    location: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert finding to dictionary for JSON serialization."""
        return {
            "finding_id": self.finding_id,
            "detector_id": self.detector_id,
            "signal_type": self.signal_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "sourceRef": self.source_ref,
            "readiness_effect": self.readiness_effect.value,
            "redaction_hint": self.redaction_hint,
            "quarantine_action": self.quarantine_action.value,
            "allowlist_ref": self.allowlist_ref,
            "policy_refs": self.policy_refs,
            "span": self.span,
            "location": self.location,
            "created_at": self.created_at,
        }


@dataclass(kw_only=True)
class ArtifactSafetyFinding(SafetyFinding):
    """Extended finding for artifact safety with additional fields."""

    artifact_id: str
    artifact_kind: str  # trace, screenshot, video, log, coverage, static, report, other
    artifact_path: str
    classification: str  # public, internal, confidential, restricted
    redaction_status: str  # not_required, redacted, pending, failed
    safe_for_summary: bool
    detected_value_snippet: str | None = None  # Safe snippet, never raw secret
    context_before: str | None = None
    context_after: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with artifact-specific fields."""
        base = super().to_dict()
        base.update({
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "artifact_path": self.artifact_path,
            "classification": self.classification,
            "redaction_status": self.redaction_status,
            "safe_for_summary": self.safe_for_summary,
            "detected_value_snippet": self.detected_value_snippet,
            "context_before": self.context_before,
            "context_after": self.context_after,
        })
        return base


@dataclass
class QuarantineDecisionRecord:
    """Quarantine decision record for artifact safety."""

    artifact_id: str
    quarantine_status: str  # none, quarantined, released
    quarantine_reason: str
    quarantine_action: QuarantineAction
    released_by: str | None = None
    released_at: str | None = None
    review_required: bool = False
    source_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "quarantine_status": self.quarantine_status,
            "quarantine_reason": self.quarantine_reason,
            "quarantine_action": self.quarantine_action.value,
            "released_by": self.released_by,
            "released_at": self.released_at,
            "review_required": self.review_required,
            "source_refs": self.source_refs,
        }


@dataclass
class ArtifactSafetyReportSummary:
    """Summary statistics for artifact safety report."""

    overall_status: str  # pass, soft_gap, hold, hard_dq
    total_artifacts_scanned: int
    findings_count: int
    secrets_detected: int
    pii_detected: int
    unsafe_paths_detected: int
    external_urls_detected: int
    archive_risks_detected: int
    quarantined_count: int
    redaction_required_count: int
    allowlisted_count: int
    safe_for_summary_count: int
    profile_effect: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_status": self.overall_status,
            "total_artifacts_scanned": self.total_artifacts_scanned,
            "findings_count": self.findings_count,
            "secrets_detected": self.secrets_detected,
            "pii_detected": self.pii_detected,
            "unsafe_paths_detected": self.unsafe_paths_detected,
            "external_urls_detected": self.external_urls_detected,
            "archive_risks_detected": self.archive_risks_detected,
            "quarantined_count": self.quarantined_count,
            "redaction_required_count": self.redaction_required_count,
            "allowlisted_count": self.allowlisted_count,
            "safe_for_summary_count": self.safe_for_summary_count,
            "profile_effect": self.profile_effect,
        }
