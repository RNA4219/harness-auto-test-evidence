---
intent_id: INT-HATE-PRODUCT-E2E-UAT-CONTRACT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Product E2E UAT Contract

This contract closes HATE-GAP-020 for end-to-end product acceptance.

## 1. Required Journeys

| Journey | Positive fixture | Negative fixture | Owner |
|---|---|---|---|
| Developer PR loop | `fixtures/e2e/developer-pr-loop/fixture.json` | `fixtures/e2e/developer-pr-loop/parser-failure/fixture.json` | Developer |
| QA risk review | `fixtures/e2e/qa-risk-review/fixture.json` | `fixtures/e2e/qa-risk-review/no-oracle/fixture.json` | QA Lead |
| Release review | `fixtures/e2e/release-review/fixture.json` | `fixtures/e2e/release-review/qeg-invalid/fixture.json` | Release Manager |
| Admin governance | `fixtures/e2e/admin-governance/fixture.json` | `fixtures/e2e/admin-governance/rbac-denied/fixture.json` | Platform Admin |
| Security quarantine | `fixtures/e2e/security-quarantine/fixture.json` | `fixtures/e2e/security-quarantine/block/fixture.json` | Security Engineer |
| Support triage | `fixtures/e2e/support-triage/fixture.json` | `fixtures/e2e/support-triage/raw-artifact-denied/fixture.json` | Support Engineer |

## 2. UAT Evidence

Each E2E run emits:

- product-e2e-uat-report.json
- journey-summary.md
- evidence-map.json
- open-risk-register.json
- screenshots or rendered report where UI is involved

## 3. No-Go

- E2E journey has only happy path
- UI/API journey has no RBAC negative case
- release journey claims QEG approval
- support journey exposes customer source, secret, PII, or unsafe artifact

## 4. Acceptance

Product E2E is accepted when all six journeys pass positive and negative cases
and produce scope-safe UAT evidence.
