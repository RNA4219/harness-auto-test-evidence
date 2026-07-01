---
intent_id: INT-HATE-PLATFORM-DASHBOARD-WIREFRAME-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Platform Dashboard Wireframe Specification

本書は dashboard/read model の view composition と state fixtures を定義する。

## 1. View Inventory

| View | Primary Job | Required Data |
|---|---|---|
| Portfolio Overview | repo health and trend | repo scores, open holds, expired debt |
| Repo Detail | suite status and regressions | run history, score trend, suite failures |
| Run Detail | explain one run | command summary, score breakdown, findings |
| Findings Queue | triage open work | operating records, owner, due date |
| Risk Debt Board | manage accepted debt | debt lifecycle, expiry, evidence refs |
| Manual Review Queue | decide blocked work | review requests, required decision |
| Policy Drift | explain threshold/profile changes | effective policy and hash diff |
| Scheduler Status | observe queue and leases | jobs, retries, leases, poison messages |
| Artifact Quarantine | review unsafe artifacts | metadata, redaction reason, approval state |

## 2. Common Layout

Every view has:

- header with scope, profile, stale marker
- summary metrics
- filter bar
- primary table or timeline
- right-side detail panel for selected record
- sourceRefs panel
- unsafe data redaction notices

No view recomputes readiness. Views consume canonical read model resources.

## 3. State Matrix

| State | Required UI Behavior |
|---|---|
| loading | stable skeleton, no fake counts |
| empty | no-data reason and next action |
| partial | missing resource list and stale marker |
| stale | age, source, rebuild action if allowed |
| permission denied | denial reason without restricted body |
| unsafe hidden | redaction reason and approval path |
| degraded | performance budget exceeded, reduced data mode |

## 4. View Model Contracts

Each view model requires:

- `view_id`
- `scope`
- `generated_at`
- `stale`
- `permissions`
- `summary`
- `items`
- `selected_item`
- `sourceRefs`
- `redactions`
- `errors`

## 5. Visual Acceptance

Dashboard implementation must prove:

- all table columns have stable labels and empty values
- stale/partial/permission denied/unsafe hidden states are visually distinct
- score breakdown is visible without requiring raw JSON inspection
- sourceRefs are reachable from every finding and score panel
- unsafe artifact body is never rendered, including expanded detail panels
- keyboard focus order reaches filters, tables, detail panels, and sourceRefs
- mobile/narrow layout preserves the same critical information

Visual snapshot or browser UAT must cover portfolio overview, repo detail,
findings queue, manual review queue, policy drift, and artifact quarantine.

## 6. Required Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/platform/dashboard/portfolio-overview/fixture.json` | health/trend/open holds |
| `fixtures/platform/dashboard/repo-regression-detail/fixture.json` | regression visible |
| `fixtures/platform/dashboard/findings-owner-queue/fixture.json` | owner/due sorting |
| `fixtures/platform/dashboard/manual-review-blocking/fixture.json` | required decision visible |
| `fixtures/platform/dashboard/policy-drift/fixture.json` | hash diff visible |
| `fixtures/platform/dashboard/artifact-unsafe-hidden/fixture.json` | unsafe body hidden |
| `fixtures/platform/dashboard/degraded-large-query/fixture.json` | degraded state visible |
| `fixtures/platform/dashboard/mobile-critical-summary/fixture.json` | narrow layout preserves critical information |
