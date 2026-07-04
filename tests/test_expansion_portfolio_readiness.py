"""Tests for HATE-GAP-041..048 portfolio readiness expansion reports."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.portfolio_readiness import (
    build_developer_experience_report,
    build_governance_review_report,
    build_provider_integration_report,
    build_recurring_real_repo_eval_report,
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
    if record_type == "provider-integration-report":
        assert "provider_diagnostics" in report
        assert {
            "duplicate_providers",
            "providers_missing_permission_policy",
            "providers_missing_artifact_policy",
            "providers_missing_annotation_policy",
            "providers_missing_rerun_policy",
            "overbroad_permission_providers",
            "permission_source_ref_missing_providers",
            "unsafe_artifact_policy_providers",
            "unsafe_annotation_policy_providers",
            "nondeterministic_rerun_providers",
        } <= set(report["provider_diagnostics"])
    if record_type == "rollout-adoption-report":
        assert "rollout_diagnostics" in report
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
    if record_type == "runner-dialect-coverage-report":
        assert "runner_diagnostics" in report
        assert {
            "duplicate_dialects",
            "missing_capabilities_by_dialect",
            "unsupported_capabilities_by_dialect",
            "summary_mismatch_dialects",
            "missing_source_ref_dialects",
            "noisy_without_filter_dialects",
            "partial_parse_without_gap_dialects",
            "malformed_fixture_missing_dialects",
        } <= set(report["runner_diagnostics"])
    if record_type == "recurring-real-repo-eval-report":
        assert "recurring_eval_diagnostics" in report
        assert {
            "duplicate_repos",
            "missing_owner_repos",
            "missing_source_ref_repos",
            "external_unclassified_repos",
            "stale_or_unhealthy_repos",
            "runs_missing_identity",
            "runs_with_baseline_profile_mismatch",
            "runs_with_timeout_budget_exceeded",
            "runs_without_privacy_fingerprint",
            "parser_gap_without_review_runs",
            "duplicate_trend_windows",
            "unsafe_trend_windows",
            "retry_rules_without_isolation",
        } <= set(report["recurring_eval_diagnostics"])
    if record_type == "governance-review-report":
        assert "governance_diagnostics" in report
        assert {
            "duplicate_policy_templates",
            "duplicate_exception_requests",
            "templates_missing_source_ref",
            "templates_missing_diff_or_rollback",
            "templates_missing_separation",
            "exceptions_missing_source_ref",
            "exceptions_missing_risk_or_evidence",
            "exceptions_missing_audit_event",
            "broad_exception_requests",
            "delegations_without_bounds",
            "delegation_conflicts",
            "review_packet_missing_source_ref",
        } <= set(report["governance_diagnostics"])
    if record_type == "value-measurement-report":
        assert "value_diagnostics" in report
        assert {
            "missing_required_metrics",
            "missing_evidence_metrics",
            "missing_confidence_interval_metrics",
            "wrong_direction_metrics",
            "causal_claim_without_counterfactual",
            "sample_size_below_minimum",
            "roi_inputs_missing_period_or_cost_basis",
            "counterfactual_missing_basis",
            "privacy_violation",
        } <= set(report["value_diagnostics"])
    if record_type == "security-procurement-report":
        assert "procurement_diagnostics" in report
        assert {
            "duplicate_control_claims",
            "claims_missing_evidence",
            "stale_control_claims",
            "claims_missing_reviewer_decision",
            "vulnerability_slas_missing_owner_due",
            "export_manifest_missing",
            "unsafe_export_detected",
            "review_decisions_without_source_ref",
        } <= set(report["procurement_diagnostics"])
    if record_type == "developer-experience-report":
        assert "dx_diagnostics" in report
        assert {
            "missing_source_ref_groups",
            "missing_explain_or_replay_groups",
            "generic_feedback_groups",
            "suppression_scope",
            "suppression_has_review_record",
            "recommendation_actions_count",
            "command_loop_complete",
            "latency_budget_exceeded",
        } <= set(report["dx_diagnostics"])
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


def test_provider_identity_ambiguity_is_hold() -> None:
    report = build_provider_integration_report({
        "required_providers": ["github"],
        "providers": [{"provider": "github", "support_state": "supported"}],
        "ambiguous_identity_detected": True,
    })

    assert "provider_integration_ambiguous_identity_hard_dq" in _codes(report)


def test_provider_positive_fixture_has_full_policy_diagnostics() -> None:
    result = evaluate_provider_integration_fixture(_fixture("provider-matrix", "gitlab-identity-pass"))
    report = result["report"]

    assert result["status"] == "pass"
    assert report["provider_diagnostics"]["providers_missing_permission_policy"] == []
    assert report["provider_diagnostics"]["providers_missing_artifact_policy"] == []
    assert report["provider_diagnostics"]["providers_missing_annotation_policy"] == []
    assert report["provider_diagnostics"]["providers_missing_rerun_policy"] == []
    assert report["summary"]["permission_rule_count"] == 8
    assert report["summary"]["unsafe_artifact_policy_count"] == 0
    _assert_report_contract(report, "provider-integration-report", "provider_config")


def test_provider_missing_policies_and_raw_token_hold() -> None:
    report = build_provider_integration_report({
        "required_providers": ["github"],
        "providers": [
            {
                "provider": "github",
                "support_state": "supported",
                "commit_identity": "sha",
                "review_identity": "pr",
                "run_attempt": "run_attempt",
                "artifact_lifetime": "90d",
                "annotation_target": "check-run",
                "rerun_semantics": "attempt",
            }
        ],
        "minimum_permissions_declared": True,
        "raw_token_present": True,
    })

    codes = _codes(report)
    assert "provider_integration_permission_policy_missing" in codes
    assert "provider_integration_artifact_policy_missing" in codes
    assert "provider_integration_annotation_policy_missing" in codes
    assert "provider_integration_rerun_policy_missing" in codes
    assert "provider_integration_raw_token_denied" in codes
    assert report["summary"]["missing_permission_policy_count"] == 1
    _assert_report_contract(report, "provider-integration-report", "provider_config")


def test_provider_unsafe_artifact_annotation_and_rerun_hold() -> None:
    report = build_provider_integration_report({
        "required_providers": ["github"],
        "providers": [
            {
                "provider": "github",
                "support_state": "supported",
                "commit_identity": "sha",
                "review_identity": "pr",
                "run_attempt": "run_attempt",
                "artifact_lifetime": "90d",
                "annotation_target": "check-run",
                "rerun_semantics": "attempt",
            },
            {
                "provider": "github",
                "support_state": "supported",
                "commit_identity": "sha",
                "review_identity": "pr",
                "run_attempt": "run_attempt",
                "artifact_lifetime": "90d",
                "annotation_target": "check-run",
                "rerun_semantics": "attempt",
            },
        ],
        "permission_matrix": [{"provider": "github", "scope": "admin", "sourceRef": ""}],
        "artifact_policies": [{"provider": "github", "retention_days": 0, "redaction": False, "allows_raw_logs": True}],
        "annotation_policies": [{"provider": "github", "stable_target": False, "sourceRef": "", "can_post_secret": True}],
        "rerun_policies": [{"provider": "github", "attempt_identity": "", "idempotency_key": "", "preserves_previous_attempt": False}],
        "minimum_permissions_declared": True,
    })

    codes = _codes(report)
    assert "provider_integration_duplicate_provider" in codes
    assert "provider_integration_overbroad_permission_denied" in codes
    assert "provider_integration_permission_source_ref_missing" in codes
    assert "provider_integration_artifact_policy_unsafe" in codes
    assert "provider_integration_annotation_policy_unsafe" in codes
    assert "provider_integration_rerun_nondeterministic" in codes
    assert report["provider_diagnostics"]["duplicate_providers"] == ["github"]


def test_runner_support_claim_requires_conformance() -> None:
    report = build_runner_dialect_coverage_report({
        "required_families": ["dotnet"],
        "runner_families": [{"family": "dotnet", "support_state": "supported"}],
        "dialects": [{"dialect": "xunit", "family": "dotnet"}],
        "claim_without_conformance_detected": True,
    })

    assert "runner_dialect_claim_without_conformance" in _codes(report)


def test_runner_positive_fixture_has_capability_diagnostics() -> None:
    result = evaluate_runner_dialect_coverage_fixture(_fixture("runner-dialects", "dotnet-xunit-pass"))
    report = result["report"]

    assert result["status"] == "pass"
    assert report["runner_diagnostics"]["missing_capabilities_by_dialect"] == {}
    assert report["runner_diagnostics"]["summary_mismatch_dialects"] == []
    assert report["summary"]["required_capability_count"] == 5
    assert all(item["passed"] for item in report["results"])
    _assert_report_contract(report, "runner-dialect-coverage-report", "runner_config")


def test_runner_missing_capability_summary_and_noise_hold() -> None:
    report = build_runner_dialect_coverage_report({
        "required_families": ["dotnet"],
        "runner_families": [{"family": "dotnet", "support_state": "supported"}],
        "required_capabilities": ["summary_counts", "failure_location", "duration", "retry_attempt", "stdout_noise_filter"],
        "dialects": [
            {
                "dialect": "mstest",
                "family": "dotnet",
                "conformance_fixture_ref": "fixture:mstest",
                "malformed_fixture_ref": "",
                "sourceRef": "",
                "capabilities": ["summary_counts"],
                "expected_summary": {"passed": 4, "failed": 0},
                "observed_summary": {"passed": 3, "failed": 1},
                "noise_lines": ["SDK banner"],
                "ignored_noise": [],
                "parser_status": "parsed",
            }
        ],
    })

    codes = _codes(report)
    assert "runner_dialect_required_capability_missing" in codes
    assert "runner_dialect_summary_mismatch" in codes
    assert "runner_dialect_source_ref_missing" in codes
    assert "runner_dialect_noise_filter_missing" in codes
    assert "runner_dialect_malformed_fixture_missing" in codes
    assert report["summary"]["missing_capability_dialect_count"] == 1
    assert report["results"][0]["passed"] is False
    _assert_report_contract(report, "runner-dialect-coverage-report", "runner_config")


def test_runner_partial_parse_requires_gap_and_raw_log_denied() -> None:
    report = build_runner_dialect_coverage_report({
        "required_families": ["rust"],
        "runner_families": [{"family": "rust", "support_state": "partial"}],
        "required_capabilities": ["summary_counts"],
        "dialects": [
            {
                "dialect": "nextest-json",
                "family": "rust",
                "conformance_fixture_ref": "fixture:nextest",
                "malformed_fixture_ref": "fixture:nextest-malformed",
                "sourceRef": "runner:nextest",
                "capabilities": ["summary_counts"],
                "expected_summary": {"passed": 10},
                "observed_summary": {"passed": 10},
                "parser_status": "partial",
            }
        ],
        "raw_log_retention_denied": True,
    })

    codes = _codes(report)
    assert "runner_dialect_partial_parse_gap_missing" in codes
    assert "runner_dialect_raw_log_retention_denied" in codes
    assert report["runner_diagnostics"]["partial_parse_without_gap_dialects"] == ["nextest-json"]


def test_recurring_eval_requires_privacy_safe_trend() -> None:
    report = build_recurring_real_repo_eval_report({
        "required_repo_classes": ["small"],
        "repo_roster": [{"repo": "repo-a", "class": "small"}],
        "runs": [{"run_id": "eval-001", "baseline_ref": "b", "current_result_ref": "c"}],
        "timeout_budget_by_class": {"small": 300},
        "trend_privacy_safe": False,
    })

    assert "recurring_eval_trend_privacy_unsafe" in _codes(report)


def test_recurring_eval_positive_fixture_has_identity_and_safe_trends() -> None:
    result = evaluate_recurring_real_repo_eval_fixture(_fixture("recurring-real-repo-eval", "baseline-trend-pass"))
    report = result["report"]

    assert result["status"] == "pass"
    assert report["recurring_eval_diagnostics"]["runs_missing_identity"] == []
    assert report["recurring_eval_diagnostics"]["unsafe_trend_windows"] == []
    assert report["summary"]["trend_window_count"] == 1
    assert report["summary"]["retry_isolation_rule_count"] == 2
    _assert_report_contract(report, "recurring-real-repo-eval-report", "evaluation_config")


def test_recurring_eval_identity_profile_timeout_and_privacy_hold() -> None:
    report = build_recurring_real_repo_eval_report({
        "required_repo_classes": ["small"],
        "repo_roster": [
            {"repo": "repo-a", "class": "small", "owner": "qa", "ownership": "owned", "sourceRef": "repo:a", "health": "active"}
        ],
        "runs": [
            {
                "run_id": "eval-bad",
                "repo_class": "small",
                "baseline_ref": "baseline",
                "current_result_ref": "current",
                "baseline_profile": "default",
                "current_profile": "release",
                "duration_seconds": 600,
            }
        ],
        "timeout_budget_by_class": {"small": 300},
        "trend_windows": [{"window_id": "w1", "aggregate_only": False, "contains_raw_repo_name": True, "sample_size": 1}],
        "retry_isolation_rules": [{"rule_id": "timeout"}],
        "trend_privacy_safe": True,
        "quarantine_policy_present": True,
    })

    codes = _codes(report)
    assert "recurring_eval_run_identity_missing" in codes
    assert "recurring_eval_baseline_profile_mismatch" in codes
    assert "recurring_eval_timeout_budget_exceeded" in codes
    assert "recurring_eval_privacy_fingerprint_missing" in codes
    assert "recurring_eval_trend_window_unsafe" in codes
    assert "recurring_eval_retry_isolation_missing" in codes
    _assert_report_contract(report, "recurring-real-repo-eval-report", "evaluation_config")


def test_recurring_eval_roster_external_and_stale_hold() -> None:
    report = build_recurring_real_repo_eval_report({
        "required_repo_classes": ["small"],
        "repo_roster": [
            {"repo": "repo-a", "class": "small", "ownership": "owned", "health": "active"},
            {"repo": "repo-a", "class": "small", "ownership": "external", "health": "stale"},
        ],
        "runs": [{"run_id": "eval-1", "baseline_ref": "b", "current_result_ref": "c", "roster_hash": "r", "policy_hash": "p", "environment_fingerprint": "e", "privacy_fingerprint": "pf"}],
        "timeout_budget_by_class": {"small": 300},
        "trend_windows": [{"window_id": "w1", "aggregate_only": True, "contains_raw_repo_name": False, "sample_size": 3}],
        "retry_isolation_rules": [{"rule_id": "timeout", "failure_class": "timeout", "max_retries": 1, "quarantine_after": 2}],
        "trend_privacy_safe": True,
        "quarantine_policy_present": False,
    })

    codes = _codes(report)
    assert "recurring_eval_duplicate_repo" in codes
    assert "recurring_eval_roster_metadata_incomplete" in codes
    assert "recurring_eval_external_boundary_unclassified" in codes
    assert "recurring_eval_stale_repo_quarantined" in codes
    assert "recurring_eval_quarantine_policy_missing" in codes


def test_governance_exception_requires_compensating_evidence() -> None:
    report = build_governance_review_report({
        "policy_templates": [{"author": "a", "approver": "b", "effective_date": "2026-07-01", "review_cadence": "quarterly", "rollback_owner": "c"}],
        "exception_requests": [{"owner": "qa", "expiry": "2026-08-01", "rationale": "gap", "affected_risks": ["r"], "reviewer_decision": "accepted"}],
    })

    assert "governance_exception_request_incomplete" in _codes(report)


def test_governance_positive_fixture_has_audit_and_policy_diagnostics() -> None:
    result = evaluate_governance_review_fixture(_fixture("governance-workflow", "policy-approved-pass"))
    report = result["report"]

    assert result["status"] == "pass"
    assert report["governance_diagnostics"]["templates_missing_diff_or_rollback"] == []
    assert report["governance_diagnostics"]["exceptions_missing_audit_event"] == []
    assert report["governance_diagnostics"]["delegations_without_bounds"] == []
    assert report["summary"]["delegation_count"] == 1
    assert report["summary"]["audit_event_count"] == 1
    _assert_report_contract(report, "governance-review-report", "governance_config")


def test_governance_policy_diff_source_and_audit_gaps_hold() -> None:
    report = build_governance_review_report({
        "policy_templates": [
            {
                "template_id": "policy-dup",
                "author": "platform",
                "approver": "platform",
                "effective_date": "2026-07-01",
                "review_cadence": "quarterly",
                "rollback_owner": "platform",
            },
            {
                "template_id": "policy-dup",
                "author": "platform",
                "approver": "governance",
                "effective_date": "2026-07-01",
                "review_cadence": "quarterly",
                "rollback_owner": "platform",
            },
        ],
        "exception_requests": [
            {
                "request_id": "ex-1",
                "owner": "qa",
                "expiry": "2026-08-01",
                "scope": "risk",
                "rationale": "gap",
                "affected_risks": ["risk"],
                "compensating_evidence": ["manual"],
                "reviewer_decision": "accepted",
            }
        ],
        "review_packet": {"expired_exception_count": 0, "unresolved_high_risk_debt_count": 0},
        "policy_diff_required": True,
    })

    codes = _codes(report)
    assert "governance_duplicate_record" in codes
    assert "governance_self_approval_denied" in codes
    assert "governance_source_ref_missing" in codes
    assert "governance_policy_diff_or_rollback_missing" in codes
    assert "governance_exception_audit_event_missing" in codes
    assert report["summary"]["duplicate_policy_template_count"] == 1
    _assert_report_contract(report, "governance-review-report", "governance_config")


def test_governance_broad_exception_delegation_and_service_account_hold() -> None:
    report = build_governance_review_report({
        "policy_templates": [
            {
                "template_id": "policy-001",
                "author": "platform",
                "approver": "governance",
                "effective_date": "2026-07-01",
                "review_cadence": "quarterly",
                "rollback_owner": "platform",
                "policy_diff_ref": "diff",
                "rollback_plan_ref": "rollback",
                "sourceRef": "policy",
            }
        ],
        "exception_requests": [
            {
                "request_id": "ex-global",
                "owner": "qa",
                "expiry": "2026-08-01",
                "scope": "global",
                "rationale": "too broad",
                "affected_risks": [],
                "compensating_evidence": [],
                "reviewer_decision": "blanket_accept",
                "sourceRef": "exception",
            }
        ],
        "delegations": [{"delegation_id": "del-bad", "delegator": "governance", "delegate": "governance"}],
        "audit_events": [{"event_id": "audit", "target_ref": "ex-global", "actor": "governance"}],
        "review_packet": {"expired_exception_count": 0, "unresolved_high_risk_debt_count": 0, "sourceRef": "review"},
        "service_account_approval_detected": True,
    })

    codes = _codes(report)
    assert "governance_service_account_approval_denied" in codes
    assert "governance_exception_request_incomplete" in codes
    assert "governance_exception_risk_or_evidence_missing" in codes
    assert "governance_broad_exception_denied" in codes
    assert "governance_delegation_invalid" in codes


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


def test_value_measurement_positive_fixture_has_roi_diagnostics() -> None:
    result = evaluate_value_measurement_fixture(_fixture("value-measurement", "aggregate-roi-pass"))
    report = result["report"]

    assert result["status"] == "pass"
    assert report["value_diagnostics"]["missing_required_metrics"] == []
    assert report["value_diagnostics"]["wrong_direction_metrics"] == []
    assert report["value_diagnostics"]["privacy_violation"] is False
    assert report["summary"]["counterfactual_present"] is True
    assert report["summary"]["missing_confidence_interval_metric_count"] == 0
    _assert_report_contract(report, "value-measurement-report", "value_config")


def test_value_measurement_counterfactual_confidence_and_direction_hold() -> None:
    report = build_value_measurement_report({
        "aggregate_metrics": [
            {"metric_id": "review_time_saved", "delta": -1, "causal_claim": True, "sourceRef": "safe:1"},
            {"metric_id": "release_blocker_lead_time", "delta": 3, "sourceRef": "safe:2"},
            {"metric_id": "risk_debt_burn_down", "delta": 1, "sourceRef": "safe:3"},
            {"metric_id": "repeat_finding_rate", "delta": -0.1, "sourceRef": "safe:4"},
            {"metric_id": "avoided_unsupported_claims", "delta": 1, "sourceRef": "safe:5"},
        ],
        "roi_inputs": {"period": "monthly"},
        "confidence": 0.8,
        "limitations": ["small sample"],
        "sample_size": 3,
        "minimum_sample_size": 10,
        "baseline_present": True,
        "safe_evidence_refs": ["safe:1", "safe:2", "safe:3", "safe:4", "safe:5"],
        "privacy_aggregate_only": True,
    })

    codes = _codes(report)
    assert "value_measurement_sample_size_too_small" in codes
    assert "value_measurement_roi_basis_missing" in codes
    assert "value_measurement_counterfactual_missing" in codes
    assert "value_measurement_confidence_interval_missing" in codes
    assert "value_measurement_metric_direction_suspicious" in codes
    assert report["value_diagnostics"]["wrong_direction_metrics"] == ["release_blocker_lead_time", "review_time_saved"]
    _assert_report_contract(report, "value-measurement-report", "value_config")


def test_value_measurement_privacy_and_evidence_hold() -> None:
    report = build_value_measurement_report({
        "aggregate_metrics": [
            {"metric_id": "review_time_saved", "delta": 1, "confidence_interval": [0, 2]},
            {"metric_id": "risk_debt_burn_down", "delta": 1, "confidence_interval": [0, 2]},
            {"metric_id": "release_blocker_lead_time", "delta": -1, "confidence_interval": [-2, 0]},
            {"metric_id": "repeat_finding_rate", "delta": -0.1, "confidence_interval": [-0.2, 0]},
            {"metric_id": "avoided_unsupported_claims", "delta": 1, "confidence_interval": [0, 2]},
        ],
        "roi_inputs": {"period": "monthly", "cost_basis": "hours"},
        "counterfactual": {"basis": "baseline", "sourceRef": "baseline"},
        "confidence": 0.8,
        "limitations": ["privacy fixture"],
        "sample_size": 12,
        "baseline_present": True,
        "safe_evidence_refs": [],
        "privacy_aggregate_only": False,
        "raw_user_metric_present": True,
    })

    codes = _codes(report)
    assert "value_measurement_safe_evidence_refs_missing" in codes
    assert "value_measurement_privacy_aggregation_denied" in codes
    assert report["summary"]["missing_evidence_metric_count"] == 5


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


def test_developer_experience_positive_fixture_has_explain_replay_and_diagnostics() -> None:
    result = evaluate_developer_experience_fixture(_fixture("developer-experience", "actionable-pr-feedback"))
    report = result["report"]

    assert result["status"] == "pass"
    assert report["dx_diagnostics"]["missing_source_ref_groups"] == []
    assert report["dx_diagnostics"]["missing_explain_or_replay_groups"] == []
    assert report["dx_diagnostics"]["command_loop_complete"] is True
    assert report["summary"]["recommendation_actions_count"] == 2
    _assert_report_contract(report, "developer-experience-report", "dx_config")


def test_developer_experience_missing_source_and_replay_links_hold() -> None:
    report = build_developer_experience_report({
        "feedback_groups": [
            {
                "group_id": "fg-missing-links",
                "fix_action": "add oracle",
                "risk_impact": "high",
                "owner": "dev",
                "blocking_status": "hold",
                "deep_link": "pr://1#comment-1",
            }
        ],
        "local_explain_available": True,
        "local_replay_available": True,
        "ide_loop_available": True,
        "offline_safe_mode": True,
        "suppression_controls": {
            "owner": "dev",
            "expiry_required": True,
            "scope": "finding",
            "reviewer": "qa",
            "rationale": "temporary",
            "audit_ref": "audit:1",
        },
        "recommendation_actions": ["add_oracle"],
        "recommendation_quality_score": 0.9,
        "latency_ms": 1000,
        "latency_budget_ms": 5000,
        "replay_command": "",
        "explain_command": "hate explain --risk risk:1",
        "stable_deep_links": True,
    })

    codes = _codes(report)
    assert "developer_experience_source_ref_missing" in codes
    assert "developer_experience_explain_replay_link_missing" in codes
    assert report["summary"]["missing_source_ref_group_count"] == 1
    assert report["summary"]["missing_explain_or_replay_group_count"] == 1
    _assert_report_contract(report, "developer-experience-report", "dx_config")


def test_developer_experience_generic_action_and_global_suppression_hold() -> None:
    report = build_developer_experience_report({
        "feedback_groups": [
            {
                "group_id": "fg-generic",
                "fix_action": "improve",
                "risk_impact": "unknown",
                "owner": "dev",
                "blocking_status": "hold",
                "deep_link": "pr://1#comment-1",
                "sourceRef": "finding:1",
                "explain_ref": "explain:1",
                "replay_ref": "replay:1",
            }
        ],
        "local_explain_available": True,
        "local_replay_available": True,
        "ide_loop_available": False,
        "offline_safe_mode": False,
        "suppression_controls": {
            "owner": "dev",
            "expiry_required": True,
            "scope": "global",
            "reviewer": "",
            "rationale": "",
            "audit_ref": "",
        },
        "recommendation_actions": [],
        "recommendation_quality_score": 0.9,
        "latency_ms": 6000,
        "latency_budget_ms": 5000,
        "replay_command": "hate replay --case 1",
        "explain_command": "hate explain --risk 1",
        "stable_deep_links": True,
    })

    codes = _codes(report)
    assert "developer_experience_recommendation_action_weak" in codes
    assert "developer_experience_suppression_review_incomplete" in codes
    assert "developer_experience_ide_offline_loop_missing" in codes
    assert "developer_experience_latency_budget_exceeded" in codes
    assert report["dx_diagnostics"]["generic_feedback_groups"] == ["fg-generic"]
