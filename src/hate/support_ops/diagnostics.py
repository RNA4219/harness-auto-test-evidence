"""Safe diagnostic bundle generation for support operations."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from hate.support_ops.error_catalog import map_findings_to_error_records


SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|token|secret|bearer|password|private[_-]?key|AKIA[0-9A-Z]{16})")
PII_PATTERN = re.compile(r"(?i)([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b\d{3}-\d{2}-\d{4}\b)")
PATH_PATTERN = re.compile(r"(?i)([A-Z]:\\Users\\[^\\\s]+|/home/[^/\s]+|/Users/[^/\s]+|\\\\[^\\\s]+\\[^\\\s]+)")
PRIVATE_URL_PATTERN = re.compile(r"(?i)https?://(?:localhost|127\.0\.0\.1|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[0-1])\.)[^\s]*")
RAW_FIELDS = {
    "raw_artifact",
    "raw_artifact_content",
    "artifact_content",
    "customer_source",
    "source_code",
    "raw_log",
    "raw_stack",
    "full_environment",
}


@dataclass
class DiagnosticBundleResult:
    """Safe diagnostic bundle plus support ops findings."""

    bundle: dict[str, Any]
    findings: list[dict[str, Any]] = field(default_factory=list)
    error_records: list[dict[str, Any]] = field(default_factory=list)

    def to_report(self) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "support-ops-report",
            "report_id": self.bundle["bundle_id"],
            "overall_status": _status_from_findings(self.findings),
            "logs": [],
            "metrics": [],
            "alerts": [],
            "incidents": [],
            "diagnostic_bundles": [self.bundle],
            "error_records": self.error_records,
            "findings": self.findings,
            "summary": {
                "diagnostic_bundle_count": 1,
                "error_record_count": len(self.error_records),
                "finding_count": len(self.findings),
                "safe_for_support": self.bundle.get("safe_for_summary") is True,
            },
            "sourceRefs": self.bundle.get("sourceRefs", []),
        }


def build_diagnostic_bundle(data: dict[str, Any]) -> DiagnosticBundleResult:
    """Build a safe diagnostic bundle from support data.

    Raw artifacts and customer-sensitive fields are excluded. Any unsafe input is
    represented as a finding, not copied into the bundle.
    """

    bundle_id = str(data.get("bundle_id") or "support-diagnostic-bundle")
    source_refs = list(data.get("sourceRefs") or [])
    artifacts = list(data.get("artifacts") or [])
    findings = list(data.get("findings") or [])
    safe_artifacts: list[dict[str, Any]] = []
    excluded_artifacts: list[dict[str, Any]] = []
    diagnostic_findings: list[dict[str, Any]] = []
    redaction_log: list[dict[str, Any]] = []

    for index, artifact in enumerate(artifacts):
        unsafe_reason = _unsafe_artifact_reason(artifact)
        artifact_id = str(artifact.get("artifact_id") or f"artifact-{index}")
        if unsafe_reason:
            excluded_artifacts.append({
                "artifact_id": artifact_id,
                "reason": unsafe_reason,
                "safe_metadata": _safe_artifact_metadata(artifact),
            })
            diagnostic_findings.append(_finding(
                "raw_artifact_in_diagnostic_bundle" if unsafe_reason == "raw_field_present" else "unsafe_artifact_excluded",
                "hard_dq" if unsafe_reason == "raw_field_present" else "hold",
                "Unsafe artifact was excluded from diagnostic bundle.",
                _source_ref(artifact, source_refs, index),
            ))
            continue
        safe_artifact, artifact_redactions = _sanitize_artifact(artifact)
        redaction_log.extend(artifact_redactions)
        safe_artifacts.append(safe_artifact)

    sanitized_context, context_redactions = _sanitize_mapping(data.get("context", {}), "context")
    redaction_log.extend(context_redactions)
    error_records, catalog_findings = map_findings_to_error_records(findings + diagnostic_findings)
    all_findings = diagnostic_findings + catalog_findings

    artifact_ids = [artifact["artifact_id"] for artifact in safe_artifacts] or ["metadata-only"]
    classification = _max_classification([artifact.get("classification", "internal") for artifact in safe_artifacts] or ["internal"])
    bundle = {
        "schema_version": "HATE/v1",
        "record_type": "safe-diagnostic-bundle",
        "bundle_id": bundle_id,
        "artifact_ids": artifact_ids,
        "included_artifacts": safe_artifacts,
        "excluded_artifacts": excluded_artifacts,
        "classification": classification,
        "redaction_status": "redacted" if redaction_log else "not_required",
        "quarantine_status": "quarantined" if excluded_artifacts else "none",
        "readiness_effect": _max_effect([finding["readiness_effect"] for finding in all_findings]),
        "safe_for_summary": not any(finding.get("readiness_effect") == "hard_dq" for finding in all_findings),
        "export_surface": data.get("export_surface", "support"),
        "export_ready": not any(finding.get("readiness_effect") == "hard_dq" for finding in all_findings),
        "sanitized_context": sanitized_context,
        "error_records": error_records,
        "redaction_log": redaction_log,
        "proof_hash": _proof_hash(safe_artifacts, excluded_artifacts, error_records),
        "sourceRefs": source_refs,
        "created_at": data.get("created_at") or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "summary": {
            "artifact_count": len(safe_artifacts),
            "excluded_artifact_count": len(excluded_artifacts),
            "classification_count": _classification_count(safe_artifacts),
            "redactions_count": len(redaction_log),
            "secrets_redacted": sum(1 for item in redaction_log if item["type"] == "secret"),
            "pii_redacted": sum(1 for item in redaction_log if item["type"] == "pii"),
            "paths_redacted": sum(1 for item in redaction_log if item["type"] == "path"),
            "urls_redacted": sum(1 for item in redaction_log if item["type"] == "url"),
            "quarantined_count": len(excluded_artifacts),
            "safe_for_summary_count": len(safe_artifacts),
        },
    }
    return DiagnosticBundleResult(bundle=bundle, findings=all_findings, error_records=error_records)


def build_diagnostics_report(data: dict[str, Any]) -> dict[str, Any]:
    """Build a support-ops-report containing a safe diagnostic bundle."""

    return build_diagnostic_bundle(data).to_report()


def _unsafe_artifact_reason(artifact: dict[str, Any]) -> str:
    if any(field in artifact for field in RAW_FIELDS):
        return "raw_field_present"
    if artifact.get("quarantine_status") == "quarantined":
        return "quarantined"
    if artifact.get("classification") == "restricted":
        return "restricted"
    if artifact.get("redaction_status") in {"pending", "failed"}:
        return "redaction_not_complete"
    return ""


def _safe_artifact_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": str(artifact.get("artifact_id", "")),
        "kind": str(artifact.get("kind", "")),
        "classification": str(artifact.get("classification", "internal")),
        "quarantine_status": str(artifact.get("quarantine_status", "none")),
        "redaction_status": str(artifact.get("redaction_status", "not_required")),
        "sourceRef": str(artifact.get("sourceRef", "")),
    }


def _sanitize_artifact(artifact: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    safe: dict[str, Any] = {}
    redactions: list[dict[str, Any]] = []
    for key, value in artifact.items():
        if key in RAW_FIELDS:
            continue
        if isinstance(value, str):
            clean, logs = _sanitize_text(value, key)
            safe[key] = clean
            redactions.extend(logs)
        elif isinstance(value, dict):
            safe[key], logs = _sanitize_mapping(value, key)
            redactions.extend(logs)
        elif isinstance(value, list):
            safe[key], logs = _sanitize_list(value, key)
            redactions.extend(logs)
        else:
            safe[key] = value
    safe.setdefault("artifact_id", "artifact")
    safe.setdefault("classification", "internal")
    safe.setdefault("redaction_status", "not_required")
    return safe, redactions


def _sanitize_mapping(value: dict[str, Any], path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    safe: dict[str, Any] = {}
    logs: list[dict[str, Any]] = []
    for key, item in value.items():
        if key in RAW_FIELDS:
            logs.append(_redaction_log("secret", path, "raw field removed"))
            continue
        if isinstance(item, str):
            safe[key], item_logs = _sanitize_text(item, f"{path}.{key}")
            logs.extend(item_logs)
        elif isinstance(item, dict):
            safe[key], item_logs = _sanitize_mapping(item, f"{path}.{key}")
            logs.extend(item_logs)
        elif isinstance(item, list):
            safe[key], item_logs = _sanitize_list(item, f"{path}.{key}")
            logs.extend(item_logs)
        else:
            safe[key] = item
    return safe, logs


def _sanitize_list(values: list[Any], path: str) -> tuple[list[Any], list[dict[str, Any]]]:
    safe: list[Any] = []
    logs: list[dict[str, Any]] = []
    for index, item in enumerate(values):
        item_path = f"{path}[{index}]"
        if isinstance(item, str):
            clean, item_logs = _sanitize_text(item, item_path)
            safe.append(clean)
            logs.extend(item_logs)
        elif isinstance(item, dict):
            clean_map, item_logs = _sanitize_mapping(item, item_path)
            safe.append(clean_map)
            logs.extend(item_logs)
        else:
            safe.append(item)
    return safe, logs


def _sanitize_text(value: str, path: str) -> tuple[str, list[dict[str, Any]]]:
    logs: list[dict[str, Any]] = []
    clean = value
    for kind, pattern, marker in [
        ("secret", SECRET_PATTERN, "[REDACTED_SECRET]"),
        ("pii", PII_PATTERN, "[REDACTED_PII]"),
        ("path", PATH_PATTERN, "[REDACTED_PATH]"),
        ("url", PRIVATE_URL_PATTERN, "[REDACTED_URL]"),
    ]:
        if pattern.search(clean):
            clean = pattern.sub(marker, clean)
            logs.append(_redaction_log(kind, path, marker))
    return clean, logs


def _redaction_log(kind: str, path: str, marker: str) -> dict[str, Any]:
    return {
        "type": kind,
        "line": 1,
        "marker": marker,
        "severity": "critical" if kind == "secret" else "medium",
        "reason": f"{kind} redacted at {path}",
    }


def _finding(code: str, effect: str, message: str, source_ref: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "critical" if effect == "hard_dq" else "high",
        "readiness_effect": effect,
        "message": message,
        "sourceRef": source_ref,
    }


def _source_ref(artifact: dict[str, Any], source_refs: list[str], index: int) -> str:
    return str(artifact.get("sourceRef") or (source_refs[0] if source_refs else f"artifacts/{index}"))


def _proof_hash(*values: Any) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _classification_count(artifacts: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for artifact in artifacts:
        classification = str(artifact.get("classification", "internal"))
        counts[classification] = counts.get(classification, 0) + 1
    return counts


def _max_classification(values: list[str]) -> str:
    order = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
    return max(values, key=lambda item: order.get(item, 1), default="internal")


def _max_effect(effects: list[str]) -> str:
    order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
    return max(effects or ["pass"], key=lambda item: order.get(item, 0))


def _status_from_findings(findings: list[dict[str, Any]]) -> str:
    effect = _max_effect([finding.get("readiness_effect", "pass") for finding in findings])
    return "blocked" if effect == "hard_dq" else effect
