---
intent_id: INT-HATE-EPIC-TASK-PACKETS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Epic Task Packets

## 1. Purpose

This document expands `IMPLEMENTATION_EPIC_BREAKDOWN.md` into worker-facing task packets.
Each packet is suitable for Shipyard/GLM implementation handoff and must not be accepted
until code, schema, fixtures, negative tests, CI, UAT, and evidence report exist.

Two-pass completion status and third-pass dependency review are recorded in
`EPIC_TWO_PASS_COMPLETION_AUDIT.md`.

## 2. Packet Contract

Each packet has:

- task id
- epic id
- requirement refs
- acceptance refs
- affected paths
- inputs
- outputs
- positive fixtures
- negative fixtures
- test commands
- No-Go conditions
- evidence report

## 3. Task Packets

| Task | Epic | Title | Requirements | Acceptance | Evidence report |
|---|---|---|---|---|---|
| HATE-PG-001A | EPIC-001 | Adapter SDK interfaces and manifest schema | FR-ADP-007 | AC-REQ-015 | adapter-conformance-report.json |
| HATE-PG-001B | EPIC-001 | JUnit dialect parser corpus | FR-ADP-001 | AC-REQ-015 | adapter-conformance-report.json |
| HATE-PG-001C | EPIC-001 | Coverage dialect parser corpus | FR-ADP-002 | AC-REQ-015 | adapter-conformance-report.json |
| HATE-PG-001D | EPIC-001 | SARIF/Pact/Stryker parser corpus | FR-ADP-003..005 | AC-REQ-015 | adapter-conformance-report.json |
| HATE-PG-002A | EPIC-002 | Common envelope validator | FR-ING-006 | AC-REQ-014 | schema-validation-report.json |
| HATE-PG-002B | EPIC-002 | Cross-record sourceRef/hash validator | FR-GRAPH-005 | AC-REQ-006 | schema-validation-report.json |
| HATE-PG-003A | EPIC-003 | Evidence graph node/edge model | FR-GRAPH-001 | AC-REQ-002 | product-readiness-report.json |
| HATE-PG-003B | EPIC-003 | Risk coverage matrix and manual request bridge | FR-GRAPH-002..004 | AC-REQ-002 | product-readiness-report.json |
| HATE-PG-004A | EPIC-004 | Skip/focus/todo detector | FR-TI-001 | AC-REQ-003 | test-integrity-report.json |
| HATE-PG-004B | EPIC-004 | Mock abuse and assertion quality detector | FR-TI-002..003 | AC-REQ-003 | test-integrity-report.json |
| HATE-PG-004C | EPIC-004 | Test coupling and manual review detector | FR-TI-004..007 | AC-REQ-003 | test-integrity-report.json |
| HATE-PG-005A | EPIC-005 | Secret/PII/path/archive/external URL scanners | FR-SEC-001..004 | AC-REQ-004 | security-quarantine-report.json |
| HATE-PG-005B | EPIC-005 | Redaction and summary/export safety filter | FR-SEC-005 | AC-REQ-004 | security-quarantine-report.json |
| HATE-PG-006A | EPIC-006 | Immutable local store and indexes | FR-STO-001..002 | AC-REQ-006 | store-replay-report.json |
| HATE-PG-006B | EPIC-006 | Replay/compare/corruption doctor | FR-STO-003..004 | AC-REQ-006 | store-replay-report.json |
| HATE-PG-007A | EPIC-007 | API envelope and read resources | FR-APIX-001, FR-API-001 | AC-REQ-014 | api-contract-report.json |
| HATE-PG-007B | EPIC-007 | Bundle import, export, authz, versioning | FR-APIX-002..008 | AC-REQ-014 | api-contract-report.json |
| HATE-PG-008A | EPIC-008 | Dashboard view models | FR-UI-001..010 | AC-REQ-013 | dashboard-uat-report.json |
| HATE-PG-008B | EPIC-008 | UI state UAT fixtures | FR-UI-001..010 | AC-REQ-013 | dashboard-uat-report.json |
| HATE-PG-009A | EPIC-009 | RBAC and audit hash chain | FR-ENT-001..002 | AC-REQ-008 | enterprise-control-report.json |
| HATE-PG-009B | EPIC-009 | Retention/legal hold/export/delete | FR-ENT-003 | AC-REQ-008 | enterprise-control-report.json |
| HATE-PG-010A | EPIC-010 | SSO/SCIM dry-run connectors | FR-ENT-004 | AC-REQ-009 | enterprise-control-report.json |
| HATE-PG-010B | EPIC-010 | SIEM/warehouse/ticket dry-run connectors | FR-ENT-004 | AC-REQ-009 | enterprise-control-report.json |
| HATE-PG-011A | EPIC-011 | Large fixture generator | FR-SCALE-001..006 | AC-REQ-016 | scale-performance-report.json |
| HATE-PG-011B | EPIC-011 | Performance budget runner | FR-SCALE-001..006 | AC-REQ-016 | scale-performance-report.json |
| HATE-PG-012A | EPIC-012 | Structured logs, metrics, alerts | FR-OBS-001..003 | AC-REQ-017 | support-ops-report.json |
| HATE-PG-012B | EPIC-012 | Safe diagnostic and error catalog | FR-OBS-004..005, FR-OPS-001..004 | AC-REQ-011 | support-ops-report.json |
| HATE-PG-013A | EPIC-013 | Schema/store/API/profile migration fixtures | FR-LIFE-001..004 | AC-REQ-018 | migration-compatibility-report.json |
| HATE-PG-013B | EPIC-013 | Legal hold preserving migration | FR-LIFE-005 | AC-REQ-018 | migration-compatibility-report.json |
| HATE-PG-014A | EPIC-014 | Release candidate pack validator | FR-OPS, FR-ENT | AC-REQ-010 | release-candidate-pack.json |
| HATE-PG-015A | EPIC-015 | Commercial claim inventory and blocker | FR-OPS-005..006 | AC-REQ-012 | commercial-truthfulness-report.json |

## 4. Per-Packet No-Go

No packet can be accepted when:

- there is no negative fixture
- generated report is missing from CI
- product-ready can be claimed with `status=not_run`
- sourceRefs are absent for blocking findings
- HATE overrides QEG/Shipyard/RanD/manual-bb verdicts

## 5. EPIC-001 Detailed Task Packets

EPIC-001 is the adapter corpus and SDK epic. It is not complete when a single happy-path
parser works. It is complete only when adapter authors can implement against a stable SDK,
the core project can validate adapter manifests, representative dialect fixtures exist, and
CI emits an adapter conformance report with positive and negative evidence.

### HATE-PG-001A Adapter SDK interfaces and manifest schema

| Field | Required content |
|---|---|
| Epic | EPIC-001 Adapter Corpus and SDK |
| Requirement refs | FR-ADP-007, FR-ING-006, FR-GRAPH-005 |
| Acceptance refs | AC-REQ-014, AC-REQ-015 |
| Affected paths | `src/hate/adapters/`, `src/hate/adapter_sdk.py`, `src/hate/adapter_registry.py`, `schemas/HATE/v1/adapter-manifest.schema.json`, `schemas/HATE/v1/adapter-conformance-report.schema.json`, `fixtures/adapters/sdk/`, `tests/test_adapter_sdk.py`, `tests/test_adapter_manifest_schema.py`, `docs/process/ADAPTER_DIALECT_PARSER_SPEC.md` |
| Fixtures | `fixtures/adapters/sdk/valid-manifest/`, `fixtures/adapters/sdk/missing-required/`, `fixtures/adapters/sdk/capability-mismatch/`, `fixtures/adapters/sdk/unknown-output-record/`, `fixtures/adapters/sdk/duplicate-adapter-id/`, `fixtures/adapters/sdk/unsupported-schema-version/` |
| Schemas | `adapter-manifest.schema.json` must define adapter id, version, supported input formats, emitted record kinds, schema version range, parser entrypoint, feature flags, and conformance fixture map. `adapter-conformance-report.schema.json` must define adapter id, fixture id, result, finding severity, sourceRef, parser version, and produced record counts. |
| Tests | Manifest schema validation, adapter registry load success, duplicate id rejection, unsupported schema version rejection, capability mismatch rejection, unknown output record rejection, sample adapter conformance success, sample adapter malformed input hard DQ. |
| No-Go | No manifest schema; SDK is documentation only; sample adapter is hardcoded to fixture names; adapter can emit records not declared in manifest; malformed manifest is accepted; negative fixtures are absent; conformance report omits sourceRefs or parser version. |
| Evidence report | `adapter-conformance-report.json` generated in CI and referenced by `product-readiness-report.json`. |

Implementation notes:

- The SDK must expose a small stable contract: adapter metadata, input discovery, parse result,
  normalized records, diagnostics, and sourceRef mapping.
- Parser diagnostics must be data, not log-only output.
- Adapter authors must not need to import internal P0A/P0B functions to build a conforming adapter.

### HATE-PG-001B JUnit dialect parser corpus

| Field | Required content |
|---|---|
| Epic | EPIC-001 Adapter Corpus and SDK |
| Requirement refs | FR-ADP-001, FR-TI-001, FR-TI-004 |
| Acceptance refs | AC-REQ-003, AC-REQ-015 |
| Affected paths | `src/hate/adapters/junit.py`, `src/hate/p0a_support.py`, `fixtures/adapters/junit/`, `schemas/HATE/v1/test-result.schema.json`, `tests/test_adapters_junit.py`, `tests/test_p0a.py`, `docs/process/ADAPTER_DIALECT_PARSER_SPEC.md` |
| Fixtures | `fixtures/adapters/junit/surefire/`, `fixtures/adapters/junit/gradle/`, `fixtures/adapters/junit/pytest-junitxml/`, `fixtures/adapters/junit/jest-junit/`, `fixtures/adapters/junit/vitest-junit/`, `fixtures/adapters/junit/playwright/`, `fixtures/adapters/junit/go-junit-report/`, `fixtures/adapters/junit/parameterized/`, `fixtures/adapters/junit/windows-paths/`, `fixtures/adapters/junit/container-paths/` |
| Negative fixtures | `fixtures/adapters/junit/malformed-xml/`, `fixtures/adapters/junit/missing-testsuite/`, `fixtures/adapters/junit/skipped-without-reason/`, `fixtures/adapters/junit/duplicate-testcase-id/`, `fixtures/adapters/junit/focused-only-leak/`, `fixtures/adapters/junit/xfailed-as-pass/` |
| Schemas | `test-result.schema.json` must preserve framework, suite, class name, file path, test name, status, duration, failure text hash, skip/xfail/only/todo markers, retry index, flaky flag, sourceRef, and parser diagnostics. |
| Tests | Dialect-specific success tests for each fixture family, path normalization tests, status mapping tests for pass/fail/error/skip/xfail/todo/only, retry/flaky preservation tests, duplicate id finding tests, malformed XML hard DQ tests, fixture-name coupling tests that rename fixture directories and require identical results. |
| No-Go | Only one JUnit dialect is represented; skipped/xfail/todo records are treated as pass; `classname` or file path is dropped; malformed XML is silently ignored; parser branches on fixture directory names; adapter conformance can pass without a negative fixture. |
| Evidence report | `adapter-conformance-report.json` with one entry per dialect fixture and negative fixture, plus produced `test_records` counts by status. |

