---
intent_id: INT-HATE-USER-STORY-MAP-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# User Story Map

## 1. Purpose

This document maps HATE product requirements into user activities, stories, release slices,
acceptance references, and product-grade blockers. It is the story-level companion to
`PRODUCT_REQUIREMENTS_DEFINITION.md`.

No story is complete when it only produces a report. Each story must connect to a persona,
journey, acceptance ID, fixture family, and evidence report.

## 2. Personas

| Persona | Primary outcome | Release-critical questions |
|---|---|---|
| Developer | Fix evidence gaps in a PR quickly | What failed? What test/evidence should I add? Did I accidentally weaken tests? |
| QA Lead | Verify risk coverage and oracle adequacy | Which high risks lack meaningful evidence? What needs manual review? |
| Release Manager | Decide evidence eligibility before QEG gate | Is this bundle safe to send to QEG? What still blocks release readiness? |
| Security Engineer | Prevent unsafe artifact exposure | Did traces/logs/screenshots leak secret, PII, local paths, or unsafe archives? |
| Auditor | Replay and explain historical decisions | Can the same evidence and decision be regenerated later? |
| Platform Admin | Operate policies, adapters, tenants, connectors | Which repos/profiles/adapters are healthy and compliant? |
| Support Engineer | Triage customer issues safely | Can I diagnose without raw customer code or unsafe artifacts? |
| Executive | Understand quality and release risk trends | Are risk debt, evidence coverage, and adoption improving? |

## 3. Story Backbone

| Activity | Outcome | Primary personas |
|---|---|---|
| A1 Onboard repo | HATE can run locally and in CI | Developer, Platform Admin |
| A2 Ingest evidence | CI/test/coverage/static/artifact inputs become canonical records | Developer |
| A3 Detect quality gaps | DQ, soft gaps, test integrity, unsafe artifact issues are visible | Developer, QA Lead |
| A4 Trace risk to evidence | Requirement/risk/test/evidence/artifact graph is navigable | QA Lead, Release Manager |
| A5 Review and fix | Recommendations and manual-bb requests drive action | Developer, QA Lead |
| A6 Export to governance | QEG/workflow/Shipyard/RanD receive advisory evidence without verdict override | Release Manager |
| A7 Operate product | Store, replay, API, dashboard, RBAC, audit, retention, connectors work | Platform Admin |
| A8 Release and audit | Release pack, evidence room, support bundle, migration proof are complete | Release Manager, Auditor |

## 4. Release Slices

| Slice | Goal | Must include | Must not claim |
|---|---|---|---|
| S0 Prototype | Local golden path proves basic evidence normalization | P0a/P0b CLI, minimal fixture, DQ basics | product-ready |
| S1 Internal Alpha | Multiple internal repos can produce QEG-compatible bundles | adapter expansion, risk graph, replay basics | enterprise-ready |
| S2 Private Beta | Customer-like repos can run with safety and doctor guidance | test integrity, artifact safety, local store, recommendations | regulated-ready |
| S3 Team GA | Teams can rely on CI loop and support docs | GitHub Action, adapter SDK, QEG export, support diagnostic | full enterprise compliance |
| S4 Enterprise Ready | Admins can operate API/dashboard/RBAC/audit/retention/connectors | hosted read model, dashboard, admin, audit, retention | regulated assurance |
| S5 Regulated Ready | Auditors can review evidence room and legal/compliance packs | legal hold, assurance pack, audit walkthrough, migration proof | QEG verdict ownership |

## 5. Story Map

