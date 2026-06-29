---
intent_id: INT-HATE-GLM-IMPLEMENTATION-DISPATCH-PACK-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# GLM Implementation Dispatch Pack

## 1. Purpose

This dispatch pack is the implementation handoff contract for GLM workers. It converts the
product-grade HATE epic specification into ordered implementation waves, worker packets,
acceptance commands, UAT checks, return conditions, and Codex-side UAT responsibilities.

This document does not replace:

- `EPIC_TASK_PACKETS.md`
- `EPIC_TWO_PASS_COMPLETION_AUDIT.md`
- `IMPLEMENTATION_EPIC_BREAKDOWN.md`
- `REFACTORING_PLAN.md`
- `PRODUCT_GRADE_IMPLEMENTATION_SPEC.md`

GLM workers must treat those documents as source contracts. This document defines how to dispatch
the work and how Codex must verify the result before the next packet is accepted.

## 2. Dispatch Principles

- Implement the product, not a demo.
- Each worker packet must produce code, schemas, fixtures, negative fixtures, tests, docs, and the
  named evidence report.
- Do not claim product-ready, enterprise-ready, release-ready, or commercial-ready until the
  relevant report proves it.
- Keep HATE local-first. External connectors and hosted/API surfaces must support dry-run or local
  projection first.
- Preserve QEG/Shipyard/RanD/manual-bb boundaries. HATE may reference their verdicts; it must not
  override or impersonate them.
- Keep generated and hand-written artifacts distinct.
- Respect `REFACTORING_PLAN.md`; no hand-written Python source file may be pushed toward a
  1000-line monolith.

## 3. EPIC Implementation Order

| Order | Epic | Dispatch wave | Reason |
|---:|---|---|---|
| 0 | Refactoring prerequisites | Foundation | Required before adapter and schema expansion. |
| 1 | EPIC-001 Adapter Corpus and SDK | Foundation | Ingests test, coverage, static, contract, and mutation evidence. |
| 2 | EPIC-002 Cross-Record Schema and Validator | Foundation | Stabilizes records before graph/store/API consume them. |
| 3 | EPIC-003 Evidence Graph and Risk Coverage | Core readiness | Creates the shared explanation model for readiness. |
| 4 | EPIC-005 Artifact Safety and Privacy | Core safety | Must exist before API/UI/support/connectors/release expose artifacts. |
| 5 | EPIC-004 Test Integrity and AI-Abuse Detector | Core quality | Adds oracle quality and AI-abuse gates into readiness. |
| 6 | EPIC-006 Local Store, Replay, Compare | Persistence | Makes evidence immutable, replayable, and comparable. |
| 7 | EPIC-011 Scale and Performance | Scale proof | Proves the architecture survives large evidence sets. |
| 8 | EPIC-007 API Read Model | Product surface | Exposes report-backed resources without independent verdict logic. |
| 9 | EPIC-008 Dashboard and UI Workflow | Product surface | Defines dashboard state and manual UAT expectations. |
| 10 | EPIC-009 RBAC, Audit, Retention, Legal | Enterprise controls | Adds enterprise access, audit, retention, legal hold. |
| 11 | EPIC-010 Enterprise Connectors | Enterprise integrations | Adds dry-run SSO/SCIM/SIEM/warehouse/ticket integrations. |
| 12 | EPIC-012 Observability and Support Ops | Operations | Adds logs, metrics, alerts, error catalog, safe bundles. |
| 13 | EPIC-013 Migration and Compatibility | Lifecycle | Preserves old bundles, versions, profiles, legal holds. |
| 14 | EPIC-015 Commercial Truthfulness | Release guard | Blocks unsupported product/procurement/sales claims. |
| 15 | EPIC-014 Release Candidate and Assurance Pack | Release gate | Assembles final deterministic release evidence pack. |

## 4. Dependency Blocks

GLM must not start a packet when its blocking prerequisite is missing.

