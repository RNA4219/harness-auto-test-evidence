---
intent_id: INT-HATE-PRODUCT-PLATFORM-PHASE-DETAIL-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Product Platform Phase Detail Specification

本書は `PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md` の実装仕様正本である。
物理 store、policy config、RBAC、dashboard、benchmark fixture の詳細は
以下の正本仕様に分割する。

- `PLATFORM_STORE_SCHEMA_SPEC.md`
- `PLATFORM_POLICY_CONFIG_SPEC.md`
- `PLATFORM_RBAC_MATRIX_SPEC.md`
- `PLATFORM_DASHBOARD_WIREFRAME_SPEC.md`
- `PLATFORM_BENCHMARK_FIXTURE_SPEC.md`
- `PLATFORM_CONNECTOR_SYNC_SPEC.md`
- `PLATFORM_PLUGIN_SANDBOX_SPEC.md`

仕様上の共通規則:

- すべての record は `schema_version`, `record_type`, `record_id`, `sourceRefs` を持つ。
- 判定系 record は `decision_basis` を持ち、score や readiness を説明可能にする。
- external repo を対象にした評価は `ownership_scope=external` を必須とし、HATE 側の修正対象にしない。
- raw artifact body、secret、PII、外部署名 URL は read model/API/dashboard に出さない。
- subset evidence は `proves_full_suite=false` を必須とし、full readiness と混同しない。

## 1. Canonical Record Types

| Record Type | Purpose | Phase |
|---|---|---|
| `real-repo-roster-v2` | repo/suite/schedule/policy を含む評価 roster | 評価基盤 |
| `real-repo-run-history-entry` | 個別 run の保存単位 | 評価基盤 |
| `real-repo-score-report` | score、breakdown、regression、trend | 評価基盤 |
| `real-repo-baseline-event` | baseline の承認、凍結、失効、取消 | 評価基盤 |
| `operating-finding-record` | finding/debt/review を束ねる current projection | 運用基盤 |
| `operating-event-record` | append-only lifecycle event | 運用基盤 |
| `operating-notification-event` | escalation、通知、SLA breach の証跡 | 運用基盤 |
| `detector-plugin-manifest` | detector plugin の契約 | 拡張基盤 |
| `effective-policy-report` | profile/policy/threshold 解決結果 | 拡張基盤 |
| `plugin-compatibility-report` | plugin API semver と migration 状態 | 拡張基盤 |
| `platform-read-model-response` | CLI/API/dashboard 共通 read model envelope | 利用面 |
| `html-report-manifest` | HTML report の生成 manifest | 利用面 |
| `platform-rbac-decision-record` | role/tenant/resource scope の許可・拒否 | 利用面 |
| `execution-cache-index` | cache key と freshness 判定 | 大規模化 |
| `roster-scheduler-state` | scheduled run、lease、retry、cancel 状態 | 大規模化 |
| `artifact-store-record` | CAS/quarantine/retention/legal hold metadata | 大規模化 |
| `platform-store-recovery-report` | backup/restore/rebuild/migration の検証結果 | 大規模化 |

## 2. Phase A: Evaluation Foundation

### 2.1 Roster v2 Schema

`real-repo-roster-v2` fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `schema_version` | string | yes | `HATE/v1` |
| `record_type` | string | yes | `real-repo-roster-v2` |
| `roster_id` | string | yes | stable roster id |
| `source_version` | string | yes | roster source version |
| `default_policy_ref` | string | yes | policy config id |
| `repositories` | array | yes | repo entries |
| `schedules` | array | no | scheduler hints |

Repository entry fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `repo_id` | string | yes | stable id |
| `path` | string | yes | local path or checkout-relative path |
| `ownership_scope` | enum | yes | `owned`, `external`, `third_party_sample` |
| `repo_class` | enum | yes | `small`, `medium`, `large`, `xlarge`, `monorepo` |
| `suites` | array | yes | suite entries |
| `tags` | string[] | no | portfolio tags |
| `risk_profile` | string | no | risk profile ref |