Implementation notes:

- JUnit parsing must handle both `<testsuite>` roots and `<testsuites>` roots.
- Missing optional attributes may be soft diagnostics, but ambiguous identity or invalid XML must
  produce a hard DQ.
- The parser must keep enough identity to connect test records to integrity checks in EPIC-004.

### HATE-PG-001C Coverage dialect parser corpus

| Field | Required content |
|---|---|
| Epic | EPIC-001 Adapter Corpus and SDK |
| Requirement refs | FR-ADP-002, FR-GRAPH-002, FR-GRAPH-005 |
| Acceptance refs | AC-REQ-002, AC-REQ-006, AC-REQ-015 |
| Affected paths | `src/hate/adapters/coverage.py`, `src/hate/p0a_support.py`, `fixtures/adapters/coverage/`, `fixtures/adapters/coveragepy/`, `schemas/HATE/v1/coverage-slice.schema.json`, `tests/test_adapters_coverage.py`, `tests/test_p0a.py`, `docs/process/ADAPTER_DIALECT_PARSER_SPEC.md` |
| Fixtures | `fixtures/adapters/coverage/coveragepy-json/`, `fixtures/adapters/coverage/coveragepy-xml/`, `fixtures/adapters/coverage/lcov/`, `fixtures/adapters/coverage/cobertura/`, `fixtures/adapters/coverage/jacoco/`, `fixtures/adapters/coverage/branch-coverage/`, `fixtures/adapters/coverage/partial-contexts/`, `fixtures/adapters/coverage/windows-paths/`, `fixtures/adapters/coverage/container-paths/` |
| Negative fixtures | `fixtures/adapters/coverage/malformed-json/`, `fixtures/adapters/coverage/malformed-xml/`, `fixtures/adapters/coverage/show-contexts-false/`, `fixtures/adapters/coverage/contextless-lines/`, `fixtures/adapters/coverage/unknown-file-path/`, `fixtures/adapters/coverage/coverage-only-no-test-results/` |
| Schemas | `coverage-slice.schema.json` must preserve file path, normalized path, covered lines, missing lines, branch totals, covered branches, contexts, sourceRef, parser diagnostics, and input format. |
| Tests | Coverage.py JSON context preservation, show_contexts=false hard DQ, partial contexts eligible-with-gap, LCOV line mapping, Cobertura and JaCoCo XML mapping, branch coverage preservation, Windows/container path normalization, coverage-only soft gap/no product-ready, malformed input hard DQ. |
| No-Go | Coverage alone can make evidence eligible without test records; contexts are dropped; `show_contexts=false` is accepted as complete evidence; branch coverage exists but is ignored without diagnostic; file paths are not normalized; malformed coverage is downgraded to non-blocking. |
| Evidence report | `adapter-conformance-report.json` with coverage dialect results and `coverage_adapter_errors`; `product-readiness-report.json` must show soft gap or DQ when coverage lacks meaningful test evidence. |

Implementation notes:

- Context-aware coverage is required for strong evidence; contextless coverage can be retained only
  as weak supporting evidence.
- Coverage parser output must connect to sourceRef/hash validation in EPIC-002 and evidence graph
  construction in EPIC-003.

### HATE-PG-001D SARIF/Pact/Stryker parser corpus

| Field | Required content |
|---|---|
| Epic | EPIC-001 Adapter Corpus and SDK |
| Requirement refs | FR-ADP-003, FR-ADP-004, FR-ADP-005, FR-RISK-001 |
| Acceptance refs | AC-REQ-002, AC-REQ-004, AC-REQ-015 |
| Affected paths | `src/hate/adapters/sarif.py`, `src/hate/adapters/pact.py`, `src/hate/adapters/stryker.py`, `src/hate/p0b_support.py`, `fixtures/adapters/sarif/`, `fixtures/adapters/pact/`, `fixtures/adapters/stryker/`, `schemas/HATE/v1/static-finding.schema.json`, `schemas/HATE/v1/contract-evidence.schema.json`, `schemas/HATE/v1/mutation-evidence.schema.json`, `tests/test_adapters_static_contract_mutation.py`, `docs/process/ADAPTER_DIALECT_PARSER_SPEC.md` |
| Fixtures | `fixtures/adapters/sarif/high-critical-changed-path/`, `fixtures/adapters/sarif/suppressed-finding/`, `fixtures/adapters/sarif/multiple-runs/`, `fixtures/adapters/pact/provider-pass/`, `fixtures/adapters/pact/provider-fail/`, `fixtures/adapters/pact/version-mismatch/`, `fixtures/adapters/stryker/killed-survived-timeout/`, `fixtures/adapters/stryker/no-coverage/`, `fixtures/adapters/stryker/incremental/` |
| Negative fixtures | `fixtures/adapters/sarif/malformed-json/`, `fixtures/adapters/sarif/missing-result-location/`, `fixtures/adapters/pact/malformed-json/`, `fixtures/adapters/pact/missing-interaction-id/`, `fixtures/adapters/stryker/malformed-json/`, `fixtures/adapters/stryker/unknown-mutant-status/` |
| Schemas | `static-finding.schema.json` must preserve rule id, severity, file path, line, suppression state, changed-path flag, sourceRef, and tool metadata. `contract-evidence.schema.json` must preserve provider, consumer, interaction id, result, pact version, failure class, sourceRef. `mutation-evidence.schema.json` must preserve mutant id, file path, line, status, test coverage relation, score, sourceRef. |
| Tests | SARIF high/critical changed-path finding blocks product-ready, SARIF suppressed finding is retained but not blocking unless configured, Pact provider failure blocks affected contract claims, Pact version mismatch DQ, Stryker survived/timeout lowers oracle confidence, no-coverage mutant produces soft gap, malformed input hard DQ, optional parser failure visible in conformance report. |
| No-Go | Failed contract evidence is hidden; survived mutants do not affect oracle strength; high/critical SARIF on changed code is not visible; suppressed findings are deleted instead of marked; malformed optional parser failures are ignored; parser output cannot be traced to sourceRef. |
| Evidence report | `adapter-conformance-report.json` with static, contract, and mutation sections; downstream `product-readiness-report.json` must include risk/oracle effects from parsed records. |

Implementation notes:

- These adapters are not decoration. Their records must affect readiness through EPIC-003 risk
  coverage and EPIC-004/005 quality gates.
- Optional source families may be absent, but when present they must be parsed, validated, and
  reported with explicit pass/gap/DQ status.

## 6. EPIC-002 Detailed Task Packets

EPIC-002 is the cross-record schema and validator epic. It is complete only when every
adapter-produced record enters a shared envelope, validates against a record schema, and can be
rejected when sourceRef, hash, identity, or cross-record references are inconsistent.

### HATE-PG-002A Common envelope validator

| Field | Required content |
|---|---|
| Epic | EPIC-002 Cross-Record Schema and Validator |
| Requirement refs | FR-ING-006, FR-GRAPH-005, NFR-007 |
| Acceptance refs | AC-REQ-006, AC-REQ-014 |
| Affected paths | `src/hate/schema_validator.py`, `src/hate/evidence_envelope.py`, `schemas/HATE/v1/evidence-envelope.schema.json`, `schemas/HATE/v1/test-result.schema.json`, `schemas/HATE/v1/coverage-slice.schema.json`, `schemas/HATE/v1/static-finding.schema.json`, `schemas/HATE/v1/contract-evidence.schema.json`, `schemas/HATE/v1/mutation-evidence.schema.json`, `fixtures/schema/envelope/`, `tests/test_schema_validator.py`, `docs/process/SCHEMA_REGISTRY_CONTRACT.md` |
| Fixtures | `fixtures/schema/envelope/valid-test-result/`, `fixtures/schema/envelope/valid-coverage-slice/`, `fixtures/schema/envelope/valid-static-finding/`, `fixtures/schema/envelope/valid-contract-evidence/`, `fixtures/schema/envelope/valid-mutation-evidence/` |
| Negative fixtures | `fixtures/schema/envelope/missing-record-kind/`, `fixtures/schema/envelope/unknown-schema-version/`, `fixtures/schema/envelope/missing-source-ref/`, `fixtures/schema/envelope/invalid-timestamp/`, `fixtures/schema/envelope/record-kind-schema-mismatch/`, `fixtures/schema/envelope/unredacted-secret/` |
| Schemas | `evidence-envelope.schema.json` must define record id, record kind, schema version, producer, parser version, sourceRef, source hash, collected_at, normalized path set, diagnostics, and payload. Record schemas must be selected by `record_kind` and `schema_version`. |
| Tests | Valid envelope acceptance, record-kind schema dispatch, schema version rejection, sourceRef required rejection, invalid timestamp rejection, secret-in-envelope rejection, unknown record kind rejection, schema registry missing file rejection, report generation for accepted/rejected counts. |
| No-Go | Records bypass envelope validation; schema version is ignored; unknown record kinds are accepted; sourceRef is optional; validator returns logs only; schema failures do not affect product-ready; validation report is missing from CI. |
| Evidence report | `schema-validation-report.json` with accepted count, rejected count, rejection classes, schema versions, fixture ids, and sourceRefs. |

Implementation notes:

- The validator is the boundary between adapter output and product claims.
- Schema failures must be deterministic and reproducible from fixture input.
- Report entries must carry enough detail for UAT and manual review without exposing secrets.

### HATE-PG-002B Cross-record sourceRef/hash validator

