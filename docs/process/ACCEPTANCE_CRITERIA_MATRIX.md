---
intent_id: INT-HATE-ACCEPTANCE-CRITERIA-MATRIX-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Acceptance Criteria Matrix

## 1. Purpose

This matrix expands `AC-REQ-*` from `PRODUCT_REQUIREMENTS_DEFINITION.md` into
testable criteria. An acceptance item is incomplete until it names positive fixtures,
negative fixtures, product status impact, evidence report, and UAT owner.

## 2. Acceptance Matrix

| AC ID | Scope | Positive fixtures | Negative fixtures | Required evidence | Product impact | UAT owner |
|---|---|---|---|---|---|---|
| AC-REQ-001 | Developer PR loop | minimal-pr-pass, recommendation-fixed | missing-test, unsafe-artifact, parser-failure | precheck, recommendation, summary | eligible/conditional/hold | Developer |
| AC-REQ-002 | QA high-risk oracle | high-risk-with-oracle, manual-request-created | high-risk-execution-no-oracle, coverage-only-risk | risk debt, manual request, evidence graph | hold if unresolved | QA Lead |
| AC-REQ-003 | Test integrity | boundary-mock-with-oracle | focused-test-only, new-xfail-high-risk, no-assertion-smoke-test, production-branches-on-fixture | test-integrity-report | hold/hard_dq | QA Lead |
| AC-REQ-004 | Artifact safety | safe-trace, redacted-log | fake-token-log, pii-screenshot, traversal-path, unsafe-archive, metadata-url | security-quarantine-report | quarantine/hold | Security |
| AC-REQ-005 | QEG boundary | qeg-validate-pass, shipyard-advisory | verdict-modified-by-hate, qeg-schema-fail | qeg integration result, shipyard evidence | block export if invalid | Release Manager |
| AC-REQ-006 | Replay/audit | frozen-replay-stable, compare-explains-change | mutated-bundle, corrupt-index, missing-source-ref | store-replay-report | hold audit readiness | Auditor |
| AC-REQ-007 | API/dashboard | all-resources-contract-pass, dashboard-view-pass | unauthorized-raw-artifact, stale-hidden, unpaginated-large-list | api-contract-report, dashboard-uat-report | block product-ready | Platform Admin |
| AC-REQ-008 | RBAC/audit/retention | legal-hold-blocks-delete, audit-hash-chain | auditor-write, service-account-human-review, retention-deletes-legal-hold | enterprise-control-report | block enterprise-ready | Platform Admin |
| AC-REQ-009 | Connector non-gating | siem-dry-run-pass, scim-unavailable | connector-mutates-canonical, token-in-diagnostic | connector result, enterprise-control-report | non-gating failure | Platform Admin |
| AC-REQ-010 | Release pack | all-required-reports-present | missing-report, unsupported-claim, unresolved-manual-review, qeg-fail | release-candidate-pack | block release-ready | Release Manager |
| AC-REQ-011 | Support/ops | safe-diagnostic, error-code-remediation | diagnostic-has-secret, no-error-code, rollback-missing | support-ops-report | block supportable | Support |
| AC-REQ-012 | Commercial truthfulness | supported-claim-with-evidence | planned-claim-marked-available, contract-exception-hidden | commercial-truthfulness-report | block product-ready | Product/Legal |
| AC-REQ-013 | UI workflow | overview-risk-graph-admin-pass | empty-state-missing, error-state-hidden, color-only-severity, restricted-link-visible | dashboard-uat-report | block dashboard-ready | QA Lead |
| AC-REQ-014 | API contract | request-response-error-pass | undocumented-field, authz-leak, missing-pagination, non-idempotent-import | api-contract-report | block API-ready | Platform Admin |
| AC-REQ-015 | Adapter corpus | dialect-matrix-pass | malformed-required-input, unsupported-hidden, capability-misreported | adapter-conformance-report | block adapter-ready | Developer Platform |
| AC-REQ-016 | Scale/performance | large-run-budget-pass | memory-unbounded, no-pagination-large-graph, stale-cache-undetected | scale-performance-report | block product-ready | SRE |
| AC-REQ-017 | Observability | metrics-logs-alerts-pass | unredacted-log, no-request-id, alert-missing | support-ops-report | block operationalized | SRE |
| AC-REQ-018 | Lifecycle compatibility | old-bundle-replay, migration-rollback | breaking-change-no-guide, deprecated-field-no-warning, legal-hold-lost | migration-compatibility-report | block release-ready | Release Manager |

## 3. Status Impact Rules

| Condition | Minimum impact |
|---|---|
| focused test marker committed | hard_dq in release/product profile |
| high/critical risk without oracle | hold |
| behavior under test replaced by mock | hold or hard_dq |
| unsafe artifact required by evidence | quarantine plus hold if required |
| missing required product report | product-ready blocked |
| connector failure | non-gating unless canonical bundle changes |
| QEG verdict modified by HATE | hard_dq / boundary violation |
| commercial unsupported claim hidden | product-ready blocked |

## 4. Acceptance Completion Rule

Each AC must have:

- at least one positive fixture
- at least one negative fixture
- an expected status impact
- a named evidence report
- a UAT owner
- a source requirement family

If any element is missing, the AC is `specified` but not `accepted`.

