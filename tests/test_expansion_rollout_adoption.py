"""Focused tests for HATE-GAP-041 rollout adoption diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.portfolio_readiness import (
    build_rollout_adoption_report,
    evaluate_rollout_adoption_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion"


def _fixture(area: str, case: str) -> dict[str, object]:
    return json.loads((FIXTURES / area / case / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict[str, object]) -> list[str]:
    return [finding["code"] for finding in report.get("findings", [])]


def _assert_rollout_contract(report: dict[str, object]) -> None:
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "rollout-adoption-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert "rollout_config" in report
    assert {
        "duplicate_waves",
        "duplicate_repos",
        "waves_missing_source_ref",
        "waves_without_order",
        "invalid_status_transition_repos",
        "adoption_gap_repos",
        "missing_repo_metadata",
        "exceptions_missing_expiry_or_review",
        "broad_exceptions",
        "unsafe_portfolio_metrics",
        "rollback_plan_incomplete",
    } <= set(report["rollout_diagnostics"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_rollout_adoption_extra_no_go_conditions() -> None:
    report = build_rollout_adoption_report({
        "waves": [],
        "portfolio_metrics_safe": False,
        "rollback_plan_present": False,
    })

    assert {"rollout_adoption_wave_missing", "rollout_adoption_rollback_plan_missing"}.issubset(set(_codes(report)))


def test_rollout_positive_fixture_has_rollout_diagnostics() -> None:
    result = evaluate_rollout_adoption_fixture(_fixture("rollout-adoption", "staged-wave-pass"))
    report = result["report"]

    assert result["status"] == "pass"
    assert report["rollout_diagnostics"]["invalid_status_transition_repos"] == []
    assert report["rollout_diagnostics"]["unsafe_portfolio_metrics"] == []
    assert report["summary"]["portfolio_metric_count"] == 1
    assert report["summary"]["wave_source_ref_gap_count"] == 0
    _assert_rollout_contract(report)


def test_rollout_invalid_transition_metadata_and_metric_hold() -> None:
    report = build_rollout_adoption_report({
        "waves": [
            {
                "wave_id": "wave-1",
                "owner": "platform",
                "policy_template": "default",
                "entry_criteria": "entry",
                "exit_criteria": "exit",
            },
            {
                "wave_id": "wave-1",
                "owner": "platform",
                "policy_template": "default",
                "entry_criteria": "entry",
                "exit_criteria": "exit",
            },
        ],
        "repo_statuses": [
            {"repo": "repo-a", "previous_status": "retired", "status": "active", "adoption_gap": True},
            {"repo": "repo-a", "previous_status": "planned", "status": "bootstrapping"},
        ],
        "exceptions": [{"exception_id": "ex-1", "owner": "platform", "scope": "global"}],
        "portfolio_metrics": [
            {
                "metric_id": "unsafe",
                "aggregate_only": False,
                "contains_raw_repo_name": True,
                "contains_test_name": True,
            }
        ],
        "rollback_plan": {},
        "portfolio_metrics_safe": True,
        "rollback_plan_present": True,
    })

    codes = _codes(report)
    assert "rollout_adoption_duplicate_record" in codes
    assert "rollout_adoption_wave_traceability_missing" in codes
    assert "rollout_adoption_illegal_status_transition" in codes
    assert "rollout_adoption_repo_metadata_missing" in codes
    assert "rollout_adoption_gap_unresolved" in codes
    assert "rollout_adoption_exception_review_incomplete" in codes
    assert "rollout_adoption_broad_exception_denied" in codes
    assert "rollout_adoption_portfolio_metrics_unsafe" in codes
    assert "rollout_adoption_rollback_plan_missing" in codes
    _assert_rollout_contract(report)