Suite entry fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `suite_id` | string | yes | stable suite id |
| `suite_kind` | enum | yes | `unit`, `integration`, `e2e`, `build`, `typecheck`, `lint`, `security`, `smoke`, `package-split` |
| `command` | string[] | yes | command argv |
| `timeout_profile` | string | yes | timeout policy ref |
| `subset` | boolean | yes | subset flag |
| `subset_label` | string | conditional | required when subset=true |
| `expected_record_floor` | integer | no | regression floor |
| `baseline_ref` | string | no | pinned baseline |
| `env` | object | no | string-only env overrides |

### 2.2 Run History

Each command execution writes one `real-repo-run-history-entry`.

Required fields:

- `run_id`
- `repo_id`
- `suite_id`
- `ownership_scope`
- `source_version`
- `roster_hash`
- `policy_hash`
- `environment_fingerprint`
- `started_at`
- `finished_at`
- `duration_ms`
- `command_exit_code`
- `status`: `pass`, `hold`, `blocked`
- `record_count`
- `command_summary`
- `failure_kind`
- `timeout_recorded`
- `subset`
- `command_excerpt_ref`
- `sourceRefs`

`environment_fingerprint` contains OS family, shell family, tool versions that
affect parser or runner semantics, and redacted path class. It must not contain
username, home path, tokens, or raw environment values.

### 2.3 Score Model

Score output is `real-repo-score-report`.

The score is a bounded 0-100 value:

```text
base = evidence_strength * 40
     + coverage_confidence * 15
     + oracle_confidence * 15
     + freshness_score * 10
     + stability_score * 10
     + ownership_clarity * 10

penalty = regression_penalty
        + timeout_penalty
        + record_collapse_penalty
        + manual_debt_penalty
        + expired_debt_penalty
        + unsafe_artifact_penalty

score = clamp(base - penalty, 0, 100)
```

Component requirements:

| Component | Range | Source |
|---|---:|---|
| `evidence_strength` | 0.0-1.0 | executed tests, contract checks, mutation/static/manual evidence |
| `coverage_confidence` | 0.0-1.0 | coverage with context and evidence map |
| `oracle_confidence` | 0.0-1.0 | assertion quality and risk oracle mapping |
| `freshness_score` | 0.0-1.0 | age against policy TTL |
| `stability_score` | 0.0-1.0 | trend and flake/retry rate |
| `ownership_clarity` | 0.0-1.0 | owner/due date/manual decision completeness |

Penalty requirements:

| Penalty | Rule |
|---|---|
| `regression_penalty` | pass→hold or new failure kind: 20-40 |
| `timeout_penalty` | timeout without partial evidence: 20; timeout with partial evidence: 10 |
| `record_collapse_penalty` | record count drop beyond threshold: 10-30 |
| `manual_debt_penalty` | accepted debt open: severity weighted 3-15 |
| `expired_debt_penalty` | expired accepted debt: 20-50 |
| `unsafe_artifact_penalty` | unsafe required artifact: 20-50 |

No score may be emitted without `score_breakdown` and `decision_basis`.

### 2.4 Regression Detection

Regression classes:

| Class | Trigger | Effect |
|---|---|---|
| `status_regression` | baseline pass/eligible -> current hold/blocked | hold |
| `record_count_collapse` | current records < floor or drop > threshold | hold |
| `runtime_drift` | runtime exceeds baseline by configured ratio | soft_gap or hold |
| `failure_kind_new` | new failure_kind not present in baseline | hold |
| `parser_quality_regression` | summary parser loses records or misclassifies logs | hold |
| `external_hold_detected` | external repo fails under local profile | external finding, not HATE implementation failure |

### 2.5 Required Fixtures

