---
intent_id: INT-HATE-IMPLEMENTATION-EPIC-BREAKDOWN-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Implementation Epic Breakdown

## 1. Purpose

This document decomposes HATE product requirements into implementation epics suitable for
Shipyard/GLM worker packets. It is not a completion claim. Each epic must be split into tasks
with code, schema, fixtures, tests, docs, CI, UAT, and evidence reports.

Refactoring constraint: implementation must follow `REFACTORING_PLAN.md`. Hand-written Python
source files should be split before 900 lines, and no new product-grade work should push a
hand-written source module to 1000 lines.

Epic specification two-pass completion and third-pass dependency review are tracked in
`EPIC_TWO_PASS_COMPLETION_AUDIT.md`.

GLM worker dispatch, revision loops, acceptance commands, and Codex UAT responsibilities are
defined in `GLM_IMPLEMENTATION_DISPATCH_PACK.md`.

## 2. Epic Status Model

| Status | Meaning |
|---|---|
| specified | requirements and acceptance exist |
| designed | data/API/UI/state design exists |
| implemented | production code exists and is reachable |
| verified | automated tests and CI evidence pass |
| accepted | UAT/manual-bb/product evidence report pass |
| blocked | external dependency or unresolved contradiction |

No epic may skip from specified to accepted.

## 3. Epic List

| Epic ID | Title | Requirement refs | Primary docs | Evidence report |
|---|---|---|---|---|
| EPIC-001 | Adapter Corpus and SDK | FR-ING, FR-ADP, AC-REQ-015 | PRODUCT_REQUIREMENTS, API_REQUIREMENTS | adapter-conformance-report |
| EPIC-002 | Cross-Record Schema and Validator | FR-ING, FR-GRAPH, NFR-007 | SPECIFICATION, SCHEMA_REGISTRY_CONTRACT | schema-validation-report |
| EPIC-003 | Evidence Graph and Risk Coverage | FR-GRAPH, AC-REQ-002 | USER_STORY_MAP, PRODUCT_GRADE_IMPLEMENTATION_SPEC | product-readiness-report |
| EPIC-004 | Test Integrity and AI-Abuse Detector | FR-TI, AC-REQ-003 | PRODUCT_GRADE_IMPLEMENTATION_SPEC | test-integrity-report |
| EPIC-005 | Artifact Safety and Privacy | FR-SEC, AC-REQ-004 | DATA_RETENTION_LEGAL_REQUIREMENTS | security-quarantine-report |
| EPIC-006 | Local Store, Replay, Compare | FR-STO, AC-REQ-006 | PRODUCT_REQUIREMENTS, SCALE_PERFORMANCE_REQUIREMENTS | store-replay-report |
| EPIC-007 | API Read Model | FR-API, FR-APIX, AC-REQ-014 | API_REQUIREMENTS | api-contract-report |
| EPIC-008 | Dashboard and UI Workflow | FR-UI, AC-REQ-013 | UI_WORKFLOW_REQUIREMENTS | dashboard-uat-report |
| EPIC-009 | RBAC, Audit, Retention, Legal | FR-ENT, DRL, AC-REQ-008 | DATA_RETENTION_LEGAL_REQUIREMENTS | enterprise-control-report |
| EPIC-010 | Enterprise Connectors | FR-ENT, AC-REQ-009 | API_REQUIREMENTS, DATA_RETENTION_LEGAL_REQUIREMENTS | enterprise-control-report |
| EPIC-011 | Scale and Performance | FR-SCALE, NFR-002/003, AC-REQ-016 | SCALE_PERFORMANCE_REQUIREMENTS | scale-performance-report |
| EPIC-012 | Observability and Support Ops | FR-OBS, FR-OPS, AC-REQ-011/017 | DATA_RETENTION_LEGAL_REQUIREMENTS | support-ops-report |
| EPIC-013 | Migration and Compatibility | FR-LIFE, AC-REQ-018 | SCALE_PERFORMANCE_REQUIREMENTS | migration-compatibility-report |
| EPIC-014 | Release Candidate and Assurance Pack | FR-OPS, FR-ENT, AC-REQ-010 | ACCEPTANCE_CRITERIA_MATRIX | release-candidate-pack |
| EPIC-015 | Commercial Truthfulness | FR-OPS-005/006, AC-REQ-012 | DATA_RETENTION_LEGAL_REQUIREMENTS | commercial-truthfulness-report |

## 4. Epic Details

### EPIC-001 Adapter Corpus and SDK

Worker packets:

- `EPIC_TASK_PACKETS.md#5-epic-001-detailed-task-packets`
- `HATE-PG-001A` Adapter SDK interfaces and manifest schema
- `HATE-PG-001B` JUnit dialect parser corpus
- `HATE-PG-001C` Coverage dialect parser corpus
- `HATE-PG-001D` SARIF/Pact/Stryker parser corpus

