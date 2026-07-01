"""Platform policy config resolution and validation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


BUILTIN_PROFILES = {"default", "strict", "release", "regulated", "experimental"}
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "record_type",
    "policy_id",
    "policy_version",
    "profiles",
    "thresholds",
    "detectors",
    "plugins",
    "scheduler",
    "retention",
    "artifact_safety",
    "sourceRefs",
}
THRESHOLD_ORDER = [
    ("repo_id", "suite_id"),
    ("repo_class", "suite_kind"),
    ("risk_class",),
    tuple(),
]


def build_platform_policy_report(data: dict[str, Any], report_id: str = "platform-policy") -> dict[str, Any]:
    """Resolve platform policy config and explain effective profile/thresholds."""
    raw_base = data.get("base_policy") or data.get("policy") or {}
    base = _normalize_policy(raw_base if isinstance(raw_base, dict) else {})
    overrides = [_normalize_policy(item) for item in data.get("overrides", []) if isinstance(item, dict)]
    merged = _merge_policies(base, overrides)
    profile_name = str(data.get("profile") or "default")
    context = dict(data.get("threshold_context") or {})
    plugin_request = dict(data.get("plugin_request") or {})
    retention_request = dict(data.get("retention_request") or {})

    findings = _policy_findings(raw_base if isinstance(raw_base, dict) else {}, merged, profile_name)
    effective_profile = _resolve_profile(merged, profile_name)
    thresholds = _resolve_thresholds(merged, context, profile_name)
    plugin_decision = _evaluate_plugin_trust(merged, effective_profile, plugin_request)
    retention_decision = _evaluate_retention(merged, retention_request)
    scheduler_decision = _evaluate_scheduler_budget(merged)
    findings.extend(plugin_decision.pop("findings"))
    findings.extend(retention_decision.pop("findings"))
    findings.extend(scheduler_decision.pop("findings"))

    overall_status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-policy-report",
        "report_id": report_id,
        "overall_status": overall_status,
        "readiness_effect": "hold" if findings else "none",
        "policy_id": merged.get("policy_id", ""),
        "policy_version": merged.get("policy_version", ""),
        "profile": profile_name,
        "policy_hash": _stable_hash(merged),
        "effective_profile": effective_profile,
        "resolved_thresholds": thresholds,
        "plugin_trust_decision": plugin_decision,
        "retention_decision": retention_decision,
        "scheduler_decision": scheduler_decision,
        "findings": findings,
        "summary": {
            "profile_supported": profile_name in BUILTIN_PROFILES,
            "threshold_count": len(thresholds),
            "override_count": len(overrides),
            "finding_count": len(findings),
        },
        "sourceRefs": list(merged.get("sourceRefs") or data.get("sourceRefs") or []),
    }


def _normalize_policy(policy: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(policy)
    normalized.setdefault("schema_version", "HATE/v1")
    normalized.setdefault("record_type", "platform-policy-config")
    normalized.setdefault("profiles", {})
    normalized.setdefault("thresholds", [])
    normalized.setdefault("detectors", {})
    normalized.setdefault("plugins", {})
    normalized.setdefault("scheduler", {})
    normalized.setdefault("retention", {})
    normalized.setdefault("artifact_safety", {})
    normalized.setdefault("sourceRefs", [])
    return normalized


def _merge_policies(base: dict[str, Any], overrides: list[dict[str, Any]]) -> dict[str, Any]:
    merged = deepcopy(base)
    for override in overrides:
        merged = _deep_merge(merged, override)
        merged["sourceRefs"] = _dedupe([*merged.get("sourceRefs", []), *override.get("sourceRefs", [])])
    return merged


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        elif isinstance(value, list) and key == "thresholds":
            result[key] = [*result.get(key, []), *deepcopy(value)]
        else:
            result[key] = deepcopy(value)
    return result


def _policy_findings(base: dict[str, Any], merged: dict[str, Any], profile_name: str) -> list[dict[str, Any]]:
    findings = []
    missing = sorted(field for field in REQUIRED_TOP_LEVEL if field not in base)
    if missing:
        findings.append(_finding("platform_policy_required_field_missing", {"missing_fields": missing}))
    if merged.get("record_type") != "platform-policy-config":
        findings.append(_finding("platform_policy_record_type_invalid"))
    if profile_name not in BUILTIN_PROFILES:
        findings.append(_finding("platform_policy_unknown_profile", {"profile": profile_name}))
    return findings


def _resolve_profile(policy: dict[str, Any], profile_name: str) -> dict[str, Any]:
    profiles = policy.get("profiles", {})
    chain = []
    current = profile_name
    seen = set()
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        current = str(profiles.get(current, {}).get("inherits") or "")
    effective: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for name in reversed(chain):
        for key, value in profiles.get(name, {}).items():
            if key == "inherits":
                continue
            effective[key] = deepcopy(value)
            sources[key] = name
    return {
        "profile": profile_name,
        "inherits": list(reversed(chain)),
        "rules": effective,
        "rule_sources": sources,
        "profile_hash": _stable_hash({"profile": profile_name, "rules": effective, "chain": chain}),
    }


def _resolve_thresholds(policy: dict[str, Any], context: dict[str, Any], profile_name: str) -> list[dict[str, Any]]:
    detector = str(context.get("detector") or "")
    signal = str(context.get("signal") or "")
    matches = [
        item for item in policy.get("thresholds", [])
        if item.get("detector") == detector and item.get("signal") == signal
    ]
    for layer in THRESHOLD_ORDER:
        specific = [
            item for item in matches
            if all(item.get(key) == context.get(key) for key in layer)
            and all(key not in item for key in _more_specific_keys(layer))
        ]
        if specific:
            selected = specific[-1]
            return [_threshold_result(selected, _layer_name(layer))]
    defaults = policy.get("profiles", {}).get(profile_name, {}).get("threshold_defaults", {})
    value = defaults.get(signal, defaults.get("default"))
    if value is None:
        return []
    return [{
        "detector": detector,
        "signal": signal,
        "value": value,
        "source_layer": "profile_default",
        "source_path": f"profiles.{profile_name}.threshold_defaults",
        "reason": "profile default threshold",
    }]


def _more_specific_keys(layer: tuple[str, ...]) -> set[str]:
    all_keys = {"repo_id", "suite_id", "repo_class", "suite_kind", "risk_class"}
    return all_keys - set(layer)


def _layer_name(layer: tuple[str, ...]) -> str:
    if layer == ("repo_id", "suite_id"):
        return "repo_suite"
    if layer == ("repo_class", "suite_kind"):
        return "repo_class_suite_kind"
    if layer == ("risk_class",):
        return "risk_class"
    return "detector_signal"


def _threshold_result(item: dict[str, Any], source_layer: str) -> dict[str, Any]:
    return {
        "detector": item.get("detector", ""),
        "signal": item.get("signal", ""),
        "value": item.get("value"),
        "source_layer": source_layer,
        "source_path": item.get("source_path", "thresholds[]"),
        "reason": item.get("reason", "matched threshold"),
    }


def _evaluate_plugin_trust(policy: dict[str, Any], effective_profile: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    if not request:
        return {
            "plugin_id": "",
            "publisher": "",
            "signed": False,
            "allowed": True,
            "findings": [],
        }

    plugin_policy = dict(policy.get("plugins", {}))
    profile_rules = effective_profile.get("rules", {})
    profile_name = str(effective_profile.get("profile") or "")
    unsigned_policy = profile_rules.get("unsigned_plugin_policy")
    if unsigned_policy == "deny" or profile_name in {"release", "regulated"}:
        plugin_policy["allow_unsigned"] = False
        plugin_policy["required_signature"] = True
    publisher = str(request.get("publisher") or "")
    plugin_id = str(request.get("plugin_id") or "")
    signed = bool(request.get("signed", False))
    findings = []
    allowed = True
    if plugin_id in set(plugin_policy.get("denylist", [])):
        allowed = False
        findings.append(_finding("platform_policy_plugin_denylisted", {"plugin_id": plugin_id}))
    if not signed and not plugin_policy.get("allow_unsigned", False):
        allowed = False
        findings.append(_finding("platform_policy_unsigned_plugin_denied", {"plugin_id": plugin_id}))
    if plugin_policy.get("required_signature", False) and not signed:
        allowed = False
        findings.append(_finding("platform_policy_plugin_signature_required", {"plugin_id": plugin_id}))
    trusted = set(plugin_policy.get("trusted_publishers", []))
    if trusted and publisher not in trusted:
        allowed = False
        findings.append(_finding("platform_policy_unknown_publisher_denied", {"publisher": publisher}))
    return {
        "plugin_id": plugin_id,
        "publisher": publisher,
        "signed": signed,
        "allowed": allowed,
        "findings": findings,
    }


def _evaluate_retention(policy: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    retention = policy.get("retention", {})
    legal_hold_active = bool(request.get("legal_hold_active", False))
    deletion_mode = str(request.get("deletion_mode") or retention.get("deletion_mode") or "metadata_only")
    effective_deletion_mode = "tombstone" if legal_hold_active else deletion_mode
    findings = []
    if legal_hold_active and deletion_mode == "full_delete":
        findings.append(_finding("platform_policy_legal_hold_overrides_full_delete"))
    return {
        "default_retention_days": retention.get("default_retention_days"),
        "unsafe_artifact_retention_days": retention.get("unsafe_artifact_retention_days"),
        "legal_hold_active": legal_hold_active,
        "requested_deletion_mode": deletion_mode,
        "effective_deletion_mode": effective_deletion_mode,
        "findings": findings,
    }


def _evaluate_scheduler_budget(policy: dict[str, Any]) -> dict[str, Any]:
    scheduler = dict(policy.get("scheduler") or {})
    max_concurrent_repos = _positive_int(scheduler.get("max_concurrent_repos"))
    max_concurrent_suites = _positive_int(scheduler.get("max_concurrent_suites"))
    max_concurrent_plugins = _positive_int(scheduler.get("max_concurrent_plugins"))
    lease_seconds = _positive_int(scheduler.get("lease_seconds"))
    heartbeat_seconds = _positive_int(scheduler.get("heartbeat_seconds"))
    findings = []

    if max_concurrent_repos is None:
        findings.append(_finding("platform_policy_scheduler_repo_budget_invalid"))
    if max_concurrent_suites is None and "max_concurrent_suites" in scheduler:
        findings.append(_finding("platform_policy_scheduler_suite_budget_invalid"))
    if max_concurrent_plugins is None and "max_concurrent_plugins" in scheduler:
        findings.append(_finding("platform_policy_scheduler_plugin_budget_invalid"))
    if lease_seconds is None:
        findings.append(_finding("platform_policy_scheduler_lease_invalid"))
    if heartbeat_seconds is None:
        findings.append(_finding("platform_policy_scheduler_heartbeat_invalid"))
    if lease_seconds is not None and heartbeat_seconds is not None and heartbeat_seconds >= lease_seconds:
        findings.append(_finding("platform_policy_scheduler_heartbeat_not_less_than_lease"))

    return {
        "max_concurrent_repos": max_concurrent_repos,
        "max_concurrent_suites": max_concurrent_suites,
        "max_concurrent_plugins": max_concurrent_plugins,
        "lease_seconds": lease_seconds,
        "heartbeat_seconds": heartbeat_seconds,
        "command_timeout_profiles": dict(scheduler.get("command_timeout_profiles") or {}),
        "retry_policy": dict(scheduler.get("retry_policy") or {}),
        "findings": findings,
    }


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


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


def _dedupe(values: list[Any]) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        marker = str(value)
        if marker and marker not in seen:
            seen.add(marker)
            result.append(value)
    return result
