---
intent_id: INT-HATE-UI-WORKFLOW-REQUIREMENTS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# UI Workflow Requirements

## 1. Purpose

This document defines dashboard and admin workflow requirements. The UI is a read-model consumer.
It must not compute, override, or hide HATE/QEG/Shipyard/RanD/manual-bb verdicts.

## 2. Global UI Requirements

- All decision reasons link to sourceRefs, unsupported claim, or explicit missing evidence.
- All views support loading, empty, stale, error, unauthorized, and high-volume states.
- All restricted artifacts are represented by safe placeholders unless caller is authorized.
- Severity is never color-only.
- Product-ready cannot be displayed while required reports are missing.
- Every view has UAT cases and view-model fixtures.

## 3. Required Views

| View | Primary persona | User question | Required AC |
|---|---|---|---|
| Run Overview | Developer, Release Manager | Why is this run eligible/conditional/hold/hard_dq? | AC-REQ-013 |
| Risk Coverage | QA Lead | Which risks lack meaningful evidence or oracle? | AC-REQ-002, AC-REQ-013 |
| Evidence Graph | QA Lead, Auditor | Can I trace requirement to artifact safely? | AC-REQ-013 |
| Adapter Health | Platform Admin | Which adapters are weak, failing, disabled, or unsupported? | AC-REQ-015 |
| Artifact Safety | Security Engineer | What was quarantined and why? | AC-REQ-004 |
| Doctor | Developer, Support | What should be fixed first? | AC-REQ-011 |
| Risk Debt | QA Lead, Release Manager | What gaps are aging or blocked? | AC-REQ-008 |
| Release Pack | Release Manager | Can we claim release-ready? | AC-REQ-010 |
| Admin Console | Platform Admin | Who can access what and which policies apply? | AC-REQ-008 |
| Support Triage | Support Engineer | Can I diagnose this safely? | AC-REQ-011 |
| Executive Portfolio | Executive | Are risk, debt, quality, and adoption trending correctly? | AC-REQ-012 |

## 4. View Requirements

### 4.1 Run Overview

Must show:

- run provenance
- profile
- precheck decision
- DQ and soft gap counts
- test integrity signals
- AETE summary
- parser failures
- artifact safety status
- previous run diff
- QEG export status

No-Go:

- showing green status without open hard DQ/manual review state
- hiding parser failures under collapsed advanced section by default

### 4.2 Risk Coverage

Must support filters:

- severity
- owner
- changed path
- required layer
- execution status
- oracle status
- manual request status
- risk debt status

Default sort puts high/critical unresolved risk first.

### 4.3 Evidence Graph

Must support:

- node search
- edge filtering
- sourceRef drawer
- unsupported claim view
- quarantine placeholder
- large graph aggregation
- path normalization display

No-Go:

- direct raw artifact link from graph without safety/RBAC check
- coverage-only edge shown as execution

### 4.4 Adapter Health

Must show:

- adapter id/version
- input formats
- conformance status
- dialect coverage
- parser failures
- known limits
- enablement policy
- last successful fixture run

Failed adapter cannot be marked healthy.

### 4.5 Artifact Safety

Must show:

- artifact id/type/hash
- classification
- redaction status
- quarantine reason
- export eligibility
- summary eligibility
- remediation

Unsafe artifact exposure is a P0 UI defect.

### 4.6 Release Pack

Must show:

- required report checklist
- missing report list
- QEG validate/import/gate/record refs
- unresolved manual reviews
- unsupported claims
- open hard DQ
- migration compatibility
- commercial truthfulness status

Product-ready badge is forbidden unless all required reports pass.

## 5. UI State Matrix

| State | Required behavior |
|---|---|
| loading | skeleton or progress without fake status |
| empty | explains missing input and next action |
| stale | shows source bundle hash and stale reason |
| error | stable error code and remediation |
| unauthorized | no restricted path or tenant leakage |
| high-volume | pagination, aggregation, virtualized graph/list |
| partial | visible parser failures or unsupported claims |
| quarantined | safe placeholder, no raw link |

## 6. UI UAT

Dashboard-ready requires:

- view-model fixture for every required view
- UAT script for each view state
- accessibility check for severity/status
- RBAC negative test
- high-volume rendering test
- no product-ready badge when reports are missing
- `dashboard-uat-report.json`

