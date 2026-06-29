---
intent_id: INT-HATE-DATA-RETENTION-LEGAL-REQUIREMENTS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Data Retention and Legal Requirements

## 1. Purpose

This document defines data classification, retention, legal hold, export, deletion,
audit, and commercial truthfulness requirements for HATE.

HATE must remain local-first while supporting enterprise and regulated deployment modes.
Retention and legal controls must not mutate canonical evidence silently.

## 2. Data Classification

| Class | Examples | Summary allowed | Export allowed | Default retention |
|---|---|---|---|---|
| public | safe aggregate counts, error code names | yes | yes | 1 year |
| internal | run metadata, normalized test names where allowed | yes with policy | yes with policy | 1 year |
| confidential | repo paths, sourceRefs, internal URLs | limited | limited | 180 days |
| restricted | secrets, PII, raw screenshots/logs/traces | no | no by default | quarantine metadata only |
| regulated | customer-specific compliance evidence | policy-based | policy-based | customer policy |

## 3. Retention Requirements

| ID | Requirement | Acceptance |
|---|---|---|
| DRL-RET-001 | Retention policy applies by artifact classification and tenant policy | policy fixture maps class to action |
| DRL-RET-002 | Canonical bundle metadata remains replayable after artifact body expiry | expired artifact fixture still explains decision |
| DRL-RET-003 | Retention action emits audit event with actor/tool, policy, target, before/after | audit event fixture |
| DRL-RET-004 | Retention never deletes legal-hold protected metadata | legal hold fixture |
| DRL-RET-005 | Retention policy changes support dry-run and preview diff | admin UI/API UAT |

## 4. Legal Hold Requirements

| ID | Requirement | Acceptance |
|---|---|---|
| DRL-HOLD-001 | Legal hold blocks deletion/export mutation for protected resources | delete request denied |
| DRL-HOLD-002 | Legal hold has owner, source contract/ref, scope, start, expiry/review date | schema fixture |
| DRL-HOLD-003 | Legal hold state is visible in release/evidence room/admin views | UI UAT |
| DRL-HOLD-004 | Legal hold survives migration | migration fixture |
| DRL-HOLD-005 | HATE does not claim QEG retention authority | boundary test |

## 5. Customer Export and Deletion

| Request | Required behavior |
|---|---|
| customer export | metadata-only by default; raw artifact export requires explicit policy and safety check |
| deletion request | delete or tombstone according to retention/legal hold policy |
| evidence room export | excludes unsafe artifacts and includes limitations |
| diagnostic export | safe-to-share bundle only |
| commercial procurement export | claims mapped to implemented evidence or unsupported status |

No-Go:

- export includes customer source code or artifact body by default
- deletion removes audit trail required for legal hold
- unsupported claim omitted from procurement response

## 6. Audit Requirements

Audit event required fields:

```yaml
event_id: string
event_type: string
actor:
  id: string
  type: user | service_account | system
target:
  resource_type: string
  resource_id: string
tenant:
  organization_id: string
  workspace_id: string
before: object | null
after: object | null
source_refs: array
created_at: ISO-8601
hash:
  previous: string | null
  current: string
```

Required audit events:

- bundle.imported
- profile.changed
- adapter.enabled
- risk_debt.updated
- artifact.quarantined
- retention.policy_applied
- legal_hold.created
- customer_export.requested
- deletion.requested
- external_export.started
- external_export.failed
- access.denied
- manual_review.recorded

## 7. Legal and Commercial Truthfulness

| Requirement | Acceptance |
|---|---|
| Every customer-facing claim maps to implemented, planned, unsupported, or exception status | commercial-truthfulness-report |
| Planned capability must not appear as available | negative fixture |
| Contract exception must include source contract/ref and owner | exception fixture |
| Procurement response must list unsupported claims and limitations | UAT |

## 8. Product-Ready Gate

Product-ready is blocked when:

- legal hold can be bypassed
- restricted artifact is exported by default
- audit event lacks actor/sourceRefs/hash
- deletion mutates canonical bundle without tombstone/audit
- commercial unsupported claim is hidden
- migration loses retention/legal hold state

## 9. Enterprise Control Evaluation

`enterprise-control-report` は retention / legal hold evaluation を保持する。
canonical bundle には `retention_policy_id` が必須であり、release / regulated
profile で欠けた場合は hard DQ とする。default profile では hold として扱う。

Retention expiry は evidence の実削除ではなく、metadata-only の
`metadata_purge_eligible` projection として出す。HATE のテストと dry-run は
canonical evidence を削除せず、`canonical_evidence_deleted=false` を維持する。

Legal hold が active の resource では purge、delete、raw export、export mutation、
hold release を blocked operation とする。migration / replay / export 後に
legal hold metadata が失われた場合は `legal_hold_lost` finding とし、release /
regulated profile では hard DQ とする。

Migration / replay / export / retention transition は legal hold を preserved field として
扱う。active hold 中の retention transition は `retain` のみ許可し、purge/delete や
raw export へ進む場合は hard DQ として report に残す。
