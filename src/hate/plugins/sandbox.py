"""Platform plugin sandbox policy decisions."""

from __future__ import annotations

import hashlib
import json
from typing import Any


RELEASE_PROFILES = {"release", "regulated"}
RELEASE_ALLOWED_MODES = {"in_process_builtin", "containerized"}


def build_plugin_sandbox_report(data: dict[str, Any], report_id: str = "plugin-sandbox") -> dict[str, Any]:
    """Build an explanatory sandbox report for a detector plugin execution."""
    profile = str(data.get("profile") or "default")
    plugin = dict(data.get("plugin") or {})
    limits = dict(data.get("limits") or {})
    execution = dict(data.get("execution") or {})
    findings: list[dict[str, Any]] = []

    mode_decision = _mode_decision(profile, plugin, findings)
    input_decision = _input_decision(data, findings)
    resource_decision = _resource_decision(limits, execution, findings)
    output_decision = _output_decision(plugin, limits, execution, findings)
    isolation_decision = _isolation_decision(plugin, execution, findings)

    required_blocking = bool(plugin.get("required_blocking", False))
    blocking_failure = required_blocking and any(finding["code"] != "plugin_output_budget_exceeded" for finding in findings)
    overall_status = "blocked" if blocking_failure else "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-plugin-sandbox-report",
        "report_id": report_id,
        "overall_status": overall_status,
        "readiness_effect": "blocked" if blocking_failure else "hold" if findings else "none",
        "profile": profile,
        "plugin_id": str(plugin.get("plugin_id") or ""),
        "detector_id": str(plugin.get("detector_id") or ""),
        "execution_mode": mode_decision["execution_mode"],
        "mode_decision": mode_decision,
        "input_decision": input_decision,
        "resource_decision": resource_decision,
        "output_decision": output_decision,
        "isolation_decision": isolation_decision,
        "findings": findings,
        "summary": {
            "finding_count": len(findings),
            "platform_continues": isolation_decision["platform_continues"],
            "required_blocking": required_blocking,
        },
        "sourceRefs": list(data.get("sourceRefs") or plugin.get("sourceRefs") or []),
    }


def _mode_decision(profile: str, plugin: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    mode = str(plugin.get("execution_mode") or "disabled")
    signed = bool(plugin.get("signed", False))
    trusted = bool(plugin.get("trusted", False))
    allowed = mode != "disabled"
    if mode == "disabled":
        findings.append(_finding("plugin_trust_denied", {"reason": "execution mode disabled"}))
    if profile in RELEASE_PROFILES and mode not in RELEASE_ALLOWED_MODES:
        allowed = False
        findings.append(_finding("plugin_trust_denied", {"reason": "mode not allowed in release profile"}))
    if profile in RELEASE_PROFILES and mode == "subprocess_local" and not signed:
        allowed = False
        findings.append(_finding("plugin_trust_denied", {"reason": "unsigned workspace plugin denied"}))
    return {
        "execution_mode": mode,
        "signed": signed,
        "trusted": trusted,
        "allowed": allowed,
    }


def _input_decision(data: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    input_bundle = dict(data.get("input_bundle") or {})
    receives_raw_unsafe_body = bool(input_bundle.get("raw_unsafe_artifact_body", False))
    receives_secrets = bool(input_bundle.get("secrets", False))
    unrestricted_paths = bool(input_bundle.get("unrestricted_filesystem_paths", False))
    if receives_raw_unsafe_body or receives_secrets or unrestricted_paths:
        findings.append(_finding("plugin_forbidden_filesystem_access", {"reason": "unsafe input boundary"}))
    return {
        "redacted_canonical_input": bool(input_bundle.get("redacted_canonical_input", True)),
        "read_only_artifact_metadata": bool(input_bundle.get("read_only_artifact_metadata", True)),
        "raw_unsafe_artifact_body": receives_raw_unsafe_body,
        "secrets": receives_secrets,
        "unrestricted_filesystem_paths": unrestricted_paths,
    }


def _resource_decision(limits: dict[str, Any], execution: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    timeout_ms = _positive_int(limits.get("timeout_ms"))
    max_output_bytes = _positive_int(limits.get("max_output_bytes"))
    max_input_bytes = _positive_int(limits.get("max_input_bytes"))
    max_memory_mb = _positive_int(limits.get("max_memory_mb"))
    if timeout_ms is None or max_output_bytes is None or max_input_bytes is None:
        findings.append(_finding("plugin_resource_limit_missing"))
    if execution.get("timed_out"):
        findings.append(_finding("plugin_timeout"))
    return {
        "timeout_ms": timeout_ms,
        "max_output_bytes": max_output_bytes,
        "max_input_bytes": max_input_bytes,
        "max_memory_mb": max_memory_mb,
        "filesystem_allowlist": list(limits.get("filesystem_allowlist") or []),
        "network_mode": str(limits.get("network_mode") or "none"),
    }


def _output_decision(
    plugin: dict[str, Any],
    limits: dict[str, Any],
    execution: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    output_bytes = _non_negative_int(execution.get("output_bytes")) or 0
    max_output_bytes = _positive_int(limits.get("max_output_bytes"))
    output = execution.get("output")
    output_hash = _stable_hash(output) if isinstance(output, dict) else ""
    if max_output_bytes is not None and output_bytes > max_output_bytes:
        findings.append(_finding("plugin_output_budget_exceeded"))
    if output is not None and not _output_valid(plugin, output):
        findings.append(_finding("plugin_output_invalid"))
    return {
        "output_bytes": output_bytes,
        "max_output_bytes": max_output_bytes,
        "schema_versioned": isinstance(output, dict) and bool(output.get("schema_version")),
        "detector_scoped": isinstance(output, dict) and output.get("detector_id") == plugin.get("detector_id"),
        "deterministic_hash": output_hash,
    }


def _isolation_decision(plugin: dict[str, Any], execution: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    required_blocking = bool(plugin.get("required_blocking", False))
    network_attempted = bool(execution.get("network_access_attempted", False))
    network_mode = str(execution.get("network_mode") or "")
    forbidden_filesystem = bool(execution.get("forbidden_filesystem_access", False))
    crashed = bool(execution.get("crashed", False))
    if network_attempted and network_mode in {"", "none", "unrestricted-denied-in-release"}:
        findings.append(_finding("plugin_forbidden_network_access"))
    if forbidden_filesystem:
        findings.append(_finding("plugin_forbidden_filesystem_access"))
    if crashed:
        findings.append(_finding("plugin_execution_failed"))
    return {
        "network_access_attempted": network_attempted,
        "forbidden_filesystem_access": forbidden_filesystem,
        "crashed": crashed,
        "platform_continues": not required_blocking,
    }


def _output_valid(plugin: dict[str, Any], output: dict[str, Any]) -> bool:
    return (
        bool(output.get("schema_version"))
        and output.get("detector_id") == plugin.get("detector_id")
        and isinstance(output.get("sourceRefs", []), list)
    )


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) and value > 0 else None


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) and value >= 0 else None


def _finding(code: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": code,
        "sourceRefs": [],
    }
    if extra:
        finding.update(extra)
    return finding


def _stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
