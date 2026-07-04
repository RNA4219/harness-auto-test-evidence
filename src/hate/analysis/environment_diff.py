"""Environment diff analysis for HATE-GAP-055."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EnvironmentDiffFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_environment_diff_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_environment_diff_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "environment-diff-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_environment_diff_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "environment-diff-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["environment-diff"])
    diff_config = _normalize_diff_config(input_data.get("diff_config", input_data))
    diagnostics = _derive_diagnostics(diff_config)
    findings = _findings_for(diff_config, diagnostics, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "environment-diff-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "diff_config": diff_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "delta_count": len(diff_config["environment_deltas"]),
            "drift_class_count": len(diff_config["drift_classes"]),
            "attempt_count": len(diff_config["attempts_compared"]),
            "derived_delta_count": len(diagnostics["derived_deltas"]),
            "missing_snapshot_count": len(diagnostics["missing_snapshot_attempt_ids"]),
            "duplicate_attempt_count": len(diagnostics["duplicate_attempt_ids"]),
            "unexplained_derived_delta_count": len(diagnostics["unexplained_derived_delta_ids"]),
            "confidence": diff_config["confidence"],
            "finding_count": len(findings),
        },
        "environment_deltas": diff_config["environment_deltas"],
        "attempts_compared": diff_config["attempts_compared"],
        "drift_classes": diff_config["drift_classes"],
        "environment_diff_diagnostics": diagnostics,
        "analysis_scope": diff_config["analysis_scope"],
        "input_refs": diff_config["input_refs"],
        "confidence": diff_config["confidence"],
        "limits": diff_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_diff_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    environment_deltas = [
        _normalize_environment_delta(d)
        for d in config.get("environment_deltas", [])
        if isinstance(d, dict)
    ]
    attempts_compared = [
        _normalize_attempt(a)
        for a in config.get("attempts_compared", [])
        if isinstance(a, dict)
    ]
    drift_classes = [
        _normalize_drift_class(c)
        for c in config.get("drift_classes", [])
        if isinstance(c, dict)
    ]
    return {
        "environment_deltas": environment_deltas,
        "attempts_compared": attempts_compared,
        "drift_classes": drift_classes,
        "runtime_version_drift_explained": bool(config.get("runtime_version_drift_explained", True)),
        "cache_state_known": bool(config.get("cache_state_known", True)),
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
    }


def _normalize_environment_delta(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "delta_id": str(d.get("delta_id", "") or ""),
        "delta_type": str(d.get("delta_type", "") or ""),
        "category": str(d.get("category", "") or ""),
        "severity": str(d.get("severity", "") or ""),
        "confidence": float(d.get("confidence", 0.0) or 0.0),
        "sourceRef": str(d.get("sourceRef", "") or ""),
        "rationale": str(d.get("rationale", "") or ""),
        "explained": bool(d.get("explained", True)),
    }


def _normalize_attempt(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt_id": str(a.get("attempt_id", "") or ""),
        "environment_ref": str(a.get("environment_ref", "") or ""),
        "timestamp": str(a.get("timestamp", "") or ""),
        "snapshot": dict(a.get("snapshot", {}) or {}),
    }


def _normalize_drift_class(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "class_id": str(c.get("class_id", "") or ""),
        "class_type": str(c.get("class_type", "") or ""),
        "drift_count": int(c.get("drift_count", 0) or 0),
        "severity": str(c.get("severity", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_deltas": int(limits.get("max_deltas", 100) or 100),
        "max_attempts": int(limits.get("max_attempts", 10) or 10),
        "max_drift_classes": int(limits.get("max_drift_classes", 20) or 20),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _derive_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    attempt_ids = [a["attempt_id"] for a in config["attempts_compared"] if a["attempt_id"]]
    seen: set[str] = set()
    duplicate_attempt_ids: list[str] = []
    for attempt_id in attempt_ids:
        if attempt_id in seen and attempt_id not in duplicate_attempt_ids:
            duplicate_attempt_ids.append(attempt_id)
        seen.add(attempt_id)

    missing_snapshot_attempt_ids = sorted(
        a["attempt_id"] or a["environment_ref"] or "unknown"
        for a in config["attempts_compared"]
        if not a["snapshot"]
    )
    derived_deltas = _derive_snapshot_deltas(config["attempts_compared"])
    explained_delta_keys = {
        _delta_key(d["category"], d["delta_type"])
        for d in config["environment_deltas"]
        if d.get("explained")
    }
    unexplained_derived_delta_ids = sorted(
        d["delta_id"]
        for d in derived_deltas
        if _delta_key(d["category"], d["delta_type"]) not in explained_delta_keys
    )
    return {
        "derived_deltas": derived_deltas,
        "missing_snapshot_attempt_ids": missing_snapshot_attempt_ids,
        "duplicate_attempt_ids": sorted(duplicate_attempt_ids),
        "unexplained_derived_delta_ids": unexplained_derived_delta_ids,
    }


def _derive_snapshot_deltas(attempts: list[dict[str, Any]]) -> list[dict[str, str]]:
    attempts_with_snapshots = [a for a in attempts if a["snapshot"]]
    if len(attempts_with_snapshots) < 2:
        return []
    baseline = attempts_with_snapshots[0]
    deltas: list[dict[str, str]] = []
    for attempt in attempts_with_snapshots[1:]:
        for key, baseline_value in baseline["snapshot"].items():
            if key not in attempt["snapshot"]:
                continue
            current_value = attempt["snapshot"][key]
            if current_value == baseline_value:
                continue
            category, delta_type = _classify_snapshot_key(str(key))
            deltas.append({
                "delta_id": f"{baseline['attempt_id']}..{attempt['attempt_id']}:{key}",
                "category": category,
                "delta_type": delta_type,
                "baseline_attempt_id": baseline["attempt_id"],
                "current_attempt_id": attempt["attempt_id"],
                "field": str(key),
                "baseline_value": str(baseline_value),
                "current_value": str(current_value),
            })
    return deltas


def _classify_snapshot_key(key: str) -> tuple[str, str]:
    lowered = key.lower()
    if lowered in {"python", "python_version", "node", "node_version", "java", "go", "rust"}:
        return "runtime", "runtime_version_drift"
    if lowered in {"os", "os_version", "runner_os", "kernel"}:
        return "os", "os_drift"
    if "browser" in lowered:
        return "browser", "browser_version_drift"
    if lowered in {"container", "image", "image_digest", "docker_image"}:
        return "container", "container_drift"
    if "dependency" in lowered or lowered in {"lockfile_hash", "package_lock_hash", "uv_lock_hash"}:
        return "dependency", "dependency_drift"
    if "cache" in lowered:
        return "cache", "cache_drift"
    if lowered.startswith("env.") or lowered.startswith("env_"):
        return "env", "env_var_drift"
    if "service" in lowered:
        return "service", "service_drift"
    if "shard" in lowered:
        return "shard", "shard_drift"
    return "environment", "environment_drift"


def _delta_key(category: str, delta_type: str) -> str:
    return f"{category}:{delta_type}"


def _findings_for(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[EnvironmentDiffFinding]:
    findings: list[EnvironmentDiffFinding] = []

    # HATE-GAP-055 primary negative: unexplained drift
    runtime_drifts = [
        d for d in config["environment_deltas"]
        if d.get("delta_type") == "runtime_version_drift" and not d.get("explained")
    ]

    if runtime_drifts:
        findings.append(_finding(
            "environment_diff_unexplained_drift_hold",
            "Unexplained runtime version drift detected.",
            source_ref,
        ))

    if diagnostics["unexplained_derived_delta_ids"]:
        findings.append(_finding(
            "environment_diff_unexplained_derived_drift_hold",
            f"Derived environment drift lacks matching explained delta: {', '.join(diagnostics['unexplained_derived_delta_ids'])}.",
            source_ref,
        ))

    if diagnostics["missing_snapshot_attempt_ids"]:
        findings.append(_finding(
            "environment_diff_attempt_snapshot_missing",
            f"Environment snapshots missing for attempts: {', '.join(diagnostics['missing_snapshot_attempt_ids'])}.",
            source_ref,
        ))

    if diagnostics["duplicate_attempt_ids"]:
        findings.append(_finding(
            "environment_diff_duplicate_attempt_id",
            f"Duplicate attempt ids detected: {', '.join(diagnostics['duplicate_attempt_ids'])}.",
            source_ref,
        ))

    # Additional finding: runtime_version_drift_explained flag false
    if not config["runtime_version_drift_explained"]:
        runtime_deltas = [d for d in config["environment_deltas"] if d.get("delta_type") == "runtime_version_drift"]
        if runtime_deltas:
            findings.append(_finding(
                "environment_diff_unexplained_drift_hold",
                "Runtime version drift not marked as explained.",
                source_ref,
            ))

    # Additional finding: cache_state_unknown
    if not config["cache_state_known"]:
        findings.append(_finding(
            "environment_diff_cache_state_unknown",
            "Cache state not known for environment comparison.",
            source_ref,
        ))

    # Check for missing sourceRef on deltas
    for d in config["environment_deltas"]:
        if not d.get("sourceRef"):
            findings.append(_finding(
                "environment_diff_unexplained_drift_hold",
                f"Environment delta '{d.get('delta_id')}' missing sourceRef.",
                source_ref,
            ))

    if len(config["environment_deltas"]) > config["limits"]["max_deltas"]:
        findings.append(_finding(
            "environment_diff_delta_budget_exceeded",
            f"Environment delta count {len(config['environment_deltas'])} exceeds limit {config['limits']['max_deltas']}.",
            source_ref,
        ))

    if len(config["attempts_compared"]) > config["limits"]["max_attempts"]:
        findings.append(_finding(
            "environment_diff_attempt_budget_exceeded",
            f"Attempt count {len(config['attempts_compared'])} exceeds limit {config['limits']['max_attempts']}.",
            source_ref,
        ))

    if len(config["drift_classes"]) > config["limits"]["max_drift_classes"]:
        findings.append(_finding(
            "environment_diff_drift_class_budget_exceeded",
            f"Drift class count {len(config['drift_classes'])} exceeds limit {config['limits']['max_drift_classes']}.",
            source_ref,
        ))

    # Confidence threshold check
    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "environment_diff_unexplained_drift_hold",
            f"Environment diff confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> EnvironmentDiffFinding:
    return EnvironmentDiffFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
