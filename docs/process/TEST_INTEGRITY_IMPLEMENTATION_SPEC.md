---
intent_id: INT-HATE-TEST-INTEGRITY-IMPLEMENTATION-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-08
---

# Test Integrity Implementation Spec

This document closes the requirements-to-spec gap for `FR-TI-*`, `AC-REQ-003`,
and `HATE-PG-013`. `PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` defines the product
requirement; this document fixes the implementation-facing detector contract.

## 1. Scope

The detector suite covers:

- `test_skip_detected`
- `mock_abuse_detected`
- `assertion_quality`
- `implementation_test_coupling`
- `risk_without_oracle`
- `coverage_without_evidence`
- `manual_review_required`

## 2. Required Inputs

| Input | Required fields |
|---|---|
| `changed_files` | path, language, diff hunks, file role |
| `test_sources` | path, framework, parsed markers, assertion summary |
| `production_sources` | path, symbols, env/test/fixture references |
| `test_results` | canonical test id, status, retry, skip/focus/todo metadata |
| `coverage_slices` | file, line/branch, context, test refs |
| `risk_matrix` | risk id, severity, required evidence classes, owner |
| `manual_review_records` | reviewer, decision, expiry, sourceRefs |

## 3. Detector Output

Every detector emits a canonical finding:

```yaml
integrity_finding:
  finding_id: string
  detector_id: string
  signal_id: string
  severity: low | medium | high | critical
  status: present | absent | inconclusive
  readiness_effect: none | soft_gap | hold | blocked
  affected_refs: array
  reason: string
  recommended_action: string
  sourceRefs: array
```

## 4. Detection Rules

| Signal | Required behavior | No-Go |
|---|---|---|
| `test_skip_detected` | detect new or increased skip/xfail/only/todo/focused tests from test source and result records | do not rely only on pytest result status |
| `mock_abuse_detected` | distinguish external-boundary mocks from behavior-under-test mocks | do not treat empty stubs as oracle |
| `assertion_quality` | classify no assertion, smoke-only, snapshot-only, truthiness-only, no-exception-only | do not count execution alone as oracle |
| `implementation_test_coupling` | detect production references to fixture names, test names, golden paths, test env markers | do not allow production behavior to branch for tests |
| `risk_without_oracle` | hold high/critical risks lacking expected value, property, contract, mutation, or manual oracle | do not use coverage as oracle |
| `coverage_without_evidence` | mark coverage-only evidence as soft gap or hard DQ by profile | do not create `executed_by` edge from coverage alone |
| `manual_review_required` | route unresolved suspicious cases to human review with owner/expiry | do not synthesize human approval |

## 5. Fixture Matrix

Required fixture directories:

- `fixtures/test-integrity/skip-focus/focused-test-only/fixture.json`
- `fixtures/test-integrity/mock-assertion/behavior-under-test-mocked/fixture.json`
- `fixtures/test-integrity/mock-assertion/no-assertion-smoke-test/fixture.json`
- `fixtures/test-integrity/coupling/test-name-branch/fixture.json`
- `fixtures/test-integrity/coupling/risk-without-oracle/fixture.json`
- `fixtures/test-integrity/coupling/coverage-without-evidence/fixture.json`
- `fixtures/test-integrity/coupling/manual-review-expired/fixture.json`

## 6. Acceptance

Implementation is acceptable only when:

- all seven signals have positive and negative tests
- profile-specific `readiness_effect` is tested
- sourceRefs identify the specific test/source/risk/coverage record
- no detector uses fixture name as the only behavioral oracle
- `test-integrity-report.schema.json` validates canonical findings
- unresolved `manual_review_required` blocks product-ready claims