| Fixture | Purpose |
|---|---|
| `fixtures/platform/evaluation/baseline-pass-current-pass/fixture.json` | stable pass history |
| `fixtures/platform/evaluation/pass-to-hold-regression/fixture.json` | status regression |
| `fixtures/platform/evaluation/record-collapse/fixture.json` | record collapse |
| `fixtures/platform/evaluation/runtime-drift/fixture.json` | runtime drift |
| `fixtures/platform/evaluation/external-repo-hold/fixture.json` | external hold separation |
| `fixtures/platform/evaluation/noisy-runner-log/fixture.json` | parser ignores non-summary error logs |
| `fixtures/platform/evaluation/baseline-approval-freeze/fixture.json` | baseline approval and freeze |
| `fixtures/platform/evaluation/redacted-deterministic-output/fixture.json` | redaction and deterministic normalization |

### 2.6 Baseline Governance

`real-repo-baseline-event` fields:

- `baseline_id`
- `repo_id`
- `suite_id`
- `baseline_run_id`
- `event_type`: `proposed`, `approved`, `frozen`, `expired`, `revoked`, `superseded`
- `actor`
- `reason`
- `approved_by`
- `expires_at`
- `policy_hash`
- `sourceRefs`

Rules:

- A baseline cannot be used for regression comparison before `approved`.
- A frozen baseline cannot be replaced without `superseded` and reviewer reason.
- Expired baseline produces `baseline_expired` finding and cannot hide regressions.
- External repo baseline must include `ownership_scope=external` and cannot be
  used as HATE implementation readiness proof.

### 2.7 Output Redaction and Normalization

Command output persistence must run through:

1. ANSI/control character normalization
2. path redaction for user home, workspace temp, private absolute paths
3. secret/PII pattern redaction
4. line-ending normalization
5. deterministic truncation with truncation marker
6. summary parser dialect extraction

The raw command output may be kept only as a quarantined artifact store object
with explicit raw access approval. Read model and HTML report must use redacted
excerpt refs.

## 3. Phase B: Operations Foundation

### 3.1 Unified Operating Model

`operating-finding-record` is the current projection for findings, risk debt,
and manual review.

Required fields:

- `operating_record_id`
- `entity_kind`: `finding`, `risk_debt`, `manual_review`, `policy_drift`, `external_hold`
- `entity_id`
- `status`: `open`, `accepted`, `expired`, `resolved`, `revoked`, `superseded`, `merged`
- `severity`
- `readiness_effect`
- `owner`
- `due_date`
- `expiry_date`
- `sourceRefs`
- `evidence_refs`
- `decision_basis`
- `last_event_id`

`operating-event-record` is append-only.

Event types:

- `finding_opened`
- `finding_deduplicated`
- `owner_assigned`
- `due_date_changed`
- `manual_review_requested`
- `manual_review_decided`
- `risk_debt_accepted`
- `risk_debt_expired`
- `risk_debt_revoked`
- `risk_debt_resolved`
- `record_superseded`
- `tracker_sync_requested`
- `tracker_sync_completed`
- `sla_breach_detected`
- `notification_requested`
- `notification_sent`
- `notification_failed`
- `projection_rebuilt`
- `retention_applied`
- `legal_hold_applied`

### 3.2 Lifecycle Rules

| Current | Event | Next | Validation |
|---|---|---|---|
| open | `risk_debt_accepted` | accepted | owner, expiry_date, justification required |
| accepted | time passes expiry | expired | generated by expiry scanner |
| accepted | `risk_debt_resolved` | resolved | resolving evidence required |
| accepted | `risk_debt_revoked` | revoked | actor and reason required |
| open | `record_superseded` | superseded | superseding record id required |
| open | `manual_review_decided` | accepted or resolved | reviewer, required_decision, evidence_refs required |

### 3.3 Readiness Effects

