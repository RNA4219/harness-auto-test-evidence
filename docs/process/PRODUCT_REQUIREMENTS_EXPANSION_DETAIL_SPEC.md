---
intent_id: INT-HATE-PRODUCT-REQUIREMENTS-EXPANSION-DETAIL-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-08
---

# Product Requirements Expansion Detail Spec

This document hardens the HATE-GAP-027 through HATE-GAP-040 expansion wave after
implementation UAT exposed thin requirement boundaries. It is the detail layer
below `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md` and
`PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md`.

## 1. Purpose

Expansion implementations must not infer core behavior from test names, fixture
directory names, or worker summaries. Every worker handoff must state:

- canonical fixture names and prohibited aliases
- canonical report record type and schema path
- accepted input vocabulary and backward-compatible aliases
- finding code taxonomy
- readiness effect mapping
- positive and negative oracle expectations
- schema-registry behavior
- UAT evidence and no-skip verification

If a packet lacks these fields, the correct implementation state is `hold`, not
`pass`.

## 2. Common Detail Contract

Every expansion report must emit:

| Field | Requirement |
|---|---|
| `schema_version` | `HATE/v1` |
| `record_type` | Stable kebab-case report name ending in `-report` |
| `report_id` | Caller-provided ID or deterministic fixture ID |
| `overall_status` | `pass` when no findings exist, otherwise `hold` unless the packet explicitly defines `blocked` |
| `readiness_effect` | `none` for pass, `hold` for evidence gaps and policy violations, `blocked` only for release-blocking hard DQ |
| `findings[]` | Objects with `code`, `severity`, `message`, `sourceRef`, `readiness_effect` |
| `summary` | Count fields plus packet-specific decision fields |
| `sourceRefs[]` | Stable source refs, sorted and deduplicated |

Every expansion fixture must emit:

| Field | Requirement |
|---|---|
| `schema_version` | `HATE/expansion-gap-fixture/v1` |
| `fixture_id` | `expansion-{area}-{fixture-name}` |
| `gap_id` | Matching `HATE-GAP-027` through `HATE-GAP-040` |
| `packet_id` | Matching packet ledger ID |
| `task_seed_id` | `TASK-HATE-GAP-{nnn}` |
| `acceptance_id` | `AC-HATE-GAP-{nnn}` |
| `case_kind` | `positive` or `negative` |
| `input` | Report input payload, never inferred from fixture path |
| `expected` | `status`, `readiness_effect`, `uat_report`, and `finding_code` for negative cases |

## 3. Verification Rules

- Tests must fail on missing fixtures with `assert fixture_path.exists()`.
- Tests must not call `pytest.skip` for missing canonical fixtures.
- Noncanonical fixture aliases are prohibited unless listed in this document.
- Schema-registry entries must reference `*.schema.json`, never duplicate
  `*-report.json` schema aliases.
- Worker completion reports are not acceptance evidence. The repository must
  contain tests, fixtures, schemas, and generated Birdseye updates.
- Finding code changes require either an explicit compatibility alias or a
  migration note in this document.

## 4. HATE-GAP-027 Guided Onboarding Detail

Canonical paths:

- positive: `fixtures/expansion/onboarding/golden-walkthrough/fixture.json`
- negative: `fixtures/expansion/onboarding/parser-failure-tutorial/fixture.json`
- schema: `schemas/HATE/v1/onboarding-report.schema.json`
- report: `onboarding-uat-report.json`

Input vocabulary:

- `sample_repo_defined`: sample repository metadata exists.
- `expected_output_defined`: walkthrough expected output is versioned.
- `walkthrough_steps[]`: ordered steps with user-visible command or action.
- `parser_failure_tutorial_defined`: failed parse tutorial exists.
- `support_handoff_defined`: support handoff evidence exists.
- `elapsed_minutes`: walkthrough duration estimate.

Finding codes:

- `onboarding_sample_repo_missing`
- `onboarding_expected_output_missing`
- `onboarding_walkthrough_missing`
- `onboarding_parser_failure_tutorial_missing`
- `onboarding_support_handoff_missing`
- `onboarding_walkthrough_too_long`

Pass oracle:

- positive fixture must return `overall_status=pass`, `readiness_effect=none`,
  and no findings.

Negative oracle:

- parser failure tutorial absence must return `overall_status=hold` and
  `finding_code=onboarding_parser_failure_tutorial_missing`.

## 5. HATE-GAP-028 Policy Simulation Detail

Canonical paths:

- positive: `fixtures/expansion/policy-simulation/safe-dry-run/fixture.json`
- negative: `fixtures/expansion/policy-simulation/blast-radius-unbounded/fixture.json`
- schema: `schemas/HATE/v1/policy-simulation-report.schema.json`
- report: `policy-simulation-uat-report.json`

Input vocabulary:

- `dry_run`: simulation must be non-mutating.
- `diff_summary`: policy/profile diff summary exists.
- `affected_repos[]`: affected repositories are enumerated.
- `eligibility_impact`: evidence eligibility delta is present.
- `rollback_plan_defined`: rollback evidence exists.
- `blast_radius_limit`: maximum allowed affected repo count.

