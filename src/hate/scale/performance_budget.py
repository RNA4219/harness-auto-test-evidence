"""Performance budget evaluation for scale manifests and run metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


OPERATIONS = (
    "ingest",
    "validation",
    "graph_build",
    "store_index",
    "replay",
    "report_generation",
)

DEFAULT_THRESHOLDS_MS = {
    "ingest": 300_000,
    "validation": 120_000,
    "graph_build": 180_000,
    "store_index": 90_000,
    "replay": 120_000,
    "report_generation": 60_000,
}

PROFILE_EFFECTS = {
    "default": {
        "missing_metrics": "hold",
        "soft_gap_ratio": 1.10,
        "hold_ratio": 1.50,
        "hard_dq_ratio": 3.00,
    },
    "product": {
        "missing_metrics": "hard_dq",
        "soft_gap_ratio": 1.05,
        "hold_ratio": 1.25,
        "hard_dq_ratio": 2.00,
    },
    "release": {
        "missing_metrics": "hard_dq",
        "soft_gap_ratio": 1.00,
        "hold_ratio": 1.10,
        "hard_dq_ratio": 1.50,
    },
}


@dataclass(frozen=True)
class PerformanceBudgetInput:
    """Input metrics for evaluating performance budgets."""

    scenario_id: str
    profile: str
    dataset_shape: dict[str, int]
    observed_ms: dict[str, int | float | None] = field(default_factory=dict)
    estimated_counters: dict[str, int | float] = field(default_factory=dict)
    thresholds_ms: dict[str, int | float] = field(default_factory=dict)
    sourceRefs: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PerformanceBudgetInput":
        return cls(
            scenario_id=data["scenario_id"],
            profile=data.get("profile", "default"),
            dataset_shape={key: int(value) for key, value in data.get("dataset_shape", {}).items()},
            observed_ms=data.get("observed_ms", {}),
            estimated_counters=data.get("estimated_counters", {}),
            thresholds_ms=data.get("thresholds_ms", {}),
            sourceRefs=data.get("sourceRefs", []),
        )


def evaluate_performance_budget(input_data: PerformanceBudgetInput | dict[str, Any]) -> dict[str, Any]:
    """Evaluate operation budgets and return a scale-performance-report."""
    budget_input = (
        PerformanceBudgetInput.from_dict(input_data)
        if isinstance(input_data, dict)
        else input_data
    )
    profile_config = PROFILE_EFFECTS.get(budget_input.profile, PROFILE_EFFECTS["default"])
    thresholds = {**DEFAULT_THRESHOLDS_MS, **budget_input.thresholds_ms}

    budget_results: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    effects: list[str] = []

    for operation in OPERATIONS:
        threshold = thresholds[operation]
        observed = budget_input.observed_ms.get(operation)
        if observed is None:
            effect = profile_config["missing_metrics"]
            finding = _finding(
                "missing_performance_metric",
                effect,
                f"Missing performance metric for {operation}",
                budget_input,
                operation,
            )
            findings.append(finding)
            effects.append(effect)
            budget_results.append(_budget_row(operation, threshold, None, "not_run", effect))
            continue

        ratio = float(observed) / float(threshold) if threshold else 0.0
        effect = _effect_for_ratio(ratio, profile_config)
        status = "pass" if effect == "pass" else "fail"
        budget_results.append(_budget_row(operation, threshold, observed, status, effect))
        effects.append(effect)
        if effect != "pass":
            findings.append(_finding(
                "performance_budget_exceeded",
                effect,
                f"{operation} exceeded budget ratio {ratio:.2f}",
                budget_input,
                operation,
                {"ratio": round(ratio, 4), "threshold_ms": threshold, "observed_ms": observed},
            ))

    quadratic_findings = _detect_quadratic_risk(budget_input)
    findings.extend(quadratic_findings)
    effects.extend(item["readiness_effect"] for item in quadratic_findings)

    overall_effect = _worst_effect(effects)
    return {
        "schema_version": "HATE/v1",
        "record_type": "scale-performance-report",
        "scenario_id": budget_input.scenario_id,
        "profile": budget_input.profile,
        "dataset_shape": budget_input.dataset_shape,
        "scale_targets": {
            "tests": budget_input.dataset_shape.get("tests", 0),
            "coverage_records": budget_input.dataset_shape.get("coverage_records", 0),
            "artifact_metadata": budget_input.dataset_shape.get("artifact_metadata", 0),
            "graph_nodes": budget_input.dataset_shape.get("graph_nodes", 0),
            "graph_edges": budget_input.dataset_shape.get("graph_edges", 0),
        },
        "budgets": budget_results,
        "estimated_counters": budget_input.estimated_counters,
        "resource_limits": {
            "max_memory_mb": int(budget_input.estimated_counters.get("peak_memory_mb", 512)),
            "max_input_bytes": int(budget_input.estimated_counters.get("input_bytes", 0)),
            "max_archive_entries": int(budget_input.estimated_counters.get("archive_entries", 0)),
        },
        "pagination": {
            "required": _pagination_required(budget_input.dataset_shape),
            "tested": bool(budget_input.estimated_counters.get("pagination_tested", False)),
        },
        "staleness": {
            "cache_invalidation_tested": bool(budget_input.estimated_counters.get("cache_invalidation_tested", False)),
        },
        "findings": findings,
        "overall_status": _status_for_effect(overall_effect),
        "readiness_effect": overall_effect,
        "sourceRefs": budget_input.sourceRefs,
    }


def _effect_for_ratio(ratio: float, profile_config: dict[str, Any]) -> str:
    if ratio <= profile_config["soft_gap_ratio"]:
        return "pass"
    if ratio <= profile_config["hold_ratio"]:
        return "soft_gap"
    if ratio <= profile_config["hard_dq_ratio"]:
        return "hold"
    return "hard_dq"


def _detect_quadratic_risk(budget_input: PerformanceBudgetInput) -> list[dict[str, Any]]:
    counters = budget_input.estimated_counters
    dataset = budget_input.dataset_shape
    item_count = max(
        int(dataset.get("tests", 0)),
        int(dataset.get("graph_nodes", 0)),
        int(dataset.get("artifact_metadata", 0)),
        1,
    )
    pairwise = int(counters.get("pairwise_comparisons", 0))
    if pairwise <= item_count * max(1, item_count.bit_length()) * 8:
        return []
    return [_finding(
        "quadratic_complexity_risk",
        "hard_dq",
        "Measured/estimated pairwise comparisons indicate unsupported O(N^2) behavior",
        budget_input,
        "complexity",
        {"pairwise_comparisons": pairwise, "item_count": item_count},
    )]


def _budget_row(
    operation: str,
    threshold: int | float,
    observed: int | float | None,
    status: str,
    readiness_effect: str,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "target_ms": threshold,
        "observed_ms": observed,
        "status": status,
        "readiness_effect": readiness_effect,
    }


def _finding(
    code: str,
    readiness_effect: str,
    message: str,
    budget_input: PerformanceBudgetInput,
    operation: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "critical" if readiness_effect == "hard_dq" else readiness_effect,
        "readiness_effect": readiness_effect,
        "message": message,
        "operation": operation,
        "sourceRef": f"fixtures/scale/performance/{budget_input.scenario_id}/fixture.json",
        "details": details or {},
    }


def _worst_effect(effects: list[str]) -> str:
    order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
    if not effects:
        return "pass"
    return max(effects, key=lambda item: order[item])


def _status_for_effect(effect: str) -> str:
    return {
        "pass": "pass",
        "soft_gap": "soft_gap",
        "hold": "hold",
        "hard_dq": "blocked",
    }[effect]


def _pagination_required(dataset_shape: dict[str, int]) -> bool:
    return (
        dataset_shape.get("tests", 0) > 1000
        or dataset_shape.get("coverage_records", 0) > 10000
        or dataset_shape.get("artifact_metadata", 0) > 1000
        or dataset_shape.get("graph_nodes", 0) > 10000
    )
