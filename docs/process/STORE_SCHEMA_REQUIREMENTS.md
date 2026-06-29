---
intent_id: INT-HATE-STORE-SCHEMA-REQUIREMENTS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Store Schema Requirements

## 1. Purpose

This document defines table, index, migration, and corruption-handling requirements for the
local/hosted HATE store. The store is a read/replay substrate, not a QEG authority.

## 2. Logical Tables

| Table | Primary key | Required indexes |
|---|---|---|
| organizations | organization_id | edition, region |
| workspaces | workspace_id | organization_id, region |
| repositories | repo_id | organization_id, workspace_id, provider, repo_ref |
| runs | run_id, attempt | repo_id, commit_sha, profile, decision, created_at |
| bundles | bundle_hash | run_id, schema_version, immutable, created_at |
| evidence | evidence_id | bundle_hash, kind, status, risk_id, test_id |
| risks | risk_id | bundle_hash, severity, owner, oracle_status |
| artifacts | artifact_id | bundle_hash, classification, safe_for_summary, quarantine_status |
| risk_debt | debt_id | status, severity, owner, age_days |
| test_integrity_signals | signal_id, run_id | severity, status, decision_impact |
| audit_events | event_id | tenant, actor, target, event_type, created_at |
| connector_results | connector_result_id | provider, status, non_gating |
| migrations | migration_id | from_version, to_version, status |

## 3. Store Invariants

- Canonical bundle content is immutable after import.
- Derived read models may be rebuilt from canonical bundle and indexes.
- Audit events are append-only and hash-linked.
- Legal hold blocks deletion of protected metadata.
- External export never mutates canonical bundle.
- Store corruption is a doctor finding, not silent recovery.
- sourceRefs are accepted only when their normalized path resolves inside the imported bundle.
- Evidence record `source_hash` values must match artifact manifest `sha256` values before store import.
- Replay-required records must have deterministic record ids derived from record kind, sourceRefs, and stable payload identity fields.

## 4. Migration Requirements

Each migration must define:

- migration id
- from and to versions
- affected tables
- forward transform
- rollback or no-rollback rationale
- before fixture
- after fixture
- legal hold preservation test
- old bundle replay test

## 5. Index and Query Requirements

| Query | Required index strategy |
|---|---|
| latest run by repo/branch | repositories + runs created_at |
| evidence by risk/test/kind | evidence composite indexes |
| artifacts by classification/quarantine | artifacts classification and quarantine indexes |
| risk debt by owner/status/severity | risk_debt owner/status/severity |
| audit by actor/target/event/date | audit_events composite index |
| bundle by hash | bundles primary key |

## 6. No-Go

- index rebuild changes canonical bundle hash
- migration drops legal hold metadata
- missing index is ignored for high-volume query
- audit event can be updated in place
- old bundle unreadable after minor migration
- hash mismatch is downgraded to a soft warning
- path traversal or external URL sourceRefs enter the canonical store
- coverage contexts reference tests that do not exist in the same bundle
- static findings reference files missing from the artifact manifest