Required deliverables:

- parser interfaces
- adapter manifests
- dialect fixture matrix
- malformed/partial/unsupported fixtures
- capability report
- conformance runner
- adapter enablement policy

No-Go:

- one happy path fixture per adapter
- hidden optional parser failure
- unsupported dialect reported as success

### EPIC-002 Cross-Record Schema and Validator

Worker packets:

- `EPIC_TASK_PACKETS.md#6-epic-002-detailed-task-packets`
- `HATE-PG-002A` Common envelope validator
- `HATE-PG-002B` Cross-record sourceRef/hash validator

Required deliverables:

- common envelope validator
- record-specific schemas
- cross-record sourceRef/hash/ref validator
- invalid fixture corpus
- compatibility/migration hooks

No-Go:

- schema-valid artifact with broken sourceRefs accepted as clean
- generated expected files hand-edited without regeneration evidence

### EPIC-003 Evidence Graph and Risk Coverage

Worker packets:

- `EPIC_TASK_PACKETS.md#7-epic-003-detailed-task-packets`
- `HATE-PG-003A` Evidence graph node/edge model
- `HATE-PG-003B` Risk coverage matrix and manual request bridge

Required deliverables:

- requirement/risk/test/execution/coverage/finding/artifact/manual nodes
- requires_test/executed_by/covered_by/supported_by/contradicted_by edges
- risk coverage matrix
- unsupported claim handling
- manual-bb request generation

No-Go:

- coverage-only edge treated as execution
- high/critical risk hidden below low-risk warnings

### EPIC-004 Test Integrity and AI-Abuse Detector

Worker packets:

- `EPIC_TASK_PACKETS.md#8-epic-004-detailed-task-packets`
- `HATE-PG-004A` Skip/focus/todo detector
- `HATE-PG-004B` Mock abuse and assertion quality detector
- `HATE-PG-004C` Test coupling and manual review detector

Required deliverables:

- skip/xfail/only/todo detector
- mock abuse detector
- assertion quality detector
- implementation-test coupling detector
- risk_without_oracle detector
- coverage_without_evidence detector
- manual review routing and record validation

No-Go:

- HATE synthesizes human review record
- `only` focused test is warning-only in release/product profile

### EPIC-005 Artifact Safety and Privacy

Worker packets:

- `EPIC_TASK_PACKETS.md#9-epic-005-detailed-task-packets`
- `HATE-PG-005A` Secret/PII/path/archive/external URL scanners
- `HATE-PG-005B` Redaction and summary/export safety filter

Required deliverables:

- secret/PII/path/archive/external URL/redaction scanners
- quarantine report
- summary/export/dashboard safety filters
- safe diagnostic bundle filter

No-Go:

- failed redaction exported
- restricted artifact path visible to unauthorized caller

### EPIC-006 Local Store, Replay, Compare

Worker packets:

- `EPIC_TASK_PACKETS.md#10-epic-006-detailed-task-packets`
- `HATE-PG-006A` Immutable local store and indexes
- `HATE-PG-006B` Replay/compare/corruption doctor

Required deliverables:

- immutable bundle store
- atomic write
- indexes
- replay
- compare
- corruption doctor
- migration hooks

No-Go:

- external export mutates canonical bundle
- baseline resolution based only on filename sorting

### EPIC-007 API Read Model

Worker packets:

- `EPIC_TASK_PACKETS.md#11-epic-007-detailed-task-packets`
- `HATE-PG-007A` API envelope and read resources
- `HATE-PG-007B` Bundle import, export, authz, versioning

Required deliverables:

- resource handlers
- response envelope
- authz middleware
- pagination/filter/sort
- idempotent bundle import
- non-gating export workflow
- API contract tests

No-Go:

- unauthorized response leaks tenant existence or restricted path
- stale read model returned as fresh

### EPIC-008 Dashboard and UI Workflow

Worker packets:

- `EPIC_TASK_PACKETS.md#12-epic-008-detailed-task-packets`
- `HATE-PG-008A` Dashboard view models
- `HATE-PG-008B` UI state UAT fixtures

Required deliverables:

- run overview
- risk coverage
- evidence graph
- adapter health
- artifact safety
- doctor
- risk debt
- release pack
- admin console
- support triage

No-Go:

- UI computes verdict independently
- product-ready badge appears with missing required report

### EPIC-009 RBAC, Audit, Retention, Legal

Worker packets:

- `EPIC_TASK_PACKETS.md#13-epic-009-detailed-task-packets`
- `HATE-PG-009A` RBAC and audit hash chain
- `HATE-PG-009B` Retention/legal hold/export/delete

