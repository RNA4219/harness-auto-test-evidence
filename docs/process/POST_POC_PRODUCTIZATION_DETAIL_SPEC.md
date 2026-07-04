---
intent_id: INT-HATE-POST-POC-PRODUCTIZATION-DETAIL-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-03
next_review_due: 2026-07-17
---

# Post-PoC Productization Detail Specification

This specification lowers every gap in
`POST_POC_REQUIREMENTS_GAP_AUDIT.md` into implementable product specification.
It is the detail-spec counterpart to
`POST_POC_SPEC_TRACEABILITY_CHECKLIST.md`.

PoC completion remains valid, but the items below are the required next layer
before HATE can claim product, enterprise, or regulated operational readiness.

## 1. Shared Productization Contract

Every post-PoC record produced by this specification must include:

- `schema_version`
- `record_type`
- `record_id`
- `sourceRefs`
- `created_at`
- `actor` or `system_actor`
- `tenant_id` when hosted or multi-tenant behavior is involved
- `decision_basis`
- `readiness_effect`
- `unsafe_output_policy`

Every implementation must preserve these invariants:

- HATE remains pre-QEG evidence and does not claim final release approval.
- External repos are evaluation targets, not automatic repair targets.
- Raw secrets, PII, unsafe artifact bodies, unrestricted local paths, and
  external signed URLs must not appear in read models, dashboards, or
  connector payloads.
- A report-only feature is not enough when the user workflow requires runtime
  action, delivery, approval, scheduling, or review.
- A green happy path fixture is not enough; every gap needs denial, stale,
  malformed, or permission-boundary fixtures.

## HATE-POSTPOC-GAP-001: Hosted Scheduler Runtime

Record types:

- `hosted-scheduler-worker-state`
- `hosted-scheduler-lease-event`
- `hosted-scheduler-job-result`

Required fields:

- `worker_id`, `queue_id`, `lease_id`, `job_id`
- `job_kind`: `repo_suite_run`, `detector_run`, `report_generation`,
  `connector_delivery`, `maintenance`
- `lease_state`: `available`, `leased`, `heartbeat_lost`, `expired`,
  `cancel_requested`, `completed`, `failed`
- `heartbeat_at`, `lease_expires_at`, `retry_after`, `attempt`, `max_attempts`
- `resume_token`, `partial_result_ref`, `cleanup_status`

State transitions:

| Current | Event | Next | Validation |
|---|---|---|---|
| available | lease_acquired | leased | worker_id and lease_expires_at required |
| leased | heartbeat_seen | leased | heartbeat_at must be monotonic |
| leased | cancel_requested | cancel_requested | actor and reason required |
| leased | lease_expired | expired | heartbeat older than policy TTL |
| expired | retry_scheduled | available | attempt < max_attempts |
| leased | job_completed | completed | result hash and sourceRefs required |
| leased | job_failed | failed | failure_kind and excerpt_ref required |

Failure taxonomy:

- `scheduler_worker_heartbeat_missing`
- `scheduler_lease_expired`
- `scheduler_cancel_without_actor`
- `scheduler_retry_budget_exhausted`
- `scheduler_resume_token_missing`
- `scheduler_cleanup_failed`

Required fixtures:

- `fixtures/post-poc/scheduler/lease-acquire-heartbeat/fixture.json`
- `fixtures/post-poc/scheduler/stale-lease-recovered/fixture.json`
- `fixtures/post-poc/scheduler/cancel-requested/fixture.json`
- `fixtures/post-poc/scheduler/retry-budget-exhausted/fixture.json`
- `fixtures/post-poc/scheduler/resume-token-missing/fixture.json`

Acceptance:

- An interrupted job can be recovered without losing sourceRefs.
- A stale lease never becomes pass.
- Cancellation writes an audit event and does not delete partial evidence.

## HATE-POSTPOC-GAP-002: Interactive Dashboard Frontend

Record types:

- `dashboard-session-view`
- `dashboard-route-state`
- `dashboard-action-intent`

Routes:

- `/dashboard/portfolio`
- `/dashboard/repos/:repo_id`
- `/dashboard/findings`
- `/dashboard/debt`
- `/dashboard/manual-review`
- `/dashboard/policies`
- `/dashboard/audit`