| Block | Must precede | Return if missing |
|---|---|---|
| P0A split from `REFACTORING_PLAN.md` | HATE-PG-001B, HATE-PG-001C | Return for Codex refactor/UAT. |
| HATE-PG-001A | HATE-PG-001B, HATE-PG-001C, HATE-PG-001D | Return; adapters require SDK/manifest schema. |
| HATE-PG-002A | EPIC-003, EPIC-004, EPIC-006, EPIC-007 | Return; downstream must consume validated envelopes. |
| HATE-PG-002B | EPIC-003, EPIC-006, EPIC-013 | Return; graph/replay/migration require sourceRef/hash identity. |
| HATE-PG-003A | EPIC-004, EPIC-008, EPIC-014 | Return; readiness explanation must be shared. |
| HATE-PG-005A/B | EPIC-007, EPIC-008, EPIC-010, EPIC-012, EPIC-014 | Return; no unsafe artifact exposure. |
| HATE-PG-006A/B | EPIC-011, EPIC-013, EPIC-014 | Return; scale/migration/release need stable store. |
| HATE-PG-009A | EPIC-007, EPIC-008, EPIC-010, EPIC-014 | Return; enterprise surfaces require authz/audit. |
| HATE-PG-015A | HATE-PG-014A | Return; release pack must consume commercial truthfulness. |

## 5. GLM Worker Packets

Each worker receives exactly one packet group unless Codex explicitly batches adjacent packets.
The detailed packet content comes from `EPIC_TASK_PACKETS.md`.

| Worker packet | Source packet(s) | Required output report |
|---|---|---|
| GLM-W00-refactor-p0a | `REFACTORING_PLAN.md` P0A split verification and follow-up cleanup | no product report; must keep tests green |
| GLM-W01-adapter-sdk | HATE-PG-001A | `adapter-conformance-report.json` |
| GLM-W02-junit-corpus | HATE-PG-001B | `adapter-conformance-report.json` |
| GLM-W03-coverage-corpus | HATE-PG-001C | `adapter-conformance-report.json` |
| GLM-W04-static-contract-mutation-corpus | HATE-PG-001D | `adapter-conformance-report.json` |
| GLM-W05-envelope-validator | HATE-PG-002A | `schema-validation-report.json` |
| GLM-W06-source-ref-validator | HATE-PG-002B | `schema-validation-report.json` |
| GLM-W07-evidence-graph | HATE-PG-003A | `product-readiness-report.json` |
| GLM-W08-risk-matrix-manual-bridge | HATE-PG-003B | `product-readiness-report.json`, `manual-review-required.json` |
| GLM-W09-skip-focus-detector | HATE-PG-004A | `test-integrity-report.json` |
| GLM-W10-mock-assertion-detector | HATE-PG-004B | `test-integrity-report.json` |
| GLM-W11-coupling-manual-detector | HATE-PG-004C | `test-integrity-report.json`, `manual-review-required.json` |
| GLM-W12-artifact-scanners | HATE-PG-005A | `security-quarantine-report.json` |
| GLM-W13-redaction-export-filter | HATE-PG-005B | `security-quarantine-report.json`, `safe-diagnostic-bundle.json` |
| GLM-W14-local-store-indexes | HATE-PG-006A | `store-replay-report.json` |
| GLM-W15-replay-compare-doctor | HATE-PG-006B | `store-replay-report.json` |
| GLM-W16-scale-fixtures | HATE-PG-011A | `scale-performance-report.json` |
| GLM-W17-performance-budget | HATE-PG-011B | `scale-performance-report.json` |
| GLM-W18-api-read-model | HATE-PG-007A | `api-contract-report.json` |
| GLM-W19-api-import-export-authz | HATE-PG-007B | `api-contract-report.json` |
| GLM-W20-dashboard-view-models | HATE-PG-008A | `dashboard-uat-report.json` |
| GLM-W21-ui-uat-states | HATE-PG-008B | `dashboard-uat-report.json` |
| GLM-W22-rbac-audit | HATE-PG-009A | `enterprise-control-report.json` |
| GLM-W23-retention-legal-hold | HATE-PG-009B | `enterprise-control-report.json` |
| GLM-W24-sso-scim-dry-run | HATE-PG-010A | `enterprise-control-report.json` |
| GLM-W25-ops-connectors-dry-run | HATE-PG-010B | `enterprise-control-report.json` |
| GLM-W26-logs-metrics-alerts | HATE-PG-012A | `support-ops-report.json` |
| GLM-W27-diagnostics-error-catalog | HATE-PG-012B | `support-ops-report.json`, `safe-diagnostic-bundle.json` |
| GLM-W28-migration-compatibility | HATE-PG-013A | `migration-compatibility-report.json` |
| GLM-W29-legal-hold-migration | HATE-PG-013B | `migration-compatibility-report.json`, `enterprise-control-report.json` |
| GLM-W30-commercial-truthfulness | HATE-PG-015A | `commercial-truthfulness-report.json` |
| GLM-W31-release-pack | HATE-PG-014A | `release-candidate-pack.json` |