| Condition | Effect |
|---|---|
| critical/high risk without oracle and no accepted debt | hold |
| expired accepted debt | hard_dq or hold, profile-dependent |
| owner missing for blocking finding | hold |
| due_date missing for release profile | hold |
| manual review missing evidence_refs | hold |
| duplicate finding merged into active record | no additional penalty, but history retained |
| SLA breach for high/critical record | hold until owner or expiry policy resolves |
| notification failure for blocking record | soft_gap or hold, profile-dependent |

### 3.4 Tracker Sync

External trackers are mirrors, not source of truth.

Sync payload fields:

- `operating_record_id`
- `external_system`
- `external_ref`
- `sync_direction`
- `sync_status`
- `last_synced_at`
- `sync_error`

Tracker sync must never overwrite canonical lifecycle state without an explicit
`tracker_sync_completed` event carrying actor and sourceRef.

### 3.5 Notification and Escalation

Escalation policy inputs:

- severity
- readiness_effect
- owner
- due_date
- expiry_date
- lifecycle_state
- repo criticality
- release window

Notification targets:

- local report
- CLI summary
- GitHub issue/comment/check annotation
- Slack channel or DM
- external tracker sync payload

Every notification attempt writes `operating-notification-event` with
`delivery_target`, `delivery_status`, `attempt`, `error_code`, and `sourceRefs`.
Notification failure must never close or downgrade the canonical finding.

### 3.6 Retention, Legal Hold, and Projection Rebuild

Operating events are retained according to `DATA_RETENTION_LEGAL_REQUIREMENTS.md`.
Projection rebuild must:

- preserve legal hold metadata
- preserve accepted debt expiry
- preserve manual review decision trail
- detect missing event gaps
- produce `projection_rebuild_failed` finding when current projection cannot be reproduced

### 3.7 Required Fixtures

| Fixture | Purpose |
|---|---|
| `fixtures/platform/operations/finding-owner-due-date/fixture.json` | required owner and due date |
| `fixtures/platform/operations/accepted-debt-expired/fixture.json` | expiry scanner creates hold |
| `fixtures/platform/operations/manual-review-no-evidence/fixture.json` | invalid manual review |
| `fixtures/platform/operations/debt-resolved-with-evidence/fixture.json` | resolution path |
| `fixtures/platform/operations/deduplicate-findings/fixture.json` | audit trail retained |
| `fixtures/platform/operations/tracker-mirror-not-source/fixture.json` | canonical source protection |
| `fixtures/platform/operations/escalation-notification-failed/fixture.json` | notification failure retained |
| `fixtures/platform/operations/projection-rebuild-legal-hold/fixture.json` | rebuild preserves legal hold |

## 4. Phase C: Extension Foundation

### 4.1 Detector Plugin Manifest

`detector-plugin-manifest` fields:

| Field | Type | Required |
|---|---|---:|
| `plugin_id` | string | yes |
| `plugin_version` | semver | yes |
| `api_version` | string | yes |
| `detectors` | array | yes |
| `input_contract` | object | yes |
| `output_contract` | object | yes |
| `capabilities` | string[] | yes |
| `trust_level` | enum | yes |
| `entrypoint` | object | yes |
| `resource_limits` | object | yes |

Detector entry fields:

- `detector_id`
- `signal_ids`
- `supported_profiles`
- `default_thresholds`
- `required_inputs`
- `emitted_record_types`

### 4.2 Policy Resolution

Policy layers, lowest to highest:

1. built-in defaults
2. product default policy file
3. organization policy file
4. workspace policy file
5. roster suite override
6. CLI explicit override

`effective-policy-report` must include:

- `policy_hash`
- `profile`
- `resolved_layers`
- `effective_thresholds`
- `disabled_detectors`
- `unsigned_plugin_denials`
- `explain`

### 4.3 Plugin Execution

Execution phases:

1. discover manifests
2. validate manifest schema
3. resolve trust level and signature policy
4. build effective policy
5. prepare input bundle
6. run plugin with timeout/resource limit
7. validate output
8. normalize to canonical findings
9. emit detector execution report

