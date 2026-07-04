from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


REQUIRED_SCENARIOS = {
    "100-repo-roster",
    "1000-repo-roster",
    "100k-findings",
    "1m-findings",
    "large-monorepo",
    "cold-cache",
    "warm-cache",
}


@dataclass(frozen=True)
class CapacityFinding:
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


def evaluate_capacity_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    report = build_capacity_report(
        payload.get("input", {}),
        report_id=str(payload.get("fixture_id") or "capacity-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_capacity_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "capacity-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["capacity"])
    runs = [_normalize_run(item) for item in input_data.get("runs", [])]
    machine_profile = _normalize_machine_profile(input_data.get("machine_profile", {}))
    baseline = _baseline_record(input_data, runs, machine_profile)
    degradation = _degradation_report(runs)
    findings = _findings_for(runs, machine_profile, baseline, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "capacity-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "benchmark_runs": runs,
        "baseline_record": baseline,
        "degradation_report": degradation,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "scenario_count": len(runs),
            "dataset_hashes": sorted({run["dataset_hash"] for run in runs if run["dataset_hash"]}),
            "budget_status": "hold" if findings else "within_budget",
            "degradation_modes": sorted({run["degradation_mode"] for run in runs if run["degradation_mode"]}),
            "machine_profile_present": bool(machine_profile["profile_id"] and machine_profile["cpu_model"]),
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_capacity_regression_packet(
    current_input: dict[str, Any],
    previous_input: dict[str, Any],
    *,
    packet_id: str = "capacity-regression-packet",
    source_refs: list[str] | None = None,
    runtime_regression_threshold: float = 0.2,
    memory_regression_threshold: float = 0.2,
    cache_drop_threshold: float = 0.1,
) -> dict[str, Any]:
    source_refs = list(source_refs or current_input.get("sourceRefs") or ["capacity-regression"])
    current = (
        current_input
        if current_input.get("record_type") == "capacity-report"
        else build_capacity_report(current_input, report_id=f"{packet_id}:current", source_refs=source_refs)
    )
    previous = (
        previous_input
        if previous_input.get("record_type") == "capacity-report"
        else build_capacity_report(previous_input, report_id=f"{packet_id}:previous", source_refs=source_refs)
    )
    comparisons = _capacity_comparisons(
        current.get("benchmark_runs", []),
        previous.get("benchmark_runs", []),
        runtime_regression_threshold,
        memory_regression_threshold,
        cache_drop_threshold,
    )
    findings = _capacity_regression_findings(current, previous, comparisons, source_refs[0])
    packet = {
        "schema_version": "HATE/v1",
        "record_type": "capacity-regression-packet",
        "packet_id": packet_id,
        **productization_envelope(current_input, report_id=packet_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "current_report_id": current.get("report_id", ""),
        "previous_report_id": previous.get("report_id", ""),
        "comparisons": comparisons,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "comparison_count": len(comparisons),
            "regression_count": sum(1 for item in comparisons if item["regression_detected"]),
            "missing_previous_count": sum(1 for item in comparisons if item["comparison_status"] == "missing_previous"),
            "finding_count": len(findings),
            "ready_for_capacity_promotion": not findings,
        },
        "sourceRefs": sorted(set(source_refs + list(current.get("sourceRefs", [])) + list(previous.get("sourceRefs", [])))),
    }
    return apply_productization_contract_tree(packet, source_refs=source_refs)


def write_capacity_regression_packet(packet: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "capacity-regression-packet-artifact",
        **productization_envelope(packet, report_id=f"{packet.get('packet_id') or 'capacity-regression-packet'}:artifact", source_refs=list(packet.get("sourceRefs", []))),
        "readiness_effect": str(packet.get("readiness_effect") or "none"),
        "artifact_path": str(path),
        "comparison_count": len(packet.get("comparisons", [])),
        "sourceRefs": list(packet.get("sourceRefs", [])),
    }


def _capacity_comparisons(
    current_runs: list[dict[str, Any]],
    previous_runs: list[dict[str, Any]],
    runtime_threshold: float,
    memory_threshold: float,
    cache_drop_threshold: float,
) -> list[dict[str, Any]]:
    previous_by_scenario = {run["scenario_id"]: run for run in previous_runs}
    comparisons: list[dict[str, Any]] = []
    for run in current_runs:
        previous = previous_by_scenario.get(run["scenario_id"])
        if not previous:
            comparisons.append({
                "record_type": "capacity-regression-comparison",
                "scenario_id": run["scenario_id"],
                "comparison_status": "missing_previous",
                "runtime_delta_ratio": None,
                "memory_delta_ratio": None,
                "cache_hit_delta": None,
                "regression_detected": True,
                "regression_reasons": ["capacity_previous_baseline_missing"],
            })
            continue
        runtime_delta = _ratio_delta(run["duration_ms"], previous["duration_ms"])
        memory_delta = _ratio_delta(run["peak_memory_mb"], previous["peak_memory_mb"])
        cache_delta = round(run["cache_hit_rate"] - previous["cache_hit_rate"], 4)
        reasons: list[str] = []
        if runtime_delta is not None and runtime_delta > runtime_threshold:
            reasons.append("capacity_runtime_regression")
        if memory_delta is not None and memory_delta > memory_threshold:
            reasons.append("capacity_memory_regression")
        if cache_delta < -cache_drop_threshold:
            reasons.append("capacity_cache_regression")
        if run["budget_status"] != "within_budget":
            reasons.append("capacity_budget_status_regression")
        comparisons.append({
            "record_type": "capacity-regression-comparison",
            "scenario_id": run["scenario_id"],
            "comparison_status": "compared",
            "runtime_delta_ratio": runtime_delta,
            "memory_delta_ratio": memory_delta,
            "cache_hit_delta": cache_delta,
            "regression_detected": bool(reasons),
            "regression_reasons": reasons,
        })
    return comparisons


def _capacity_regression_findings(
    current: dict[str, Any],
    previous: dict[str, Any],
    comparisons: list[dict[str, Any]],
    source_ref: str,
) -> list[CapacityFinding]:
    findings: list[CapacityFinding] = []
    if current.get("findings"):
        findings.append(_finding("capacity_current_report_has_findings", "Current capacity report has findings.", source_ref))
    if previous.get("findings"):
        findings.append(_finding("capacity_previous_report_has_findings", "Previous capacity report has findings.", source_ref))
    for comparison in comparisons:
        for reason in comparison["regression_reasons"]:
            findings.append(_finding(reason, f"Capacity regression detected for {comparison['scenario_id']}.", source_ref))
    return findings


def _ratio_delta(current: int, previous: int) -> float | None:
    if previous <= 0:
        return None
    return round((current - previous) / previous, 4)


def _normalize_run(raw: dict[str, Any]) -> dict[str, Any]:
    run = dict(raw or {})
    duration_ms = _int(run.get("duration_ms"), 0)
    peak_memory_mb = _int(run.get("peak_memory_mb"), 0)
    runtime_budget_ms = _int(run.get("runtime_budget_ms"), -1)
    memory_budget_mb = _int(run.get("memory_budget_mb"), -1)
    return {
        "record_type": "capacity-benchmark-run",
        "scenario_id": str(run.get("scenario_id") or ""),
        "dataset_hash": str(run.get("dataset_hash") or ""),
        "repo_count": _int(run.get("repo_count"), 0),
        "finding_count": _int(run.get("finding_count"), 0),
        "duration_ms": duration_ms,
        "peak_memory_mb": peak_memory_mb,
        "cache_hit_rate": _float(run.get("cache_hit_rate"), 0.0),
        "timeout_count": _int(run.get("timeout_count"), 0),
        "degradation_mode": str(run.get("degradation_mode") or ""),
        "budget_status": str(run.get("budget_status") or _budget_status(duration_ms, peak_memory_mb, runtime_budget_ms, memory_budget_mb)),
        "runtime_budget_ms": runtime_budget_ms,
        "memory_budget_mb": memory_budget_mb,
    }


def _normalize_machine_profile(raw: dict[str, Any]) -> dict[str, Any]:
    profile = dict(raw or {})
    return {
        "profile_id": str(profile.get("profile_id") or ""),
        "cpu_model": str(profile.get("cpu_model") or ""),
        "logical_cores": _int(profile.get("logical_cores"), 0),
        "memory_mb": _int(profile.get("memory_mb"), 0),
        "os": str(profile.get("os") or ""),
    }


def _baseline_record(input_data: dict[str, Any], runs: list[dict[str, Any]], machine_profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "capacity-baseline-record",
        "baseline_id": str(input_data.get("baseline_id") or "capacity-baseline"),
        "machine_profile": machine_profile,
        "scenario_ids": [run["scenario_id"] for run in runs],
        "dataset_hashes": sorted({run["dataset_hash"] for run in runs if run["dataset_hash"]}),
        "run_count": len(runs),
    }


def _degradation_report(runs: list[dict[str, Any]]) -> dict[str, Any]:
    modes = sorted({run["degradation_mode"] for run in runs if run["degradation_mode"]})
    exceeded = [run["scenario_id"] for run in runs if run["budget_status"] != "within_budget" or run["timeout_count"] > 0]
    return {
        "record_type": "capacity-degradation-mode-report",
        "degradation_modes": modes,
        "budget_exceeded_scenarios": exceeded,
        "timeout_count": sum(run["timeout_count"] for run in runs),
    }


def _findings_for(
    runs: list[dict[str, Any]],
    machine_profile: dict[str, Any],
    baseline: dict[str, Any],
    source_ref: str,
) -> list[CapacityFinding]:
    findings: list[CapacityFinding] = []
    scenario_ids = {run["scenario_id"] for run in runs}
    dataset_hashes = {run["dataset_hash"] for run in runs if run["dataset_hash"]}
    if not runs or not machine_profile["profile_id"] or not machine_profile["cpu_model"]:
        findings.append(_finding("capacity_baseline_missing", "Measured baseline or machine profile is missing.", source_ref))
    if not dataset_hashes or any(not run["dataset_hash"].startswith("sha256:") for run in runs):
        findings.append(_finding("capacity_dataset_not_reproducible", "Every benchmark run requires a reproducible sha256 dataset hash.", source_ref))
    if any(run["runtime_budget_ms"] >= 0 and run["duration_ms"] > run["runtime_budget_ms"] for run in runs):
        findings.append(_finding("capacity_runtime_budget_exceeded", "One or more benchmark runs exceeded runtime budget.", source_ref))
    if any(run["memory_budget_mb"] >= 0 and run["peak_memory_mb"] > run["memory_budget_mb"] for run in runs):
        findings.append(_finding("capacity_memory_budget_exceeded", "One or more benchmark runs exceeded memory budget.", source_ref))
    if any(run["timeout_count"] > 0 or run["budget_status"] != "within_budget" for run in runs):
        missing_mode = [run for run in runs if (run["timeout_count"] > 0 or run["budget_status"] != "within_budget") and not run["degradation_mode"]]
        if missing_mode:
            findings.append(_finding("capacity_degradation_mode_missing", "Budget failures require an explicit degradation mode.", source_ref))
    if baseline["run_count"] and not REQUIRED_SCENARIOS.intersection(scenario_ids):
        findings.append(_finding("capacity_baseline_missing", "Benchmark baseline does not cover required capacity scenarios.", source_ref))
    return findings


def _budget_status(duration_ms: int, peak_memory_mb: int, runtime_budget_ms: int, memory_budget_mb: int) -> str:
    if runtime_budget_ms >= 0 and duration_ms > runtime_budget_ms:
        return "runtime_exceeded"
    if memory_budget_mb >= 0 and peak_memory_mb > memory_budget_mb:
        return "memory_exceeded"
    return "within_budget"


def _finding(code: str, message: str, source_ref: str) -> CapacityFinding:
    return CapacityFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