Required UI states:

- `loading`
- `empty`
- `partial`
- `stale`
- `permission_denied`
- `unsafe_artifact_hidden`
- `action_pending`
- `action_failed`

Actions:

- assign owner
- change due date
- request manual review
- accept/revoke/resolve debt
- propose baseline
- trigger rerun
- export safe report

No-Go:

- Dashboard must not recompute verdicts outside canonical read model records.
- Dashboard must not display unsafe artifact body or raw connector payload.
- Action buttons must produce auditable intents, not silent local mutations.

Required fixtures:

- `fixtures/post-poc/dashboard/portfolio-loaded/fixture.json`
- `fixtures/post-poc/dashboard/permission-denied/fixture.json`
- `fixtures/post-poc/dashboard/stale-read-model/fixture.json`
- `fixtures/post-poc/dashboard/unsafe-artifact-hidden/fixture.json`
- `fixtures/post-poc/dashboard/manual-review-action/fixture.json`

Acceptance:

- Browser UAT proves route navigation, state rendering, RBAC denial, and unsafe
  hidden behavior.
- Every dashboard action is visible as an intent with actor and sourceRefs.

## HATE-POSTPOC-GAP-003: Notification Delivery Runtime

Record types:

- `notification-delivery-plan`
- `notification-delivery-attempt`
- `notification-dead-letter-event`

Delivery targets:

- `slack_channel`
- `slack_dm`
- `email`
- `github_comment`
- `github_check_annotation`
- `webhook`

Required fields:

- `notification_id`, `operating_record_id`, `delivery_target`,
  `target_ref`, `dedupe_key`, `payload_hash`
- `attempt`, `max_attempts`, `next_retry_at`, `delivery_status`,
  `error_code`
- `signature_ref` for webhook delivery
- `redaction_report_ref`

Failure taxonomy:

- `notification_payload_unsafe`
- `notification_target_missing`
- `notification_signature_missing`
- `notification_delivery_failed`
- `notification_dead_lettered`
- `notification_duplicate_suppressed`

No-Go:

- Notification failure must not close or downgrade the finding.
- Notification payload must not include raw secrets, PII, or unsafe artifact
  bodies.
- Duplicate suppression must preserve an audit event.

Required fixtures:

- `fixtures/post-poc/notifications/slack-delivered/fixture.json`
- `fixtures/post-poc/notifications/webhook-signed/fixture.json`
- `fixtures/post-poc/notifications/duplicate-suppressed/fixture.json`
- `fixtures/post-poc/notifications/dead-lettered/fixture.json`
- `fixtures/post-poc/notifications/unsafe-payload-denied/fixture.json`

Acceptance:

- Delivery retry and dead-letter behavior is deterministic and sourceRef-backed.
- Signed webhook payloads can be verified without exposing secrets.

## HATE-POSTPOC-GAP-004: Baseline Promotion Workflow

Record types:

- `baseline-promotion-request`
- `baseline-promotion-decision`
- `baseline-immutability-event`

State transitions:

| Current | Event | Next |
|---|---|---|
| none | proposed | proposed |
| proposed | approved | approved |
| approved | frozen | frozen |
| frozen | superseded | superseded |
| approved | expired | expired |
| proposed | rejected | rejected |
| approved | revoked | revoked |

Required fields:

- `baseline_id`, `repo_id`, `suite_id`, `candidate_run_id`
- `actor`, `reviewer`, `reason`, `evidence_refs`
- `policy_hash`, `expires_at`, `frozen_at`
- `immutability_hash`, `previous_baseline_ref`

Failure taxonomy:

- `baseline_candidate_missing_evidence`
- `baseline_approval_missing_reviewer`
- `baseline_self_approval_denied`
- `baseline_expired`
- `baseline_revoked`
- `baseline_unapproved_for_comparison`

Required fixtures:

- `fixtures/post-poc/baseline/propose-approve-freeze/fixture.json`
- `fixtures/post-poc/baseline/self-approval-denied/fixture.json`
- `fixtures/post-poc/baseline/expired-baseline-denied/fixture.json`
- `fixtures/post-poc/baseline/revoked-baseline-denied/fixture.json`
- `fixtures/post-poc/baseline/unapproved-comparison-holds/fixture.json`