| Field | Required content |
|---|---|
| Epic | EPIC-002 Cross-Record Schema and Validator |
| Requirement refs | FR-GRAPH-005, FR-STO-001, FR-STO-003 |
| Acceptance refs | AC-REQ-006, AC-REQ-015 |
| Affected paths | `src/hate/source_ref.py`, `src/hate/cross_record_validator.py`, `schemas/HATE/v1/source-ref.schema.json`, `fixtures/schema/cross-record/`, `tests/test_cross_record_validator.py`, `docs/process/STORE_SCHEMA_REQUIREMENTS.md`, `docs/process/SCHEMA_REGISTRY_CONTRACT.md` |
| Fixtures | `fixtures/schema/cross-record/matching-test-coverage-source/`, `fixtures/schema/cross-record/matching-finding-changed-file/`, `fixtures/schema/cross-record/container-path-normalized/`, `fixtures/schema/cross-record/windows-path-normalized/`, `fixtures/schema/cross-record/replayed-bundle-stable/` |
| Negative fixtures | `fixtures/schema/cross-record/hash-mismatch/`, `fixtures/schema/cross-record/missing-source-artifact/`, `fixtures/schema/cross-record/path-traversal-source-ref/`, `fixtures/schema/cross-record/coverage-refers-unknown-test/`, `fixtures/schema/cross-record/finding-refers-unknown-file/`, `fixtures/schema/cross-record/non-deterministic-record-id/` |
| Schemas | `source-ref.schema.json` must define artifact id, path, normalized path, content hash, line/column range, optional context id, and allowed source families. Cross-record validator output must define violation id, severity, affected record ids, relation kind, expected value, observed value, and sourceRef. |
| Tests | Hash match acceptance, hash mismatch hard DQ, missing artifact hard DQ, path traversal rejection, Windows/container path normalization, unknown referenced record rejection, deterministic record id replay, validation report stable ordering, sourceRef redaction safety. |
| No-Go | Hash mismatches are soft warnings; records can reference files outside the run bundle; path normalization differs by OS; replay changes record ids; cross-record violations lack affected ids; product-ready ignores validator hard DQ. |
| Evidence report | `schema-validation-report.json` with cross-record violation section; `store-replay-report.json` must prove deterministic ids after replay once EPIC-006 exists. |

Implementation notes:

- This packet must be implemented before durable store replay is claimed.
- The validator must separate invalid evidence from weak evidence. Invalid sourceRef/hash is a hard
  DQ; missing optional relation can be a soft gap only when the requirement allows it.

## 7. EPIC-003 Detailed Task Packets

EPIC-003 is the evidence graph and risk coverage epic. It is complete only when HATE can explain
which requirements and risks are supported, contradicted, weakly supported, or unsupported by the
validated evidence records.

### HATE-PG-003A Evidence graph node/edge model

| Field | Required content |
|---|---|
| Epic | EPIC-003 Evidence Graph and Risk Coverage |
| Requirement refs | FR-GRAPH-001, FR-GRAPH-003, FR-GRAPH-005 |
| Acceptance refs | AC-REQ-002, AC-REQ-006 |
| Affected paths | `src/hate/evidence_graph.py`, `src/hate/readiness_model.py`, `schemas/HATE/v1/evidence-graph.schema.json`, `schemas/HATE/v1/product-readiness-report.schema.json`, `fixtures/graph/model/`, `tests/test_evidence_graph.py`, `tests/test_product_readiness_report.py`, `docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` |
| Fixtures | `fixtures/graph/model/requirement-test-coverage/`, `fixtures/graph/model/risk-static-finding/`, `fixtures/graph/model/contract-mutation-evidence/`, `fixtures/graph/model/manual-review-supported/`, `fixtures/graph/model/contradictory-evidence/` |
| Negative fixtures | `fixtures/graph/model/orphan-evidence/`, `fixtures/graph/model/cycle-in-requires/`, `fixtures/graph/model/missing-requirement-ref/`, `fixtures/graph/model/unknown-edge-kind/`, `fixtures/graph/model/unsupported-claim-marked-ready/` |
| Schemas | `evidence-graph.schema.json` must define requirement, risk, test, execution, coverage, finding, artifact, manual_review, and release_claim nodes. Edge kinds must include requires_test, executed_by, covered_by, supported_by, contradicted_by, blocked_by, reviewed_by, and derived_from. |
| Tests | Node construction from validated records, edge construction by sourceRef and requirement refs, contradiction handling, orphan evidence finding, cycle rejection, stable graph serialization, product-readiness report generation, unsupported claim No-Go. |
| No-Go | Product-ready is computed without graph edges; orphan evidence can support claims; contradictory evidence is ignored; graph cycles are accepted; release claims can exist without requirement refs; graph serialization is nondeterministic. |
| Evidence report | `product-readiness-report.json` with graph summary, unsupported claim list, contradiction list, hard DQ list, soft gap list, and sourceRefs. |

Implementation notes:

- The graph is the core explanation layer. It must be inspectable and deterministic.
- A claim is not supported because evidence exists somewhere; it is supported only when the graph
  connects the claim to valid evidence through allowed edges.

### HATE-PG-003B Risk coverage matrix and manual request bridge

| Field | Required content |
|---|---|
| Epic | EPIC-003 Evidence Graph and Risk Coverage |
| Requirement refs | FR-GRAPH-002, FR-GRAPH-004, FR-RISK-001, FR-RISK-002 |
| Acceptance refs | AC-REQ-002, AC-REQ-005, AC-REQ-013 |
| Affected paths | `src/hate/risk_matrix.py`, `src/hate/manual_review_bridge.py`, `schemas/HATE/v1/risk-coverage-matrix.schema.json`, `schemas/HATE/v1/manual-review-request.schema.json`, `fixtures/graph/risk-matrix/`, `tests/test_risk_matrix.py`, `tests/test_manual_review_bridge.py`, `docs/process/RISK_DEBT_REGISTER.md`, `docs/process/USER_STORY_MAP.md` |
| Fixtures | `fixtures/graph/risk-matrix/covered-critical-risk/`, `fixtures/graph/risk-matrix/weak-coverage/`, `fixtures/graph/risk-matrix/manual-review-required/`, `fixtures/graph/risk-matrix/risk-debt-accepted/`, `fixtures/graph/risk-matrix/security-risk-blocked/` |
| Negative fixtures | `fixtures/graph/risk-matrix/high-risk-no-oracle/`, `fixtures/graph/risk-matrix/manual-review-without-owner/`, `fixtures/graph/risk-matrix/expired-risk-debt/`, `fixtures/graph/risk-matrix/coverage-without-evidence/`, `fixtures/graph/risk-matrix/risk-claim-without-requirement/` |
| Schemas | `risk-coverage-matrix.schema.json` must define risk id, requirement refs, severity, required evidence classes, observed evidence classes, oracle strength, gap class, owner, due date, and readiness effect. `manual-review-request.schema.json` must define reason, owner, sourceRefs, blocking flag, required decision, and expiry. |
| Tests | Critical risk covered acceptance, high risk without oracle hold, coverage without evidence soft gap, manual review request generation, missing owner hard DQ, expired risk debt blocker, risk debt accepted with expiry, dashboard-ready matrix projection. |
| No-Go | High risk can pass with no oracle; coverage percentage is accepted as evidence by itself; manual review has no owner or expiry; risk debt never expires; readiness effect is missing; dashboard cannot explain why a risk is blocked or held. |
| Evidence report | `product-readiness-report.json` with risk matrix section; `manual-review-required.json` when manual decisions are blocking or time-bound. |

Implementation notes:

- Risk coverage must distinguish executable oracle, static finding, contract check, mutation score,
  coverage-only evidence, and human review.
- Manual review is a controlled evidence class, not a way to hide unsupported claims.

## 8. EPIC-004 Detailed Task Packets

EPIC-004 is the test integrity and AI-abuse detector epic. It is complete only when HATE can
detect evidence that appears to exist but is structurally unreliable: skipped tests, focused test
leaks, empty assertions, over-mocking, fixture-name coupling, missing oracles, and suspicious
manual-review bypasses.

### HATE-PG-004A Skip/focus/todo detector

| Field | Required content |
|---|---|
| Epic | EPIC-004 Test Integrity and AI-Abuse Detector |
| Requirement refs | FR-TI-001, FR-RISK-001 |
| Acceptance refs | AC-REQ-003, AC-REQ-010 |
| Affected paths | `src/hate/test_integrity/skip_focus.py`, `src/hate/test_integrity/models.py`, `schemas/HATE/v1/test-integrity-report.schema.json`, `fixtures/test-integrity/skip-focus/`, `tests/test_test_integrity_skip_focus.py`, `docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` |
| Fixtures | `fixtures/test-integrity/skip-focus/clean-suite/`, `fixtures/test-integrity/skip-focus/known-skip-with-owner/`, `fixtures/test-integrity/skip-focus/xfail-with-issue-ref/`, `fixtures/test-integrity/skip-focus/todo-non-release-profile/` |
| Negative fixtures | `fixtures/test-integrity/skip-focus/only-focused-leak/`, `fixtures/test-integrity/skip-focus/skip-without-reason/`, `fixtures/test-integrity/skip-focus/xfail-without-expiry/`, `fixtures/test-integrity/skip-focus/todo-in-release-profile/`, `fixtures/test-integrity/skip-focus/skip-in-critical-risk-area/` |
| Schemas | `test-integrity-report.schema.json` must define finding id, detector id, severity, profile, affected test id, marker kind, reason, owner, expiry, sourceRef, readiness effect, and suggested manual review action. |
| Tests | Clean suite pass, known skip accepted as risk debt, `only` hard DQ in release/product profile, missing skip reason hold, expired xfail hard DQ, critical-risk skip blocker, deterministic finding ids, report schema validation. |
| No-Go | `only` is warning-only in product profile; skip/xfail/todo markers are counted as executed evidence; missing owner or expiry is accepted; marker findings lack sourceRef; release readiness can pass with focused tests. |
| Evidence report | `test-integrity-report.json` with marker summary, blocker list, hold list, risk-debt list, and sourceRefs. |

Implementation notes:

- Detector severity must depend on product profile. Development profiles may allow more weak
  evidence; release/product profiles must block focused tests and critical unowned skips.
- This packet consumes normalized test records from EPIC-001/002 and must not parse raw framework
  files independently once adapter output exists.

### HATE-PG-004B Mock abuse and assertion quality detector

| Field | Required content |
|---|---|
| Epic | EPIC-004 Test Integrity and AI-Abuse Detector |
| Requirement refs | FR-TI-002, FR-TI-003, FR-RISK-001 |
| Acceptance refs | AC-REQ-003, AC-REQ-005 |
| Affected paths | `src/hate/test_integrity/mock_assertion.py`, `src/hate/test_integrity/source_scan.py`, `schemas/HATE/v1/test-integrity-report.schema.json`, `fixtures/test-integrity/mock-assertion/`, `tests/test_test_integrity_mock_assertion.py`, `docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` |
| Fixtures | `fixtures/test-integrity/mock-assertion/real-boundary-mock/`, `fixtures/test-integrity/mock-assertion/asserts-domain-output/`, `fixtures/test-integrity/mock-assertion/property-assertion/`, `fixtures/test-integrity/mock-assertion/snapshot-with-semantic-guard/` |
| Negative fixtures | `fixtures/test-integrity/mock-assertion/empty-stub/`, `fixtures/test-integrity/mock-assertion/mock-internal-function/`, `fixtures/test-integrity/mock-assertion/assert-no-exception-only/`, `fixtures/test-integrity/mock-assertion/snapshot-only/`, `fixtures/test-integrity/mock-assertion/assert-true-constant/`, `fixtures/test-integrity/mock-assertion/no-oracle-risk-test/` |
| Schemas | Mock/quality findings must include language, framework, file path, symbol name, detector rule, confidence, sourceRef, readiness effect, and whether the finding is auto-blocking or manual-review-required. |
| Tests | Boundary mock allowed, internal function mock flagged, empty stub flagged, assert-no-exception-only flagged, constant assertion flagged, snapshot-only soft gap/hold by profile, semantic assertion accepted, no-oracle risk hold, false-positive suppression with owner/expiry. |
| No-Go | Detector flags all mocks equally; empty assertions pass as meaningful oracle; snapshot-only tests satisfy high-risk requirements; findings cannot be traced to source lines; suppressions have no owner or expiry; implementation code branches on fixture names. |
| Evidence report | `test-integrity-report.json` with mock abuse section, assertion quality section, confidence, sourceRefs, and suppression/risk-debt records. |

