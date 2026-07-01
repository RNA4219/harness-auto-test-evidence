# Product Requirements Portfolio Readiness Detail Spec

This document owns the focused runtime contract for HATE-GAP-041 through
HATE-GAP-048. It is split from `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md`
so each requirements document stays below the 1000-line maintainability guard.

## 1. HATE-GAP-041 Through HATE-GAP-048 Runtime Contract

HATE-GAP-041 through HATE-GAP-048 are implemented as third-wave portfolio
readiness reports in `src/hate/expansion/portfolio_readiness.py`. The module
owns deterministic builders and fixture evaluators for company rollout,
provider breadth, runner dialect coverage, recurring real repository
evaluation, governance review, security procurement, value measurement, and
daily developer experience.

Canonical builder and evaluator functions:

- HATE-GAP-041: `build_rollout_adoption_report` and
  `evaluate_rollout_adoption_fixture`
- HATE-GAP-042: `build_provider_integration_report` and
  `evaluate_provider_integration_fixture`
- HATE-GAP-043: `build_runner_dialect_coverage_report` and
  `evaluate_runner_dialect_coverage_fixture`
- HATE-GAP-044: `build_recurring_real_repo_eval_report` and
  `evaluate_recurring_real_repo_eval_fixture`
- HATE-GAP-045: `build_governance_review_report` and
  `evaluate_governance_review_fixture`
- HATE-GAP-046: `build_security_procurement_report` and
  `evaluate_security_procurement_fixture`
- HATE-GAP-047: `build_value_measurement_report` and
  `evaluate_value_measurement_fixture`
- HATE-GAP-048: `build_developer_experience_report` and
  `evaluate_developer_experience_fixture`

Each builder must accept a mapping input and return a report with
`schema_version`, `record_type`, `report_id`, `overall_status`,
`readiness_effect`, `findings`, `summary`, `sourceRefs`, and the packet-specific
configuration object. Each evaluator must load the canonical `input` object
from a fixture and return the same report contract. Builders must not infer pass
from fixture names; they must evaluate explicit fields in the packet-specific
configuration.

## 2. Schemas, Fixtures, And Findings

The following schema and fixture contracts are canonical:

- HATE-GAP-041 uses `rollout-adoption-report.schema.json`,
  `fixtures/expansion/rollout-adoption/staged-wave-pass/fixture.json`, and
  `fixtures/expansion/rollout-adoption/expired-exception-blocks/fixture.json`.
- HATE-GAP-042 uses `provider-integration-report.schema.json`,
  `fixtures/expansion/provider-matrix/gitlab-identity-pass/fixture.json`, and
  `fixtures/expansion/provider-matrix/overbroad-permission-denied/fixture.json`.
- HATE-GAP-043 uses `runner-dialect-coverage-report.schema.json`,
  `fixtures/expansion/runner-dialects/dotnet-xunit-pass/fixture.json`, and
  `fixtures/expansion/runner-dialects/unsupported-runner-capability-gap/fixture.json`.
- HATE-GAP-044 uses `recurring-real-repo-eval-report.schema.json`,
  `fixtures/expansion/recurring-real-repo-eval/baseline-trend-pass/fixture.json`,
  and `fixtures/expansion/recurring-real-repo-eval/regression-timeout-hold/fixture.json`.
- HATE-GAP-045 uses `governance-review-report.schema.json`,
  `fixtures/expansion/governance-workflow/policy-approved-pass/fixture.json`,
  and `fixtures/expansion/governance-workflow/self-approval-denied/fixture.json`.
- HATE-GAP-046 uses `security-procurement-report.schema.json`,
  `fixtures/expansion/security-procurement/trust-packet-safe/fixture.json`, and
  `fixtures/expansion/security-procurement/unsupported-certification-claim/fixture.json`.
- HATE-GAP-047 uses `value-measurement-report.schema.json`,
  `fixtures/expansion/value-measurement/aggregate-roi-pass/fixture.json`, and
  `fixtures/expansion/value-measurement/individual-leaderboard-denied/fixture.json`.
- HATE-GAP-048 uses `developer-experience-report.schema.json`,
  `fixtures/expansion/developer-experience/actionable-pr-feedback/fixture.json`,
  and `fixtures/expansion/developer-experience/broad-suppression-denied/fixture.json`.

Required finding vocabulary:

- `rollout_adoption_expired_exception_blocks`
- `rollout_adoption_wave_missing`
- `rollout_adoption_rollback_plan_missing`
- `provider_integration_overbroad_permission_denied`
- `provider_integration_ambiguous_identity_hard_dq`
- `runner_dialect_conformance_fixture_missing`
- `runner_dialect_unsupported_capability_gap`
- `runner_dialect_claim_without_conformance`
- `recurring_eval_repo_class_missing`
- `recurring_eval_regression_detected`
- `recurring_eval_timeout_hidden_evidence_denied`
- `recurring_eval_trend_privacy_unsafe`
- `governance_self_approval_denied`
- `governance_exception_request_incomplete`
- `security_procurement_unsupported_certification_claim`
- `security_procurement_raw_artifact_export_denied`
- `security_procurement_overdue_critical_vulnerability`
- `value_measurement_individual_leaderboard_denied`
- `value_measurement_noisy_signal_denied`
- `value_measurement_required_metric_missing`
- `developer_experience_broad_suppression_denied`
- `developer_experience_raw_secret_denied`
- `developer_experience_feedback_group_incomplete`

## 3. Test And Release Minimum

The third-wave portfolio readiness implementation must be connected to:

- `src/hate/expansion_runner.py` through one `ExpansionReportSpec` per gap
- `schemas/HATE/v1/schema-registry.json` through canonical `*.schema.json`
  paths only
- `fixtures/release/candidate-pack/all-green/fixture.json`
- `fixtures/release/candidate-pack/missing-required-report/fixture.json`
- `fixtures/release/candidate-pack/non-deterministic-input/fixture.json`
- `docs/acceptance/HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md`

`tests/test_expansion_portfolio_readiness.py` must assert canonical fixture
paths, positive pass behavior, negative exact finding codes, report contract
fields, schema registry entries, and at least one extra No-Go case per packet.
The release candidate pack tests must require these record types so a future
release bundle cannot silently omit HATE-GAP-041 through HATE-GAP-048.
