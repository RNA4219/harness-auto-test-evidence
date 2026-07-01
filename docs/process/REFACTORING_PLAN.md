---
intent_id: INT-HATE-REFACTORING-PLAN-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Refactoring Plan

## 1. Purpose

This plan prevents HATE from becoming a large but brittle product. The target is not simply more
lines. The target is a product-grade codebase where adapter logic, schema validation, graph
construction, reports, CLI commands, fixtures, and tests can grow without producing 1000-line
modules or unreadable specification files.

## 2. File Size Policy

| Class | Warning threshold | Hard threshold | Policy |
|---|---:|---:|---|
| Python source module | 700 lines | 900 lines | Split before adding major behavior. No hand-written source file should reach 1000 lines. |
| Python test module | 700 lines | 900 lines | Split by feature packet, not by arbitrary helper grouping. |
| Markdown specification | 800 lines | 1000 lines | Split into contract docs and keep root specs as indexes. |
| JSON/YAML fixture | 1000 lines | 5000 lines | Large generated fixtures are allowed only with generator, schema, and checksum evidence. |
| Generated report fixture | 1000 lines | 5000 lines | Allowed when immutable golden evidence; must not be hand-maintained as business logic. |

No-Go:

- New implementation work pushes a hand-written Python source file above 900 lines.
- A file above 900 lines is modified without either splitting it or adding a linked split plan.
- A specification root file keeps accumulating detailed packet text instead of linking to a focused
  contract document.
- A test module grows by copy-paste instead of fixture parametrization or feature-specific split.

## 3. Current Hotspots

Measured on 2026-06-30:

| File | Lines | Status | Required action |
|---|---:|---|---|
| `src/hate/p0a_support.py` | 88 | Completed | Split into focused P0A modules; compatibility shim remains below 200 lines. |
| `docs/process/SPECIFICATION.md` | 1225 | Approved root index pending split | Convert to index plus focused contracts. |
| `src/hate/p0b.py` | 742 | Partially split | SARIF/contract/mutation helpers moved to `src/hate/p0b_sarif.py`; remaining split target is QEG export orchestration vs report construction. |
| `src/hate/p1b.py` | 469 | Partially split | Workflow evidence record assembly moved to `src/hate/p1b_evidence.py`; RanD requirement alignment and trace links moved to `src/hate/p1b_alignment.py`; remaining split target is Shipyard evidence vs workflow artifact report generation. |
| `src/hate/test_integrity/coupling.py` | 582 | Partially split | Classifications and coupling patterns moved to `src/hate/test_integrity/coupling_types.py`; finding records moved to `src/hate/test_integrity/coupling_findings.py`; remaining split target is risk/oracle detectors vs report assembly. |
| `src/hate/test_integrity/mock_assertion.py` | 709 | Partially split | Classifications and mock/assertion patterns moved to `src/hate/test_integrity/mock_assertion_types.py`; remaining split target is report assembly. |
| `src/hate/risk_matrix.py` | 648 | Partially split | Risk matrix constants, policy thresholds, and dataclasses moved to `src/hate/risk_matrix_types.py`; remaining split target is evidence classification vs dashboard projection. |
| `src/hate/api/read_model.py` | 608 | Partially split | Response envelope, resource filter/sort contracts, and request validators moved to `src/hate/api/read_model_contract.py`; remaining split target is resource handlers vs projection assembly. |
| `tests/test_p2p3.py` | 812 | Warning zone | Split by report family and enterprise feature area. |
| `docs/process/RUNBOOK.md` | 765 | Warning zone | Keep as operator index; move feature-specific runbooks out. |
| `tests/test_test_integrity_coupling.py` | 756 | Completed below hard threshold | Canonical fixture/schema tests split to `tests/test_test_integrity_coupling_fixtures.py`. |
| `tests/test_api_read_model_contract.py` | 884 | Completed below hard threshold | Resource inventory tests split to `tests/test_api_read_model_inventory.py`. |

Generated/golden evidence above 1000 lines is acceptable only when it remains fixture data:

- `fixtures/golden/p2p3-product-readiness-minimal/expected/rbac-matrix-report.json`

## 4. Target Module Boundaries

### P0A adapter and coverage ingestion

Split `src/hate/p0a_support.py` into:

- `src/hate/p0a/models.py`: normalized test, coverage, and DQ data classes.
- `src/hate/p0a/junit_adapter.py`: JUnit XML dialect parsing.
- `src/hate/p0a/pytest_json_adapter.py`: pytest JSON parsing.
- `src/hate/p0a/js_test_adapters.py`: Vitest/Jest JSON parsing.
- `src/hate/p0a/coveragepy_adapter.py`: coverage.py JSON parsing.
- `src/hate/p0a/merge.py`: JUnit/JSON/coverage merge rules.
- `src/hate/p0a/report.py`: P0A report serialization.
- `src/hate/p0a/dq.py`: hard DQ, soft gap, and warning classification.