Failure handling:

| Failure | Output |
|---|---|
| manifest invalid | `plugin_manifest_invalid` finding |
| unsigned release plugin | `plugin_trust_denied` finding |
| timeout | `plugin_timeout` finding |
| malformed output | `plugin_output_invalid` finding |
| unsupported api version | `plugin_api_incompatible` finding |

### 4.4 Required Fixtures

| Fixture | Purpose |
|---|---|
| `fixtures/platform/extensions/plugin-valid/fixture.json` | valid plugin manifest and output |
| `fixtures/platform/extensions/plugin-malformed-output/fixture.json` | malformed output denied |
| `fixtures/platform/extensions/plugin-timeout/fixture.json` | timeout converted to finding |
| `fixtures/platform/extensions/policy-override-threshold/fixture.json` | threshold override |
| `fixtures/platform/extensions/release-unsigned-plugin-denied/fixture.json` | trust policy |
| `fixtures/platform/extensions/effective-policy-explain/fixture.json` | explainable config resolution |
| `fixtures/platform/extensions/plugin-api-migration/fixture.json` | semver and migration note |
| `fixtures/platform/extensions/plugin-signature-allowlist/fixture.json` | signature and allowlist enforcement |

### 4.5 Plugin Compatibility and Trust

`plugin-compatibility-report` fields:

- `plugin_id`
- `plugin_version`
- `api_version`
- `compatibility_status`: `compatible`, `deprecated`, `migration_required`, `blocked`
- `migration_note_ref`
- `deprecated_fields`
- `breaking_changes`
- `trust_status`: `trusted`, `unsigned`, `unallowlisted`, `revoked`
- `signature_ref`
- `allowlist_ref`

Release and regulated profiles must block plugins when:

- signature is missing or invalid
- plugin id/version is not allowlisted
- API version is unsupported
- migration note is missing for breaking output changes
- plugin requests capabilities not declared in manifest

## 5. Phase D: Consumption Surfaces

### 5.1 CLI

Required commands:

| Command | Purpose |
|---|---|
| `hate platform run` | run roster with policy, history, cache |
| `hate platform history` | query run history |
| `hate platform compare` | compare baseline/current |
| `hate platform findings` | list/filter operating findings |
| `hate platform debt` | accept/expire/resolve risk debt |
| `hate platform review` | create/decide manual review |
| `hate platform policy explain` | show effective policy |
| `hate platform report html` | generate HTML report |
| `hate platform serve` | serve JSON API/dashboard |

### 5.1.1 Platform CLI Minimum Contract

The first platform CLI implementation is an orchestration layer over canonical
reports, not a new verdict engine. It must preserve the output contracts of the
underlying commands and add operator-facing projections only when the projection
can retain sourceRefs.

| Command | Required inputs | Output record | No-Go |
|---|---|---|---|
| `hate platform run` | `--roster`, `--out`, optional `--source-version` | `real-repo-evaluation-run-report` | must not suppress hold, timeout, external hold, or output safety findings |
| `hate platform history` | `--store`, optional filters | `real-repo-history-query-report` | must not synthesize missing history as pass |
| `hate platform compare` | `--base`, `--head`, optional `--out` | `platform-comparison-report` | must not ignore pass-to-hold, record count, runtime, dialect, or finding deltas |
| `hate platform findings` | `--input` report dir/file | `platform-findings-report` | must not drop sourceRef/sourceRefs |
| `hate platform debt` | `--input` report dir/file | `platform-debt-report` | empty debt must be explicit, not hidden |
| `hate platform review` | `--input` report dir/file | `platform-review-report` | manual review requests must remain requests, not waivers |
| `hate platform policy explain` | `--policy` JSON, optional `--out`, `--profile` | `platform-policy-report` | release/regulated plugin trust denials must not be softened |
| `hate platform report html` | `--input` report dir/file, `--out` HTML path | offline HTML | must not embed raw unsafe artifact body, secret, PII, or unrestricted local paths |
| `hate platform serve` | `--readiness`, optional host/port | hosted read-model REST envelope | must delegate to product read model and not recompute verdicts |

