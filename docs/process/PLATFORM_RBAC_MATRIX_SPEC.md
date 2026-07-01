---
intent_id: INT-HATE-PLATFORM-RBAC-MATRIX-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Platform RBAC Matrix Specification

本書は platform read model、JSON API、dashboard、raw artifact access の RBAC 正本である。

## 1. Roles

| Role | Summary |
|---|---|
| `admin` | organization and project administration |
| `maintainer` | project policy, review, debt operations |
| `developer` | own repo/run/finding work |
| `auditor` | read-only audit and replay |
| `viewer` | safe summary read |
| `service` | CI/scheduler/write automation |

## 2. Resource Actions

| Resource | Actions |
|---|---|
| `run` | read, create, cancel, retry |
| `finding` | read, assign, resolve, supersede |
| `risk_debt` | read, accept, revoke, resolve |
| `manual_review` | read, request, decide |
| `policy` | read, propose, approve, change |
| `artifact` | metadata_read, safe_read, raw_access, quarantine_release, delete |
| `audit_event` | read |
| `scheduler` | read, enqueue, lease, cancel |

## 3. Permission Matrix

| Role | Default Allow | Explicit Deny |
|---|---|---|
| admin | all non-raw actions, quarantine release | bypassing legal hold |
| maintainer | repo/project run, finding, debt, review, policy propose | org admin, raw unsafe artifact without approval |
| developer | own run read/create, own finding read/update | policy change, debt accept, manual review decide |
| auditor | read run/finding/debt/review/audit metadata | mutation, raw artifact without policy |
| viewer | safe summaries and safe artifact metadata | raw artifact, audit detail, mutation |
| service | configured CI/scheduler actions | human review decisions unless delegated |

## 4. Tenant and Scope Rules

- Authorization is evaluated before restricted payload load.
- Tenant scope includes organization, workspace, project, repository.
- Cross-tenant resource ids return `403` when resource existence is not visible.
- Same-tenant missing resources return `404`.
- RBAC denial records must avoid raw artifact path and secret leakage.

## 5. Raw Artifact Access

Raw access requires:

- role permission
- artifact safety state
- approval event
- purpose
- expiry
- audit event

Unsafe artifact body is never returned to viewer/developer roles.

## 6. Required Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/platform/rbac/admin-policy-change/fixture.json` | admin allowed |
| `fixtures/platform/rbac/developer-debt-accept-denied/fixture.json` | developer denied |
| `fixtures/platform/rbac/auditor-read-only/fixture.json` | auditor read, mutation denied |
| `fixtures/platform/rbac/cross-tenant-hidden/fixture.json` | restricted existence not leaked |
| `fixtures/platform/rbac/raw-artifact-approval/fixture.json` | raw access requires approval |
| `fixtures/platform/rbac/raw-artifact-missing-approval/fixture.json` | raw access denied without approval event |