Implementation notes:

- Mock abuse detection must distinguish external-boundary mocks from internal logic replacement.
- Assertion quality must be conservative: strong findings block; medium-confidence findings hold
  and request manual review instead of pretending certainty.

### HATE-PG-004C Test coupling and manual review detector

| Field | Required content |
|---|---|
| Epic | EPIC-004 Test Integrity and AI-Abuse Detector |
| Requirement refs | FR-TI-004, FR-TI-005, FR-TI-006, FR-TI-007 |
| Acceptance refs | AC-REQ-003, AC-REQ-005, AC-REQ-010 |
| Affected paths | `src/hate/test_integrity/coupling.py`, `src/hate/test_integrity/manual_review.py`, `schemas/HATE/v1/manual-review-request.schema.json`, `fixtures/test-integrity/coupling/`, `tests/test_test_integrity_coupling.py`, `tests/test_manual_review_bridge.py`, `docs/process/RISK_DEBT_REGISTER.md` |
| Fixtures | `fixtures/test-integrity/coupling/data-driven-parser/`, `fixtures/test-integrity/coupling/fixture-renamed-stable/`, `fixtures/test-integrity/coupling/manual-review-owned/`, `fixtures/test-integrity/coupling/coverage-with-executed-tests/` |
| Negative fixtures | `fixtures/test-integrity/coupling/fixture-name-branch/`, `fixtures/test-integrity/coupling/test-name-branch/`, `fixtures/test-integrity/coupling/risk-without-oracle/`, `fixtures/test-integrity/coupling/coverage-without-evidence/`, `fixtures/test-integrity/coupling/manual-review-without-human-record/`, `fixtures/test-integrity/coupling/manual-review-expired/` |
| Schemas | Manual review request and test coupling findings must include detector id, evidence class, triggering records, sourceRefs, required human decision, owner, expiry, readiness effect, and relation to risk matrix entry. |
| Tests | Fixture rename stability, test-name branch detection, implementation-test coupling hold, risk_without_oracle hold, coverage_without_evidence soft gap, manual review request generation, missing human decision hard DQ, expired manual review blocker. |
| No-Go | HATE synthesizes approval records; test/fixture-name coupling passes; high-risk feature passes without oracle; coverage percentage alone is enough; manual review has no owner/expiry/sourceRef; manual-review-required is omitted from release pack. |
| Evidence report | `test-integrity-report.json` plus `manual-review-required.json` when manual decisions are required. |

Implementation notes:

- Manual review is an explicit state transition. The system can request review and validate review
  records, but it cannot invent approval.
- Coupling checks must be robust against fixture renaming and test renaming.

## 9. EPIC-005 Detailed Task Packets

EPIC-005 is the artifact safety and privacy epic. It is complete only when HATE can ingest,
store, display, export, and diagnose evidence without leaking secrets, PII, restricted paths, raw
customer source, archive contents, or external URLs outside policy.

### HATE-PG-005A Secret/PII/path/archive/external URL scanners

| Field | Required content |
|---|---|
| Epic | EPIC-005 Artifact Safety and Privacy |
| Requirement refs | FR-SEC-001, FR-SEC-002, FR-SEC-003, FR-SEC-004 |
| Acceptance refs | AC-REQ-004, AC-REQ-008, AC-REQ-011 |
| Affected paths | `src/hate/artifact_safety/scanners.py`, `src/hate/artifact_safety/classifier.py`, `schemas/HATE/v1/security-quarantine-report.schema.json`, `fixtures/artifact-safety/scanners/`, `tests/test_artifact_safety_scanners.py`, `docs/process/PRIVACY_QUARANTINE_CONTRACT.md`, `docs/process/DATA_RETENTION_LEGAL_REQUIREMENTS.md` |
| Fixtures | `fixtures/artifact-safety/scanners/clean-report/`, `fixtures/artifact-safety/scanners/allowed-public-url/`, `fixtures/artifact-safety/scanners/redacted-secret/`, `fixtures/artifact-safety/scanners/relative-path-safe/`, `fixtures/artifact-safety/scanners/small-archive-metadata-only/` |
| Negative fixtures | `fixtures/artifact-safety/scanners/aws-secret/`, `fixtures/artifact-safety/scanners/github-token/`, `fixtures/artifact-safety/scanners/email-pii/`, `fixtures/artifact-safety/scanners/absolute-home-path/`, `fixtures/artifact-safety/scanners/path-traversal/`, `fixtures/artifact-safety/scanners/archive-bomb/`, `fixtures/artifact-safety/scanners/unapproved-external-url/` |
| Schemas | `security-quarantine-report.schema.json` must define artifact id, scanner id, finding class, severity, redaction status, quarantine status, sourceRef, policy id, allowed export surfaces, and required owner action. |
| Tests | Clean artifact pass, known redacted secret accepted, raw secret hard DQ, PII quarantine, restricted path quarantine, path traversal blocker, archive bomb blocker, unapproved external URL blocker, deterministic redaction hash, report schema validation. |
| No-Go | Raw secret appears in logs/report/export; PII is downgraded without policy; archive contents are expanded without limits; external URLs are fetched during scan; restricted path is exposed to unauthorized caller; scanner finding lacks sourceRef. |
| Evidence report | `security-quarantine-report.json` with scanner results, quarantine decisions, redaction status, and export eligibility. |

Implementation notes:

- Scanners must operate offline. They must not fetch external URLs.
- Quarantine is not deletion. The store must keep safe metadata and enforce access/export policy.

### HATE-PG-005B Redaction and summary/export safety filter

| Field | Required content |
|---|---|
| Epic | EPIC-005 Artifact Safety and Privacy |
| Requirement refs | FR-SEC-005, FR-APIX-006, FR-UI-009, FR-OBS-004 |
| Acceptance refs | AC-REQ-004, AC-REQ-011, AC-REQ-013 |
| Affected paths | `src/hate/artifact_safety/redaction.py`, `src/hate/artifact_safety/export_filter.py`, `src/hate/artifact_safety/summary_filter.py`, `schemas/HATE/v1/safe-diagnostic-bundle.schema.json`, `fixtures/artifact-safety/redaction/`, `tests/test_artifact_safety_redaction.py`, `docs/process/PRIVACY_QUARANTINE_CONTRACT.md` |
| Fixtures | `fixtures/artifact-safety/redaction/safe-summary/`, `fixtures/artifact-safety/redaction/secret-redacted/`, `fixtures/artifact-safety/redaction/path-tokenized/`, `fixtures/artifact-safety/redaction/dashboard-safe-view/`, `fixtures/artifact-safety/redaction/support-bundle-safe/` |
| Negative fixtures | `fixtures/artifact-safety/redaction/raw-secret-export/`, `fixtures/artifact-safety/redaction/raw-pii-summary/`, `fixtures/artifact-safety/redaction/reversible-redaction/`, `fixtures/artifact-safety/redaction/unauthorized-restricted-path/`, `fixtures/artifact-safety/redaction/diagnostic-bundle-raw-artifact/` |
| Schemas | Safe diagnostic bundle schema must define export surface, redaction profile, included artifact ids, excluded artifact ids, redaction findings, policy version, actor scope, and non-reversibility proof hash. |
| Tests | Secret redacted in report/export/dashboard, PII omitted from summary, restricted path tokenized by actor scope, reversible redaction rejection, support bundle excludes raw artifacts, safe diagnostic bundle schema validation, product-ready blocked when required redaction fails. |
| No-Go | Failed redaction still exports; dashboard shows raw quarantined content; support bundle includes customer source by default; redaction is reversible without privileged store access; summary filter invents or hides readiness findings. |
| Evidence report | `security-quarantine-report.json` plus `safe-diagnostic-bundle.json` when support/export bundle is generated. |

Implementation notes:

- Redaction must preserve enough traceability for sourceRef and debugging while removing sensitive
  content from unprivileged surfaces.
- Summary/export filters must not change readiness verdicts. They only control representation.

## 10. EPIC-006 Detailed Task Packets

EPIC-006 is the local store, replay, and compare epic. It is complete only when evidence bundles
are immutable, atomically written, replayable, comparable across runs, and diagnosable when
corrupted or partially written.

### HATE-PG-006A Immutable local store and indexes

| Field | Required content |
|---|---|
| Epic | EPIC-006 Local Store, Replay, Compare |
| Requirement refs | FR-STO-001, FR-STO-002, FR-GRAPH-005 |
| Acceptance refs | AC-REQ-006, AC-REQ-014 |
| Affected paths | `src/hate/store/local_store.py`, `src/hate/store/indexes.py`, `src/hate/store/atomic_write.py`, `schemas/HATE/v1/store-manifest.schema.json`, `fixtures/store/local/`, `tests/test_store_local.py`, `docs/process/STORE_SCHEMA_REQUIREMENTS.md` |
| Fixtures | `fixtures/store/local/single-run-bundle/`, `fixtures/store/local/multi-run-index/`, `fixtures/store/local/atomic-write-success/`, `fixtures/store/local/content-addressed-artifacts/`, `fixtures/store/local/legal-hold-metadata/` |
| Negative fixtures | `fixtures/store/local/partial-write/`, `fixtures/store/local/hash-mismatch/`, `fixtures/store/local/index-missing-record/`, `fixtures/store/local/path-traversal-key/`, `fixtures/store/local/mutable-canonical-bundle/` |
| Schemas | `store-manifest.schema.json` must define run id, bundle id, source version, schema versions, artifact ids, content hashes, index hashes, legal hold markers, retention policy id, created_at, and producer version. |
| Tests | Atomic write creates complete manifest, content-addressed artifact hash stable, index lookup by run/requirement/risk/sourceRef, partial write ignored or quarantined, path traversal rejected, mutable canonical bundle blocked, legal hold metadata retained. |
| No-Go | External export mutates canonical bundle; artifact content is addressed only by filename; partial write appears as valid run; index can reference missing records; path traversal writes outside store root; legal hold metadata is optional. |
| Evidence report | `store-replay-report.json` with store manifest validation, index validation, hash validation, and partial-write diagnostics. |

Implementation notes:

- Canonical store writes must be append-only for completed bundles.
- Derived/exported views can be regenerated, but canonical evidence and manifest hashes must stay
  stable.

### HATE-PG-006B Replay/compare/corruption doctor