Finding codes:

- `policy_simulation_not_dry_run`
- `policy_simulation_diff_missing`
- `policy_simulation_affected_repos_missing`
- `policy_simulation_eligibility_impact_missing`
- `policy_simulation_rollback_plan_missing`
- `policy_simulation_blast_radius_unbounded`

Pass oracle:

- safe dry run must not mutate policy state and must return no findings.

Negative oracle:

- affected repo count above `blast_radius_limit` must return
  `policy_simulation_blast_radius_unbounded`.

## 6. HATE-GAP-029 Bulk Portability Detail

Canonical paths:

- positive: `fixtures/expansion/bulk-portability/resumable-export/fixture.json`
- negative: `fixtures/expansion/bulk-portability/cross-tenant-import-denied/fixture.json`
- schema: `schemas/HATE/v1/bulk-portability-report.schema.json`
- report: `bulk-portability-uat-report.json`

Input vocabulary:

- `chunk_manifest_defined`
- `resume_token_defined`
- `integrity_hashes_defined`
- `partial_failure_handling_defined`
- `source_tenant_id`
- `target_tenant_id`
- `cross_tenant_import_requested`

Finding codes:

- `bulk_portability_chunk_manifest_missing`
- `bulk_portability_resume_token_missing`
- `bulk_portability_integrity_manifest_missing`
- `bulk_portability_partial_failure_handling_missing`
- `bulk_portability_cross_tenant_import_denied`

Pass oracle:

- resumable export must include chunk manifest, resume token, and integrity
  manifest.

Negative oracle:

- cross-tenant import without an explicit approved migration envelope must hold.

## 7. HATE-GAP-030 Notifications Detail

Canonical paths:

- positive: `fixtures/expansion/notifications/signed-delivery/fixture.json`
- negative: `fixtures/expansion/notifications/unsigned-webhook-denied/fixture.json`
- schema: `schemas/HATE/v1/notification-report.schema.json`
- report: `notification-uat-report.json`

Input vocabulary:

- `event_taxonomy_defined`
- `signature_required`
- `signature_present`
- `retry_schedule_defined`
- `dedupe_key_defined`
- `dead_letter_defined`
- `tenant_scoped_delivery`

Finding codes:

- `notification_event_taxonomy_missing`
- `notification_signature_missing`
- `notification_retry_schedule_missing`
- `notification_dedupe_key_missing`
- `notification_dead_letter_missing`
- `notification_tenant_scope_missing`

Pass oracle:

- signed delivery must include signature, retry schedule, dedupe key,
  dead-letter behavior, and tenant scope.

Negative oracle:

- unsigned webhook when `signature_required=true` must hold with
  `notification_signature_missing`.

## 8. HATE-GAP-031 Self-Hosted Detail

Canonical paths:

- positive: `fixtures/expansion/self-hosted/upgrade-compatible/fixture.json`
- negative: `fixtures/expansion/self-hosted/rollback-required/fixture.json`
- schema: `schemas/HATE/v1/self-hosted-report.schema.json`
- report: `self-hosted-uat-report.json`

Input vocabulary:

- `installer_contract_defined`
- `configuration_schema_defined`
- `upgrade_plan_defined`
- `rollback_supported`
- `backup_prerequisite_defined`
- `offline_verification_supported`
- `air_gapped_mode`
- `current_version`
- `target_version`
- `downgrade_requested`

Finding codes:

- `self_hosted_installer_contract_missing`
- `self_hosted_config_schema_missing`
- `self_hosted_upgrade_plan_missing`
- `self_hosted_rollback_required`
- `self_hosted_backup_prerequisite_missing`
- `self_hosted_offline_verification_missing`
- `self_hosted_downgrade_without_rollback`

Compatibility:

- `self_hosted_installer_missing` is an obsolete alias and must not be emitted
  by new code.

## 9. HATE-GAP-032 Data Classification Detail

Canonical paths:

- positive: `fixtures/expansion/data-classification/public-summary-safe/fixture.json`
- negative: `fixtures/expansion/data-classification/prohibited-telemetry-denied/fixture.json`
- schema: `schemas/HATE/v1/data-classification-report.schema.json`
- report: `data-classification-uat-report.json`

Input vocabulary:

- `field_taxonomy_defined`
- `taxonomy_defined` as backward-compatible alias
- `sink_allowlist_defined`
- `allowed_sinks[]` as backward-compatible alias and explicit allowlist
- `redaction_policy_defined`
- `redaction_rules_defined` as backward-compatible alias
- `telemetry_allowed`: telemetry sink is allowed by classification policy.
- `telemetry_sink_allowed`: request to send telemetry; may be denied.
- `telemetry_destination`
- `public_summary_safe`
- `classified_fields[]`
- `prohibited_field_exposed`
- `sink_type`

Finding codes:

- `data_classification_taxonomy_missing`
- `data_classification_sink_allowlist_missing`
- `data_classification_allowed_sinks_missing`
- `data_classification_redaction_missing`
- `data_classification_invalid_sink`
- `data_classification_prohibited_telemetry`
- `data_classification_prohibited_field_exposed`