Acceptance:

- Public CLI behavior remains unchanged.
- Existing `tests/test_p0a.py` passes before and after split.
- New adapter SDK work imports from the new package, not from the old monolith.
- A temporary compatibility shim may remain in `p0a_support.py`, but it must stay below 200 lines.

Status as of 2026-06-29: completed. The shim now re-exports focused modules for context,
test adapters, coverage adapters, static evidence, artifact safety, records, and schema
validation.

### P1A trust and privacy hardening

Split `src/hate/p1a_support.py` into:

- `src/hate/p1a/scanners.py`: secret, PII, path, archive, external URL scanners.
- `src/hate/p1a/redaction.py`: redaction and safe summary transformations.
- `src/hate/p1a/quarantine.py`: quarantine records and severity mapping.
- `src/hate/p1a/report.py`: security trust packet output.
- `src/hate/p1a/policy.py`: policy thresholds and allowlists.

Acceptance:

- Scanner tests are independent from report formatting tests.
- New artifact safety features do not increase `p1a_support.py`.
- Redaction logic has negative fixtures for over-redaction and under-redaction.

### P0B QEG export

Split `src/hate/p0b.py` into:

- `src/hate/p0b/exporter.py`: QEG bundle construction.
- `src/hate/p0b/models.py`: QEG typed records.
- `src/hate/p0b/validators.py`: bundle and sourceRef validation.
- `src/hate/p0b/report.py`: export report construction.
- `src/hate/p0b/cli.py`: command wiring only.

Acceptance:

- CLI module contains argument handling only.
- Bundle validation can run without invoking CLI.
- Golden fixtures remain byte-stable unless the schema version changes.

Status as of 2026-07-01: completed for the current split target. Public imports remain available
through `src/hate/p0b.py`; orchestration lives in `src/hate/p0b_exporter.py`, typed/shared
records in `src/hate/p0b_types.py`, filesystem input loading in `src/hate/p0b_inputs.py`,
graph seed construction in `src/hate/p0b_graph.py`, QEG graph phases in
`src/hate/p0b_phases.py`, output/report serialization in `src/hate/p0b_outputs.py`, and
SARIF/contract/mutation normalization in `src/hate/p0b_sarif.py`.

### P1B workflow mapping

Split `src/hate/p1b.py` into:

- `src/hate/p1b/models.py`: workflow mapping records.
- `src/hate/p1b/mapper.py`: mapping logic.
- `src/hate/p1b/validators.py`: invalid mapping and missing evidence checks.
- `src/hate/p1b/report.py`: output serialization.
- `src/hate/p1b/cli.py`: command wiring only.

Acceptance:

- Mapping logic is testable without filesystem writes.
- Report serialization is snapshot/golden tested separately from mapping rules.

Status as of 2026-06-30: partial. Workflow evidence record assembly is isolated in
`src/hate/p1b_evidence.py`; RanD requirement alignment, trace-link assembly, gate aggregation,
audit summary preservation, and manual bridge items are isolated in `src/hate/p1b_alignment.py`.

### API read model

Split `src/hate/api/read_model.py` into:

- `src/hate/api/read_model_contract.py`: envelopes, pagination, staleness, filter and sort contracts.
- `src/hate/api/read_model_projection.py`: canonical report to resource projection assembly.
- `src/hate/api/read_model_handlers.py`: resource handler functions.
- `src/hate/api/read_model_authz.py`: read-model authorization checks that remain pure and deterministic.

Acceptance:

- Public imports from `src/hate/api/__init__.py` remain compatible.
- Resource handlers keep tenant data only in the envelope tenant field.
- Projection logic remains deterministic and does not recompute readiness verdicts.
- `tests/test_api_read_model.py`, `tests/test_api_read_model_contract.py`,
  and `tests/test_api_read_model_inventory.py` pass before and after each split step.

Status as of 2026-07-01: completed for the current split target. Response envelope models,
staleness metadata, resource filter/sort definitions, and request validators remain isolated in
`src/hate/api/read_model_contract.py`; canonical report projection and default model construction
are isolated in `src/hate/api/read_model_projection.py`; `src/hate/api/read_model.py` now contains
response builders plus resource handlers.

## 5. Specification Split Policy

Root specification files must become navigation and contract indexes:

- `SPECIFICATION.md` keeps product scope, phase map, and authoritative links only.
- `PRODUCT_REQUIREMENTS_DEFINITION.md` keeps requirement inventory and links to detailed contracts.
- `EPIC_TASK_PACKETS.md` keeps packet index plus active detailed packets. When a section exceeds
  800 lines, move completed packet groups to `EPIC_TASK_PACKETS_<EPIC>.md`.