| Field | Required content |
|---|---|
| Epic | EPIC-006 Local Store, Replay, Compare |
| Requirement refs | FR-STO-003, FR-STO-004, FR-LIFE-001 |
| Acceptance refs | AC-REQ-006, AC-REQ-010, AC-REQ-018 |
| Affected paths | `src/hate/store/replay.py`, `src/hate/store/compare.py`, `src/hate/store/doctor.py`, `schemas/HATE/v1/store-replay-report.schema.json`, `fixtures/store/replay/`, `tests/test_store_replay_compare.py`, `docs/process/STORE_SCHEMA_REQUIREMENTS.md`, `docs/process/RELEASE_MIGRATION_POLICY.md` |
| Fixtures | `fixtures/store/replay/replay-stable/`, `fixtures/store/replay/compare-baseline-improved/`, `fixtures/store/replay/compare-baseline-regressed/`, `fixtures/store/replay/schema-minor-compatible/`, `fixtures/store/replay/rebuild-index/` |
| Negative fixtures | `fixtures/store/replay/corrupt-manifest/`, `fixtures/store/replay/missing-artifact/`, `fixtures/store/replay/hash-mismatch/`, `fixtures/store/replay/unsupported-schema-version/`, `fixtures/store/replay/baseline-by-filename-only/`, `fixtures/store/replay/legal-hold-lost/` |
| Schemas | `store-replay-report.schema.json` must define replay input bundle, produced report hashes, expected report hashes, diff entries, corruption findings, migration compatibility status, baseline resolution evidence, and legal hold preservation. |
| Tests | Replay produces byte-stable reports, compare detects improvement/regression/no-change, corrupt manifest hard DQ, missing artifact hard DQ, hash mismatch hard DQ, unsupported schema version migration hold, baseline cannot be selected by filename sorting only, legal hold preservation check. |
| No-Go | Replay depends on current filesystem outside bundle; compare baseline selected by filename sorting only; corruption doctor mutates canonical evidence without explicit repair output; legal hold is lost during replay/migration; unsupported schema is silently accepted. |
| Evidence report | `store-replay-report.json` with replay hash comparison, diff summary, corruption doctor findings, migration status, and baseline selection proof. |

Implementation notes:

- Replay must be deterministic enough for CI and UAT to compare hashes.
- Doctor commands may produce repair suggestions or derived repaired copies. They must not silently
  rewrite canonical evidence.

## 11. EPIC-007 Detailed Task Packets

EPIC-007 is the API read model epic. It is complete only when validated bundles can be queried
through stable, versioned, authorization-aware resources without changing canonical evidence or
recomputing verdicts differently from the CLI/report engine.

### HATE-PG-007A API envelope and read resources

| Field | Required content |
|---|---|
| Epic | EPIC-007 API Read Model |
| Requirement refs | FR-API-001, FR-APIX-001, FR-GRAPH-001, FR-GRAPH-002 |
| Acceptance refs | AC-REQ-013, AC-REQ-014 |
| Affected paths | `src/hate/api/envelope.py`, `src/hate/api/read_model.py`, `src/hate/api/resources.py`, `schemas/HATE/v1/api-response-envelope.schema.json`, `fixtures/api/read-model/`, `tests/test_api_read_model.py`, `docs/process/API_REQUIREMENTS.md`, `docs/process/API_OPENAPI.yaml`, `docs/process/HOSTED_READ_MODEL_API.md` |
| Fixtures | `fixtures/api/read-model/run-overview/`, `fixtures/api/read-model/requirement-detail/`, `fixtures/api/read-model/risk-matrix/`, `fixtures/api/read-model/evidence-graph-page/`, `fixtures/api/read-model/adapter-health/`, `fixtures/api/read-model/artifact-safety-summary/` |
| Negative fixtures | `fixtures/api/read-model/missing-report/`, `fixtures/api/read-model/stale-read-model/`, `fixtures/api/read-model/invalid-pagination-token/`, `fixtures/api/read-model/unsupported-api-version/`, `fixtures/api/read-model/unavailable-required-report/` |
| Schemas | API response envelope must define status, request id, API version, resource version, generated_at, stale flag, data, warnings, errors, pagination, and source report refs. Resource schemas must map directly from canonical reports. |
| Tests | Run overview serialization, requirement detail includes sourceRefs, risk matrix pagination, evidence graph pagination, stale read model flagged, missing required report hard error, unsupported version error, OpenAPI contract validation, stable sorting and pagination tokens. |
| No-Go | API computes verdict independently from reports; stale read model is returned as fresh; missing report is hidden; pagination changes item order between requests; response lacks source report refs; OpenAPI spec diverges from implementation. |
| Evidence report | `api-contract-report.json` with OpenAPI validation, resource fixture results, stale/missing report cases, and response envelope validation. |

Implementation notes:

- API resources are projections of canonical evidence. They must not create a second readiness
  engine.
- Every user-visible verdict must trace back to source report ids and sourceRefs.

### HATE-PG-007B Bundle import, export, authz, versioning

| Field | Required content |
|---|---|
| Epic | EPIC-007 API Read Model |
| Requirement refs | FR-APIX-002, FR-APIX-003, FR-APIX-004, FR-APIX-005, FR-APIX-006, FR-APIX-007, FR-APIX-008 |
| Acceptance refs | AC-REQ-004, AC-REQ-008, AC-REQ-014 |
| Affected paths | `src/hate/api/import_export.py`, `src/hate/api/authz.py`, `src/hate/api/versioning.py`, `schemas/HATE/v1/bundle-import-report.schema.json`, `schemas/HATE/v1/api-authz-decision.schema.json`, `fixtures/api/import-export/`, `tests/test_api_import_export_authz.py`, `docs/process/API_REQUIREMENTS.md`, `docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md` |
| Fixtures | `fixtures/api/import-export/idempotent-import/`, `fixtures/api/import-export/safe-export/`, `fixtures/api/import-export/version-compatible/`, `fixtures/api/import-export/tenant-scoped-read/`, `fixtures/api/import-export/redacted-artifact-export/` |
| Negative fixtures | `fixtures/api/import-export/cross-tenant-read/`, `fixtures/api/import-export/raw-secret-export/`, `fixtures/api/import-export/import-mutates-existing-bundle/`, `fixtures/api/import-export/unsupported-version/`, `fixtures/api/import-export/missing-entitlement/`, `fixtures/api/import-export/replay-unsafe-export/` |
| Schemas | Import report must define idempotency key, bundle id, accepted/rejected status, schema version, hash validation, authz decision, and sourceRefs. Authz decision schema must define actor, tenant, scopes, resource, decision, reason code, and redacted denial response. |
| Tests | Idempotent import returns same bundle id, import validates hashes, export never mutates canonical bundle, cross-tenant access denied without tenant leakage, secret export blocked, unsupported version error, entitlement denied, API version negotiation, denial response schema validation. |
| No-Go | Unauthorized response leaks tenant existence or restricted path; import overwrites canonical bundle; export includes quarantined raw artifacts; idempotency key ignored; unsupported version silently upgraded; authz decision is not auditable. |
| Evidence report | `api-contract-report.json` with import/export/authz/versioning sections and denied-case evidence. |

Implementation notes:

- Authz failures must be safe by default and auditable without leaking restricted details.
- Import/export is a product surface, not a gate override. It must not change readiness verdicts.

## 12. EPIC-008 Detailed Task Packets

EPIC-008 is the dashboard and UI workflow epic. It is complete only when the UI can display the
same readiness state as the reports/API, explain why each state exists, and handle missing,
stale, blocked, quarantined, and high-volume evidence without misleading the user.

### HATE-PG-008A Dashboard view models

| Field | Required content |
|---|---|
| Epic | EPIC-008 Dashboard and UI Workflow |
| Requirement refs | FR-UI-001, FR-UI-002, FR-UI-003, FR-UI-004, FR-UI-005, FR-UI-006, FR-UI-007, FR-UI-008, FR-UI-009, FR-UI-010 |
| Acceptance refs | AC-REQ-013, AC-REQ-014 |
| Affected paths | `src/hate/ui/view_models.py`, `src/hate/ui/dashboard_projection.py`, `schemas/HATE/v1/dashboard-view-model.schema.json`, `fixtures/ui/view-models/`, `tests/test_dashboard_view_models.py`, `docs/process/UI_WORKFLOW_REQUIREMENTS.md`, `docs/process/API_OPENAPI.yaml` |
| Fixtures | `fixtures/ui/view-models/product-ready/`, `fixtures/ui/view-models/hard-dq/`, `fixtures/ui/view-models/soft-gap/`, `fixtures/ui/view-models/manual-review-required/`, `fixtures/ui/view-models/quarantined-artifact/`, `fixtures/ui/view-models/stale-read-model/`, `fixtures/ui/view-models/high-volume-graph/` |
| Negative fixtures | `fixtures/ui/view-models/missing-required-report/`, `fixtures/ui/view-models/conflicting-verdicts/`, `fixtures/ui/view-models/raw-secret-in-view/`, `fixtures/ui/view-models/product-ready-with-hard-dq/`, `fixtures/ui/view-models/unbounded-graph-nodes/` |
| Schemas | Dashboard view model schema must define run overview, readiness badge, blockers, holds, soft gaps, risk matrix summary, graph page metadata, adapter health, artifact safety, manual review queue, release pack status, and support diagnostics. |
| Tests | Product-ready projection, hard DQ projection, soft gap projection, manual review queue projection, quarantined artifact hidden/redacted, stale read model warning, missing report blocker, conflicting verdict blocker, high-volume graph pagination, raw secret exclusion. |
| No-Go | UI computes readiness independently; product-ready badge appears with hard DQ or missing report; raw quarantined content is rendered; evidence graph renders all nodes at once; stale data lacks visible status; user cannot trace blocker to sourceRef. |
| Evidence report | `dashboard-uat-report.json` with view model fixture results, schema validation, redaction checks, and pagination checks. |

Implementation notes:

- The UI projection layer must be deterministic and API-compatible.
- The dashboard can summarize, filter, and page evidence, but it cannot reinterpret verdict rules.

### HATE-PG-008B UI state UAT fixtures

