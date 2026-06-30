---
intent_id: INT-HATE-TENANT-ISOLATION-CONTRACT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Tenant Isolation Contract

This contract closes HATE-GAP-002. Tenant isolation applies to hosted and
enterprise modes. Local-first single-user mode may use a synthetic tenant, but
must preserve tenant_id in records that can be imported later.

## 1. Isolation Surfaces

| Surface | Isolation rule | Negative fixture |
|---|---|---|
| Store records | tenant_id must match caller tenant | `fixtures/enterprise/tenant/cross-org-denied/fixture.json` |
| Artifacts | raw access denied across tenant regardless of URL knowledge | `fixtures/enterprise/tenant/artifact-cross-access-denied/fixture.json` |
| Cache | cache key includes tenant_id and data class | `fixtures/enterprise/tenant/cache-bleed-denied/fixture.json` |
| Audit log | auditor reads only scoped tenant unless global auditor role exists | `fixtures/enterprise/tenant/audit-cross-read-denied/fixture.json` |
| Export | exporter cannot mix tenant bundles | `fixtures/enterprise/tenant/export-mixed-tenant-denied/fixture.json` |
| Support bundle | support bundle omits other tenant metadata | `fixtures/enterprise/tenant/support-bundle-isolated/fixture.json` |
| Telemetry | aggregate metrics cannot include tenant-identifying payload | `fixtures/enterprise/tenant/telemetry-payload-denied/fixture.json` |

## 2. Required Checks

- Every hosted API request resolves tenant before resource lookup.
- Resource IDs are not sufficient authorization.
- Artifact safety runs after tenant authorization, not instead of it.
- Audit events include tenant_id, actor_id, role, action, resource_ref, decision.

## 3. Acceptance

Tenant isolation is accepted when every isolation surface has allow and deny
fixtures, RBAC tests, and audit events for denial.