| Story ID | Activity | Persona | Story | Priority | Acceptance | Evidence |
|---|---|---|---|---:|---|---|
| US-001 | A1 | Developer | As a developer, I can run HATE on a minimal repo in under five minutes so that I can see evidence gaps before asking others. | P0 | AC-REQ-001 | quickstart run, summary, precheck |
| US-002 | A1 | Platform Admin | As an admin, I can define repo profile defaults so that teams start from consistent policy. | P2 | AC-REQ-008 | profile-report, audit event |
| US-003 | A2 | Developer | As a developer, CI test results from JUnit/pytest/Jest/Vitest/Playwright are normalized without losing retry/flaky/snapshot metadata. | P0 | AC-REQ-015 | adapter-conformance-report |
| US-004 | A2 | Developer | As a developer, coverage from LCOV/Cobertura/JaCoCo/coverage.py is normalized but never treated as execution evidence alone. | P0 | AC-REQ-015 | coverage fixture, DQ/soft gap |
| US-005 | A2 | Security Engineer | As security, Playwright traces, screenshots, videos, logs, archives, and external URLs are scanned before public exposure. | P0 | AC-REQ-004 | security-quarantine-report |
| US-006 | A3 | QA Lead | As QA, high-risk changes without an oracle are held rather than hidden behind coverage. | P0 | AC-REQ-002 | test-integrity-report, risk debt |
| US-007 | A3 | Developer | As a developer, new skip/xfail/only/todo and weak assertions are called out with remediation. | P0 | AC-REQ-003 | test-integrity-report |
| US-008 | A3 | Release Manager | As release manager, production code that branches on test/fixture names blocks product-ready. | P1 | AC-REQ-003 | doctor finding |
| US-009 | A4 | QA Lead | As QA, I can trace requirement -> risk -> test -> execution -> artifact from one graph. | P0b | AC-REQ-002 | evidence graph |
| US-010 | A4 | Auditor | As auditor, every decision reason links to sourceRefs and immutable bundle hash. | P1 | AC-REQ-006 | store-replay-report |
| US-011 | A5 | Developer | As a developer, recommendations identify missing test layer, owner, sourceRefs, and likely fixture/test target. | P1 | AC-REQ-001 | recommendation-report |
| US-012 | A5 | QA Lead | As QA, manual-bb supplement requests are generated for evidence gaps but do not waive the gap. | P1 | AC-REQ-002 | manual request |
| US-013 | A6 | Release Manager | As release manager, HATE exports QEG optional evidence without modifying QEG verdict. | P0b | AC-REQ-005 | qeg integration result |
| US-014 | A6 | Release Manager | As release manager, Shipyard/RanD/workflow artifacts preserve upstream verdicts and advisory-only status. | P1b | AC-REQ-005 | shipyard-run-evidence |
| US-015 | A7 | Platform Admin | As admin, adapter enablement is controlled by org/workspace/repo/profile policy. | P3 | AC-REQ-008 | enterprise-control-report |
| US-016 | A7 | Platform Admin | As admin, risk debt status transitions produce audit events and deny illegal transitions. | P2 | AC-REQ-008 | audit log |
| US-017 | A7 | Developer | As a user of dashboard, I can filter large risk/evidence sets without loading every node at once. | P2 | AC-REQ-013 | dashboard-uat-report |
| US-018 | A7 | API Client | As an API client, I can page/filter/sort resources and receive explicit stale/partial/error metadata. | P2 | AC-REQ-014 | api-contract-report |
| US-019 | A8 | Release Manager | As release manager, release pack lists required reports, missing reports, unsupported claims, QEG refs, and open manual reviews. | P2 | AC-REQ-010 | release-candidate-pack |
| US-020 | A8 | Support Engineer | As support, I can triage with safe diagnostic bundle, version matrix, store health, adapter health, and remediation catalog. | P2 | AC-REQ-011 | support-ops-report |
| US-021 | A8 | Auditor | As auditor, old bundles remain replayable after schema/store/API migration. | P2 | AC-REQ-018 | migration-compatibility-report |
| US-022 | A8 | Executive | As executive, I can see portfolio health, risk debt aging, evidence coverage, and unsupported commercial claims. | P3 | AC-REQ-012 | commercial-truthfulness-report |

## 6. Story No-Go Rules

- A story with no negative fixture is not ready for implementation.
- A story with no acceptance ID is only a note.
- A story that changes release readiness must state which evidence report proves it.
- A story that exposes artifacts must state RBAC and safety behavior.
- A story that touches upstream/downstream governance must state that HATE does not override external verdicts.