### 5.1.2 Product-Grade Recalculation Contract

`product grade-reports` must evaluate more than the existence of requirement
documents. The report generator must combine:

- required specification document presence
- implementation file presence for each product-grade area
- mapped test file presence
- latest real-repo bulk validation acceptance evidence, when present
- QEG smoke evidence, when present in the acceptance record
- unresolved residual blockers such as owned repo holds, environment cache
  friction, or build/typecheck-only evidence constraints

Output status:

| Status | Meaning |
|---|---|
| `no_go` | required docs or mapped implementation/test evidence is missing |
| `conditional_go` | required docs and mapped implementation/test evidence exist, but residual operational blockers remain |
| `verified` | required docs, mapped implementation/test evidence, real-data validation, and QEG smoke pass with no residual blockers |

`product_ready` remains false unless status is `verified` and a release/QEG
approval record exists. HATE must not promote itself to final release authority.

### 5.2 Read Model Resources

Resources:

- `runs`
- `repos`
- `suites`
- `scores`
- `findings`
- `risk-debt`
- `manual-review`
- `policies`
- `artifacts`
- `scheduler`

Common response envelope:

```json
{
  "schema_version": "HATE/v1",
  "record_type": "platform-read-model-response",
  "request_id": "req_...",
  "resource": "runs",
  "status": "ok",
  "stale": false,
  "data": [],
  "page": {
    "next_cursor": null
  },
  "sourceRefs": []
}
```

### 5.3 JSON API

Endpoints:

| Method | Path | Resource |
|---|---|---|
| GET | `/api/v1/runs` | run history |
| GET | `/api/v1/runs/{run_id}` | run detail |
| GET | `/api/v1/repos/{repo_id}/trend` | score trend |
| GET | `/api/v1/findings` | operating findings |
| GET | `/api/v1/risk-debt` | debt projection |
| POST | `/api/v1/risk-debt/{id}/accept` | accept debt |
| POST | `/api/v1/manual-review/{id}/decide` | decide review |
| GET | `/api/v1/policies/effective` | policy explain |
| GET | `/api/v1/reports/{report_id}` | report metadata |

All endpoints support:

- `request_id`
- pagination cursor
- filter
- sort
- RBAC denial envelope
- stale cache marker

### 5.3.1 RBAC Matrix

RBAC decisions write `platform-rbac-decision-record`.

Required dimensions:

- role: `admin`, `maintainer`, `developer`, `auditor`, `viewer`, `service`
- tenant scope: organization, workspace, project, repository
- resource scope: run, artifact, finding, risk debt, manual review, policy, audit event
- action: read, write, decide, export, raw_access, quarantine_release

Denial responses must not reveal restricted raw artifact paths, secret values,
or hidden resource body. They may reveal stable resource ids only when policy
allows metadata visibility.

### 5.4 HTML Report

Report types:

- single run report
- portfolio health report
- regression diff report
- external hold report
- manual review brief
- expired debt report

Required sections:

- summary
- score breakdown
- regression findings
- open operating records
- policy hash/effective profile
- unsafe artifact exclusions
- sourceRefs
- generated_at

### 5.5 Dashboard

Views:

- portfolio overview
- repo detail
- run detail
- findings queue
- risk debt board
- manual review queue
- policy drift
- scheduler status
- artifact quarantine

State matrix:

| State | Required behavior |
|---|---|
| loading | skeleton without fake counts |
| empty | explicit no-data reason |
| partial | identify missing resources |
| stale | show stale age and source |
| permission denied | do not leak hidden resource existence beyond allowed metadata |
| unsafe hidden | show redacted reason and approval path |

