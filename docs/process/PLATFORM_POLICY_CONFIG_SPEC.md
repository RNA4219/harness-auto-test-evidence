---
intent_id: INT-HATE-PLATFORM-POLICY-CONFIG-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Platform Policy Config Specification

本書は profile、policy、threshold、plugin trust、retention、scheduler budget の
外部設定形状を定義する。

## 1. Config Files

| File | Scope | Required |
|---|---|---:|
| `hate-policy.json` | product/workspace default | yes |
| `hate-policy.override.json` | local override | no |
| `org-policy.json` | organization hosted policy | no |
| `roster-policy.json` | roster-specific policy | no |

## 2. Top-Level Shape

Required fields:

- `schema_version`
- `record_type`: `platform-policy-config`
- `policy_id`
- `policy_version`
- `profiles`
- `thresholds`
- `detectors`
- `plugins`
- `scheduler`
- `retention`
- `artifact_safety`
- `sourceRefs`

## 3. Profile Rules

Supported built-in profiles:

- `default`
- `strict`
- `release`
- `regulated`
- `experimental`

Profile fields:

- `inherits`
- `readiness_effect_overrides`
- `required_owner`
- `required_due_date`
- `accepted_debt_max_age_days`
- `manual_review_requires_evidence_refs`
- `unsigned_plugin_policy`

## 4. Threshold Resolution

Threshold lookup order:

1. detector + signal + repo_id + suite_id
2. detector + signal + repo_class + suite_kind
3. detector + signal + risk_class
4. detector + signal
5. profile default

Each resolved threshold must include:

- `value`
- `source_layer`
- `source_path`
- `reason`

## 5. Plugin Trust Policy

Plugin trust fields:

- `allow_unsigned`
- `allowlist`
- `denylist`
- `required_signature`
- `trusted_publishers`
- `capability_limits`

Release and regulated profiles must set:

- `allow_unsigned=false`
- `required_signature=true`
- deny unknown publishers

## 6. Retention and Legal Hold

Retention policy fields:

- `default_retention_days`
- `artifact_retention_days`
- `unsafe_artifact_retention_days`
- `audit_event_retention_days`
- `legal_hold_override`
- `deletion_mode`: `tombstone`, `metadata_only`, `full_delete`

Legal hold always overrides deletion.

## 7. Scheduler Budget

Scheduler fields:

- `max_concurrent_repos`
- `max_concurrent_suites`
- `max_concurrent_plugins`
- `command_timeout_profiles`
- `retry_policy`
- `lease_seconds`
- `heartbeat_seconds`

## 8. Required Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/platform/policy/default-effective/fixture.json` | default profile resolves |
| `fixtures/platform/policy/layered-override/fixture.json` | override source explained |
| `fixtures/platform/policy/release-unsigned-plugin-denied/fixture.json` | trust denied |
| `fixtures/platform/policy/regulated-unsigned-plugin-denied/fixture.json` | regulated trust denied even with thin profile rule |
| `fixtures/platform/policy/threshold-specificity/fixture.json` | most-specific threshold wins |
| `fixtures/platform/policy/legal-hold-retention-override/fixture.json` | legal hold overrides deletion |
| `fixtures/platform/policy/scheduler-invalid-budget/fixture.json` | invalid scheduler budget becomes hold |
| `fixtures/platform/policy/required-fields-missing/fixture.json` | required top-level field omission becomes hold |