| Field | Required content |
|---|---|
| Epic | EPIC-008 Dashboard and UI Workflow |
| Requirement refs | FR-UI-001..010, FR-OBS-004, FR-SEC-005 |
| Acceptance refs | AC-REQ-004, AC-REQ-013, AC-REQ-017 |
| Affected paths | `fixtures/ui/uat-states/`, `tests/test_dashboard_uat_states.py`, `docs/process/UI_WORKFLOW_REQUIREMENTS.md`, `docs/process/MANUAL_BB_GATE_FULL_IMPLEMENTATION.md`, `docs/process/RUNBOOK.md` |
| Fixtures | `fixtures/ui/uat-states/new-run-processing/`, `fixtures/ui/uat-states/go-ready/`, `fixtures/ui/uat-states/no-go-hard-dq/`, `fixtures/ui/uat-states/hold-manual-review/`, `fixtures/ui/uat-states/security-quarantine/`, `fixtures/ui/uat-states/adapter-degraded/`, `fixtures/ui/uat-states/store-corruption/`, `fixtures/ui/uat-states/release-pack-ready/` |
| Negative fixtures | `fixtures/ui/uat-states/missing-copy-for-blocker/`, `fixtures/ui/uat-states/ambiguous-cta/`, `fixtures/ui/uat-states/leaks-restricted-path/`, `fixtures/ui/uat-states/empty-state-without-action/`, `fixtures/ui/uat-states/conflicting-status-labels/` |
| Schemas | UAT state manifest must define state id, required input reports, expected primary status, expected actions, forbidden text/content, required sourceRefs, and screenshot/checklist expectations. |
| Tests | Every state fixture validates, Go/No-Go/Hold labels match reports, blocker states include actionable next step, restricted paths/secrets absent, adapter degraded state points to conformance report, store corruption state points to doctor report, release pack state requires all reports. |
| No-Go | UI state lacks required sourceRefs; blocker has no actionable command/report link; restricted path or raw secret appears; empty state hides missing required report; visual state conflicts with report verdict. |
| Evidence report | `dashboard-uat-report.json` plus manual UAT checklist entries for screenshot-based or browser-based verification. |

Implementation notes:

- UAT fixtures should be usable before a real frontend exists. They define the states the frontend
  must render and the assertions the UAT harness must verify.
- Manual UAT remains evidence, but the expected states must be machine-readable.

## 13. EPIC-009 Detailed Task Packets

EPIC-009 is the RBAC, audit, retention, and legal control epic. It is complete only when
enterprise controls protect evidence access and lifecycle without weakening canonical readiness
or losing legal/audit traceability.

### HATE-PG-009A RBAC and audit hash chain

| Field | Required content |
|---|---|
| Epic | EPIC-009 RBAC, Audit, Retention, Legal |
| Requirement refs | FR-ENT-001, FR-ENT-002, FR-APIX-004 |
| Acceptance refs | AC-REQ-008, AC-REQ-011, AC-REQ-014 |
| Affected paths | `src/hate/enterprise/rbac.py`, `src/hate/enterprise/audit.py`, `schemas/HATE/v1/rbac-policy.schema.json`, `schemas/HATE/v1/audit-event.schema.json`, `fixtures/enterprise/rbac-audit/`, `tests/test_enterprise_rbac_audit.py`, `docs/process/DATA_RETENTION_LEGAL_REQUIREMENTS.md`, `docs/process/ENTERPRISE_DOMAIN_MODEL.md` |
| Fixtures | `fixtures/enterprise/rbac-audit/admin-read/`, `fixtures/enterprise/rbac-audit/auditor-read-redacted/`, `fixtures/enterprise/rbac-audit/developer-run-scope/`, `fixtures/enterprise/rbac-audit/support-safe-diagnostic/`, `fixtures/enterprise/rbac-audit/hash-chain-valid/` |
| Negative fixtures | `fixtures/enterprise/rbac-audit/cross-tenant-access/`, `fixtures/enterprise/rbac-audit/restricted-path-visible/`, `fixtures/enterprise/rbac-audit/missing-actor/`, `fixtures/enterprise/rbac-audit/hash-chain-break/`, `fixtures/enterprise/rbac-audit/privilege-escalation/` |
| Schemas | RBAC policy schema must define roles, scopes, tenant boundaries, resource classes, redaction profiles, and deny reason codes. Audit event schema must define actor, action, resource, decision, sourceRefs, previous hash, event hash, timestamp, and policy version. |
| Tests | Role permission matrix, tenant isolation, restricted path redaction, deny response no tenant leak, audit event generated for allow/deny/export/import, hash chain validation, hash chain break hard DQ, missing actor rejection. |
| No-Go | Unauthorized caller can infer tenant or restricted path; audit event lacks actor/sourceRefs/hash; deny decisions are not auditable; hash chain is optional; support role can access raw quarantined content by default. |
| Evidence report | `enterprise-control-report.json` with RBAC matrix results, audit hash-chain validation, denied-case evidence, and safe diagnostic access proof. |

Implementation notes:

- RBAC decisions must be used by API, UI, export, and support bundle flows.
- Audit is not best-effort logging. Enterprise control evidence depends on it.

### HATE-PG-009B Retention/legal hold/export/delete

| Field | Required content |
|---|---|
| Epic | EPIC-009 RBAC, Audit, Retention, Legal |
| Requirement refs | FR-ENT-003, FR-LIFE-005, FR-STO-001 |
| Acceptance refs | AC-REQ-008, AC-REQ-010, AC-REQ-018 |
| Affected paths | `src/hate/enterprise/retention.py`, `src/hate/enterprise/legal_hold.py`, `src/hate/enterprise/customer_export.py`, `schemas/HATE/v1/retention-policy.schema.json`, `schemas/HATE/v1/legal-hold.schema.json`, `fixtures/enterprise/retention/`, `tests/test_enterprise_retention_legal.py`, `docs/process/DATA_RETENTION_LEGAL_REQUIREMENTS.md`, `docs/process/RELEASE_MIGRATION_POLICY.md` |
| Fixtures | `fixtures/enterprise/retention/default-policy/`, `fixtures/enterprise/retention/legal-hold-active/`, `fixtures/enterprise/retention/customer-export-redacted/`, `fixtures/enterprise/retention/delete-expired-derived-view/`, `fixtures/enterprise/retention/migration-preserves-hold/` |
| Negative fixtures | `fixtures/enterprise/retention/legal-hold-bypass/`, `fixtures/enterprise/retention/delete-held-evidence/`, `fixtures/enterprise/retention/export-raw-quarantined-artifact/`, `fixtures/enterprise/retention/retention-policy-missing/`, `fixtures/enterprise/retention/migration-drops-hold/` |
| Schemas | Retention policy schema must define policy id, tenant, resource class, retention period, deletion mode, legal hold override, export profile, audit requirements, and effective dates. Legal hold schema must define hold id, owner, reason, sourceRefs, scope, created_at, expires_at or review_at, and migration behavior. |
| Tests | Default retention applied, legal hold blocks deletion, held evidence migration preservation, expired derived view deletion, customer export redaction, raw quarantined export blocked, missing retention policy hold, all actions audited. |
| No-Go | Legal hold bypass; held evidence deleted; migration loses legal hold; customer export leaks quarantined raw content; retention policy missing but action proceeds; delete/export action lacks audit event. |
| Evidence report | `enterprise-control-report.json` with retention/legal hold/export/delete sections and audit refs. |

Implementation notes:

- Legal hold overrides retention and delete flows.
- Export/delete operations must be represented as auditable lifecycle events, not filesystem-only
  side effects.

## 14. EPIC-010 Detailed Task Packets

EPIC-010 is the enterprise connector epic. It is complete only when external system integrations
can be dry-run, validated, and audited without making connector availability a readiness gate or
leaking credentials into evidence.

### HATE-PG-010A SSO/SCIM dry-run connectors

| Field | Required content |
|---|---|
| Epic | EPIC-010 Enterprise Connectors |
| Requirement refs | FR-ENT-004, FR-APIX-004, FR-OBS-004 |
| Acceptance refs | AC-REQ-009, AC-REQ-011 |
| Affected paths | `src/hate/connectors/sso.py`, `src/hate/connectors/scim.py`, `src/hate/connectors/dry_run.py`, `schemas/HATE/v1/connector-dry-run-report.schema.json`, `fixtures/connectors/sso-scim/`, `tests/test_connectors_sso_scim.py`, `docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md`, `docs/process/ENTERPRISE_DOMAIN_MODEL.md` |
| Fixtures | `fixtures/connectors/sso-scim/oidc-config-valid/`, `fixtures/connectors/sso-scim/saml-config-valid/`, `fixtures/connectors/sso-scim/scim-user-provision-preview/`, `fixtures/connectors/sso-scim/group-mapping-preview/`, `fixtures/connectors/sso-scim/disabled-connector-non-gating/` |
| Negative fixtures | `fixtures/connectors/sso-scim/missing-client-secret-redacted/`, `fixtures/connectors/sso-scim/invalid-issuer/`, `fixtures/connectors/sso-scim/scim-destructive-action/`, `fixtures/connectors/sso-scim/token-in-diagnostics/`, `fixtures/connectors/sso-scim/connector-failure-gates-readiness/` |
| Schemas | Connector dry-run report must define connector id, mode, enabled flag, configuration status, simulated actions, denied actions, redacted diagnostics, entitlement status, readiness effect, and audit event refs. |
| Tests | OIDC/SAML config dry-run, SCIM user/group preview, destructive SCIM action rejected, disabled connector non-gating, invalid issuer reported, missing secret redacted, token never appears in diagnostics, connector failure does not change readiness verdict. |
| No-Go | Connector failure changes product-ready/precheck verdict; token appears in diagnostic bundle; dry-run performs destructive action; SSO config is accepted without issuer/audience validation; disabled connector is reported as product failure. |
| Evidence report | `enterprise-control-report.json` with connector dry-run section and redacted diagnostics. |

Implementation notes:

- Dry-run means no external side effects. Network-backed validation can be added later only behind
  explicit configuration and redacted diagnostics.
- Connectors are enterprise enablement, not core readiness evidence.

### HATE-PG-010B SIEM/warehouse/ticket dry-run connectors

| Field | Required content |
|---|---|
| Epic | EPIC-010 Enterprise Connectors |
| Requirement refs | FR-ENT-004, FR-OBS-001, FR-OBS-004 |
| Acceptance refs | AC-REQ-009, AC-REQ-011, AC-REQ-017 |
| Affected paths | `src/hate/connectors/siem.py`, `src/hate/connectors/warehouse.py`, `src/hate/connectors/ticketing.py`, `schemas/HATE/v1/connector-dry-run-report.schema.json`, `fixtures/connectors/ops/`, `tests/test_connectors_ops.py`, `docs/process/SLO_INCIDENT_RESPONSE_CONTRACT.md`, `docs/process/PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` |
| Fixtures | `fixtures/connectors/ops/siem-event-preview/`, `fixtures/connectors/ops/warehouse-row-preview/`, `fixtures/connectors/ops/ticket-create-preview/`, `fixtures/connectors/ops/ticket-update-preview/`, `fixtures/connectors/ops/rate-limit-preview/` |
| Negative fixtures | `fixtures/connectors/ops/raw-secret-in-siem-event/`, `fixtures/connectors/ops/raw-code-in-warehouse-row/`, `fixtures/connectors/ops/ticket-with-restricted-path/`, `fixtures/connectors/ops/connector-timeout-gates-readiness/`, `fixtures/connectors/ops/unbounded-batch-export/` |
| Schemas | Ops connector dry-run records must define destination type, event/row/ticket preview, redaction profile, batch size, rate limit policy, retry policy, readiness effect, and audit refs. |
| Tests | SIEM preview redacted, warehouse row preview schema-valid, ticket preview includes safe blocker summary, restricted path omitted, timeout non-gating, unbounded batch rejected, rate limit policy applied, connector diagnostics redacted. |
| No-Go | Connector timeout blocks readiness; SIEM/warehouse/ticket preview leaks raw secrets or restricted paths; batch export is unbounded; retry policy can duplicate external side effects in dry-run; connector report lacks audit refs. |
| Evidence report | `enterprise-control-report.json` with SIEM/warehouse/ticket dry-run results and redaction proof. |

