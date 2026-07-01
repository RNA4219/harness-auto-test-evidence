"""Bounded real-repo evaluation score model."""

from __future__ import annotations

from typing import Any


COMPONENT_WEIGHTS = {
    "evidence_strength": 40.0,
    "coverage_confidence": 15.0,
    "oracle_confidence": 15.0,
    "freshness_score": 10.0,
    "stability_score": 10.0,
    "ownership_clarity": 10.0,
}


def build_real_repo_score_report(data: dict[str, Any], report_id: str = "real-repo-score") -> dict[str, Any]:
    """Build a bounded score report with explicit breakdown and decision basis."""
    components = _normalize_components(data.get("components", data))
    penalties = _normalize_penalties(data.get("penalties", data))
    score_breakdown = _score_breakdown(components, penalties)
    decision_basis = _decision_basis(components, penalties, score_breakdown)
    score = score_breakdown["score"]
    score_band = _score_band(score)
    return {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-score-report",
        "report_id": report_id,
        "repo_id": str(data.get("repo_id") or ""),
        "suite_id": str(data.get("suite_id") or "default"),
        "source_version": str(data.get("source_version") or ""),
        "policy_hash": str(data.get("policy_hash") or ""),
        "score": score,
        "score_band": score_band,
        "release_approval": False,
        "score_breakdown": score_breakdown,
        "decision_basis": decision_basis,
        "sourceRefs": list(data.get("sourceRefs") or [f"fixtures/platform/evaluation/{report_id}/fixture.json"]),
    }


def _normalize_components(data: dict[str, Any]) -> dict[str, float]:
    return {key: _clamp01(data.get(key, 0.0)) for key in COMPONENT_WEIGHTS}


def _normalize_penalties(data: dict[str, Any]) -> dict[str, float]:
    return {
        "regression_penalty": _bounded(data.get("regression_penalty", 0.0), 0.0, 40.0),
        "timeout_penalty": _bounded(data.get("timeout_penalty", 0.0), 0.0, 20.0),
        "record_collapse_penalty": _bounded(data.get("record_collapse_penalty", 0.0), 0.0, 30.0),
        "manual_debt_penalty": _bounded(data.get("manual_debt_penalty", 0.0), 0.0, 15.0),
        "expired_debt_penalty": _bounded(data.get("expired_debt_penalty", 0.0), 0.0, 50.0),
        "unsafe_artifact_penalty": _bounded(data.get("unsafe_artifact_penalty", 0.0), 0.0, 50.0),
    }


def _score_breakdown(components: dict[str, float], penalties: dict[str, float]) -> dict[str, Any]:
    component_points = {
        key: round(value * COMPONENT_WEIGHTS[key], 2)
        for key, value in components.items()
    }
    base_score = round(sum(component_points.values()), 2)
    penalty_total = round(sum(penalties.values()), 2)
    score = round(_bounded(base_score - penalty_total, 0.0, 100.0), 2)
    return {
        "component_weights": COMPONENT_WEIGHTS,
        "components": components,
        "component_points": component_points,
        "base_score": base_score,
        "penalties": penalties,
        "penalty_total": penalty_total,
        "score": score,
    }


def _decision_basis(components: dict[str, float], penalties: dict[str, float], breakdown: dict[str, Any]) -> list[dict[str, Any]]:
    basis = [
        {
            "basis_id": f"component:{key}",
            "kind": "component",
            "value": value,
            "points": breakdown["component_points"][key],
            "rationale": f"{key} contributes bounded weighted evidence.",
        }
        for key, value in components.items()
    ]
    basis.extend(
        {
            "basis_id": f"penalty:{key}",
            "kind": "penalty",
            "value": value,
            "points": -value,
            "rationale": f"{key} reduces confidence when the corresponding risk is present.",
        }
        for key, value in penalties.items()
        if value > 0
    )
    return basis


def _score_band(score: float) -> str:
    if score >= 85:
        return "strong"
    if score >= 70:
        return "usable"
    if score >= 50:
        return "weak"
    return "blocked"


def _clamp01(value: Any) -> float:
    return _bounded(value, 0.0, 1.0)


def _bounded(value: Any, lower: float, upper: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return min(upper, max(lower, number))