- `RUNBOOK.md` keeps common operator flows. Adapter, schema, graph, and enterprise runbooks move
  to feature-specific files once they exceed 150 lines each.

Required focused contracts:

- `ADAPTER_SDK_CONTRACT.md`
- `SCHEMA_REGISTRY_CONTRACT.md`
- `EVIDENCE_GRAPH_CONTRACT.md`
- `TEST_INTEGRITY_CONTRACT.md`
- `PRIVACY_QUARANTINE_CONTRACT.md`
- `STORE_REPLAY_CONTRACT.md`
- `HOSTED_READ_MODEL_API.md`
- `DASHBOARD_VIEW_MODEL_CONTRACT.md`
- `ENTERPRISE_CONTROL_CONTRACT.md`
- `RELEASE_ASSURANCE_PACK_CONTRACT.md`

## 6. Refactoring Execution Order

Full-tree scan as of 2026-07-01:

- Git-tracked plus non-ignored untracked files: 2344 files, 150376 lines.
- Main split pressure: `docs` 55613 lines, `src` 39985 lines, `fixtures` 23280 lines,
  `tests` 22257 lines, `schemas` 8166 lines.
- Current hard guard status: pass. No hand-maintained Python source exceeds 900 lines, no
  non-approved Markdown spec exceeds 1000 lines, and generated Birdseye/index data is excluded.
- Warning-zone source modules: `src/hate/gap_closure.py` 774, `src/hate/p0b.py` 741,
  `src/hate/store/local_store.py` 719, `src/hate/security/artifact_safety.py` 713,
  `src/hate/test_integrity/mock_assertion.py` 709, `src/hate/risk_matrix.py` 649,
  `src/hate/test_integrity/skip_focus.py` 624, `src/hate/dashboard/uat_states.py` 609,
  `src/hate/api/read_model.py` 608, `src/hate/expansion/portfolio_readiness.py` 602.
- Warning-zone tests: `tests/test_api_read_model_contract.py` 882, `tests/test_p2p3.py` 832,
  `tests/test_test_integrity_skip_focus.py` 807, `tests/test_store_replay_compare.py` 780,
  `tests/test_test_integrity_coupling.py` 754.
- Warning-zone docs: `docs/process/PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` 965. It must
  remain an index and continue moving detailed packets to focused spec files.

Updated execution order:

1. Split `src/hate/p0b.py` before any further QEG/export behavior. `export_qeg` is 702 lines and
   76 branch points; it is the highest-risk runtime hotspot.
2. Split `src/hate/cli.py` command dispatch before adding new CLI surfaces. `main` is 302 lines and
   57 branch points; command handlers should move to focused modules.
3. Split `src/hate/risk_matrix.py` evidence classification. `_classify_evidence_for_risk` is 139
   lines and 45 branch points; keep matrix assembly separate from evidence matching policy.
4. Split `src/hate/api/read_model.py` projection/handler assembly before API expansion resumes.
5. Split `src/hate/security/artifact_safety.py` archive/binary scanning from report assembly before
   adding more artifact detectors.
6. Split `src/hate/test_integrity/mock_assertion.py` and `src/hate/test_integrity/skip_focus.py`
   report assembly from detector rules before new integrity signals are added.
7. Split large test modules by fixture family after their matching runtime split, starting with
   `tests/test_api_read_model_contract.py`, `tests/test_p2p3.py`, and
   `tests/test_test_integrity_skip_focus.py`.
8. Keep `docs/process/SPECIFICATION.md` as an approved root index only; do not add detailed
   packet text there.

Status as of 2026-07-01: execution order items 1-5 are completed for the current high-priority
refactoring phase. `src/hate/p0b.py` is now a compatibility facade, `src/hate/cli.py` keeps parser
and thin entrypoint only, risk evidence matching moved to `src/hate/risk_matrix_evidence.py`,
read-model projection moved to `src/hate/api/read_model_projection.py`, and archive/binary artifact
scanning moved to `src/hate/security/artifact_archive.py`.

## 7. CI Guardrail Requirement

Add a CI guard before product-grade implementation accelerates:

- command: `uv run python tools/check_file_size.py`
- source files over 900 lines: fail
- test files over 900 lines: fail
- Markdown over 1000 lines: fail unless listed as approved root index pending split
- generated fixtures over 1000 lines: allowed only when path matches `fixtures/golden/**/expected/*.json`

The guardrail must print path, line count, threshold, and required split target.

Status as of 2026-06-30: implemented in `tools/check_file_size.py` with regression coverage in
`tests/test_check_file_size.py`. The current tree passes the guard after splitting
`tests/test_test_integrity_coupling.py` and `tests/test_api_read_model_contract.py`.