Required deliverables:

- role/permission/scope matrix
- audit hash chain
- retention policy engine
- legal hold
- customer export/delete
- evidence room safety rules

No-Go:

- legal hold bypass
- audit event missing actor/sourceRefs/hash

### EPIC-010 Enterprise Connectors

Worker packets:

- `EPIC_TASK_PACKETS.md#14-epic-010-detailed-task-packets`
- `HATE-PG-010A` SSO/SCIM dry-run connectors
- `HATE-PG-010B` SIEM/warehouse/ticket dry-run connectors

Required deliverables:

- SSO/SCIM dry-run
- SIEM export dry-run
- warehouse export dry-run
- ticketing export dry-run
- connector failure non-gating proof

No-Go:

- connector failure changes precheck/QEG bundle
- connector token appears in diagnostic bundle

### EPIC-011 Scale and Performance

Worker packets:

- `EPIC_TASK_PACKETS.md#15-epic-011-detailed-task-packets`
- `HATE-PG-011A` Large fixture generator
- `HATE-PG-011B` Performance budget runner

Required deliverables:

- large fixture generator
- streaming/chunked parser proof
- API pagination performance
- dashboard high-volume aggregation
- shard/matrix aggregation
- cache invalidation
- resource limits

No-Go:

- unbounded memory load of coverage/test/artifact input
- all graph nodes rendered at once

### EPIC-012 Observability and Support Ops

Worker packets:

- `EPIC_TASK_PACKETS.md#16-epic-012-detailed-task-packets`
- `HATE-PG-012A` Structured logs, metrics, alerts
- `HATE-PG-012B` Safe diagnostic and error catalog

Required deliverables:

- structured redacted logs
- metrics
- alert classes
- safe diagnostic bundle
- error catalog
- known issue/migration/rollback links

No-Go:

- support bundle contains raw customer code/secret/PII
- user-facing failure lacks stable error code

### EPIC-013 Migration and Compatibility

Worker packets:

- `EPIC_TASK_PACKETS.md#17-epic-013-detailed-task-packets`
- `HATE-PG-013A` Schema/store/API/profile migration fixtures
- `HATE-PG-013B` Legal hold preserving migration

Required deliverables:

- compatibility matrix
- schema migration fixture
- store migration fixture
- API/version migration fixture
- profile/adapter/view-model migration fixture
- rollback plan

No-Go:

- old bundles unreadable after minor upgrade
- legal hold lost during migration

### EPIC-014 Release Candidate and Assurance Pack

Worker packets:

- `EPIC_TASK_PACKETS.md#18-epic-014-detailed-task-packets`
- `HATE-PG-014A` Release candidate pack validator

Required deliverables:

- release candidate pack validator
- required report checklist
- QEG result refs
- open hard DQ/manual review/unsupported claim detection
- assurance evidence room

No-Go:

- missing report ignored
- HATE claims QEG approval

### EPIC-015 Commercial Truthfulness

Worker packets:

- `EPIC_TASK_PACKETS.md#19-epic-015-detailed-task-packets`
- `HATE-PG-015A` Commercial claim inventory and blocker

Required deliverables:

- claim inventory
- implemented/planned/unsupported/exception status
- source contract refs
- procurement response
- unsupported claim blocker

No-Go:

- planned capability shown as available
- unsupported claim hidden from release pack

## 5. Worker Packet Template

Each epic task packet must include:

```yaml
task_id: string
epic_id: string
requirement_refs: array
acceptance_refs: array
affected_paths: array
input_fixtures: array
expected_outputs: array
negative_fixtures: array
schema_refs: array
commands: array
uat_checks: array
no_go_conditions: array
evidence_report: string
```

## 6. Implementation Order

1. EPIC-001 Adapter Corpus and SDK
2. EPIC-002 Cross-Record Schema and Validator
3. EPIC-003 Evidence Graph and Risk Coverage
4. EPIC-005 Artifact Safety and Privacy
5. EPIC-004 Test Integrity and AI-Abuse Detector
6. EPIC-006 Local Store, Replay, Compare
7. EPIC-011 Scale and Performance
8. EPIC-007 API Read Model
9. EPIC-008 Dashboard and UI Workflow
10. EPIC-009 RBAC, Audit, Retention, Legal
11. EPIC-010 Enterprise Connectors
12. EPIC-012 Observability and Support Ops
13. EPIC-013 Migration and Compatibility
14. EPIC-015 Commercial Truthfulness
15. EPIC-014 Release Candidate and Assurance Pack

Order changes require updating `PRODUCT_REQUIREMENTS_DEFINITION.md`,
`ACCEPTANCE_CRITERIA_MATRIX.md`, and this document.