Acceptance:

- Unapproved baselines cannot hide regressions.
- Baseline mutation produces immutable before/after sourceRefs.

## HATE-POSTPOC-GAP-005: Real-Repo Roster Operations

Record types:

- `real-repo-roster-maintenance-plan`
- `real-repo-environment-recipe`
- `real-repo-quarantine-event`

Required fields:

- `repo_id`, `ownership_scope`, `repo_class`, `suite_id`
- `discovery_source`, `last_seen_at`, `stale_after`
- `environment_recipe_ref`, `dependency_bootstrap_command`
- `quarantine_reason`, `retry_isolation_group`
- `external_repair_allowed`: must be false unless repo is owned and explicitly
  requested

Failure taxonomy:

- `roster_repo_stale`
- `roster_environment_recipe_missing`
- `roster_dependency_bootstrap_failed`
- `roster_external_repo_repair_denied`
- `roster_retry_isolation_missing`
- `roster_expected_record_floor_missing`

Required fixtures:

- `fixtures/post-poc/roster/owned-repo-bootstrap/fixture.json`
- `fixtures/post-poc/roster/external-repair-denied/fixture.json`
- `fixtures/post-poc/roster/stale-repo-quarantined/fixture.json`
- `fixtures/post-poc/roster/dependency-bootstrap-failed/fixture.json`
- `fixtures/post-poc/roster/large-roster-100-repos/fixture.json`

Acceptance:

- 100+ repo dry-run produces deterministic maintenance output.
- External repo failures are not converted into HATE implementation failures.

## HATE-POSTPOC-GAP-006: Plugin Distribution and Trust

Record types:

- `plugin-package-manifest`
- `plugin-signature-verification`
- `plugin-revocation-event`
- `plugin-distribution-index`

Required fields:

- `plugin_id`, `plugin_version`, `api_version`, `package_hash`
- `signature_algorithm`, `signature_ref`, `trust_source`
- `allowlist_ref`, `revocation_ref`, `compatibility_status`
- `capabilities`, `resource_limits`, `migration_note_ref`

Failure taxonomy:

- `plugin_package_hash_mismatch`
- `plugin_signature_invalid`
- `plugin_revoked`
- `plugin_allowlist_missing`
- `plugin_api_migration_required`
- `plugin_distribution_index_stale`

Required fixtures:

- `fixtures/post-poc/plugin-distribution/signed-allowed/fixture.json`
- `fixtures/post-poc/plugin-distribution/unsigned-release-denied/fixture.json`
- `fixtures/post-poc/plugin-distribution/revoked-plugin-denied/fixture.json`
- `fixtures/post-poc/plugin-distribution/api-migration-required/fixture.json`
- `fixtures/post-poc/plugin-distribution/stale-index-holds/fixture.json`

Acceptance:

- Release and regulated profiles deny unsigned, revoked, unallowlisted, or
  incompatible plugins.

## HATE-POSTPOC-GAP-007: Live Connector Runtime

Record types:

- `connector-runtime-plan`
- `connector-runtime-attempt`
- `connector-idempotency-record`
- `connector-rollback-visibility-record`

Modes:

- `dry_run`
- `live`
- `replay`
- `rollback_preview`

Required fields:

- `connector_id`, `connector_type`, `mode`, `endpoint_ref`
- `idempotency_key`, `payload_hash`, `redaction_report_ref`
- `token_ref`, not raw token
- `rollback_available`, `external_ref`, `sync_status`

Failure taxonomy:

- `connector_live_mode_not_allowed`
- `connector_token_exposed`
- `connector_idempotency_key_missing`
- `connector_endpoint_unavailable`
- `connector_rollback_visibility_missing`
- `connector_payload_rejected`

Required fixtures:

- `fixtures/post-poc/connectors/fake-ticket-live-success/fixture.json`
- `fixtures/post-poc/connectors/dry-run-no-side-effect/fixture.json`
- `fixtures/post-poc/connectors/idempotent-retry/fixture.json`
- `fixtures/post-poc/connectors/token-exposure-denied/fixture.json`
- `fixtures/post-poc/connectors/rollback-visibility-missing/fixture.json`