### 5.6 Required Fixtures

| Fixture | Purpose |
|---|---|
| `fixtures/platform/ux/read-model-runs/fixture.json` | run query |
| `fixtures/platform/ux/api-rbac-denied/fixture.json` | RBAC denial |
| `fixtures/platform/ux/html-regression-report/fixture.json` | HTML report manifest |
| `fixtures/platform/ux/dashboard-stale-partial/fixture.json` | partial stale view |
| `fixtures/platform/ux/unsafe-artifact-hidden/fixture.json` | safe display |
| `fixtures/platform/ux/manual-review-brief/fixture.json` | review brief |
| `fixtures/platform/ux/rbac-role-tenant-denial/fixture.json` | RBAC role and tenant denial |
| `fixtures/platform/ux/offline-html-performance/fixture.json` | offline report and read-model performance |

## 6. Phase E: Scale Foundation

### 6.1 Execution Cache

Cache key:

```text
cache_key = sha256(
  input_hash
  + tool_version
  + detector_version
  + policy_hash
  + environment_fingerprint
  + command_signature
)
```

Cache entry fields:

- `cache_key`
- `cache_status`: `hit`, `miss`, `stale`, `incompatible`, `poisoned`
- `created_at`
- `expires_at`
- `input_hash`
- `policy_hash`
- `tool_versions`
- `sourceRefs`
- `artifact_refs`

Cache cannot be used when:

- policy hash changed and compatibility rule is absent
- detector version changed with breaking migration
- sourceRefs are missing
- unsafe artifact dependency is unresolved
- previous run was timeout without resume token

### 6.2 Parallel Execution

Scheduler uses task graph nodes:

- repo checkout node
- suite command node
- adapter parse node
- detector node
- score node
- projection update node
- report render node

Resource budgets:

- max concurrent repos
- max concurrent commands
- max CPU weight
- max memory weight
- per-repo serialization lock
- artifact store write lock

### 6.3 Incremental Scan

Inputs:

- changed files
- dependency graph
- risk map
- detector input map
- previous evidence index
- policy change map

Output:

- `included_scope`
- `skipped_scope`
- `skip_reason`
- `full_suite_proven`
- `required_followup`

Incremental scan cannot claim full-suite readiness unless it has explicit
policy permission and previous full evidence is fresh.

### 6.4 Roster Scheduler

Scheduler states:

- `queued`
- `leased`
- `running`
- `succeeded`
- `held`
- `failed`
- `timed_out`
- `cancel_requested`
- `cancelled`
- `retry_wait`
- `poisoned`

Lease fields:

- `lease_id`
- `worker_id`
- `leased_at`
- `lease_expires_at`
- `heartbeat_at`

Retry policy:

- deterministic retry for infrastructure failures
- no blind retry for assertion failures
- backoff with max attempts
- poison message after repeated launch failure

### 6.5 Artifact Store

Artifact store properties:

- content-addressed object id
- metadata record separated from body
- quarantine state
- retention policy
- legal hold
- raw access approval
- GC mark/sweep
- redaction manifest

Artifact states:

- `stored_safe`
- `quarantined`
- `redacted`
- `expired`
- `legal_hold`
- `deleted_metadata_only`
- `deleted_full`

### 6.6 Store Recovery and Capacity

`platform-store-recovery-report` fields:

- `operation`: `backup`, `restore`, `projection_rebuild`, `migration`, `corruption_scan`
- `store_version`
- `target_store_version`
- `record_count`
- `finding_count`
- `artifact_count`
- `legal_hold_count`
- `checksum_before`
- `checksum_after`
- `status`
- `findings`

Recovery requirements:

- backup and restore preserve legal hold, retention, accepted debt expiry, and audit events
- migration writes compatibility report and rollback note
- corruption scan identifies missing event sequence and orphan artifact metadata
- projection rebuild compares rebuilt projection hash with current projection hash