Implementation notes:

- These connectors must consume safe summaries and redacted projections from EPIC-005/007.
- A connector can report degraded integration health without changing the product readiness verdict.

## 15. EPIC-011 Detailed Task Packets

EPIC-011 is the scale and performance epic. It is complete only when large evidence inputs,
high-cardinality graphs, matrix runs, and dashboard/API projections can be generated and measured
without unbounded memory use or misleading readiness claims.

### HATE-PG-011A Large fixture generator

| Field | Required content |
|---|---|
| Epic | EPIC-011 Scale and Performance |
| Requirement refs | FR-SCALE-001, FR-SCALE-002, FR-SCALE-003, FR-SCALE-004, FR-SCALE-005, FR-SCALE-006 |
| Acceptance refs | AC-REQ-016 |
| Affected paths | `tools/generate_scale_fixtures.py`, `src/hate/scale/fixture_generator.py`, `schemas/HATE/v1/scale-fixture-manifest.schema.json`, `fixtures/scale/`, `tests/test_scale_fixture_generator.py`, `docs/process/SCALE_PERFORMANCE_REQUIREMENTS.md` |
| Fixtures | `fixtures/scale/small-1k/`, `fixtures/scale/medium-100k/`, `fixtures/scale/large-500k-manifest/`, `fixtures/scale/matrix-shards/`, `fixtures/scale/high-cardinality-graph/` |
| Negative fixtures | `fixtures/scale/missing-generator-manifest/`, `fixtures/scale/non-deterministic-output/`, `fixtures/scale/pathological-long-test-name/`, `fixtures/scale/oversized-single-artifact/`, `fixtures/scale/unbounded-edge-fanout/` |
| Schemas | Scale fixture manifest must define seed, target record counts, generated artifact ids, expected hashes, shard counts, graph cardinality, max artifact size, and generation profile. |
| Tests | Deterministic generation by seed, manifest hash validation, 1k smoke fixture, 100k CI-budget fixture, 500k manifest-only proof, shard consistency, pathological input guard, schema validation. |
| No-Go | Large fixture is hand-maintained; generator output is nondeterministic; fixture lacks manifest/hash evidence; generator emits unbounded fanout; performance claims are made without reproducible fixture profile. |
| Evidence report | `scale-performance-report.json` with fixture profile, generated counts, hashes, resource estimates, and skipped-large-case reason when CI uses manifest-only proof. |

### HATE-PG-011B Performance budget runner

| Field | Required content |
|---|---|
| Epic | EPIC-011 Scale and Performance |
| Requirement refs | FR-SCALE-001..006, NFR-002, NFR-003 |
| Acceptance refs | AC-REQ-016, AC-REQ-017 |
| Affected paths | `src/hate/scale/budget_runner.py`, `src/hate/scale/metrics.py`, `schemas/HATE/v1/scale-performance-report.schema.json`, `fixtures/scale/performance/`, `tests/test_scale_performance.py`, `.github/workflows/ci.yml`, `docs/process/SCALE_PERFORMANCE_REQUIREMENTS.md` |
| Fixtures | `fixtures/scale/performance/parser-streaming/`, `fixtures/scale/performance/api-pagination/`, `fixtures/scale/performance/dashboard-aggregation/`, `fixtures/scale/performance/store-replay/`, `fixtures/scale/performance/matrix-aggregation/` |
| Negative fixtures | `fixtures/scale/performance/unbounded-memory-load/`, `fixtures/scale/performance/all-graph-nodes-rendered/`, `fixtures/scale/performance/cache-stale-after-import/`, `fixtures/scale/performance/timeout-no-partial-report/` |
| Schemas | Performance report must define scenario id, dataset profile, duration, peak memory, record throughput, page latency, cache hit/miss, threshold, result, and source fixture manifest. |
| Tests | Streaming parser stays within memory budget, API pagination threshold, dashboard aggregation threshold, store replay threshold, matrix aggregation threshold, timeout emits partial diagnostic, stale cache rejected. |
| No-Go | Full input loaded into memory for required large cases; all graph nodes rendered at once; timeout loses diagnostics; stale cache is served as fresh; performance report lacks threshold comparison. |
| Evidence report | `scale-performance-report.json` generated in CI for small/medium budgets and optionally offline for 500k-class profiles. |

## 16. EPIC-012 Detailed Task Packets

EPIC-012 is the observability and support operations epic. It is complete only when failures are
diagnosable with stable redacted logs, metrics, alerts, safe bundles, and user-facing error codes.

### HATE-PG-012A Structured logs, metrics, alerts

| Field | Required content |
|---|---|
| Epic | EPIC-012 Observability and Support Ops |
| Requirement refs | FR-OBS-001, FR-OBS-002, FR-OBS-003 |
| Acceptance refs | AC-REQ-011, AC-REQ-017 |
| Affected paths | `src/hate/observability/logging.py`, `src/hate/observability/metrics.py`, `src/hate/observability/alerts.py`, `schemas/HATE/v1/support-ops-report.schema.json`, `fixtures/observability/`, `tests/test_observability.py`, `docs/process/SLO_INCIDENT_RESPONSE_CONTRACT.md` |
| Fixtures | `fixtures/observability/normal-run/`, `fixtures/observability/hard-dq-alert/`, `fixtures/observability/adapter-degraded-alert/`, `fixtures/observability/store-corruption-alert/`, `fixtures/observability/slo-breach/` |
| Negative fixtures | `fixtures/observability/raw-secret-log/`, `fixtures/observability/missing-correlation-id/`, `fixtures/observability/cardinality-explosion/`, `fixtures/observability/alert-without-run-id/` |
| Schemas | Support ops report must define run id, correlation id, event classes, metrics, SLO result, alert class, severity, redaction status, sourceRefs, and remediation links. |
| Tests | Structured log schema, correlation id propagation, metrics emission, SLO breach alert, adapter degraded alert, store corruption alert, secret redaction, high-cardinality metric rejection. |
| No-Go | Logs contain raw customer code/secret/PII; alerts lack run id; metrics allow unbounded labels; SLO breach is warning-only; support report lacks remediation link. |
| Evidence report | `support-ops-report.json` with logs/metrics/alerts/SLO sections and redaction proof. |

### HATE-PG-012B Safe diagnostic and error catalog

| Field | Required content |
|---|---|
| Epic | EPIC-012 Observability and Support Ops |
| Requirement refs | FR-OBS-004, FR-OBS-005, FR-OPS-001, FR-OPS-002, FR-OPS-003, FR-OPS-004 |
| Acceptance refs | AC-REQ-011, AC-REQ-017 |
| Affected paths | `src/hate/observability/diagnostics.py`, `src/hate/observability/error_catalog.py`, `schemas/HATE/v1/error-catalog.schema.json`, `schemas/HATE/v1/safe-diagnostic-bundle.schema.json`, `fixtures/observability/diagnostics/`, `tests/test_safe_diagnostics.py`, `docs/process/PRODUCT_ERROR_TAXONOMY.md`, `docs/process/RUNBOOK.md` |
| Fixtures | `fixtures/observability/diagnostics/adapter-failure/`, `fixtures/observability/diagnostics/schema-dq/`, `fixtures/observability/diagnostics/store-corruption/`, `fixtures/observability/diagnostics/support-safe-bundle/`, `fixtures/observability/diagnostics/known-issue-link/` |
| Negative fixtures | `fixtures/observability/diagnostics/raw-artifact-in-bundle/`, `fixtures/observability/diagnostics/error-without-code/`, `fixtures/observability/diagnostics/missing-remediation/`, `fixtures/observability/diagnostics/unredacted-stacktrace/` |
| Schemas | Error catalog schema must define stable error code, class, severity, user message, operator message, remediation, retryability, related reports, and safe diagnostic fields. |
| Tests | Stable error code lookup, safe bundle generation, raw artifact exclusion, redacted stack traces, known issue links, retryability classification, missing remediation rejected, schema validation. |
| No-Go | User-facing failure lacks stable error code; support bundle contains raw customer code/secret/PII; diagnostic bundle can alter verdict; error catalog entry has no remediation or owner. |
| Evidence report | `support-ops-report.json` plus `safe-diagnostic-bundle.json` for support workflows. |

## 17. EPIC-013 Detailed Task Packets

EPIC-013 is the migration and compatibility epic. It is complete only when old bundles,
schemas, API versions, profiles, adapters, view models, and legal-hold metadata can be migrated
or rejected with explicit compatibility evidence.

### HATE-PG-013A Schema/store/API/profile migration fixtures

| Field | Required content |
|---|---|
| Epic | EPIC-013 Migration and Compatibility |
| Requirement refs | FR-LIFE-001, FR-LIFE-002, FR-LIFE-003, FR-LIFE-004 |
| Acceptance refs | AC-REQ-018 |
| Affected paths | `src/hate/migration/schema.py`, `src/hate/migration/store.py`, `src/hate/migration/api.py`, `src/hate/migration/profile.py`, `schemas/HATE/v1/migration-compatibility-report.schema.json`, `fixtures/migration/`, `tests/test_migration_compatibility.py`, `docs/process/RELEASE_MIGRATION_POLICY.md` |
| Fixtures | `fixtures/migration/schema-minor-upgrade/`, `fixtures/migration/store-index-rebuild/`, `fixtures/migration/api-version-alias/`, `fixtures/migration/profile-threshold-change/`, `fixtures/migration/adapter-manifest-upgrade/`, `fixtures/migration/view-model-upgrade/` |
| Negative fixtures | `fixtures/migration/unsupported-major-version/`, `fixtures/migration/destructive-schema-change/`, `fixtures/migration/old-bundle-unreadable/`, `fixtures/migration/profile-silent-verdict-change/`, `fixtures/migration/missing-rollback-plan/` |
| Schemas | Migration report must define source version, target version, migrated artifacts, compatibility class, verdict effect, rollback plan, checksum before/after, warnings, blockers, and sourceRefs. |
| Tests | Minor schema migration, store index rebuild, API version alias, profile threshold explicit verdict effect, adapter/view-model migration, unsupported major version hold/block, rollback plan required, checksum stability. |
| No-Go | Old bundles unreadable after minor upgrade; migration silently changes verdict; rollback plan missing; destructive schema change accepted; migration report lacks before/after hashes. |
| Evidence report | `migration-compatibility-report.json` with per-fixture compatibility status and verdict-effect summary. |

