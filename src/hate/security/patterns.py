"""Canonical artifact-safety matching rules.

The scanner and redactor must consume the same rules. Keeping them here avoids
silent drift where a value is detected as unsafe but is not removed from an
unprivileged representation.
"""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

NamedPattern = tuple[str, re.Pattern[str]]
PathPattern = tuple[re.Pattern[str], str]
UrlPolicy = Literal["allowlisted", "suspicious", "unapproved"]


SECRET_PATTERNS: tuple[NamedPattern, ...] = (
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
)

PRIVATE_KEY_PATTERNS: tuple[NamedPattern, ...] = (
    ("pem_private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

PII_PATTERNS: tuple[NamedPattern, ...] = (
    ("pii_email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("pii_phone", re.compile(r"\b\+?\d{1,3}[-.\s]?(?:\d{1,4}[-.\s])?\d{2,4}[-.\s]\d{2,4}[-.\s]\d{3,4}\b")),
    ("pii_user_id", re.compile(r"(?i)\b(?:user[_-]?id|customer[_-]?id)\s*[:=]\s*['\"][^'\"]+['\"]")),
    ("pii_name", re.compile(r"(?i)\b(?:full[_-]?name|name)\s*[:=]\s*['\"][A-Za-z]+ [A-Za-z]+['\"]")),
)

PATH_PATTERNS: tuple[PathPattern, ...] = (
    (
        re.compile(r"""[A-Za-z]:\\(?:Users|[Ss]hared|Program Files|ProgramData)\\[^\\"'\s]+"""),
        "Windows user/path",
    ),
    (
        re.compile(r"""/home/[A-Za-z0-9._-]+/[^\s"']+"""),
        "Unix home path",
    ),
    (
        re.compile(r"""(?<!\S)(?:/etc|/var/(?:tmp|log|private))/[^\s"']+"""),
        "Absolute/private filesystem path",
    ),
    (
        re.compile(r"(?:\.\.[\\/])+"),
        "Path traversal",
    ),
)

URL_PATTERN = re.compile(r"https?://[^\s\"'<>`]+")
ALLOWLIST_URL_DOMAINS = frozenset(
    {
        "docs.python.org",
        "readthedocs.io",
        "pypi.org",
        "github.com",
    }
)
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

SECRET_ALLOWLIST_MARKER_PATTERN = re.compile(
    r"(?i)@allowlist|allowlist[_-]?fixture|test[_-]?secret|fake[_-]?secret"
)
SYNTHETIC_PII_MARKER_PATTERN = re.compile(
    r"(?i)synthetic|@allowlist|sample[_-]?pii|fake[_-]?pii"
)


def has_secret_allowlist_marker(content: str) -> bool:
    return bool(SECRET_ALLOWLIST_MARKER_PATTERN.search(content))


def has_synthetic_pii_marker(content: str) -> bool:
    return bool(SYNTHETIC_PII_MARKER_PATTERN.search(content))


def is_url_allowlisted(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == domain or host.endswith(f".{domain}") for domain in ALLOWLIST_URL_DOMAINS)


def is_url_suspicious(url: str) -> bool:
    lower = url.lower()
    return any(token in lower for token in SUSPICIOUS_URL_HINTS)


def classify_url(url: str) -> UrlPolicy:
    """Classify a URL with suspicious signals taking precedence over allowlists."""
    if is_url_suspicious(url):
        return "suspicious"
    if is_url_allowlisted(url):
        return "allowlisted"
    return "unapproved"
