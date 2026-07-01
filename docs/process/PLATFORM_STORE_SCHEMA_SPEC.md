---
intent_id: INT-HATE-PLATFORM-STORE-SCHEMA-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Platform Store Schema Specification

本書は platform phase の履歴、operating model、read model、recovery を支える
物理 store schema 正本である。

## 1. Store Modes

| Mode | Purpose | Required Behavior |
|---|---|---|
| `local-jsonl` | local-first / test fixture | append-only JSONL + projection JSON |
| `sqlite` | team local / small hosted | transactional append, indexed query, backup |
| `postgres` | hosted / enterprise | tenant partition, concurrent workers, migration |

All modes must expose the same logical records and projection behavior.

## 2. Logical Tables

| Table | Key | Purpose |
|---|---|---|
| `run_history` | `run_id` | real-repo and platform run history |
| `run_suite_result` | `run_id, repo_id, suite_id` | suite-level status, record counts, timing |
| `score_history` | `score_id` | score, breakdown, penalties, policy hash |
| `baseline_event` | `baseline_event_id` | baseline propose/approve/freeze/expire/revoke |
| `operating_event` | `event_id` | append-only finding/debt/review lifecycle events |
| `operating_projection` | `operating_record_id` | current projection |
| `policy_snapshot` | `policy_hash` | effective policy document |
| `plugin_execution` | `plugin_execution_id` | detector plugin run result |
| `artifact_metadata` | `artifact_id` | CAS metadata, quarantine, retention, legal hold |
| `scheduler_job` | `job_id` | roster scheduler state |
| `audit_event` | `audit_event_id` | RBAC, export, mutation, scheduler, raw access |

## 3. Required Indexes

| Index | Applies To | Query |
|---|---|---|
| `idx_run_repo_time` | `run_history` | repo trend by time window |
| `idx_run_source_version` | `run_history` | source version lookup |
| `idx_suite_status` | `run_suite_result` | held suites by profile |
| `idx_score_repo_time` | `score_history` | score trend |
| `idx_operating_status_due` | `operating_projection` | open/expired due queue |
| `idx_operating_owner` | `operating_projection` | owner work queue |
| `idx_operating_entity` | `operating_projection` | finding/debt/review lookup |
| `idx_policy_hash` | `policy_snapshot` | policy explanation |
| `idx_artifact_state` | `artifact_metadata` | quarantine/retention queue |
| `idx_scheduler_state_lease` | `scheduler_job` | worker lease scan |

## 4. Event Ordering

Every append-only event table requires:

- monotonic `sequence`
- `event_id`
- `occurred_at`
- `actor`
- `sourceRefs`
- `previous_event_hash`
- `event_hash`

Projection rebuild must sort by `sequence`, verify hash continuity where
available, and emit `projection_rebuild_failed` when an event gap exists.

## 5. Migration Contract

Migration records:

- `migration_id`
- `from_store_version`
- `to_store_version`
- `started_at`
- `finished_at`
- `status`
- `pre_migration_checksum`
- `post_migration_checksum`
- `rollback_note`
- `compatibility_report_ref`

No-Go:

- migration drops legal hold metadata
- migration rewrites accepted debt expiry without event
- migration changes score history without preserving original score report
- migration removes raw access audit events

## 6. Backup and Restore

Backup manifest fields:

- `backup_id`
- `store_version`
- `created_at`
- `table_counts`
- `artifact_metadata_count`
- `legal_hold_count`
- `checksum`
- `sourceRefs`

Restore must verify:

- all append-only event counts match
- projection hash matches after rebuild
- legal hold count matches
- artifact metadata references resolve or produce orphan findings

## 7. Fixture Requirements

| Fixture | Expected |
|---|---|
| `fixtures/platform/store/minimal-local-jsonl/fixture.json` | run, score, finding projection load |
| `fixtures/platform/store/projection-rebuild-gap/fixture.json` | event gap produces rebuild failure |
| `fixtures/platform/store/migration-preserves-legal-hold/fixture.json` | legal hold survives migration |
| `fixtures/platform/store/backup-restore-checksum/fixture.json` | checksum and projection match |
| `fixtures/platform/store/orphan-artifact-metadata/fixture.json` | orphan artifact finding |