Compatibility:

- `data_classification_sink_allowlist_missing` is emitted for canonical
  `sink_allowlist_defined=false`.
- `data_classification_allowed_sinks_missing` is emitted for legacy
  `allowed_sinks=[]`.

## 10. HATE-GAP-033 Docs Lifecycle Detail

Canonical paths:

- positive: `fixtures/expansion/docs-lifecycle/version-bound-docs/fixture.json`
- negative: `fixtures/expansion/docs-lifecycle/stale-claim-denied/fixture.json`
- schema: `schemas/HATE/v1/docs-lifecycle-report.schema.json`
- report: `docs-lifecycle-uat-report.json`

Input vocabulary:

- `required_docs_defined`
- `required_docs_inventory_defined` as backward-compatible alias
- `version_binding_enforced`
- `version_binding_valid` as backward-compatible alias
- `broken_ref_detection_enabled`
- `broken_ref_scan_enabled` as backward-compatible alias
- `stale_doc_max_age_days`
- `required_docs[]`
- `doc_claim_stale`
- `stale_claim_count` as backward-compatible alias
- `doc_age_days`
- `broken_refs[]`
- `broken_ref_count` as backward-compatible alias
- `version_bound`
- `docs_version`
- `product_version`

Finding codes:

- `docs_lifecycle_required_docs_missing`
- `docs_lifecycle_inventory_missing`
- `docs_lifecycle_version_binding_missing`
- `docs_lifecycle_broken_ref_detection_missing`
- `docs_lifecycle_stale_claim_denied`
- `docs_lifecycle_doc_exceeded_max_age`
- `docs_lifecycle_broken_refs_found`
- `docs_lifecycle_version_not_bound`
- `docs_lifecycle_version_mismatch`

Compatibility:

- `docs_lifecycle_required_docs_missing` is emitted for canonical
  `required_docs_defined=false`.
- `docs_lifecycle_inventory_missing` is emitted for legacy
  `required_docs_inventory_defined=false`.
- `docs_lifecycle_version_mismatch` is emitted when `docs_version` and
  `product_version` are both present and differ.

## 11. HATE-GAP-034 Dependency Compliance Detail

Canonical paths:

- positive: `fixtures/expansion/dependency-compliance/sbom-clean/fixture.json`
- negative: `fixtures/expansion/dependency-compliance/denied-license/fixture.json`
- schema: `schemas/HATE/v1/dependency-compliance-report.schema.json`
- report: `dependency-compliance-uat-report.json`

Input vocabulary:

- `sbom_present`: SBOM artifact exists.
- `sbom_format`: allowed values are `cyclonedx-json`, `spdx-json`, or `syft-json`.
- `packages[]`: package records with `name`, `version`, `license`, `purl`, and optional `vulnerabilities[]`.
- `license_policy_defined`: license allow/deny policy exists.
- `allowed_licenses[]`
- `denied_licenses[]`
- `vulnerability_policy_defined`
- `vulnerability_max_age_days`
- `exceptions[]`: exception records with `package`, `reason`, `owner`, `expires_at`.
- `provenance_attestation_present`

Finding codes:

- `dependency_compliance_sbom_missing`
- `dependency_compliance_sbom_format_unsupported`
- `dependency_compliance_license_policy_missing`
- `dependency_compliance_denied_license`
- `dependency_compliance_vulnerability_policy_missing`
- `dependency_compliance_vulnerability_exception_expired`
- `dependency_compliance_vulnerability_over_age`
- `dependency_compliance_exception_missing_owner`
- `dependency_compliance_provenance_missing`

Pass oracle:

- `sbom-clean` must pass with SBOM present, allowed licenses only, no expired
  exceptions, and provenance attestation present.

Negative oracle:

- `denied-license` must hold with
  `finding_code=dependency_compliance_denied_license`.

No-Go:

- Do not treat a dependency scan summary as a substitute for package-level SBOM
  records.
- Do not accept permanent vulnerability exceptions.

## 12. HATE-GAP-035 Adapter Marketplace Detail

Canonical paths:

- positive: `fixtures/expansion/adapter-marketplace/signed-compatible-plugin/fixture.json`
- negative: `fixtures/expansion/adapter-marketplace/revoked-plugin-denied/fixture.json`
- schema: `schemas/HATE/v1/adapter-marketplace-report.schema.json`
- report: `adapter-marketplace-uat-report.json`

Input vocabulary:

- `plugin_manifest_present`
- `plugin_id`
- `publisher_id`
- `signature_present`
- `signature_verified`
- `compatibility_range`
- `host_version`
- `conformance_evidence_present`
- `deprecation_status`: allowed values are `active`, `deprecated`, `revoked`.
- `revocation_record_present`
- `requested_install`

Finding codes:

- `adapter_marketplace_manifest_missing`
- `adapter_marketplace_signature_missing`
- `adapter_marketplace_signature_invalid`
- `adapter_marketplace_compatibility_missing`
- `adapter_marketplace_incompatible_host`
- `adapter_marketplace_conformance_missing`
- `adapter_marketplace_deprecated_hold`
- `adapter_marketplace_revoked_plugin_denied`
- `adapter_marketplace_publisher_missing`