## 6. Packet Prompt Template

Use this template for every GLM worker dispatch.

```text
You are implementing HATE worker packet <worker-packet-id>.

Source contracts:
- docs/process/EPIC_TASK_PACKETS.md::<HATE-PG-*>
- docs/process/EPIC_TWO_PASS_COMPLETION_AUDIT.md
- docs/process/REFACTORING_PLAN.md
- docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md

Required:
- Implement the packet fully, including code, schemas, fixtures, negative fixtures, tests, docs,
  and named evidence report.
- Preserve QEG/Shipyard/RanD/manual-bb boundaries.
- Preserve local-first behavior.
- Do not claim product-ready unless the required reports prove it.
- Keep hand-written Python files under refactoring thresholds.

Return:
- Changed files
- Added fixtures
- Added schemas
- Added tests
- Evidence report path and sample output
- Commands run and results
- Known gaps, if any
```

## 7. Forbidden Actions

GLM workers must not:

- Delete or rewrite unrelated user changes.
- Collapse existing No-Go conditions into warnings.
- Add `skip`, `xfail`, `only`, `todo`, empty tests, or assertion-free smoke tests to fake coverage.
- Branch implementation logic on fixture names, test names, or golden output filenames.
- Generate product-ready or release-ready status from `status=not_run`.
- Treat coverage percentage alone as meaningful evidence.
- Accept sourceRef/hash mismatch as a soft warning.
- Export raw secrets, PII, restricted paths, raw customer code, or quarantined artifacts.
- Perform live network calls for enterprise connectors unless a packet explicitly requires a
  configured non-default live mode.
- Let external connector failure change core readiness verdicts.
- Let HATE claim QEG approval or override QEG/Shipyard/RanD/manual-bb decisions.
- Grow a hand-written Python source file beyond `REFACTORING_PLAN.md` thresholds.
- Modify canonical evidence silently during replay, doctor, export, or migration.
- Hide unsupported commercial claims from release evidence.

## 8. Acceptance Commands

Codex must run these after each GLM packet unless the packet explicitly states a narrower command
and Codex accepts the reason.

```powershell
uv run python -m compileall src tests tools
uv run pytest
uv run python tools/codemap/update.py --check
git diff --check
```

Packet-specific commands:

| Packet class | Required additional command |
|---|---|
| Adapter packets | `uv run pytest tests/test_p0a.py` plus packet-specific adapter tests |
| Schema packets | schema validator tests and generated `schema-validation-report.json` inspection |
| Evidence graph/readiness packets | product readiness report generation and sourceRef inspection |
| Security/privacy packets | quarantine/redaction tests with negative fixtures |
| Store/replay packets | replay hash comparison and corruption doctor tests |
| API packets | OpenAPI validation plus API fixture contract tests |
| UI packets | dashboard view model fixture validation and UAT state checks |
| Enterprise packets | authz/audit/retention/legal hold denied-case tests |
| Connector packets | dry-run tests proving no live side effects and redacted diagnostics |
| Scale packets | generator determinism and budget report checks |
| Release/commercial packets | release pack blocker tests and commercial claim contradiction tests |

## 9. UAT Checks

Codex UAT must verify:

- The named evidence report exists and is schema-valid.
- Positive and negative fixtures are both exercised.
- Hard DQ, hold, soft gap, and pass paths behave as specified.
- Blocking findings include sourceRefs.
- Product-ready cannot be true when required reports are missing.
- Security/privacy failures are not exposed in summaries, API, UI, support bundle, connectors, or
  release pack.
- Manual review records are requested and validated, not synthesized as approvals.
- Release pack references QEG/Shipyard/RanD/manual-bb verdicts without claiming authority over
  them.
- Local file-reference codemap remains up to date with `tools/codemap/update.py --check`.
- File-size guardrails remain satisfied or have an explicit split plan.

## 10. Return Conditions

Codex must return a GLM result for revision when any condition is true:

- Required code, schema, fixture, negative fixture, test, doc, or evidence report is missing.
- Acceptance command fails.
- The implementation violates a forbidden action.
- A downstream dependency is silently mocked instead of represented as a real contract or explicit
  pending integration.
- Report output exists but does not include sourceRefs for blockers.
- New tests only execute code without assertions.
- A parser or validator accepts malformed input that the packet defines as No-Go.
- The implementation hides unsupported claims, unsafe artifacts, failed contracts, survived
  mutants, or high/critical findings.
- The worker modifies unrelated files without explanation.
- The worker increases a hand-written file past threshold without splitting or updating the split
  plan.

## 11. Two-Revision Loop

For each worker packet:

1. GLM implements the packet and returns its completion report.
2. Codex performs UAT using this dispatch pack and the packet source contract.
3. If UAT fails, Codex returns a revision request to GLM with exact failing evidence.
4. GLM may revise up to two times.
5. After two failed GLM revisions, Codex must take over and repair the packet directly.
6. Codex marks the packet Go only after acceptance commands and UAT pass.
7. Codex records packet status in the roadmap/checklist before dispatching the next dependent
   packet.

Revision requests must include:

- failing command
- failing file/path
- expected behavior
- actual behavior
- source contract reference
- required evidence report change
- No-Go violated, if applicable

## 12. Codex UAT Responsibilities

Codex owns final acceptance. Codex must not delegate these decisions to GLM.

Codex must:

- Read the packet source contract before UAT.
- Inspect changed files, not just command output.
- Run acceptance commands.
- Inspect generated evidence reports.
- Check sourceRefs, negative fixtures, and No-Go behavior.
- Confirm no QEG/Shipyard/RanD/manual-bb boundary violation.
- Confirm local file-reference codemap freshness when files are added/removed.
- Confirm file-size thresholds.
- Decide Go / Return / Codex-repair.
- Keep a concise implementation ledger for completed packets.

Codex must not:

- Accept a packet based only on GLM's summary.
- Accept tests that only check execution.
- Accept docs-only work for implementation packets unless the packet is explicitly documentation
  only.
- Accept product-ready claims without evidence reports.
- Accept a release pack without commercial truthfulness, security, manual review, and required
  report checks.

## 13. Implementation Ledger Format

Codex should maintain a packet ledger during execution.

```markdown
| Worker packet | Status | GLM attempts | Codex repair | Evidence report | UAT result | Notes |
|---|---|---:|---|---|---|---|
| GLM-W01-adapter-sdk | pending | 0 | no | adapter-conformance-report.json | not_run | blocked by dispatch |
```

Allowed statuses:

- pending
- in_progress
- return_1
- return_2
- codex_repair
- go
- blocked

## 14. Initial Dispatch Queue

Start with:

1. `GLM-W00-refactor-p0a`: verify the completed P0A split and clean up import paths only if safe.
2. `GLM-W01-adapter-sdk`: implement SDK/manifest/conformance schema.
3. `GLM-W02-junit-corpus`: implement JUnit dialect corpus.
4. `GLM-W03-coverage-corpus`: implement coverage dialect corpus.
5. `GLM-W04-static-contract-mutation-corpus`: implement SARIF/Pact/Stryker corpus.

Do not dispatch EPIC-003 or later until EPIC-002 schema validation produces
`schema-validation-report.json`.