Capacity benchmark dimensions:

- repo count: 10, 100, 1000
- finding count: 10k, 100k, 1M
- artifact metadata count: 10k, 100k, 1M
- scheduler queue depth: 1k, 10k, 100k
- read model query P50/P95/P99
- degradation mode when budgets are exceeded

### 6.7 Required Fixtures

| Fixture | Purpose |
|---|---|
| `fixtures/platform/scale/cache-hit-compatible/fixture.json` | valid cache hit |
| `fixtures/platform/scale/cache-stale-policy-change/fixture.json` | stale cache denial |
| `fixtures/platform/scale/parallel-resource-budget/fixture.json` | budget enforcement |
| `fixtures/platform/scale/incremental-scope-limited/fixture.json` | subset warning |
| `fixtures/platform/scale/scheduler-timeout-resume/fixture.json` | resume token |
| `fixtures/platform/scale/artifact-quarantine-gc/fixture.json` | quarantine and retention |
| `fixtures/platform/scale/store-backup-restore-legal-hold/fixture.json` | recovery preserves legal hold |
| `fixtures/platform/scale/capacity-benchmark-degradation/fixture.json` | capacity and degradation mode |

## 7. Cross-Phase UAT

| UAT ID | Scenario | Expected Result |
|---|---|---|
| PPH-UAT-001 | 3 owned repos and 1 external repo are evaluated nightly | owned regression becomes HATE hold; external hold is external finding |
| PPH-UAT-002 | high risk accepted debt expires before release | expired debt appears in dashboard, API, HTML report, and score penalty |
| PPH-UAT-003 | custom detector plugin emits malformed output | plugin failure finding appears; run does not crash |
| PPH-UAT-004 | release profile changes threshold | effective policy shows source layer and score changes |
| PPH-UAT-005 | dashboard user lacks permission for artifact body | unsafe body hidden, metadata and reason visible |
| PPH-UAT-006 | large roster run times out midway | partial result and resume token are saved |
| PPH-UAT-007 | incremental scan skips unaffected suite | skipped scope is visible and full-suite claim is false |
| PPH-UAT-008 | cache hit after policy change | cache is stale/incompatible and not used for pass |

## 8. Implementation Boundaries

- Existing `real-repo` CLI may remain as compatibility surface, but new platform
  commands should use `hate platform ...`.
- Existing report schemas may be wrapped or migrated, but must not lose backward
  compatibility without migration policy.
- Existing risk matrix/manual review modules should feed the operating model
  rather than create competing lifecycle states.
- Existing dashboard/read model code should consume projection records, not
  recompute readiness decisions.
- Existing artifact safety should become artifact store admission control.

## 9. Physical Specification Links

| Area | Physical Specification | Required Before |
|---|---|---|
| Store schema | `PLATFORM_STORE_SCHEMA_SPEC.md` | PPH-PKT-EVAL-003, PPH-PKT-OPS-002, PPH-PKT-SCALE-008 |
| Policy config | `PLATFORM_POLICY_CONFIG_SPEC.md` | PPH-PKT-EXT-003, PPH-PKT-EXT-004 |
| RBAC matrix | `PLATFORM_RBAC_MATRIX_SPEC.md` | PPH-PKT-UX-003, PPH-PKT-UX-008 |
| Dashboard wireframe | `PLATFORM_DASHBOARD_WIREFRAME_SPEC.md` | PPH-PKT-UX-005 |
| Benchmark fixture | `PLATFORM_BENCHMARK_FIXTURE_SPEC.md` | PPH-PKT-SCALE-009 |
| Connector sync | `PLATFORM_CONNECTOR_SYNC_SPEC.md` | PPH-PKT-OPS-007, PPH-PKT-OPS-008 |
| Plugin sandbox | `PLATFORM_PLUGIN_SANDBOX_SPEC.md` | PPH-PKT-EXT-005, PPH-PKT-EXT-009 |