Pass oracle:

- signed compatible plugin must pass with verified signature, compatible host
  version, active status, and conformance evidence.

Negative oracle:

- revoked plugin install must hold with
  `finding_code=adapter_marketplace_revoked_plugin_denied`.

No-Go:

- Do not install, publish, or mark available any plugin with unverified
  signature or revoked status.

## 13. HATE-GAP-036 Product Analytics Detail

Canonical paths:

- positive: `fixtures/expansion/product-analytics/aggregate-opt-in/fixture.json`
- negative: `fixtures/expansion/product-analytics/raw-path-event-denied/fixture.json`
- schema: `schemas/HATE/v1/product-analytics-report.schema.json`
- report: `product-analytics-uat-report.json`

Input vocabulary:

- `event_allowlist_defined`
- `events[]`: records with `event_id`, `event_name`, `classification`, `payload_fields[]`.
- `opt_in_required`
- `tenant_opt_in`
- `aggregate_only`
- `suppression_rules_defined`
- `usage_report_defined`
- `adoption_kpis[]`
- `raw_path_present`
- `raw_artifact_ref_present`

Finding codes:

- `product_analytics_event_allowlist_missing`
- `product_analytics_unknown_event`
- `product_analytics_opt_in_missing`
- `product_analytics_raw_path_event_denied`
- `product_analytics_raw_artifact_ref_denied`
- `product_analytics_suppression_rules_missing`
- `product_analytics_usage_report_missing`
- `product_analytics_adoption_kpi_missing`

Pass oracle:

- aggregate opt-in fixture must pass with allowlisted aggregate events, tenant
  opt-in, suppression rules, and no raw paths or raw artifact refs.

Negative oracle:

- raw path event fixture must hold with
  `finding_code=product_analytics_raw_path_event_denied`.

No-Go:

- Do not collect raw file paths, raw artifact references, secrets, or
  user-level behavior replay under adoption analytics.

## 14. HATE-GAP-037 Disaster Recovery Detail

Canonical paths:

- positive: `fixtures/expansion/disaster-recovery/restore-drill-pass/fixture.json`
- negative: `fixtures/expansion/disaster-recovery/corrupt-backup-denied/fixture.json`
- schema: `schemas/HATE/v1/disaster-recovery-report.schema.json`
- report: `disaster-recovery-uat-report.json`

Input vocabulary:

- `backup_inventory_present`
- `backup_id`
- `backup_created_at`
- `backup_integrity_hash`
- `restore_drill_executed`
- `restore_verified`
- `rpo_minutes`
- `rto_minutes`
- `rpo_budget_minutes`
- `rto_budget_minutes`
- `corrupt_backup_detected`
- `incident_evidence_present`

Finding codes:

- `disaster_recovery_backup_inventory_missing`
- `disaster_recovery_restore_drill_missing`
- `disaster_recovery_restore_verification_missing`
- `disaster_recovery_rpo_exceeded`
- `disaster_recovery_rto_exceeded`
- `disaster_recovery_corrupt_backup_denied`
- `disaster_recovery_integrity_hash_missing`
- `disaster_recovery_incident_evidence_missing`

Pass oracle:

- restore drill pass fixture must have verified restore, valid integrity hash,
  and RPO/RTO within budget.

Negative oracle:

- corrupt backup fixture must hold with
  `finding_code=disaster_recovery_corrupt_backup_denied`.

No-Go:

- Do not count backup creation as restore readiness without a restore drill and
  verification evidence.

## 15. HATE-GAP-038 Accessibility And Localization Detail

Canonical paths:

- positive: `fixtures/expansion/a11y-l10n/locale-fallback-safe/fixture.json`
- negative: `fixtures/expansion/a11y-l10n/color-only-severity-denied/fixture.json`
- schema: `schemas/HATE/v1/a11y-l10n-report.schema.json`
- report: `a11y-l10n-uat-report.json`

Input vocabulary:

- `message_catalog_present`
- `stable_message_ids`
- `supported_locales[]`
- `requested_locale`
- `fallback_locale`
- `fallback_used`
- `keyboard_navigation_checked`
- `color_contrast_checked`
- `color_only_severity_used`
- `screen_reader_labels_present`
- `translation_stale`
- `translation_last_reviewed_at`

Finding codes:

- `a11y_l10n_message_catalog_missing`
- `a11y_l10n_message_ids_unstable`
- `a11y_l10n_locale_fallback_missing`
- `a11y_l10n_keyboard_check_missing`
- `a11y_l10n_color_contrast_missing`
- `a11y_l10n_color_only_severity_denied`
- `a11y_l10n_screen_reader_labels_missing`
- `a11y_l10n_translation_stale`

Pass oracle:

- locale fallback safe fixture must pass with stable message IDs, valid fallback,
  keyboard checks, contrast checks, and screen-reader labels.

Negative oracle:

- color-only severity fixture must hold with
  `finding_code=a11y_l10n_color_only_severity_denied`.

No-Go:

- Do not encode severity, risk, or gate decision solely by color.

