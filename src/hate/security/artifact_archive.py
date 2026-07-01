"""Archive and binary artifact risk scanning."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

from .artifact_safety import (
    ARCHIVE_EXTENSIONS,
    ARCHIVE_SIZE_LIMIT_BYTES,
    BASE64_DECODED_SIZE_THRESHOLD,
    BASE64_PATTERN,
    BINARY_EXTENSIONS,
    POLICY_REF_BY_DETECTOR,
    SEVERITY_LEVELS,
    _findings_from_matches,
    _profile_effect,
)


def scan_archive_and_binary(
    artifact_path: str,
    content: str,
    artifact_size: int,
    artifact_id: str,
    profile: str,
    allowlist_ref: str | None,
    *,
    has_manifest: bool = False,
    nested_depth: int = 0,
) -> list[dict[str, Any]]:
    del artifact_id, allowlist_ref
    findings: list[dict[str, Any]] = []
    extension = Path(artifact_path).suffix.lower()
    if extension in ARCHIVE_EXTENSIONS and not has_manifest:
        findings.extend(
            _findings_from_matches(
                "archive_detector",
                "archive_or_binary_risk",
                "",
                artifact_path,
                [(0, 0, artifact_path)],
                reason="archive artifact without manifest",
                severity=SEVERITY_LEVELS["archive_or_binary_risk"],
                readiness_effect="hard_dq",
                redaction_hint="Attach a manifest and rerun scan",
                quarantine_action="quarantine",
                policy_refs=POLICY_REF_BY_DETECTOR["archive_or_binary_risk"],
                allowlist_ref=None,
            )
        )
    if extension in ARCHIVE_EXTENSIONS and artifact_size > ARCHIVE_SIZE_LIMIT_BYTES:
        findings.extend(
            _findings_from_matches(
                "archive_detector",
                "archive_or_binary_risk",
                "",
                artifact_path,
                [(0, 0, artifact_path)],
                reason="archive exceeds 50MB limit",
                severity="high",
                readiness_effect=_profile_effect(profile, critical=True),
                redaction_hint="Keep metadata only or attach approved manifest before export",
                quarantine_action="quarantine",
                policy_refs=POLICY_REF_BY_DETECTOR["archive_or_binary_risk"],
                allowlist_ref=None,
            )
        )
    if nested_depth > 1:
        findings.extend(
            _findings_from_matches(
                "archive_detector",
                "archive_or_binary_risk",
                "",
                artifact_path,
                [(0, 0, artifact_path)],
                reason="nested archive without approved manifest",
                severity="high",
                readiness_effect=_profile_effect(profile, critical=True),
                redaction_hint="Reject nested archive or provide bounded manifest",
                quarantine_action="quarantine",
                policy_refs=POLICY_REF_BY_DETECTOR["archive_or_binary_risk"],
                allowlist_ref=None,
            )
        )
    if extension in BINARY_EXTENSIONS:
        findings.extend(
            _findings_from_matches(
                "archive_detector",
                "archive_or_binary_risk",
                "",
                artifact_path,
                [(0, 0, artifact_path)],
                reason="binary blob artifact detected",
                severity=SEVERITY_LEVELS["archive_or_binary_risk"],
                readiness_effect="hold",
                redaction_hint="Validate binary purpose and manifest",
                quarantine_action="redact",
                policy_refs=POLICY_REF_BY_DETECTOR["archive_or_binary_risk"],
                allowlist_ref=None,
            )
        )
    for match in BASE64_PATTERN.finditer(content):
        try:
            decoded = base64.b64decode(match.group(), validate=True)
        except (binascii.Error, ValueError):
            continue
        if len(decoded) <= BASE64_DECODED_SIZE_THRESHOLD:
            continue
        findings.extend(
            _findings_from_matches(
                "archive_detector",
                "archive_or_binary_risk",
                content,
                artifact_path,
                [(match.start(), match.end(), match.group())],
                reason="opaque base64 payload over 4KB decoded detected",
                severity=SEVERITY_LEVELS["archive_or_binary_risk"],
                readiness_effect=_profile_effect(profile, critical=True),
                redaction_hint="Decode and inspect base64 payload",
                quarantine_action="quarantine",
                policy_refs=POLICY_REF_BY_DETECTOR["archive_or_binary_risk"],
                allowlist_ref=None,
            )
        )
    return findings