Acceptance:

- Fake endpoint contract tests prove live-mode behavior without touching real
  external systems.
- Dry-run and live outputs are distinguishable in sourceRefs and audit events.

## HATE-POSTPOC-GAP-008: Long-Term History Analytics

Record types:

- `history-analytics-query`
- `history-analytics-result`
- `history-trend-window`

Metrics:

- `flake_rate`
- `evidence_freshness`
- `debt_age`
- `repo_health_score`
- `baseline_drift`
- `regression_cluster_count`
- `manual_review_latency`

Required fields:

- `window_start`, `window_end`, `repo_filter`, `suite_filter`
- `aggregation_level`: `suite`, `repo`, `portfolio`
- `sample_count`, `excluded_count`, `exclusion_reasons`
- `performance_budget_ms`

Failure taxonomy:

- `history_window_too_small`
- `history_query_budget_exceeded`
- `history_stale_data`
- `history_metric_source_missing`
- `history_regression_cluster_unexplained`

Required fixtures:

- `fixtures/post-poc/history/flake-rate-trend/fixture.json`
- `fixtures/post-poc/history/debt-aging-trend/fixture.json`
- `fixtures/post-poc/history/baseline-drift/fixture.json`
- `fixtures/post-poc/history/stale-data-holds/fixture.json`
- `fixtures/post-poc/history/query-budget-exceeded/fixture.json`

Acceptance:

- Trend queries are stable across deterministic input history.
- Query budget failure is explicit and not hidden as empty result.

## HATE-POSTPOC-GAP-009: Docs and Acceptance Freshness CI

Record types:

- `docs-freshness-ci-report`
- `acceptance-ledger-freshness-report`
- `state-claim-consistency-report`

Required checks:

- README test count matches latest accepted full test run or is marked stale.
- acceptance records referenced by product-grade exist.
- codemap and caps are current.
- schema registry references existing schemas.
- product-ready, enterprise-ready, regulated-ready claims have evidence.

Failure taxonomy:

- `docs_readme_state_stale`
- `docs_acceptance_record_missing`
- `docs_codemap_stale`
- `docs_schema_registry_stale`
- `docs_product_ready_overclaim`
- `docs_unlinked_gap_closed`

Required fixtures:

- `fixtures/post-poc/docs-freshness/readme-stale/fixture.json`
- `fixtures/post-poc/docs-freshness/missing-acceptance/fixture.json`
- `fixtures/post-poc/docs-freshness/codemap-stale/fixture.json`
- `fixtures/post-poc/docs-freshness/schema-registry-stale/fixture.json`
- `fixtures/post-poc/docs-freshness/product-ready-overclaim/fixture.json`

Acceptance:

- CI can intentionally fail on stale state claims.
- Emergency exceptions require owner, reason, expiry, and acceptance reference.

## HATE-POSTPOC-GAP-010: QEG and Shipyard Release Handoff

Record types:

- `external-release-handoff-request`
- `external-release-handoff-result`
- `external-approval-reference`

Required fields:

- `handoff_target`: `qeg`, `shipyard`, `agent_state_gate`,
  `agent_gatefield`
- `handoff_mode`: `dry_run`, `live_reference`, `record_only`
- `external_run_ref`, `external_decision_ref`, `external_status`
- `hate_claimed_final_approval`: must be false
- `verdict_overwrite_attempted`: must be false

Failure taxonomy:

- `handoff_external_reference_missing`
- `handoff_external_denied`
- `handoff_hate_claimed_final_approval`
- `handoff_verdict_overwrite_attempted`
- `handoff_target_unavailable`

Required fixtures:

- `fixtures/post-poc/handoff/qeg-approved-reference/fixture.json`
- `fixtures/post-poc/handoff/qeg-denied-reference/fixture.json`
- `fixtures/post-poc/handoff/shipyard-publish-denied/fixture.json`
- `fixtures/post-poc/handoff/hate-overclaim-denied/fixture.json`
- `fixtures/post-poc/handoff/missing-external-reference/fixture.json`