## 16. HATE-GAP-039 Cost Governance Detail

Canonical paths:

- positive: `fixtures/expansion/cost-governance/forecast-within-budget/fixture.json`
- negative: `fixtures/expansion/cost-governance/egress-risk-hold/fixture.json`
- schema: `schemas/HATE/v1/cost-governance-report.schema.json`
- report: `cost-governance-uat-report.json`

Input vocabulary:

- `tenant_id`
- `forecast_window_days`
- `storage_gb_current`
- `storage_gb_forecast`
- `storage_budget_gb`
- `egress_gb_forecast`
- `egress_budget_gb`
- `retention_cost_forecast`
- `budget_thresholds_defined`
- `storage_class_recommendation`
- `remediation_plan_defined`
- `non_gating_advisory`

Finding codes:

- `cost_governance_budget_thresholds_missing`
- `cost_governance_storage_budget_exceeded`
- `cost_governance_egress_risk_hold`
- `cost_governance_retention_cost_unbounded`
- `cost_governance_storage_recommendation_missing`
- `cost_governance_remediation_plan_missing`
- `cost_governance_missing_tenant_scope`

Pass oracle:

- forecast within budget fixture must pass with tenant scope, thresholds,
  storage recommendation, and remediation plan.

Negative oracle:

- egress risk fixture must hold with
  `finding_code=cost_governance_egress_risk_hold`.

No-Go:

- Cost governance findings are advisory unless they imply retention, privacy, or
  tenant isolation risk.

## 17. HATE-GAP-040 Beta Acceptance Detail

Canonical paths:

- positive: `fixtures/expansion/beta-acceptance/cohort-exit-pass/fixture.json`
- negative: `fixtures/expansion/beta-acceptance/blocker-feedback-hold/fixture.json`
- schema: `schemas/HATE/v1/beta-acceptance-report.schema.json`
- report: `beta-acceptance-uat-report.json`

Input vocabulary:

- `cohort_defined`
- `cohort_id`
- `customer_evidence_limits_defined`
- `feedback_items[]`: records with `feedback_id`, `classification`, `severity`, `sourceRef`.
- `blocker_count`
- `critical_blocker_count`
- `triage_owner`
- `exit_criteria_defined`
- `exit_criteria_met`
- `acceptance_record_present`
- `customer_secret_present`

Finding codes:

- `beta_acceptance_cohort_missing`
- `beta_acceptance_customer_evidence_limits_missing`
- `beta_acceptance_feedback_unclassified`
- `beta_acceptance_blocker_feedback_hold`
- `beta_acceptance_critical_blocker_present`
- `beta_acceptance_triage_owner_missing`
- `beta_acceptance_exit_criteria_missing`
- `beta_acceptance_exit_criteria_not_met`
- `beta_acceptance_customer_secret_denied`

Pass oracle:

- cohort exit pass fixture must pass with defined cohort, classified feedback,
  no blockers, met exit criteria, and no customer secrets.

Negative oracle:

- blocker feedback fixture must hold with
  `finding_code=beta_acceptance_blocker_feedback_hold`.

No-Go:

- Do not use beta acceptance as a waiver for missing executable evidence.
- Do not store customer secrets or raw customer artifacts in beta evidence.

## 18. W33 Implementation Readiness

HATE-GAP-034 through HATE-GAP-040 now have detail-level contracts. They may move
from `specified-thin` to `specified-ready` only when the packet ledger, task seed
ledger, and acceptance ledger reference these canonical fixture paths and report
names.

Implementation must still create runtime modules, schemas, fixtures, tests,
Birdseye updates, and generated UAT evidence before any gap is marked
`implemented`.

## 19. W33 File And Function Contract

Implementations must use these exact module, schema, and test names. Alternate names are noncanonical aliases and must be rejected in UAT.

| Gap | Module | Builder function | Fixture evaluator | Test file | Record type |
|---|---|---|---|---|---|
| HATE-GAP-034 | `src/hate/expansion/dependency_compliance.py` | `build_dependency_compliance_report` | `evaluate_dependency_compliance_fixture` | `tests/test_expansion_dependency_compliance.py` | `dependency-compliance-report` |
| HATE-GAP-035 | `src/hate/expansion/adapter_marketplace.py` | `build_adapter_marketplace_report` | `evaluate_adapter_marketplace_fixture` | `tests/test_expansion_adapter_marketplace.py` | `adapter-marketplace-report` |
| HATE-GAP-036 | `src/hate/expansion/product_analytics.py` | `build_product_analytics_report` | `evaluate_product_analytics_fixture` | `tests/test_expansion_product_analytics.py` | `product-analytics-report` |
| HATE-GAP-037 | `src/hate/expansion/disaster_recovery.py` | `build_disaster_recovery_report` | `evaluate_disaster_recovery_fixture` | `tests/test_expansion_disaster_recovery.py` | `disaster-recovery-report` |
| HATE-GAP-038 | `src/hate/expansion/a11y_l10n.py` | `build_a11y_l10n_report` | `evaluate_a11y_l10n_fixture` | `tests/test_expansion_a11y_l10n.py` | `a11y-l10n-report` |
| HATE-GAP-039 | `src/hate/expansion/cost_governance.py` | `build_cost_governance_report` | `evaluate_cost_governance_fixture` | `tests/test_expansion_cost_governance.py` | `cost-governance-report` |
| HATE-GAP-040 | `src/hate/expansion/beta_acceptance.py` | `build_beta_acceptance_report` | `evaluate_beta_acceptance_fixture` | `tests/test_expansion_beta_acceptance.py` | `beta-acceptance-report` |