### HATE-PG-013B Legal hold preserving migration

| Field | Required content |
|---|---|
| Epic | EPIC-013 Migration and Compatibility |
| Requirement refs | FR-LIFE-005, FR-ENT-003 |
| Acceptance refs | AC-REQ-008, AC-REQ-018 |
| Affected paths | `src/hate/migration/legal_hold.py`, `src/hate/enterprise/legal_hold.py`, `schemas/HATE/v1/legal-hold.schema.json`, `fixtures/migration/legal-hold/`, `tests/test_migration_legal_hold.py`, `docs/process/DATA_RETENTION_LEGAL_REQUIREMENTS.md`, `docs/process/RELEASE_MIGRATION_POLICY.md` |
| Fixtures | `fixtures/migration/legal-hold/active-hold-preserved/`, `fixtures/migration/legal-hold/expired-hold-review/`, `fixtures/migration/legal-hold/tenant-scoped-hold/`, `fixtures/migration/legal-hold/export-after-migration/` |
| Negative fixtures | `fixtures/migration/legal-hold/hold-dropped/`, `fixtures/migration/legal-hold/held-evidence-deleted/`, `fixtures/migration/legal-hold/scope-expanded/`, `fixtures/migration/legal-hold/audit-chain-broken/` |
| Schemas | Legal-hold migration output must preserve hold id, scope, owner, reason, sourceRefs, audit chain refs, effective dates, and migrated artifact hashes. |
| Tests | Active hold preserved, held evidence cannot be deleted, scope not expanded, audit chain continuity, export remains redacted, expired hold requires review, migration report links enterprise-control evidence. |
| No-Go | Legal hold lost during migration; held evidence deleted; hold scope silently expands; audit chain broken; export after migration bypasses redaction. |
| Evidence report | `migration-compatibility-report.json` and `enterprise-control-report.json` legal hold migration sections. |

## 18. EPIC-014 Detailed Task Packets

EPIC-014 is the release candidate and assurance pack epic. It is complete only when a release can
be blocked or accepted from a deterministic pack that references every required evidence report.

### HATE-PG-014A Release candidate pack validator

| Field | Required content |
|---|---|
| Epic | EPIC-014 Release Candidate and Assurance Pack |
| Requirement refs | FR-OPS-001, FR-OPS-002, FR-OPS-003, FR-ENT-001, FR-ENT-003 |
| Acceptance refs | AC-REQ-010, AC-REQ-012, AC-REQ-014 |
| Affected paths | `src/hate/release/pack.py`, `src/hate/release/validator.py`, `schemas/HATE/v1/release-candidate-pack.schema.json`, `fixtures/release/`, `tests/test_release_candidate_pack.py`, `docs/process/ACCEPTANCE_CRITERIA_MATRIX.md`, `docs/process/FULL_IMPLEMENTATION_SPEC_READINESS_CONTRACT.md` |
| Fixtures | `fixtures/release/all-reports-ready/`, `fixtures/release/manual-review-approved/`, `fixtures/release/commercial-claims-clean/`, `fixtures/release/qeg-referenced/`, `fixtures/release/evidence-room-safe/` |
| Negative fixtures | `fixtures/release/missing-required-report/`, `fixtures/release/open-hard-dq/`, `fixtures/release/open-manual-review/`, `fixtures/release/unsupported-commercial-claim/`, `fixtures/release/qeg-approval-claimed/`, `fixtures/release/quarantined-artifact-exported/` |
| Schemas | Release candidate pack schema must define release id, source version, required reports, report hashes, verdict, blockers, manual review state, commercial claim state, QEG refs, evidence room manifest, and sign-off metadata. |
| Tests | All reports ready pass, missing report blocker, open hard DQ blocker, open manual review blocker, unsupported claim blocker, QEG referenced but not claimed, evidence room redaction, deterministic pack hash. |
| No-Go | Missing report ignored; HATE claims QEG approval; open hard DQ/manual review accepted; unsupported commercial claim hidden; evidence room contains quarantined raw artifact; pack hash nondeterministic. |
| Evidence report | `release-candidate-pack.json` with required report checklist, blocker summary, hashes, and sign-off state. |

## 19. EPIC-015 Detailed Task Packets

EPIC-015 is the commercial truthfulness epic. It is complete only when product, sales, README,
release, API, and procurement claims are inventoried and blocked when unsupported by implemented
evidence.

### HATE-PG-015A Commercial claim inventory and blocker

| Field | Required content |
|---|---|
| Epic | EPIC-015 Commercial Truthfulness |
| Requirement refs | FR-OPS-005, FR-OPS-006 |
| Acceptance refs | AC-REQ-012, AC-REQ-010 |
| Affected paths | `src/hate/commercial/claims.py`, `src/hate/commercial/blocker.py`, `schemas/HATE/v1/commercial-truthfulness-report.schema.json`, `fixtures/commercial/`, `tests/test_commercial_truthfulness.py`, `README.md`, `docs/process/LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md`, `docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md` |
| Fixtures | `fixtures/commercial/implemented-claim/`, `fixtures/commercial/planned-claim-labeled/`, `fixtures/commercial/unsupported-claim-blocked/`, `fixtures/commercial/procurement-response/`, `fixtures/commercial/release-note-claim/` |
| Negative fixtures | `fixtures/commercial/planned-shown-as-available/`, `fixtures/commercial/unsupported-hidden/`, `fixtures/commercial/no-source-contract-ref/`, `fixtures/commercial/claim-contradicts-release-pack/`, `fixtures/commercial/enterprise-feature-without-entitlement-note/` |
| Schemas | Commercial truthfulness report must define claim id, claim text, surface, status, source contract refs, implementation refs, evidence report refs, release eligibility, blocker state, and procurement response text. |
| Tests | Implemented claim accepted, planned claim clearly labeled, unsupported claim blocks release, missing source contract ref hold, contradiction with release pack blocker, entitlement caveat required, procurement response generated from claim inventory. |
| No-Go | Planned capability shown as available; unsupported claim hidden from release pack; claim has no source contract ref; procurement response overstates readiness; README/release notes contradict evidence reports. |
| Evidence report | `commercial-truthfulness-report.json` consumed by `release-candidate-pack.json`. |

## 20. Two-Pass Epic Revision Matrix

This section records the second pass over every epic. A task packet is not ready for implementation
handoff until both passes are satisfied:

- Pass 1 creation: packet exists with affected paths, fixtures, negative fixtures, schemas, tests,
  No-Go, and evidence report.
- Pass 2 revision: packet has been checked against cross-epic integration, CI/UAT evidence,
  sourceRef traceability, security/privacy, scale, lifecycle, and refactoring constraints.

| Epic | Pass 1 creation evidence | Pass 2 revision requirement |
|---|---|---|
| EPIC-001 Adapter Corpus and SDK | HATE-PG-001A..001D detailed packets exist. | Verify adapter outputs feed EPIC-002 schemas, EPIC-003 graph, EPIC-004 integrity, EPIC-005 quarantine, and EPIC-011 scale fixtures. No adapter packet may depend on `p0a_support.py` staying monolithic. |
| EPIC-002 Cross-Record Schema and Validator | HATE-PG-002A..002B detailed packets exist. | Verify every schema failure has deterministic rejection class, sourceRef, fixture id, CI report entry, and replay compatibility hook for EPIC-006/013. |
| EPIC-003 Evidence Graph and Risk Coverage | HATE-PG-003A..003B detailed packets exist. | Verify no readiness claim can bypass graph edges, risk matrix, manual review owner/expiry, or unsupported claim handling consumed by EPIC-014/015. |
| EPIC-004 Test Integrity and AI-Abuse Detector | HATE-PG-004A..004C detailed packets exist. | Verify skip/mock/assertion/coupling findings influence readiness through EPIC-003 and cannot be reduced to warning-only in product/release profile. |
| EPIC-005 Artifact Safety and Privacy | HATE-PG-005A..005B detailed packets exist. | Verify API, UI, support bundle, connector, and release pack surfaces consume safe projections only and never raw quarantined artifacts. |
| EPIC-006 Local Store, Replay, Compare | HATE-PG-006A..006B detailed packets exist. | Verify canonical evidence is immutable, replay is deterministic, compare uses explicit baseline evidence, and migration/legal-hold hooks feed EPIC-013. |
| EPIC-007 API Read Model | HATE-PG-007A..007B detailed packets exist. | Verify API never computes independent verdicts, uses report refs/sourceRefs, applies RBAC, exposes stale/missing states, and respects versioning. |
| EPIC-008 Dashboard and UI Workflow | HATE-PG-008A..008B detailed packets exist. | Verify UI view models are projections of API/reports, support all Go/Hold/No-Go/quarantine/stale states, and include sourceRefs/actionable next steps. |
| EPIC-009 RBAC, Audit, Retention, Legal | HATE-PG-009A..009B detailed packets exist. | Verify RBAC/audit decisions cover API/UI/export/support flows and legal hold overrides retention, delete, migration, and customer export. |
| EPIC-010 Enterprise Connectors | HATE-PG-010A..010B detailed packets exist. | Verify connectors are dry-run/non-gating by default, redacted, audited, bounded, and cannot leak tokens or raw evidence into diagnostics. |
| EPIC-011 Scale and Performance | HATE-PG-011A..011B detailed packets exist. | Verify 500k-class scale is represented by reproducible generator/manifests and CI budgets distinguish smoke, medium, and offline large profiles. |
| EPIC-012 Observability and Support Ops | HATE-PG-012A..012B detailed packets exist. | Verify every blocking class has stable error code, redacted diagnostics, remediation link, metrics/alert coverage, and safe support bundle behavior. |
| EPIC-013 Migration and Compatibility | HATE-PG-013A..013B detailed packets exist. | Verify old bundles remain readable or explicitly blocked, verdict-changing migrations are visible, rollback exists, and legal hold/audit survive. |
| EPIC-014 Release Candidate and Assurance Pack | HATE-PG-014A detailed packet exists. | Verify release pack consumes all required evidence reports, blocks missing reports/open DQ/manual review/unsupported claims, and does not claim QEG approval. |
| EPIC-015 Commercial Truthfulness | HATE-PG-015A detailed packet exists. | Verify README, release, API, procurement, entitlement, and sales claims map to implemented evidence or are labeled planned/unsupported and release-blocking. |

Second-pass global No-Go:

- Any packet lacks negative fixtures or hard failure cases.
- Any packet lacks an evidence report consumed by CI, UAT, release pack, or another downstream epic.
- Any packet can make product-ready true without sourceRefs.
- Any packet introduces raw secret/PII/restricted-path exposure on API, UI, support, connector, or release surfaces.
- Any packet depends on hand-written Python modules exceeding the `REFACTORING_PLAN.md` thresholds.
- Any packet allows HATE to override QEG/Shipyard/RanD/manual-bb verdicts instead of referencing them.