Acceptance:

- HATE records external verdict refs and never converts them to self-owned
  release approval.

## HATE-POSTPOC-GAP-011: Hosted Multi-Tenant API

Record types:

- `hosted-api-request-record`
- `hosted-authz-decision-record`
- `hosted-rate-limit-event`

Required fields:

- `request_id`, `tenant_id`, `subject_id`, `role`
- `auth_method`: `oidc`, `api_token`, `service_account`
- `resource`, `action`, `decision`, `denial_reason`
- `token_ref`, `token_expiry`, not raw token
- `rate_limit_bucket`, `rate_limit_status`

Failure taxonomy:

- `api_cross_tenant_denied`
- `api_token_expired`
- `api_service_account_scope_denied`
- `api_rate_limit_exceeded`
- `api_audit_event_missing`
- `api_restricted_data_leaked`

Required fixtures:

- `fixtures/post-poc/hosted-api/tenant-allowed/fixture.json`
- `fixtures/post-poc/hosted-api/cross-tenant-denied/fixture.json`
- `fixtures/post-poc/hosted-api/expired-token-denied/fixture.json`
- `fixtures/post-poc/hosted-api/service-account-scope-denied/fixture.json`
- `fixtures/post-poc/hosted-api/rate-limit-exceeded/fixture.json`

Acceptance:

- Cross-tenant access denial is deterministic and does not leak restricted data.
- Every hosted request produces an authz/audit record.

## HATE-POSTPOC-GAP-012: Store Backup, Restore, and DR Operations

Record types:

- `store-backup-operation`
- `store-restore-operation`
- `store-dr-drill-result`

Required fields:

- `backup_id`, `backup_manifest_ref`, `created_at`
- `source_store_hash`, `backup_hash`, `restore_hash`
- `legal_hold_count_before`, `legal_hold_count_after`
- `rpo_seconds`, `rto_seconds`, `corruption_scan_result`
- `projection_rebuild_status`

Failure taxonomy:

- `dr_backup_inventory_missing`
- `dr_backup_hash_mismatch`
- `dr_corrupt_backup_denied`
- `dr_legal_hold_lost`
- `dr_restore_rto_exceeded`
- `dr_projection_rebuild_failed`

Required fixtures:

- `fixtures/post-poc/dr/backup-restore-success/fixture.json`
- `fixtures/post-poc/dr/corrupt-backup-denied/fixture.json`
- `fixtures/post-poc/dr/legal-hold-lost/fixture.json`
- `fixtures/post-poc/dr/rto-exceeded/fixture.json`
- `fixtures/post-poc/dr/projection-rebuild-failed/fixture.json`

Acceptance:

- Restore drill proves legal hold preservation and projection rebuild.
- Corrupt backups are denied before becoming canonical evidence.

## HATE-POSTPOC-GAP-013: Capacity Benchmark with Measured Baselines

Record types:

- `capacity-benchmark-run`
- `capacity-baseline-record`
- `capacity-degradation-mode-report`

Required scenarios:

- 100 repo roster
- 1000 repo roster
- 100k findings
- 1M findings
- large monorepo fixture
- cold cache and warm cache

Required fields:

- `scenario_id`, `dataset_hash`, `repo_count`, `finding_count`
- `duration_ms`, `peak_memory_mb`, `cache_hit_rate`
- `timeout_count`, `degradation_mode`, `budget_status`

Failure taxonomy:

- `capacity_baseline_missing`
- `capacity_runtime_budget_exceeded`
- `capacity_memory_budget_exceeded`
- `capacity_degradation_mode_missing`
- `capacity_dataset_not_reproducible`

Required fixtures:

- `fixtures/post-poc/capacity/100-repo-baseline/fixture.json`
- `fixtures/post-poc/capacity/1000-repo-baseline/fixture.json`
- `fixtures/post-poc/capacity/1m-findings-baseline/fixture.json`
- `fixtures/post-poc/capacity/warm-cache-improves/fixture.json`
- `fixtures/post-poc/capacity/budget-exceeded-holds/fixture.json`

Acceptance:

- Measured baselines include machine profile and reproducible dataset hash.
- Degradation mode is explicit and cannot be reported as normal pass.

