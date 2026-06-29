---
intent_id: INT-HATE-API-REQUIREMENTS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# API Requirements

## 1. Purpose

This document defines product API requirements for HATE hosted/read-model surfaces.
The API is a consumer of canonical bundles and local/hosted store indexes. It must not
change HATE precheck decisions, QEG verdicts, or canonical bundle content.

## 2. API Principles

- Every response includes request id, tenant scope, schema version, source bundle hash, staleness, pagination, data, and errors.
- Every mutating operation has dry-run support or idempotency where applicable.
- Every endpoint has explicit RBAC behavior and must not leak restricted artifact paths.
- Every external export is non-gating and records canonical hash before/after.
- Every resource must have contract tests for success, partial, stale, unauthorized, invalid input, not found, and high-volume cases.

## 3. Resource Inventory

| Resource | Methods | Purpose | Required AC |
|---|---|---|---|
| `/v1/runs` | GET | list runs with filtering/sorting/pagination | AC-REQ-014 |
| `/v1/runs/{run_id}/attempts/{attempt}` | GET | run detail, provenance, profile, decision | AC-REQ-014 |
| `/v1/evidence` | GET | evidence list by run/risk/test/kind/trust | AC-REQ-014 |
| `/v1/risks` | GET | changed risk, required layer, oracle, debt | AC-REQ-014 |
| `/v1/artifacts` | GET | safe artifact metadata, quarantine, redaction | AC-REQ-004, AC-REQ-014 |
| `/v1/doctor/findings` | GET | error code, severity, remediation | AC-REQ-011, AC-REQ-014 |
| `/v1/risk-debt` | GET/PATCH | risk debt lifecycle | AC-REQ-008, AC-REQ-014 |
| `/v1/profiles` | GET/POST | profile policy, diff, validation | AC-REQ-008, AC-REQ-014 |
| `/v1/bundles/import` | POST | validate and import canonical bundle | AC-REQ-006, AC-REQ-014 |
| `/v1/exports/{provider}` | POST/GET | external export workflow | AC-REQ-009, AC-REQ-014 |
| `/v1/admin/adapters` | GET/POST/PATCH | adapter registry and enablement | AC-REQ-015 |
| `/v1/admin/retention-policies` | GET/POST/PATCH | retention/legal hold policy | AC-REQ-008 |
| `/v1/release-candidates/{id}` | GET/POST | release candidate pack and validation | AC-REQ-010 |

## 4. Common Request Requirements

| Requirement | Details |
|---|---|
| Authentication | service token, user token, local signed import token where applicable |
| Authorization | role + tenant + resource scope checked before loading restricted payload |
| Tenant scope | organization_id and workspace_id resolved for every hosted request |
| Idempotency | import/export/mutating admin operations accept idempotency key |
| Dry run | profile, retention, adapter enablement, connector export support dry-run |
| Version | client may request schema/profile/API version; incompatible version returns structured error |

## 5. Common Response Envelope

```yaml
request_id: string
tenant:
  organization_id: string
  workspace_id: string
resource: string
schema_version: HATE/v1
api_version: string
generated_at: ISO-8601
source:
  bundle_hash: string | null
  run_id: string | null
  attempt: number | null
staleness:
  status: fresh | stale | rebuilding | unknown
  reason: string | null
pagination:
  limit: number
  cursor: string | null
  next_cursor: string | null
data: object | array | null
errors:
  - code: string
    message: string
    remediation: string
    source_refs: array
```

## 6. Endpoint Requirements

### 6.1 Runs

| Endpoint | Required filters | Required fields |
|---|---|---|
| `GET /v1/runs` | repo, branch, commit, profile, decision, date range, actor | run_id, attempt, commit, profile, decision, dq_count, gap_count |
| `GET /v1/runs/{run_id}/attempts/{attempt}` | include=evidence,doctor,release | provenance, inputs, outputs, decision reasons, sourceRefs |

No-Go:

- returning runs across tenant boundary
- hiding stale status when read model is rebuilding
- returning decision without source bundle hash

### 6.2 Evidence and Risks

| Endpoint | Required filters | Required fields |
|---|---|---|
| `GET /v1/evidence` | run, risk, test, kind, status, trust score, source tool | evidence id, kind, status, sourceRefs, artifact refs |
| `GET /v1/risks` | severity, owner, layer, oracle status, manual required, debt status | risk id, changed entity, required evidence, current evidence, gap |

No-Go:

- coverage-only evidence presented as execution evidence
- high/critical risk sorted below low-risk items by default
- missing oracle hidden inside generic warning

### 6.3 Artifacts

`GET /v1/artifacts` returns metadata only unless caller is authorized and artifact is safe.

Required states:

- safe
- quarantined
- redaction_pending
- redaction_failed
- restricted
- missing
- external_blocked

No-Go:

- unauthorized caller learns restricted path
- failed redaction returns signed URL
- external URL is fetched by API without policy

### 6.4 Risk Debt

`PATCH /v1/risk-debt/{debt_id}` supports lifecycle transitions only.

Allowed transitions:

| From | To |
|---|---|
| open | acknowledged, mitigated |
| acknowledged | mitigated, stale |
| mitigated | closed, reopened |
| stale | acknowledged, closed |
| accepted | closed only with external sourceRefs |

Every transition emits audit event and before/after state.

### 6.5 Bundle Import

`POST /v1/bundles/import` validates:

- schema
- hash
- sourceRefs
- artifact manifest safety
- profile compatibility
- tenant scope
- duplicate bundle hash

No-Go:

- import mutates canonical bundle
- import accepts invalid schema to "show partial UI"
- import hides parser failures

## 7. Error Taxonomy

| Prefix | Meaning |
|---|---|
| HATE-API-AUTH-* | authentication/authorization |
| HATE-API-REQ-* | invalid request/filter/pagination |
| HATE-API-SCHEMA-* | schema/version incompatibility |
| HATE-API-STORE-* | store/index/staleness/corruption |
| HATE-API-EXPORT-* | non-gating exporter failure |
| HATE-API-PRIV-* | privacy/quarantine/redaction denial |

## 8. API Acceptance

API-ready requires:

- OpenAPI or equivalent machine-readable contract
- contract tests for every endpoint
- RBAC negative tests
- pagination and large-list tests
- idempotency tests for import/export/admin mutations
- stale/partial response tests
- no restricted path leakage test
- `api-contract-report.json`

