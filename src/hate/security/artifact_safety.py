"""HATE-PG-005A Artifact-safety detector for minimal implementation.

Implements `scan_artifact_safety(fixture)` and five core detectors:
secret_detected, pii_detected, unsafe_path_detected,
external_url_detected, archive_or_binary_risk.
"""

from __future__ import annotations

import re
import uuid
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


READINESS_LEVELS = {
    "pass": 0,
    "soft_gap": 1,
    "hold": 2,
    "hard_dq": 3,
}

SEVERITY_LEVELS = {
    "secret_detected": "high",
    "pii_detected": "high",
    "unsafe_path_detected": "medium",
    "external_url_detected": "medium",
    "archive_or_binary_risk": "high",
}

POLICY_REF_BY_DETECTOR = {
    "secret_detected": ["FR-SEC-001"],
    "pii_detected": ["FR-SEC-002"],
    "unsafe_path_detected": ["FR-SEC-003"],
    "external_url_detected": ["FR-SEC-004"],
    "archive_or_binary_risk": ["FR-SEC-004"],
}

SECRET_PATTERNS = [
    (
        "api_key_like",
        re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?key|secret[_-]?key|api_secret)\s*[:=]\s*['\"]([A-Za-z0-9_]{20,})['\"]"),
    ),
    (
        "github_token_like",
        re.compile(r"(?i)\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22}_[A-Za-z0-9]{24})\b"),
    ),
    ( "aws_access_key_like", re.compile(r"(?i)\bAKIA[0-9A-Z]{16}\b") ),
    ( "openai_like", re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{40,}\b") ),
    ( "password_like", re.compile(r"(?i)\b(?:password|passwd|credential)\s*[:=]\s*['\"][^'\"\\s]{8,}['\"]") ),
]

