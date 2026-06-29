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

Measured on 2026-06-29:

| File | Lines | Status | Required action |
|---|---:|---|---|
| `src/hate/p0a_support.py` | 88 | Completed | Split into focused P0A modules; compatibility shim remains below 200 lines. |
| `docs/process/SPECIFICATION.md` | 1027 | Over hard threshold | Convert to index plus focused contracts. |
| `src/hate/p1a_support.py` | 865 | Near hard threshold | Split before adding security/privacy scanners. |
| `src/hate/p0b.py` | 842 | Near hard threshold | Split QEG export orchestration from report construction. |
| `src/hate/p1b.py` | 785 | Warning zone | Split workflow mapping models, CLI orchestration, and report generation. |
| `tests/test_p2p3.py` | 731 | Warning zone | Split by report family and enterprise feature area. |
| `docs/process/RUNBOOK.md` | 697 | Warning zone | Keep as operator index; move feature-specific runbooks out. |

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

1. Split `p0a_support.py` before implementing HATE-PG-001B/C adapter corpus expansion.
2. Split `SPECIFICATION.md` before adding EPIC-004 and later detailed packet sections.
3. Split `p1a_support.py` before implementing EPIC-005 privacy/security scanners.
4. Split `p0b.py` before expanding QEG/schema validation integration.
5. Split `p1b.py` before workflow mapping grows into UI/API support.
6. Split `tests/test_p2p3.py` when EPIC-006/009 implementation resumes.

## 7. CI Guardrail Requirement

Add a CI guard before product-grade implementation accelerates:

- command: `uv run python tools/check_file_size.py`
- source files over 900 lines: fail
- test files over 900 lines: fail
- Markdown over 1000 lines: fail unless listed as approved root index pending split
- generated fixtures over 1000 lines: allowed only when path matches `fixtures/golden/**/expected/*.json`

The guardrail must print path, line count, threshold, and required split target.
