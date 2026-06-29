from __future__ import annotations

import hashlib
import json
import mimetypes
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .p0a_constants import REDACTION_STATUS, SCHEMA_VERSION, SOURCE_TOOL
from .p0a_io import (
    _artifact_kind,
    _dq,
    _file_sha256,
    _read_optional_json,
    _slug,
    _stable_sha256,
    _stable_source_ref,
    _to_posix,
)
def _artifact_manifest(
    context: dict[str, Any],
    created_at: str,
    artifacts_dir: Path,
    artifact_refs_path: Path,
    fixture_path_prefix: str | None,
) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    if artifacts_dir.exists():
        for path in sorted(p for p in artifacts_dir.rglob("*") if p.is_file()):
            rel_from_artifacts = path.relative_to(artifacts_dir)
            manifest_path = _to_posix(str(rel_from_artifacts))
            if fixture_path_prefix:
                manifest_path = posixpath.join(fixture_path_prefix.strip("/"), "artifacts", manifest_path)
            artifact_id = f"artifact-{_slug(path.stem)}"
            security_checks = _artifact_security_checks(path, rel_from_artifacts)
            artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "kind": _artifact_kind(path),
                    "path": manifest_path,
                    "sha256": f"sha256:{_file_sha256(path)}",
                    "size_bytes": path.stat().st_size,
                    "classification": "public",
                    "redaction_status": REDACTION_STATUS,
                    "redaction_rule_version": "none",
                    "safe_for_summary": not _has_failed_check(security_checks),
                    "public_exposure": "none" if _has_failed_check(security_checks) else "summary",
                    "retention": {
                        "policy": "fixture",
                        "delete_after_days": None,
                    },
                    "security_checks": security_checks,
                }
            )
    if artifact_refs_path.exists():
        data = _read_optional_json(artifact_refs_path)
        refs = data.get("artifacts", [])
        if not isinstance(refs, list):
            raise ValueError("artifact-refs.json artifacts must be a list")
        for ref in refs:
            if not isinstance(ref, dict):
                raise ValueError("artifact-refs.json artifact entries must be objects")
            raw_path = str(ref.get("path", ""))
            if not raw_path:
                raise ValueError("artifact-refs.json artifact path is required")
            external_url = _is_external_url(raw_path)
            traversal = _is_path_traversal(raw_path)
            local_path = artifact_refs_path.parent / raw_path if not external_url else artifact_refs_path.parent / "__external_url__"
            exists = not external_url and local_path.exists() and local_path.is_file()
            manifest_path = _manifest_ref_path(raw_path, ref, fixture_path_prefix)
            if fixture_path_prefix:
                manifest_path = posixpath.join(fixture_path_prefix.strip("/"), manifest_path)
            if exists:
                security_checks = _artifact_security_checks(local_path, Path(raw_path))
            else:
                security_checks = {
                "path_exists": "blocked" if external_url or traversal else "fail",
                "secret_scan": "not_run",
                "pii_scan": "not_run",
                "mime_extension_scan": "not_run",
                "archive_scan": "fail" if _is_archive_path(raw_path) else "not_applicable",
                "path_traversal_scan": "fail" if traversal else "pass",
                "symlink_scan": "fail" if ref.get("symlink") is True else "not_run",
                "external_url_scan": "fail" if external_url else "pass",
                }
            if ref.get("symlink") is True:
                security_checks["symlink_scan"] = "fail"
            artifacts.append(
                {
                    "artifact_id": str(ref.get("artifact_id") or f"artifact-{_slug(Path(raw_path).stem)}"),
                    "kind": str(ref.get("kind") or _artifact_kind(local_path)),
                    "path": manifest_path,
                    "sha256": f"sha256:{_file_sha256(local_path)}" if exists else "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                    "size_bytes": local_path.stat().st_size if exists else 0,
                    "classification": str(ref.get("classification") or "public"),
                    "redaction_status": REDACTION_STATUS,
                    "redaction_rule_version": "none",
                    "safe_for_summary": _safe_for_summary(ref, exists, security_checks),
                    "public_exposure": _public_exposure(ref, security_checks),
                    "retention": {
                        "policy": "fixture",
                        "delete_after_days": None,
                    },
                    "security_checks": security_checks,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(context["run_id"]),
        "run_attempt": int(context["run_attempt"]),
        "commit_sha": str(context.get("commit_sha", "")),
        "created_at": created_at,
        "artifacts": artifacts,
    }

def _artifact_security_checks(path: Path, relative_path: Path) -> dict[str, str]:
    suffix = path.suffix.lower()
    text = ""
    if path.exists() and path.stat().st_size <= 1024 * 1024:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
    secret_patterns = [
        r"AKIA[0-9A-Z]{16}",
        r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}",
        r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
    has_secret = any(re.search(pattern, text) for pattern in secret_patterns)
    has_external_url = bool(re.search(r"https?://", text))
    mime_known = mimetypes.guess_type(path.name)[0] is not None or suffix in {".txt", ".trace", ".sarif", ".json", ".xml", ".info"}
    archive_status = "not_applicable"
    if _is_archive_path(path.name):
        archive_status = "fail"
    return {
        "path_exists": "pass" if path.exists() and path.is_file() else "fail",
        "secret_scan": "fail" if has_secret else "pass",
        "pii_scan": "not_run",
        "mime_extension_scan": "pass" if mime_known else "unknown",
        "archive_scan": archive_status,
        "path_traversal_scan": "fail" if ".." in relative_path.parts or path.is_symlink() else "pass",
        "symlink_scan": "fail" if path.is_symlink() else "pass",
        "external_url_scan": "fail" if has_external_url else "pass",
    }

def _has_failed_check(security_checks: dict[str, str]) -> bool:
    return any(value == "fail" for value in security_checks.values())

def _safe_for_summary(ref: dict[str, Any], exists: bool, security_checks: dict[str, str]) -> bool:
    if "safe_for_summary" in ref:
        return bool(ref["safe_for_summary"]) and not _has_failed_check(security_checks)
    return exists and not _has_failed_check(security_checks)

def _public_exposure(ref: dict[str, Any], security_checks: dict[str, str]) -> str:
    if _has_failed_check(security_checks):
        return "none"
    return str(ref.get("public_exposure") or "summary")

def _manifest_ref_path(raw_path: str, ref: dict[str, Any], fixture_path_prefix: str | None) -> str:
    if _is_external_url(raw_path):
        return f"redacted/external-url/{_slug(str(ref.get('artifact_id') or 'artifact'))}"
    if _is_path_traversal(raw_path):
        return f"redacted/path-traversal/{_slug(str(ref.get('artifact_id') or Path(raw_path).stem or 'artifact'))}"
    manifest_path = _to_posix(raw_path)
    if ref.get("symlink") is True:
        return f"redacted/symlink/{_slug(str(ref.get('artifact_id') or Path(raw_path).stem or 'artifact'))}"
    return manifest_path

def _is_external_url(raw_path: str) -> bool:
    return bool(re.match(r"(?i)^https?://", raw_path))

def _is_path_traversal(raw_path: str) -> bool:
    if _is_external_url(raw_path):
        return False
    normalized = _to_posix(raw_path)
    if re.match(r"^[A-Za-z]:/", normalized) or normalized.startswith("/"):
        return True
    return ".." in Path(raw_path).parts or "../" in normalized or normalized.startswith("..")

def _is_archive_path(raw_path: str) -> bool:
    suffixes = [suffix.lower() for suffix in Path(raw_path).suffixes]
    return any(suffix in {".zip", ".tar", ".tgz", ".gz", ".7z"} for suffix in suffixes)

def _quarantine_report(
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    artifact_manifest: dict[str, Any],
) -> dict[str, Any]:
    quarantined = []
    for artifact in artifact_manifest.get("artifacts", []):
        reasons = _quarantine_reasons(artifact.get("security_checks", {}))
        if artifact.get("classification") in {"secret", "pii", "restricted"} and "restricted_classification" not in reasons:
            reasons.append("restricted_classification")
        if artifact.get("safe_for_summary") is False and not reasons:
            reasons.append("unsafe_for_summary")
        if not reasons:
            continue
        quarantined.append({
            "artifact_id": artifact.get("artifact_id", ""),
            "kind": artifact.get("kind", "other"),
            "path": artifact.get("path", "redacted/unknown"),
            "reasons": reasons,
            "safe_for_summary": False,
            "public_exposure": "none",
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(context["run_id"]),
        "run_attempt": int(context["run_attempt"]),
        "commit_sha": str(context.get("commit_sha", "")),
        "created_at": created_at,
        "source_tool": SOURCE_TOOL,
        "source_version": source_version,
        "quarantined_artifacts": quarantined,
    }

def _quarantine_reasons(security_checks: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    reason_by_check = {
        "path_exists": "missing",
        "secret_scan": "secret",
        "archive_scan": "unsafe_archive",
        "path_traversal_scan": "path_traversal",
        "symlink_scan": "symlink",
        "external_url_scan": "external_url",
    }
    for check, reason in reason_by_check.items():
        if security_checks.get(check) == "fail":
            reasons.append(reason)
    return reasons

