"""Tests for HATE-GAP-041..048 portfolio readiness expansion reports."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.portfolio_readiness import (
    build_developer_experience_report,
    build_governance_review_report,
    build_provider_integration_report,
    build_recurring_real_repo_eval_report,
    build_rollout_adoption_report,
    build_runner_dialect_coverage_report,
    build_security_procurement_report,
    build_value_measurement_report,
    evaluate_developer_experience_fixture,
    evaluate_governance_review_fixture,
    evaluate_provider_integration_fixture,
    evaluate_recurring_real_repo_eval_fixture,
    evaluate_rollout_adoption_fixture,
    evaluate_runner_dialect_coverage_fixture,
    evaluate_security_procurement_fixture,
    evaluate_value_measurement_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"
REGISTRY = SCHEMAS / "schema-registry.json"


CASES = [
    (
        "rollout-adoption",
        "staged-wave-pass",
        "expired-exception-blocks",
        "rollout-adoption-report",
        "rollout_config",
        evaluate_rollout_adoption_fixture,
        "rollout_adoption_expired_exception_blocks",
    ),
    (
        "provider-matrix",
        "gitlab-identity-pass",
        "overbroad-permission-denied",
        "provider-integration-report",
        "provider_config",
        evaluate_provider_integration_fixture,
        "provider_integration_overbroad_permission_denied",
    ),
    (
        "runner-dialects",
        "dotnet-xunit-pass",
        "unsupported-runner-capability-gap",
        "runner-dialect-coverage-report",
        "runner_config",
        evaluate_runner_dialect_coverage_fixture,
        "runner_dialect_unsupported_capability_gap",
    ),
    (
        "recurring-real-repo-eval",
        "baseline-trend-pass",
        "regression-timeout-hold",
        "recurring-real-repo-eval-report",
        "evaluation_config",
        evaluate_recurring_real_repo_eval_fixture,
        "recurring_eval_regression_detected",
    ),
    (
        "governance-workflow",
        "policy-approved-pass",
        "self-approval-denied",
        "governance-review-report",
        "governance_config",
        evaluate_governance_review_fixture,
        "governance_self_approval_denied",
    ),
    (
        "security-procurement",
        "trust-packet-safe",
        "unsupported-certification-claim",
        "security-procurement-report",
        "procurement_config",
        evaluate_security_procurement_fixture,
        "security_procurement_unsupported_certification_claim",
    ),
    (
        "value-measurement",
        "aggregate-roi-pass",
        "individual-leaderboard-denied",
        "value-measurement-report",
        "value_config",
        evaluate_value_measurement_fixture,
        "value_measurement_individual_leaderboard_denied",
    ),
    (
        "developer-experience",
        "actionable-pr-feedback",
        "broad-suppression-denied",
        "developer-experience-report",
        "dx_config",
        evaluate_developer_experience_fixture,
        "developer_experience_broad_suppression_denied",
    ),
]


def _fixture(area: str, name: str) -> dict:
    return json.loads((FIXTURES / area / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict, record_type: str, config_key: str) -> None:
    schema = json.loads((SCHEMAS / f"{record_type}.schema.json").read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == record_type
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert config_key in report
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_gap_041_048_canonical_fixture_paths_exist() -> None:
    for area, positive, negative, *_ in CASES:
        assert (FIXTURES / area / positive / "fixture.json").is_file()
        assert (FIXTURES / area / negative / "fixture.json").is_file()


def test_gap_041_048_positive_fixtures_pass() -> None:
    for area, positive, _negative, record_type, config_key, evaluator, _finding_code in CASES:
        result = evaluator(_fixture(area, positive))

        assert result["status"] == "pass"
        assert result["finding_code"] == ""
        assert result["readiness_effect"] == "none"
        _assert_report_contract(result["report"], record_type, config_key)


def test_gap_041_048_negative_fixtures_hold_with_exact_finding() -> None:
    for area, _positive, negative, record_type, config_key, evaluator, finding_code in CASES:
        result = evaluator(_fixture(area, negative))

        assert result["status"] == "hold"
        assert result["readiness_effect"] == "hold"
        assert finding_code in _codes(result["report"])
        _assert_report_contract(result["report"], record_type, config_key)


def test_gap_041_048_schema_registry_entries_exist() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    for _area, _positive, _negative, record_type, _config_key, _evaluator, _finding_code in CASES:
        assert records[record_type] == f"schemas/HATE/v1/{record_type}.schema.json"


def test_rollout_adoption_extra_no_go_conditions() -> None:
    report = build_rollout_adoption_report({
        "waves": [],
        "portfolio_metrics_safe": False,
        "rollback_plan_present": False,
    })

    assert {"rollout_adoption_wave_missing", "rollout_adoption_rollback_plan_missing"}.issubset(set(_codes(report)))


def test_provider_identity_ambiguity_is_hold() -> None:
    report = build_provider_integration_report({
        "required_providers": ["github"],
        "providers": [{"provider": "github", "support_state": "supported"}],
        "ambiguous_identity_detected": True,
    })

    assert "provider_integration_ambiguous_identity_hard_dq" in _codes(report)


def test_runner_support_claim_requires_conformance() -> None:
    report = build_runner_dialect_coverage_report({
        "required_families": ["dotnet"],
        "runner_families": [{"family": "dotnet", "support_state": "supported"}],
        "dialects": [{"dialect": "xunit", "family": "dotnet"}],
        "claim_without_conformance_detected": True,
    })

    assert "runner_dialect_claim_without_conformance" in _codes(report)


def test_recurring_eval_requires_privacy_safe_trend() -> None:
    report = build_recurring_real_repo_eval_report({
        "required_repo_classes": ["small"],
        "repo_roster": [{"repo": "repo-a", "class": "small"}],
        "runs": [{"run_id": "eval-001", "baseline_ref": "b", "current_result_ref": "c"}],
        "timeout_budget_by_class": {"small": 300},
        "trend_privacy_safe": False,
    })

    assert "recurring_eval_trend_privacy_unsafe" in _codes(report)


def test_governance_exception_requires_compensating_evidence() -> None:
    report = build_governance_review_report({
        "policy_templates": [{"author": "a", "approver": "b", "effective_date": "2026-07-01", "review_cadence": "quarterly", "rollback_owner": "c"}],
        "exception_requests": [{"owner": "qa", "expiry": "2026-08-01", "rationale": "gap", "affected_risks": ["r"], "reviewer_decision": "accepted"}],
    })

    assert "governance_exception_request_incomplete" in _codes(report)


def test_security_procurement_raw_export_is_denied() -> None:
    report = build_security_procurement_report({
        "security_review_packet": {"architecture": "a", "data_flow": "b", "data_classes": "c", "subprocessors": "d", "encryption": "e", "secrets_handling": "f", "retention_summary": "g"},
        "control_claims": [],
        "vulnerability_slas": [],
        "procurement_export_safe": False,
        "raw_artifact_in_export": True,
    })

    assert "security_procurement_raw_artifact_export_denied" in _codes(report)


def test_value_measurement_rejects_noisy_signal_as_value() -> None:
    report = build_value_measurement_report({
        "aggregate_metrics": [
            {"metric_id": "review_time_saved"},
            {"metric_id": "risk_debt_burn_down"},
            {"metric_id": "release_blocker_lead_time"},
            {"metric_id": "repeat_finding_rate"},
            {"metric_id": "avoided_unsupported_claims"},
        ],
        "safe_evidence_refs": ["safe"],
        "confidence": 0.8,
        "sample_size": 5,
        "baseline_present": True,
        "limitations": ["sample"],
        "noisy_signal_counts_as_value": True,
    })

    assert "value_measurement_noisy_signal_denied" in _codes(report)


def test_developer_experience_rejects_secret_feedback() -> None:
    report = build_developer_experience_report({
        "feedback_groups": [{"fix_action": "fix", "risk_impact": "high", "owner": "dev", "blocking_status": "hold", "deep_link": "pr://1"}],
        "local_explain_available": True,
        "local_replay_available": True,
        "suppression_controls": {"owner": "dev", "expiry_required": True},
        "recommendation_quality_score": 0.8,
        "latency_ms": 1000,
        "stable_deep_links": True,
        "raw_secret_present": True,
    })

    assert "developer_experience_raw_secret_denied" in _codes(report)
