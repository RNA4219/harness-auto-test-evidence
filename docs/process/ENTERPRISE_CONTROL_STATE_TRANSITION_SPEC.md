---
intent_id: INT-HATE-ENTERPRISE-CONTROL-STATE-TRANSITION-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-08
---

# Enterprise Control State Transition Spec

This document closes the requirements-to-spec gap for enterprise RBAC, audit,
retention, legal hold, connector dry-run, and assurance controls. It refines
`ENTERPRISE_PRODUCT_REQUIREMENTS.md`, `DATA_RETENTION_LEGAL_REQUIREMENTS.md`,
and `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md`.

## 1. Scope

Required domains:

- RBAC decision
- audit event
- risk debt transition
- retention policy application
- legal hold
- export/delete request
- connector dry-run
- assurance pack inclusion

## 2. RBAC Decision Contract

```yaml
rbac_decision:
  decision_id: string
  actor_id: string
  role: admin | maintainer | reviewer | auditor | viewer | service_account
  action: read | write | review | export | delete | administer
  resource_kind: run | artifact | report | manual_review | export | admin | audit
  resource_id: string
  decision: allow | deny
  reason: string
  allowed_scope: tenant | workspace | repo | run | none
  sourceRefs: array
```

No-Go:

- deny decisions must not reveal restricted artifact paths
- RBAC must not alter precheck, QEG, or release verdicts

## 3. Audit Event Contract

```yaml
audit_event:
  event_id: string
  actor_id: string
  action: string
  target_kind: string
  target_id: string
  decision: allow | deny | recorded
  before_hash: string | null
  after_hash: string | null
  timestamp: ISO-8601
  sourceRefs: array
```

Audit events are append-only. Any state transition without an audit event is a
hold finding in `enterprise-control-report`.

## 4. State Machines

| Domain | Allowed transitions |
|---|---|
| risk debt | open -> acknowledged -> mitigated -> closed; stale -> acknowledged; accepted -> closed only with external sourceRefs |
| legal hold | inactive -> active -> released; active -> deleted is forbidden |
| retention | retain -> purge_eligible -> metadata_purged; retain -> deleted is forbidden under legal hold |
| export request | requested -> dry_run_passed -> exported; requested -> denied; exported -> revoked_metadata_only |
| connector dry-run | configured -> dry_run_passed; configured -> dry_run_failed; disabled -> skipped |
| assurance item | candidate -> included; candidate -> excluded_with_reason |

## 5. Required Findings

- `enterprise_rbac_denied`
- `enterprise_audit_event_missing`
- `enterprise_legal_hold_delete_denied`
- `enterprise_retention_policy_missing`
- `enterprise_export_raw_artifact_denied`
- `enterprise_connector_failure_nongating`
- `enterprise_assurance_item_unsafe_excluded`

## 6. Acceptance

Implementation is acceptable only when:

- every allowed and denied transition has fixtures
- legal hold prevents delete/export mutation
- connector failure is non-gating and canonical hash unchanged
- audit event includes actor, action, target, decision, timestamp, sourceRefs
- restricted artifacts expose safe metadata only
- `enterprise-control-report.schema.json` validates all sections