Each builder function must accept:

- `input_data: dict[str, Any]`
- optional keyword-only `report_id: str`
- optional keyword-only `source_refs: list[str]`

Each fixture evaluator must accept the whole fixture payload and return:

- `status`
- `finding_code`
- `readiness_effect`
- `report`

## 20. W33 Schema Minimum

Every W33 schema must require the common report fields from section 2 and must
pin packet-specific nested objects rather than accepting arbitrary untyped
payloads.

Required schema files:

- `schemas/HATE/v1/dependency-compliance-report.schema.json`
- `schemas/HATE/v1/adapter-marketplace-report.schema.json`
- `schemas/HATE/v1/product-analytics-report.schema.json`
- `schemas/HATE/v1/disaster-recovery-report.schema.json`
- `schemas/HATE/v1/a11y-l10n-report.schema.json`
- `schemas/HATE/v1/cost-governance-report.schema.json`
- `schemas/HATE/v1/beta-acceptance-report.schema.json`

Every schema must require:

- `schema_version`
- `record_type`
- `report_id`
- `overall_status`
- `readiness_effect`
- `findings`
- `summary`
- `sourceRefs`

Every schema must constrain:

- `schema_version` to `HATE/v1`
- `overall_status` to `pass`, `hold`, or `blocked`
- `readiness_effect` to `none`, `hold`, or `blocked`
- finding `severity` to `low`, `medium`, `high`, or `critical`
- finding `readiness_effect` to `hold` or `blocked`

## 21. W33 Minimum Test Contract

Each W33 test file must include at least:

- canonical fixture path existence tests for positive and negative fixtures
- positive fixture pass test
- negative fixture hold test with exact `finding_code`
- one extra No-Go case beyond the canonical negative fixture
- report contract assertion for common fields
- schema registry assertion for the `*.schema.json` path
- assertion that sibling `*-report.json` schema alias does not exist

Tests must not use `pytest.skip`, substring-only assertions, or a fixture name as the only behavioral oracle.

## 22. UAT Hardening Checklist

For every expansion implementation:

- `uv run pytest tests/test_expansion_*.py tests/test_requirements_expansion_docs.py -q`
- `uv run pytest -q`
- `uv run python -m compileall src tests`
- `uv run python tools/codemap/update.py`
- `git diff --check`
- confirm no `pytest.skip` was added for missing fixture paths
- confirm no duplicate `*-report.json` schema alias was added beside
  `*-report.schema.json`

## 23. W34 Core Functional Expansion Scope

HATE-GAP-049 through HATE-GAP-060 are core functional expansion packets. They
come after the PRD requirements `FR-ANALYSIS-001` through `FR-ANALYSIS-012`.
Implementation must not begin from this section alone if the PRD, backlog,
packet ledger, task seed, and acceptance ledger do not also reference the same
gap ID.

These packets are not operations, procurement, or hosted-SaaS work. They are
analysis-engine capabilities:

- impact inference
- test recommendation
- flaky classification
- oracle classification
- evidence synthesis
- test code quality analysis
- execution environment diff
- cross-evidence contradiction detection
- historical regression analysis
- multi-audience report generation
- fixture and corpus quality detection
- adapter capability diff

Common No-Go:

- Do not mark inferred facts as certain without confidence and sourceRefs.
- Do not inflate readiness from weak evidence.
- Do not recompute release, QEG, or external gate verdicts in audience reports.
- Do not use fixture names as the behavioral oracle.
- Do not hide unknown analysis as pass.

## 24. W34 Canonical File And Function Contract

Implementations must use these exact module, builder, evaluator, schema, and
test names. Alternate names are noncanonical aliases and must be rejected in
UAT.

