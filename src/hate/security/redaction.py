"""HATE-PG-005B Redaction filter for artifact safety.

Implements `redact_artifact(fixture)` to remove secrets/PII/restricted paths/private URLs
while preserving sourceRef/traceability and generating non-reversible proof hash.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# Re-use patterns from artifact_safety.py
SECRET_PATTERNS = [
    (
        "api_key_like",
        re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?key|secret[_-]?key|api_secret)\s*[:=]\s*['\"]([A-Za-z0-9_]{20,})['\"]"),
    ),
    (
        "github_token_like",
        re.compile(r"(?i)\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22}_[A-Za-z0-9]{24})\b"),
    ),
    ("aws_access_key_like", re.compile(r"(?i)\bAKIA[0-9A-Z]{16}\b")),
    ("openai_like", re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{40,}\b")),
    ("password_like", re.compile(r"(?i)\b(?:password|passwd|credential)\s*[:=]\s*['\"][^'\"\\s]{8,}['\"]")),
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
        re.compile(r"(?:^|\s)(/etc|/var/(?:tmp|log|private))/[^\s\"']+"),
        "Absolute/private filesystem path",
    ),
    (
        re.compile(r"\.\./\.\.?|\.\\\.\.\\", re.IGNORECASE),
        "Path traversal",
    ),
]

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

CLASSIFICATION_ORDER = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}

REDACTION_MARKERS = {
    "secret": "[REDACTED_SECRET]",
    "pii": "[REDACTED_PII]",
    "path": "[REDACTED_PATH]",
    "url": "[REDACTED_URL]",
}


def _redaction_id() -> str:
    return f"redaction-{uuid.uuid4().hex[:12]}"


def _is_url_allowlisted(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == domain or host.endswith(f".{domain}") for domain in ALLOWLIST_URL_DOMAINS)


def _is_url_suspicious(url: str) -> bool:
    lower = url.lower()
    return any(token in lower for token in SUSPICIOUS_URL_HINTS)


def _is_synthetic_pii_allowed(content: str) -> bool:
    return bool(re.search(r"(?i)synthetic|@allowlist|sample[_-]?pii|fake[_-]?pii", content))


def _is_test_secret_allowed(content: str) -> bool:
    return bool(re.search(r"(?i)@allowlist|allowlist[_-]?fixture|test[_-]?secret|fake[_-]?secret", content))


def _compute_proof_hash(original: str, redacted: str, redaction_log: list[dict]) -> str:
    """Compute non-reversible proof hash for redaction verification."""
    log_json = json.dumps(redaction_log, sort_keys=True)
    combined = f"{original}\n{redacted}\n{log_json}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _classify_redaction_effect(effect: str) -> str:
    """Map readiness effect to classification."""
    if effect in {"hard_dq", "hold"}:
        return "restricted"
    if effect == "soft_gap":
        return "confidential"
    return "internal"


def _max_classification(*classifications: str) -> str:
    """Return highest classification level."""
    return sorted(classifications, key=lambda c: CLASSIFICATION_ORDER.get(c, 0))[-1]


def redact_artifact(fixture: dict[str, Any]) -> dict[str, Any]:
    """Redact secrets/PII/restricted paths/private URLs from artifact content.

    Args:
        fixture: Artifact fixture with artifact_id, artifact_path, profile, content

    Returns:
        Redaction report with:
        - redacted_content: Content with sensitive values replaced by markers
        - redaction_log: List of redactions performed with type, location, proof
        - proof_hash: Non-reversible hash for verification
        - redaction_status: not_required, redacted, pending, failed
        - sourceRefs: Preserved source references
        - readiness_effect: pass, soft_gap, hold, hard_dq
        - classification: public, internal, confidential, restricted
    """
    artifact_id = fixture.get("artifact_id", "unknown")
    artifact_path = fixture.get("artifact_path", "artifact")
    profile = fixture.get("profile", "default")
    content = fixture.get("content", "")
    encoded_payload = fixture.get("encoded_payload")

    if encoded_payload and not content:
        content = encoded_payload

    if not content:
        content = json.dumps(fixture, sort_keys=True)

    original_content = content
    redacted_content = content
    redaction_log: list[dict] = []
    source_refs: list[str] = []
    readiness_effects: list[str] = []
    classifications: list[str] = []
    replacements: list[tuple[int, int, str]] = []

    # Detect and redact secrets
    for pattern_name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(original_content):
            # Check if content has test/allowlist markers
            if _is_test_secret_allowed(original_content):
                continue  # Skip all secrets in test fixtures

            start, end = match.start(), match.end()
            line_num = original_content[:start].count("\n") + 1

            replacements.append((start, end, REDACTION_MARKERS["secret"]))

            redaction_log.append({
                "type": "secret",
                "pattern": pattern_name,
                "line": line_num,
                "span": {"start": start, "end": end},
                "marker": REDACTION_MARKERS["secret"],
            })

            source_ref = f"{artifact_path}:{line_num}"
            source_refs.append(source_ref)
            readiness_effects.append("hard_dq")
            classifications.append("restricted")

    # Detect and redact private keys (critical)
    for pattern_name, pattern in PRIVATE_KEY_PATTERNS:
        for match in pattern.finditer(original_content):
            start, end = match.start(), match.end()
            line_num = original_content[:start].count("\n") + 1

            # Redact entire key block (find END marker)
            end_marker_match = re.search(r"-----END [A-Z ]*PRIVATE KEY-----", original_content[start:])
            if end_marker_match:
                end = start + end_marker_match.end()

            replacements.append((start, end, REDACTION_MARKERS["secret"]))

            redaction_log.append({
                "type": "secret",
                "pattern": pattern_name,
                "line": line_num,
                "span": {"start": start, "end": end},
                "marker": REDACTION_MARKERS["secret"],
                "severity": "critical",
            })

            source_ref = f"{artifact_path}:{line_num}"
            source_refs.append(source_ref)
            readiness_effects.append("hard_dq")
            classifications.append("restricted")

    # Detect and redact PII
    for pattern_name, pattern in PII_PATTERNS:
        for match in pattern.finditer(original_content):
            # Check if content has synthetic/allowlist markers
            if _is_synthetic_pii_allowed(original_content):
                continue  # Skip all PII in synthetic/test content

            start, end = match.start(), match.end()
            line_num = original_content[:start].count("\n") + 1

            replacements.append((start, end, REDACTION_MARKERS["pii"]))

            redaction_log.append({
                "type": "pii",
                "pattern": pattern_name,
                "line": line_num,
                "span": {"start": start, "end": end},
                "marker": REDACTION_MARKERS["pii"],
            })

            source_ref = f"{artifact_path}:{line_num}"
            source_refs.append(source_ref)
            readiness_effects.append("hard_dq")
            classifications.append("restricted")

    # Detect and redact unsafe paths
    for pattern, path_type in PATH_PATTERNS:
        for match in pattern.finditer(original_content):
            start, end = match.start(), match.end()
            line_num = original_content[:start].count("\n") + 1

            replacements.append((start, end, REDACTION_MARKERS["path"]))

            redaction_log.append({
                "type": "path",
                "pattern": path_type,
                "line": line_num,
                "span": {"start": start, "end": end},
                "marker": REDACTION_MARKERS["path"],
            })

            source_ref = f"{artifact_path}:{line_num}"
            source_refs.append(source_ref)

            # Path traversal = hard_dq, others = hold
            if "traversal" in path_type.lower():
                readiness_effects.append("hard_dq")
                classifications.append("restricted")
            else:
                readiness_effects.append("hold")
                classifications.append("confidential")

    # Detect and redact private URLs
    for match in URL_PATTERN.finditer(original_content):
        url = match.group(0)
        if _is_url_allowlisted(url):
            continue  # Skip allowlisted URLs

        if _is_url_suspicious(url):
            start, end = match.start(), match.end()
            line_num = original_content[:start].count("\n") + 1

            replacements.append((start, end, REDACTION_MARKERS["url"]))

            redaction_log.append({
                "type": "url",
                "url_domain": urlparse(url).hostname or "unknown",
                "line": line_num,
                "span": {"start": start, "end": end},
                "marker": REDACTION_MARKERS["url"],
                "reason": "suspicious_url_pattern",
            })

            source_ref = f"{artifact_path}:{line_num}"
            source_refs.append(source_ref)
            readiness_effects.append("hard_dq")
            classifications.append("restricted")

    for start, end, marker in sorted(replacements, key=lambda item: item[0], reverse=True):
        redacted_content = redacted_content[:start] + marker + redacted_content[end:]

    # Compute proof hash
    proof_hash = _compute_proof_hash(original_content, redacted_content, redaction_log)

    # Determine final status
    if not redaction_log:
        redaction_status = "not_required"
        final_readiness = "pass"
        # Allowlisted content gets internal classification (test fixtures)
        if _is_test_secret_allowed(original_content) or _is_synthetic_pii_allowed(original_content):
            final_classification = "internal"
        else:
            final_classification = "public"
    else:
        redaction_status = "redacted"
        # Max readiness effect based on profile
        if profile in {"release", "product"}:
            # Any redaction = hard_dq in release/product
            final_readiness = "hard_dq"
        elif profile == "strict":
            final_readiness = "hold"
        else:
            # Default: max of detected effects
            effect_order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
            final_readiness = sorted(readiness_effects, key=lambda e: effect_order.get(e, 0))[-1]

        final_classification = _max_classification(*classifications)

    # Check for failed redaction (marker leakage)
    if redaction_status == "redacted":
        remaining_patterns = [
            re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][^'\"]{20,}['\"]"),
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        ]
        for pattern in remaining_patterns:
            if pattern.search(redacted_content):
                redaction_status = "failed"
                final_readiness = "hard_dq"
                break

    report = {
        "schema_version": "HATE/v1",
        "record_type": "redaction-report",
        "redaction_id": _redaction_id(),
        "artifact_id": artifact_id,
        "artifact_path": artifact_path,
        "profile": profile,
        "original_content_hash": hashlib.sha256(original_content.encode("utf-8")).hexdigest(),
        "redacted_content": redacted_content,
        "redaction_log": redaction_log,
        "proof_hash": proof_hash,
        "redaction_status": redaction_status,
        "classification": final_classification,
        "readiness_effect": final_readiness,
        "sourceRefs": source_refs,
        "created_at": datetime.now(UTC).isoformat(),
        "summary": {
            "redactions_count": len(redaction_log),
            "secrets_redacted": sum(1 for r in redaction_log if r["type"] == "secret"),
            "pii_redacted": sum(1 for r in redaction_log if r["type"] == "pii"),
            "paths_redacted": sum(1 for r in redaction_log if r["type"] == "path"),
            "urls_redacted": sum(1 for r in redaction_log if r["type"] == "url"),
            "artifact_size": len(original_content.encode("utf-8")),
        },
    }

    return report