PRIVATE_KEY_PATTERNS = [
    ("pem_private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

PII_PATTERNS = [
    ("pii_email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("pii_phone", re.compile(r"\b\+?\d{1,3}[-.\s]?(?:\d{1,4}[-.\s])?\d{2,4}[-.\s]\d{2,4}[-.\s]\d{3,4}\b")),
    ("pii_user_id", re.compile(r"(?i)\b(?:user[_-]?id|customer[_-]?id)\s*[:=]\s*['\"][^'\"]+['\"]")),
    ("pii_name", re.compile(r"(?i)\b(?:full[_-]?name|name)\s*[:=]\s*['\"][A-Za-z]+ [A-Za-z]+['\"]")),
]

PATH_PATTERNS = [
    (
        re.compile(r"[A-Za-z]:\\(?:Users|\\[Ss]hared|Program Files|ProgramData)\\[^\\\"'\\s]+"),
        "Windows user/path",
    ),
    (
        re.compile(r"/home/[A-Za-z0-9._-]+/[^\s\"']+"),
        "Unix home path",
    ),
    (
        re.compile(r"(?:^|\\s)(/etc|/var/(?:tmp|log|private))/[^\s\"']+"),
        "Absolute/private filesystem path",
    ),
    (
        re.compile(r"\.\./\.\.?|\.\\\.?\\", re.IGNORECASE),
        "Path traversal",
    ),
]

ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".bz2"}
BINARY_EXTENSIONS = {".exe", ".dll", ".so", ".dylib", ".bin", ".dat"}

URL_PATTERN = re.compile(r"https?://[^\s\"'<>`]+")
ALLOWLIST_URL_DOMAINS = {
    "docs.python.org",
    "readthedocs.io",
    "pypi.org",
    "github.com",
}
SUSPICIOUS_URL_HINTS = (
    "x-amz-signature",
    "x-amz-meta",
    "signature=",
    "signed_url",
    "exp=",
    "token=",
    "oauth_token",
    "access_token",
    "bearer=",
    "secret=",
)
BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
BASE64_DECODED_SIZE_THRESHOLD = 4096
ARCHIVE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024


def _finding_id() -> str:
    return f"finding-{uuid.uuid4().hex[:12]}"


def _line_number(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def _is_allowlisted_secret(content: str, allowlist_ref: str | None, line_number: int) -> bool:
    if allowlist_ref:
        return True
    if re.search(r"(?i)@allowlist|allowlist[_-]?fixture|test[_-]?secret|fake[_-]?secret", content):
        return True
    # keep a narrow allowlist only when the signal appears on the same/adjacent lines
    return False


def _is_synthetic_pii_allowed(content: str, allowlist_ref: str | None, line_number: int) -> bool:
    if allowlist_ref:
        return True
    marker_hit = re.search(r"(?i)synthetic|@allowlist|sample[_-]?pii|fake[_-]?pii", content)
    return bool(marker_hit)


def _is_url_allowlisted(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == domain or host.endswith(f".{domain}") for domain in ALLOWLIST_URL_DOMAINS)


def _is_url_suspicious(url: str) -> bool:
    lower = url.lower()
    return any(token in lower for token in SUSPICIOUS_URL_HINTS)


def _readiness_max(*levels: str) -> str:
    return sorted(levels, key=lambda level: READINESS_LEVELS.get(level, 0))[-1]


def _profile_effect(profile: str, *, allowlisted: bool = False, critical: bool = False) -> str:
    """Return profile-based effect for artifact safety risks."""
    if allowlisted:
        return "soft_gap"
    if critical:
        return "hard_dq"
    normalized = (profile or "default").lower()
    if normalized in {"release", "product"}:
        return "hard_dq"
    if normalized == "strict":
        return "hold"
    return "soft_gap"


def _fixture_text_for_scan(fixture: dict[str, Any]) -> str:
    if "content" in fixture:
        return str(fixture.get("content", ""))
    if "encoded_payload" in fixture:
        return str(fixture.get("encoded_payload", ""))
    return json.dumps(fixture, sort_keys=True)


def _artifact_path_from_fixture(fixture: dict[str, Any]) -> str:
    if fixture.get("artifact_path"):
        return str(fixture["artifact_path"])
    artifact_info = fixture.get("artifact_info")
    if isinstance(artifact_info, dict):
        if artifact_info.get("path"):
            return str(artifact_info["path"])
        if artifact_info.get("filename"):
            return str(artifact_info["filename"])
    if fixture.get("metadata", {}).get("leaked_from"):
        return str(fixture["metadata"]["leaked_from"])
    return "artifact"


def _artifact_size_from_fixture(fixture: dict[str, Any], content: str) -> int:
    if fixture.get("artifact_size") is not None:
        return int(fixture["artifact_size"])
    artifact_info = fixture.get("artifact_info")
    if isinstance(artifact_info, dict) and artifact_info.get("size_bytes") is not None:
        return int(artifact_info["size_bytes"])
    return len(content.encode("utf-8"))


def _has_manifest(fixture: dict[str, Any]) -> bool:
    if fixture.get("manifest_present") is not None:
        return bool(fixture["manifest_present"])
    metadata = fixture.get("metadata")
    if isinstance(metadata, dict) and metadata.get("manifest_present") is not None:
        return bool(metadata["manifest_present"])
    return False


def _findings_from_matches(
    detector_id: str,
    finding_type: str,
    content: str,
    artifact_path: str,
    matches: list[tuple[int, int, str]],
    *,
    reason: str,
    severity: str,
    readiness_effect: str,
    redaction_hint: str,
    quarantine_action: str,
    policy_refs: list[str],
    allowlist_ref: str | None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for start, end, snippet in matches:
        line_number = _line_number(content, start)
        findings.append(
            {
                "finding_id": _finding_id(),
                "detector_id": detector_id,
                "finding_type": finding_type,
                "severity": severity,
                "confidence": 0.93,
                "reason": reason,
                "sourceRef": f"{artifact_path}:{line_number}",
                "location": artifact_path,
                "span": {"start": start, "end": end},
                "redaction_hint": redaction_hint,
                "quarantine_action": quarantine_action,
                "readiness_effect": readiness_effect,
                "allowlist_ref": allowlist_ref,
                "policy_refs": policy_refs,
            }
        )
    return findings


def _scan_secrets(content: str, artifact_id: str, artifact_path: str, profile: str, allowlist_ref: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for _, pattern in PRIVATE_KEY_PATTERNS:
        for match in pattern.finditer(content):
            matches = [(match.start(), match.end(), match.group())]
            findings.extend(
                _findings_from_matches(
                    "secret_detector",
                    "secret_detected",
                    content,
                    artifact_path,
                    matches,
                    reason="private-key-like block detected",
                    severity="critical",
                    readiness_effect=_profile_effect(profile, critical=True),
                    redaction_hint="Remove private key and rotate credentials",
                    quarantine_action="quarantine",
                    policy_refs=POLICY_REF_BY_DETECTOR["secret_detected"],
                    allowlist_ref=allowlist_ref,
                )
            )
    for pattern_name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(content):
            line_number = _line_number(content, match.start())
            if pattern_name == "password_like" and _is_allowlisted_secret(content, allowlist_ref, line_number):
                # test fixture / synthetic data can be explicitly allowed
                findings.extend(
                    _findings_from_matches(
                        "secret_detector",
                        "secret_detected",
                        content,
                        artifact_path,
                        [(match.start(), match.end(), match.group())],
                        reason=f"allowed secret-like marker detected ({pattern_name})",
                        severity="low",
                        readiness_effect=_profile_effect(profile, allowlisted=True),
                        redaction_hint="Keep placeholder token only",
                        quarantine_action="none",
                        policy_refs=POLICY_REF_BY_DETECTOR["secret_detected"],
                        allowlist_ref=allowlist_ref,
                    )
                )
                continue
            if _is_allowlisted_secret(content, allowlist_ref, line_number):
                findings.extend(
                    _findings_from_matches(
                        "secret_detector",
                        "secret_detected",
                        content,
                        artifact_path,
                        [(match.start(), match.end(), match.group())],
                        reason="allowlist token matched; treated as fixture-safe",
                        severity="low",
                        readiness_effect=_profile_effect(profile, allowlisted=True),
                        redaction_hint="Keep synthetic placeholder",
                        quarantine_action="none",
                        policy_refs=POLICY_REF_BY_DETECTOR["secret_detected"],
                        allowlist_ref=allowlist_ref,
                    )
                )
            else:
                findings.extend(
                    _findings_from_matches(
                        "secret_detector",
                        "secret_detected",
                        content,
                        artifact_path,
                        [(match.start(), match.end(), match.group())],
                        reason=f"real-like secret detected ({pattern_name})",
                        severity=SEVERITY_LEVELS["secret_detected"],
                        readiness_effect=_profile_effect(profile),
                        redaction_hint="Replace with placeholder and rotate credentials",
                        quarantine_action="quarantine",
                        policy_refs=POLICY_REF_BY_DETECTOR["secret_detected"],
                        allowlist_ref=None,
                    )
                )
    return findings


def _scan_pii(content: str, artifact_path: str, profile: str, allowlist_ref: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    profile = (profile or "default").lower()
    for _, pattern in PII_PATTERNS:
        for match in pattern.finditer(content):
            line_number = _line_number(content, match.start())
            allowed = _is_synthetic_pii_allowed(content, allowlist_ref, line_number)
            readiness = _profile_effect(profile, allowlisted=allowed)
            action = "none" if allowed else "redact"
            findings.extend(
                _findings_from_matches(
                    "pii_detector",
                    "pii_detected",
                    content,
                    artifact_path,
                    [(match.start(), match.end(), match.group())],
                    reason="pii-like value detected",
                    severity=SEVERITY_LEVELS["pii_detected"],
                    readiness_effect=readiness,
                    redaction_hint="Redact or tokenize PII values before release",
                    quarantine_action=action,
                    policy_refs=POLICY_REF_BY_DETECTOR["pii_detected"],
                    allowlist_ref=allowlist_ref,
                )
            )
    return findings


def _scan_paths(content: str, artifact_path: str, profile: str, allowlist_ref: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, label in PATH_PATTERNS:
        for match in pattern.finditer(content):
            matches = [(match.start(), match.end(), match.group())]
            findings.extend(
                _findings_from_matches(
                    "unsafe_path_detector",
                    "unsafe_path_detected",
                    content,
                    artifact_path,
                    matches,
                    reason=f"{label} detected",
                    severity=SEVERITY_LEVELS["unsafe_path_detected"],
                    readiness_effect=_profile_effect(profile, critical="traversal" in label.lower()),
                    redaction_hint="Replace with sanitized/test-safe path",
                    quarantine_action="quarantine",
                    policy_refs=POLICY_REF_BY_DETECTOR["unsafe_path_detected"],
                    allowlist_ref=None,
                )
            )
    return findings


def _scan_urls(content: str, artifact_path: str, profile: str, allowlist_ref: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for match in URL_PATTERN.finditer(content):
        url = match.group()
        line_number = _line_number(content, match.start())
        allowed = allowlist_ref is not None or _is_url_allowlisted(url)
        if _is_url_suspicious(url):
            findings.extend(
                _findings_from_matches(
                    "external_url_detector",
                    "external_url_detected",
                    content,
                    artifact_path,
                    [(match.start(), match.end(), url)],
                    reason="signed/private-looking URL detected",
                    severity=SEVERITY_LEVELS["external_url_detected"],
                    readiness_effect=_profile_effect(profile, critical=True),
                    redaction_hint="Remove signed URL; use allowlisted documentation URL",
                    quarantine_action="quarantine",
                    policy_refs=POLICY_REF_BY_DETECTOR["external_url_detected"],
                    allowlist_ref=None,
                )
            )
            continue
        if allowed:
            findings.extend(
                _findings_from_matches(
                    "external_url_detector",
                    "external_url_detected",
                    content,
                    artifact_path,
                    [(match.start(), match.end(), url)],
                    reason="allowlisted external URL",
                    severity="low",
                    readiness_effect="pass",
                    redaction_hint="No redaction required",
                    quarantine_action="none",
                    policy_refs=POLICY_REF_BY_DETECTOR["external_url_detected"],
                    allowlist_ref="allowlist",
                )
            )
            continue
        findings.extend(
            _findings_from_matches(
                "external_url_detector",
                "external_url_detected",
                content,
                artifact_path,
                [(match.start(), match.end(), url)],
                reason="external URL detected",
                severity=SEVERITY_LEVELS["external_url_detected"],
                readiness_effect=_profile_effect(profile),
                redaction_hint="Replace with allowlisted docs/dependency URL or block at runtime",
                quarantine_action="redact",
                policy_refs=POLICY_REF_BY_DETECTOR["external_url_detected"],
                allowlist_ref=None,
            )
        )
    return findings


def _scan_archive_and_binary(
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
    from .artifact_archive import scan_archive_and_binary

    return scan_archive_and_binary(
        artifact_path,
        content,
        artifact_size,
        artifact_id,
        profile,
        allowlist_ref,
        has_manifest=has_manifest,
        nested_depth=nested_depth,
    )


def _aggregate_readiness(levels: list[str]) -> str:
    if not levels:
        return "pass"
    return _readiness_max(*levels)


def scan_artifact_safety(fixture: dict[str, Any]) -> dict[str, Any]:
    """Scan a fixture dict and return an artifact safety report."""

    artifact_path = _artifact_path_from_fixture(fixture)
    artifact_id = str(fixture.get("artifact_id", Path(artifact_path).stem or "artifact"))
    content = _fixture_text_for_scan(fixture)
    profile = str(fixture.get("profile", "default"))
    artifact_size = _artifact_size_from_fixture(fixture, content)
    allowlist_ref = fixture.get("allowlist_ref")
    has_manifest = _has_manifest(fixture)
    nested_depth = int(fixture.get("metadata", {}).get("nested_depth", fixture.get("artifact_info", {}).get("nested_depth", 0)) or 0)

    findings: list[dict[str, Any]] = []
    findings.extend(_scan_secrets(content, artifact_id, artifact_path, profile, allowlist_ref))
    findings.extend(_scan_pii(content, artifact_path, profile, allowlist_ref))
    findings.extend(_scan_paths(content, artifact_path, profile, allowlist_ref))
    findings.extend(_scan_urls(content, artifact_path, profile, allowlist_ref))
    findings.extend(
        _scan_archive_and_binary(
            artifact_path,
            content,
            artifact_size,
            artifact_id,
            profile,
            allowlist_ref,
            has_manifest=has_manifest,
            nested_depth=nested_depth,
        )
    )

    source_refs = sorted({artifact_path, *[f["sourceRef"] for f in findings]})
    readiness = _aggregate_readiness([finding["readiness_effect"] for finding in findings])
    redaction_required = any(f["quarantine_action"] in {"redact", "quarantine"} for f in findings)
    quarantine_required = any(f["quarantine_action"] == "quarantine" for f in findings)

    finding_types = {}
    for finding in findings:
        finding_types[finding["finding_type"]] = finding_types.get(finding["finding_type"], 0) + 1

    return {
        "schema_version": "HATE/v1",
        "record_type": "artifact-safety-report",
        "artifact_id": artifact_id,
        "profile": profile,
        "findings": findings,
        "quarantine_required": quarantine_required,
        "redaction_required": redaction_required,
        "readiness_effect": readiness,
        "sourceRefs": source_refs,
        "summary": {
            "finding_count": len(findings),
            "finding_types": finding_types,
            "artifact_size": artifact_size,
            "artifact_path": artifact_path,
        },
    }


def detect_artifact_safety_signals(
    content: str,
    artifact_id: str,
    artifact_path: str,
    artifact_kind: str,
    artifact_size: int = 0,
    profile: str = "default",
    *,
    has_manifest: bool = False,
    allowlist_ref: str | None = None,
) -> list[dict[str, Any]]:
    del artifact_id, artifact_kind
    report = scan_artifact_safety(
        {
            "artifact_id": artifact_id,
            "artifact_path": artifact_path,
            "artifact_size": artifact_size,
            "content": content,
            "profile": profile,
            "manifest_present": has_manifest,
            "allowlist_ref": allowlist_ref,
        }
    )
    return report["findings"]


def build_artifact_safety_report(
    artifact_id: str,
    artifact_path: str,
    artifact_kind: str,
    content: str,
    artifact_size: int = 0,
    profile: str = "default",
    *,
    has_manifest: bool = False,
    allowlist_ref: str | None = None,
) -> dict[str, Any]:
    del artifact_kind
    return scan_artifact_safety(
        {
            "artifact_id": artifact_id,
            "artifact_path": artifact_path,
            "artifact_size": artifact_size,
            "content": content,
            "profile": profile,
            "manifest_present": has_manifest,
            "allowlist_ref": allowlist_ref,
        }
    )


def scan_for_secrets(
    content: str,
    artifact_id: str,
    artifact_path: str,
    artifact_kind: str,
    profile: str = "default",
) -> list[dict[str, Any]]:
    del artifact_id, artifact_kind
    return _scan_secrets(content, artifact_id, artifact_path, profile, allowlist_ref=None)


def scan_for_pii(
    content: str,
    artifact_id: str,
    artifact_path: str,
    artifact_kind: str,
    profile: str = "default",
) -> list[dict[str, Any]]:
    del artifact_id, artifact_kind
    return _scan_pii(content, artifact_path, profile, allowlist_ref=None)


def scan_for_unsafe_paths(
    content: str,
    artifact_id: str,
    artifact_path: str,
    artifact_kind: str,
    profile: str = "default",
) -> list[dict[str, Any]]:
    del artifact_id, artifact_kind, profile
    return _scan_paths(content, artifact_path, profile="default", allowlist_ref=None)


def scan_for_external_urls(
    content: str,
    artifact_id: str,
    artifact_path: str,
    artifact_kind: str,
    profile: str = "default",
) -> list[dict[str, Any]]:
    del artifact_id, artifact_kind
    return _scan_urls(content, artifact_path, profile, allowlist_ref=None)


def scan_for_archive_risk(
    artifact_path: str,
    artifact_size: int,
    artifact_id: str,
    artifact_kind: str,
    profile: str = "default",
) -> list[dict[str, Any]]:
    del artifact_kind
    return _scan_archive_and_binary(artifact_path, "", artifact_size, artifact_id, profile=profile, allowlist_ref=None)