| Gap | Module | Builder function | Fixture evaluator | Test file | Record type |
|---|---|---|---|---|---|
| HATE-GAP-049 | `src/hate/analysis/impact_analysis.py` | `build_impact_analysis_report` | `evaluate_impact_analysis_fixture` | `tests/test_analysis_impact_analysis.py` | `impact-analysis-report` |
| HATE-GAP-050 | `src/hate/analysis/test_recommendation.py` | `build_test_recommendation_report` | `evaluate_test_recommendation_fixture` | `tests/test_analysis_test_recommendation.py` | `test-recommendation-report` |
| HATE-GAP-051 | `src/hate/analysis/flaky_classification.py` | `build_flaky_classification_report` | `evaluate_flaky_classification_fixture` | `tests/test_analysis_flaky_classification.py` | `flaky-classification-report` |
| HATE-GAP-052 | `src/hate/analysis/oracle_classification.py` | `build_oracle_classification_report` | `evaluate_oracle_classification_fixture` | `tests/test_analysis_oracle_classification.py` | `oracle-classification-report` |
| HATE-GAP-053 | `src/hate/analysis/evidence_synthesis.py` | `build_evidence_synthesis_report` | `evaluate_evidence_synthesis_fixture` | `tests/test_analysis_evidence_synthesis.py` | `evidence-synthesis-report` |
| HATE-GAP-054 | `src/hate/analysis/test_quality.py` | `build_test_quality_report` | `evaluate_test_quality_fixture` | `tests/test_analysis_test_quality.py` | `test-quality-report` |
| HATE-GAP-055 | `src/hate/analysis/environment_diff.py` | `build_environment_diff_report` | `evaluate_environment_diff_fixture` | `tests/test_analysis_environment_diff.py` | `environment-diff-report` |
| HATE-GAP-056 | `src/hate/analysis/contradiction_detection.py` | `build_contradiction_report` | `evaluate_contradiction_fixture` | `tests/test_analysis_contradiction_detection.py` | `contradiction-report` |
| HATE-GAP-057 | `src/hate/analysis/historical_regression.py` | `build_historical_regression_report` | `evaluate_historical_regression_fixture` | `tests/test_analysis_historical_regression.py` | `historical-regression-report` |
| HATE-GAP-058 | `src/hate/analysis/audience_report_pack.py` | `build_audience_report_pack` | `evaluate_audience_report_pack_fixture` | `tests/test_analysis_audience_report_pack.py` | `audience-report-pack` |
| HATE-GAP-059 | `src/hate/analysis/fixture_quality.py` | `build_fixture_quality_report` | `evaluate_fixture_quality_fixture` | `tests/test_analysis_fixture_quality.py` | `fixture-quality-report` |
| HATE-GAP-060 | `src/hate/analysis/adapter_capability_diff.py` | `build_adapter_capability_diff_report` | `evaluate_adapter_capability_diff_fixture` | `tests/test_analysis_adapter_capability_diff.py` | `adapter-capability-diff-report` |

Each builder function must accept:

- `input_data: dict[str, Any]`
- optional keyword-only `report_id: str`
- optional keyword-only `source_refs: list[str]`

Each fixture evaluator must accept the whole fixture payload and return:

- `status`
- `finding_code`
- `readiness_effect`
- `report`

## 25. W34 Canonical Fixtures, Schemas, And Findings

| Gap | Positive fixture | Negative fixture | Schema | Primary negative finding |
|---|---|---|---|---|
| HATE-GAP-049 | `fixtures/expansion/impact-analysis/dependency-impact-pass/fixture.json` | `fixtures/expansion/impact-analysis/missing-dependency-source-hold/fixture.json` | `schemas/HATE/v1/impact-analysis-report.schema.json` | `impact_analysis_missing_dependency_source` |
| HATE-GAP-050 | `fixtures/expansion/test-recommendation/missing-oracle-actionable/fixture.json` | `fixtures/expansion/test-recommendation/generic-advice-denied/fixture.json` | `schemas/HATE/v1/test-recommendation-report.schema.json` | `test_recommendation_generic_advice_denied` |
| HATE-GAP-051 | `fixtures/expansion/flaky-classification/environment-flake-classified/fixture.json` | `fixtures/expansion/flaky-classification/unknown-flake-hold/fixture.json` | `schemas/HATE/v1/flaky-classification-report.schema.json` | `flaky_classification_unknown_flake_hold` |
| HATE-GAP-052 | `fixtures/expansion/oracle-classification/property-oracle-pass/fixture.json` | `fixtures/expansion/oracle-classification/snapshot-only-critical-hold/fixture.json` | `schemas/HATE/v1/oracle-classification-report.schema.json` | `oracle_classification_snapshot_only_critical_hold` |
| HATE-GAP-053 | `fixtures/expansion/evidence-synthesis/contract-mutation-confidence-pass/fixture.json` | `fixtures/expansion/evidence-synthesis/weak-evidence-inflation-denied/fixture.json` | `schemas/HATE/v1/evidence-synthesis-report.schema.json` | `evidence_synthesis_weak_evidence_inflation_denied` |
| HATE-GAP-054 | `fixtures/expansion/test-quality/deterministic-tests-pass/fixture.json` | `fixtures/expansion/test-quality/sleep-based-test-hold/fixture.json` | `schemas/HATE/v1/test-quality-report.schema.json` | `test_quality_sleep_based_test_hold` |
| HATE-GAP-055 | `fixtures/expansion/environment-diff/runtime-version-drift-explained/fixture.json` | `fixtures/expansion/environment-diff/unexplained-env-drift-hold/fixture.json` | `schemas/HATE/v1/environment-diff-report.schema.json` | `environment_diff_unexplained_drift_hold` |
| HATE-GAP-056 | `fixtures/expansion/contradiction-detection/consistent-evidence-pass/fixture.json` | `fixtures/expansion/contradiction-detection/pass-with-critical-finding-blocked/fixture.json` | `schemas/HATE/v1/contradiction-report.schema.json` | `contradiction_pass_with_critical_finding_blocked` |
| HATE-GAP-057 | `fixtures/expansion/historical-regression/stable-trend-pass/fixture.json` | `fixtures/expansion/historical-regression/recurring-failure-blocked/fixture.json` | `schemas/HATE/v1/historical-regression-report.schema.json` | `historical_regression_recurring_failure_blocked` |
| HATE-GAP-058 | `fixtures/expansion/audience-report-pack/shared-sourcerefs-pass/fixture.json` | `fixtures/expansion/audience-report-pack/verdict-recomputed-denied/fixture.json` | `schemas/HATE/v1/audience-report-pack.schema.json` | `audience_report_pack_verdict_recomputed_denied` |
| HATE-GAP-059 | `fixtures/expansion/fixture-quality/corpus-quality-pass/fixture.json` | `fixtures/expansion/fixture-quality/fixture-name-coupled-hold/fixture.json` | `schemas/HATE/v1/fixture-quality-report.schema.json` | `fixture_quality_fixture_name_coupled_hold` |
| HATE-GAP-060 | `fixtures/expansion/adapter-capability-diff/lossless-normalization-pass/fixture.json` | `fixtures/expansion/adapter-capability-diff/lossy-field-drop-hold/fixture.json` | `schemas/HATE/v1/adapter-capability-diff-report.schema.json` | `adapter_capability_diff_lossy_field_drop_hold` |

