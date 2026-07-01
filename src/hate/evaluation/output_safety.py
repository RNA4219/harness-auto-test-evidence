"""Output redaction and deterministic excerpting for real-repo evaluation."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SECRET_PATTERNS = [
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?key|secret[_-]?key|token|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{16,})['\"]?"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?key|secret[_-]?key|token|password)=[^\s\"']{12,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
]
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
WINDOWS_ABSOLUTE_PATH = re.compile(r"\b[A-Za-z]:\\(?:[^\\\r\n\t ]+\\)*[^\\\r\n\t ]+")
POSIX_ABSOLUTE_PATH = re.compile(r"(?<![\w:/.-])/(?:Users|home|tmp|var|private|mnt|workspace)/[^\s\"']+")


def safe_command_output(stdout: str, stderr: str, *, limit: int = 2000) -> dict[str, Any]:
    """Return a redacted deterministic command output excerpt and metadata."""
    original = f"{stdout}\n{stderr}".strip()
    normalized = _normalize_text(original)
    redacted, redactions = _redact_text(normalized)
    truncated, was_truncated = _truncate(redacted, limit)
    return {
        "excerpt": truncated,
        "metadata": {
            "redaction_status": "redacted" if redactions else "not_required",
            "redaction_rule_version": "real-repo-output-safety/v1",
            "redactions": redactions,
            "redaction_count": len(redactions),
            "line_endings_normalized": "\r" in original,
            "control_characters_removed": CONTROL_PATTERN.search(original) is not None,
            "ansi_removed": ANSI_PATTERN.search(original) is not None,
            "truncated": was_truncated,
            "limit": limit,
            "raw_output_sha256": hashlib.sha256(original.encode("utf-8", errors="replace")).hexdigest(),
            "raw_access": "quarantined_required" if redactions else "not_required",
            "safe_for_read_model": True,
        },
    }


def _normalize_text(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = ANSI_PATTERN.sub("", text)
    return CONTROL_PATTERN.sub("", text)


def _redact_text(value: str) -> tuple[str, list[dict[str, Any]]]:
    text = value
    redactions: list[dict[str, Any]] = []
    for pattern in SECRET_PATTERNS:
        text, count = pattern.subn("[REDACTED_SECRET]", text)
        if count:
            redactions.append(_redaction("secret", count))
    text, count = EMAIL_PATTERN.subn("[REDACTED_PII]", text)
    if count:
        redactions.append(_redaction("pii", count))
    for pattern in _path_patterns():
        text, count = pattern.subn("[REDACTED_PATH]", text)
        if count:
            redactions.append(_redaction("path", count))
    return text, redactions


def _path_patterns() -> list[re.Pattern[str]]:
    patterns = [WINDOWS_ABSOLUTE_PATH, POSIX_ABSOLUTE_PATH]
    home = str(Path.home())
    if home:
        patterns.append(re.compile(re.escape(home) + r"[^\s\"']*"))
    cwd = os.getcwd()
    if cwd:
        patterns.append(re.compile(re.escape(cwd) + r"[^\s\"']*"))
    return patterns


def _truncate(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    marker = "\n...[truncated:real-repo-output-safety/v1]"
    return value[: max(0, limit - len(marker))] + marker, True


def _redaction(kind: str, count: int) -> dict[str, Any]:
    return {
        "kind": kind,
        "count": count,
        "marker": f"[REDACTED_{'PII' if kind == 'pii' else kind.upper()}]",
    }
