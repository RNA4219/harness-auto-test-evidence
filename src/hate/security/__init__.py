"""Security detection package - HATE-PG-005A.

This package provides detectors for artifact safety and security signals including:
- secret_detected: tokens, API keys, private keys, passwords
- pii_detected: email, phone, address, user ID, name
- unsafe_path_detected: absolute paths, home directory, Windows drive, traversal, temp/private paths
- external_url_detected: external URLs, webhooks, signed URLs, cloud storage URLs
- archive_or_binary_risk: archives, binary blobs, base64 opaque payloads
- redaction_required / quarantine_required: readiness effects
"""

from .models import (
    SafetyFinding,
    ArtifactSafetyFinding,
    SafetySignalType,
    READINESS_EFFECTS,
    SEVERITY_LEVELS,
    SIGNAL_SEVERITY_MATRIX,
    ALLOWLIST_CONTEXTS,
)
from .artifact_safety import (
    detect_artifact_safety_signals,
    build_artifact_safety_report,
    scan_for_secrets,
    scan_for_pii,
    scan_for_unsafe_paths,
    scan_for_external_urls,
    scan_for_archive_risk,
)
from .artifact_lifecycle import (
    ArtifactLifecycleFinding,
    build_artifact_lifecycle_report,
    evaluate_artifact_lifecycle_fixture,
)

__all__ = [
    "ArtifactLifecycleFinding",
    "SafetyFinding",
    "ArtifactSafetyFinding",
    "SafetySignalType",
    "READINESS_EFFECTS",
    "SEVERITY_LEVELS",
    "SIGNAL_SEVERITY_MATRIX",
    "ALLOWLIST_CONTEXTS",
    "detect_artifact_safety_signals",
    "build_artifact_safety_report",
    "build_artifact_lifecycle_report",
    "evaluate_artifact_lifecycle_fixture",
    "scan_for_secrets",
    "scan_for_pii",
    "scan_for_unsafe_paths",
    "scan_for_external_urls",
    "scan_for_archive_risk",
]