Additional finding vocabulary:

- `impact_analysis_confidence_missing`
- `impact_analysis_affected_test_without_source_ref`
- `test_recommendation_missing_verification_command`
- `test_recommendation_missing_required_oracle`
- `flaky_classification_environment_evidence_missing`
- `flaky_classification_retry_history_missing`
- `oracle_classification_no_oracle_for_required_risk`
- `oracle_classification_semantic_guard_missing`
- `evidence_synthesis_contradiction_ignored`
- `evidence_synthesis_confidence_bounds_missing`
- `test_quality_duplicate_test_detected`
- `test_quality_nondeterministic_dependency_detected`
- `environment_diff_runtime_version_drift`
- `environment_diff_cache_state_unknown`
- `contradiction_coverage_up_mutation_down`
- `contradiction_contract_schema_conflict`
- `historical_regression_parser_regression_detected`
- `historical_regression_risk_debt_burn_up`
- `audience_report_pack_source_ref_drift`
- `audience_report_pack_view_missing`
- `fixture_quality_expected_output_leakage`
- `fixture_quality_schema_drift`
- `adapter_capability_diff_claim_drift`
- `adapter_capability_diff_unsupported_dialect_feature`

## 26. W34 Schema And Test Minimum

Every W34 schema must require the common report fields from section 2 and must
pin packet-specific nested objects. Arbitrary untyped `payload` objects are not
enough.

Every W34 schema must require:

- `schema_version`
- `record_type`
- `report_id`
- `overall_status`
- `readiness_effect`
- `findings`
- `summary`
- `sourceRefs`

Every W34 report must include:

- `analysis_scope`
- `input_refs`
- `confidence`
- `limits`
- `sourceRefs`

Packet-specific required fields:

- HATE-GAP-049: `changed_refs`, `affected_tests`, `affected_requirements`
- HATE-GAP-050: `recommendations`, `required_oracles`, `verification_commands`
- HATE-GAP-051: `flake_classes`, `attempt_history`, `environment_evidence`
- HATE-GAP-052: `oracle_classes`, `semantic_guards`, `no_oracle_risks`
- HATE-GAP-053: `risk_confidence`, `requirement_confidence`, `contradictions`
- HATE-GAP-054: `test_quality_findings`, `patterns`, `remediations`
- HATE-GAP-055: `environment_deltas`, `attempts_compared`, `drift_classes`
- HATE-GAP-056: `contradictions`, `blocking_effects`, `claim_impacts`
- HATE-GAP-057: `baseline_window`, `trend_metrics`, `recurrences`
- HATE-GAP-058: `audience_views`, `shared_sourceRefs`, `verdict_recomputed`
- HATE-GAP-059: `fixture_findings`, `corpus_scope`, `schema_drift`
- HATE-GAP-060: `raw_field_map`, `normalized_field_map`, `lossy_transforms`

Each W34 test file must include:

- canonical fixture path existence tests for positive and negative fixtures
- positive fixture pass test
- negative fixture hold or blocked test with exact `finding_code`
- one extra No-Go case beyond the canonical negative fixture
- report contract assertion for common fields
- packet-specific field assertion from the list above
- schema registry assertion for the `*.schema.json` path
- assertion that sibling `*-report.json` schema alias does not exist

Tests must not use `pytest.skip`, substring-only assertions, or a fixture name as
the only behavioral oracle.

## 27. HATE-GAP-041 Through HATE-GAP-048 Detail Spec Index

The detailed runtime, schema, fixture, finding, test, and release connection
contract for HATE-GAP-041 through HATE-GAP-048 lives in
`PRODUCT_REQUIREMENTS_PORTFOLIO_READINESS_DETAIL_SPEC.md`. This parent file
keeps only the index pointer so it remains below the 1000-line maintainability
guard.