## HATE-POSTPOC-GAP-014: Compliance and Procurement Evidence

Record types:

- `compliance-evidence-pack`
- `procurement-questionnaire-export`
- `control-claim-record`
- `compliance-review-decision`

Control claim classes:

- `data_flow`
- `subprocessor`
- `encryption`
- `retention`
- `residency`
- `access_control`
- `vulnerability_response`
- `incident_response`

Required fields:

- `control_id`, `claim_class`, `claim_text`, `evidence_refs`
- `reviewer`, `review_status`, `reviewed_at`, `expires_at`
- `customer_safe_export`: boolean
- `redaction_report_ref`

Failure taxonomy:

- `compliance_control_evidence_missing`
- `compliance_claim_stale`
- `compliance_reviewer_missing`
- `compliance_export_contains_restricted_data`
- `procurement_answer_unsupported`

Required fixtures:

- `fixtures/post-poc/compliance/procurement-pack-valid/fixture.json`
- `fixtures/post-poc/compliance/control-evidence-missing/fixture.json`
- `fixtures/post-poc/compliance/stale-control-claim/fixture.json`
- `fixtures/post-poc/compliance/reviewer-missing/fixture.json`
- `fixtures/post-poc/compliance/restricted-export-denied/fixture.json`

Acceptance:

- Procurement export is safe to share and links every claim to evidence.
- Stale or unsupported claims produce hold.

## HATE-POSTPOC-GAP-015: Observability and Incident Operations

Record types:

- `runtime-telemetry-event`
- `slo-burn-rate-report`
- `incident-lifecycle-record`
- `post-incident-evidence-pack`

Signals:

- metrics
- structured logs
- traces
- alerts
- incidents
- support diagnostics

Required fields:

- `correlation_id`, `run_id`, `tenant_id`, `service_name`
- `metric_name`, `slo_id`, `burn_rate`, `alert_status`
- `incident_id`, `incident_state`, `owner`, `severity`
- `post_incident_review_ref`

Failure taxonomy:

- `observability_correlation_id_missing`
- `observability_raw_secret_log`
- `observability_alert_route_missing`
- `observability_slo_breach`
- `incident_owner_missing`
- `incident_review_missing`

Required fixtures:

- `fixtures/post-poc/observability/telemetry-valid/fixture.json`
- `fixtures/post-poc/observability/raw-secret-log-denied/fixture.json`
- `fixtures/post-poc/observability/alert-route-missing/fixture.json`
- `fixtures/post-poc/observability/slo-burn-rate-breach/fixture.json`
- `fixtures/post-poc/observability/incident-review-missing/fixture.json`

Acceptance:

- Incident simulation produces alert, owner, timeline, decision, and safe
  support evidence.
- Raw secret logs are denied before support bundle export.

## HATE-POSTPOC-GAP-016: Human Review Operating UI/CLI

Record types:

- `human-review-workflow-request`
- `human-review-workflow-decision`
- `human-review-evidence-attachment`

Actions:

- assign reviewer
- attach evidence
- approve
- deny
- revoke
- expire
- supersede
- resolve

Required fields:

- `review_id`, `operating_record_id`, `required_decision`
- `reviewer`, `owner`, `due_date`, `expiry_date`
- `decision`, `decision_reason`, `evidence_refs`
- `previous_decision_ref`, `superseded_by`

Failure taxonomy:

- `human_review_reviewer_missing`
- `human_review_evidence_missing`
- `human_review_expired`
- `human_review_self_approval_denied`
- `human_review_revoked`
- `human_review_replay_mismatch`

Required fixtures:

- `fixtures/post-poc/human-review/approve-with-evidence/fixture.json`
- `fixtures/post-poc/human-review/deny-with-reason/fixture.json`
- `fixtures/post-poc/human-review/evidence-missing-holds/fixture.json`
- `fixtures/post-poc/human-review/revoked-decision/fixture.json`
- `fixtures/post-poc/human-review/replay-mismatch-holds/fixture.json`

Acceptance:

- CLI or UI workflow can approve, deny, revoke, expire, supersede, and replay a
  human review decision without acting as a waiver bypass.
