---
intent_id: INT-HATE-PRODUCT-PLATFORM-PHASE-IMPLEMENTATION-PACKETS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Product Platform Phase Implementation Packets

本書は `PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md` と
`PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md` に対応する実装パケット正本である。

各 packet は 0.5日〜1日以内で UAT 可能な単位を目標にする。大きい packet は
schema/fixture/runner/read-model/UI の順に分割する。

## 1. Dispatch Rules

- 要件定義を変更する場合、先に `PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md` を更新する。
- 実装仕様を変更する場合、次に `PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md` を更新する。
- store、policy、RBAC、dashboard、benchmark を触る packet は、それぞれ
  `PLATFORM_STORE_SCHEMA_SPEC.md`、`PLATFORM_POLICY_CONFIG_SPEC.md`、
  `PLATFORM_RBAC_MATRIX_SPEC.md`、`PLATFORM_DASHBOARD_WIREFRAME_SPEC.md`、
  `PLATFORM_BENCHMARK_FIXTURE_SPEC.md`、`PLATFORM_CONNECTOR_SYNC_SPEC.md`、
  `PLATFORM_PLUGIN_SANDBOX_SPEC.md` を入力正本として扱う。
- 実装は packet ID、requirement IDs、acceptance IDs、fixtures、tests を commit message / UAT report に残す。
- external repo hold は修正対象にしない。HATE 側の parser、classification、reporting の問題だけを直す。
- Birdseye/codemap は packet 完了時に更新する。

## 2. Evaluation Foundation Packets

| Packet ID | Requirements | Scope | Output | Tests | UAT Gate |
|---|---|---|---|---|---|
| PPH-PKT-EVAL-001-roster-v2-schema | PPH-EVAL-001 | `real-repo-roster-v2` schema、loader、owned/external validation | schema + loader | roster positive/negative tests | invalid ownership/suite rejected |
| PPH-PKT-EVAL-002-run-identity | PPH-EVAL-002 | run_id、roster_hash、policy_hash、environment_fingerprint | run history entry fields | deterministic hash tests | run manifest has identity fields |
| PPH-PKT-EVAL-003-history-store | PPH-EVAL-003,007 | run history append/query store | local store tables/files | multi-run query tests | repo/time/profile query works |
| PPH-PKT-EVAL-004-regression-engine | PPH-EVAL-004 | baseline/current compare classes | regression findings | pass→hold, record collapse, runtime drift tests | regression effect visible |
| PPH-PKT-EVAL-005-external-hold-boundary | PPH-EVAL-005 | external hold classification | external finding records | external vs owned tests | external hold not HATE implementation failure |
| PPH-PKT-EVAL-006-score-model | PPH-EVAL-006 | score formula and breakdown | score report | component/penalty tests | no score without breakdown |
| PPH-PKT-EVAL-007-timeout-cleanup | PPH-EVAL-008 | process cleanup, excerpt, timeout reason | timeout report fields | timeout child cleanup tests | no orphan process evidence |
| PPH-PKT-EVAL-008-runner-dialect-parsers | PPH-EVAL-NFR-004 | pytest/vitest/bun/npm summary dialect parser hardening | parser module | noisy log fixtures | no false error counts |
| PPH-PKT-EVAL-009-baseline-governance | PPH-EVAL-009 | baseline approval/freeze/expiry/revoke events | baseline event schema + reducer | approval/expiry tests | unapproved baseline cannot hide regression |
| PPH-PKT-EVAL-010-output-safety-normalization | PPH-EVAL-010, PPH-EVAL-NFR-002, PPH-EVAL-NFR-003 | redaction, deterministic excerpt, path normalization | output safety module | secret/path/line-ending tests | no raw secret/path in read model |

## 3. Operations Foundation Packets

| Packet ID | Requirements | Scope | Output | Tests | UAT Gate |
|---|---|---|---|---|---|
| PPH-PKT-OPS-001-operating-schema | PPH-OPS-001,002 | operating finding/event schemas | schemas + models | schema contract tests | finding/debt/review common fields |
| PPH-PKT-OPS-002-lifecycle-reducer | PPH-OPS-003,007 | append-only event reducer to current projection | reducer module | lifecycle transition tests | replay rebuilds projection |
| PPH-PKT-OPS-003-expiry-scanner | PPH-OPS-004 | accepted debt expiry scanner | expired debt findings | expiry date tests | expired accepted debt changes readiness |
| PPH-PKT-OPS-004-manual-review-integration | PPH-OPS-005,006 | manual review into operating model | review event/projection | invalid review tests | missing owner/evidence blocks |
| PPH-PKT-OPS-005-owner-due-date-policy | PPH-OPS-002,006 | owner/due date readiness policy | policy evaluator | profile tests | release profile holds missing owner/due |
| PPH-PKT-OPS-006-dedupe-supersede | PPH-OPS-007 | duplicate/merge/supersede operations | lifecycle events | audit retention tests | old sourceRefs retained |
| PPH-PKT-OPS-007-tracker-sync | PPH-OPS-008 | tracker mirror export/import envelope | sync records | canonical-source tests | tracker cannot overwrite state |
| PPH-PKT-OPS-008-escalation-notifications | PPH-OPS-009 | SLA breach, notification attempt, delivery failure events | notification event records | failed delivery tests | notification failure does not close finding |
| PPH-PKT-OPS-009-retention-rebuild | PPH-OPS-010, PPH-OPS-NFR-001, PPH-OPS-NFR-002, PPH-OPS-NFR-003 | retention/legal hold/projection rebuild | rebuild report | legal hold/missing event tests | projection rebuild preserves lifecycle |

## 4. Extension Foundation Packets

| Packet ID | Requirements | Scope | Output | Tests | UAT Gate |
|---|---|---|---|---|---|
| PPH-PKT-EXT-001-plugin-manifest-schema | PPH-EXT-001 | detector plugin manifest schema | schema + fixtures | manifest validation tests | invalid manifest rejected |
| PPH-PKT-EXT-002-plugin-loader | PPH-EXT-002 | built-in/workspace/org plugin discovery | loader module | resolution tests | deterministic plugin order |
| PPH-PKT-EXT-003-policy-resolution | PPH-EXT-003,008 | layered policy resolution and explain | effective policy report | layer override tests | config source explained |
| PPH-PKT-EXT-004-threshold-overrides | PPH-EXT-004 | detector/risk/repo/suite threshold overrides | threshold resolver | override matrix tests | correct threshold selected |
| PPH-PKT-EXT-005-plugin-sandbox | PPH-EXT-005 | timeout/resource/trust enforcement | sandbox runner | timeout/untrusted tests | failure becomes finding |
| PPH-PKT-EXT-006-output-normalizer | PPH-EXT-006 | plugin output to canonical finding | normalizer | malformed/unknown field tests | compatibility envelope used |
| PPH-PKT-EXT-007-conformance-suite | PPH-EXT-007 | plugin conformance fixtures and runner | conformance report | positive/negative/malformed tests | plugin cannot ship without fixtures |
| PPH-PKT-EXT-008-plugin-api-migration | PPH-EXT-009, PPH-EXT-NFR-003 | semver compatibility, migration notes, deprecated field policy | compatibility report | compatible/deprecated/blocked tests | breaking plugin requires migration note |
| PPH-PKT-EXT-009-plugin-trust-policy | PPH-EXT-010, PPH-EXT-NFR-002 | signature, allowlist, trust source enforcement | trust evaluator | unsigned/unallowlisted tests | release profile blocks untrusted plugin |

## 5. Consumption Surface Packets

| Packet ID | Requirements | Scope | Output | Tests | UAT Gate |
|---|---|---|---|---|---|
| PPH-PKT-UX-001-platform-cli | PPH-UX-001 | `hate platform ...` command skeleton and handlers | CLI commands | argparse/handler tests | all required commands exist |
| PPH-PKT-UX-002-read-model | PPH-UX-002 | resources and query envelope | read model module | query tests | runs/findings/debt/review query |
| PPH-PKT-UX-003-json-api | PPH-UX-003 | REST API envelope, pagination, errors | API server | contract tests | RBAC/stale/error envelope |
| PPH-PKT-UX-004-html-report | PPH-UX-004 | HTML report generator | static HTML + manifest | snapshot/schema tests | report contains sourceRefs and score |
| PPH-PKT-UX-005-dashboard-view-model | PPH-UX-005,006 | dashboard view models and states | JSON view models | state matrix tests | partial/stale/empty states |
| PPH-PKT-UX-006-safe-display | PPH-UX-007 | unsafe artifact redaction in views | redaction layer | secret/PII tests | raw unsafe data absent |
| PPH-PKT-UX-007-auditor-view | PPH-UX-008 | replay/sourceRef/manual trail view | audit read model | replay tests | auditor can trace decision |
| PPH-PKT-UX-008-rbac-matrix | PPH-UX-009 | role/tenant/resource/action RBAC matrix | RBAC decision records | allow/deny matrix tests | denial does not leak restricted data |
| PPH-PKT-UX-009-offline-performance-compat | PPH-UX-010, PPH-UX-NFR-001, PPH-UX-NFR-002, PPH-UX-NFR-003 | offline HTML, read-model performance, response schema compatibility | performance and compatibility report | offline/perf/schema tests | budget and compatibility evidence produced |

## 6. Scale Foundation Packets

| Packet ID | Requirements | Scope | Output | Tests | UAT Gate |
|---|---|---|---|---|---|
| PPH-PKT-SCALE-001-cache-index | PPH-SCALE-001,007 | cache key, freshness, compatibility | cache index | stale policy tests | incompatible cache denied |
| PPH-PKT-SCALE-002-parallel-planner | PPH-SCALE-002 | task graph and resource budget | planner | budget tests | no conflicting writes |
| PPH-PKT-SCALE-003-incremental-scope | PPH-SCALE-003 | changed file/risk/dependency scope | scope report | skipped scope tests | full_suite_proven false when partial |
| PPH-PKT-SCALE-004-scheduler-state | PPH-SCALE-004 | queue/lease/retry/cancel state machine | scheduler state | transition tests | timeout/retry/cancel works |
| PPH-PKT-SCALE-005-artifact-store | PPH-SCALE-005 | CAS/quarantine/retention/legal hold/GC | artifact store records | lifecycle tests | unsafe body cannot leak |
| PPH-PKT-SCALE-006-resume-token | PPH-SCALE-006 | partial result and resume token | resume records | resume tests | timed out run resumes |
| PPH-PKT-SCALE-007-scheduler-audit | PPH-SCALE-008 | scheduler/artifact audit events | audit records | read model tests | events queryable |
| PPH-PKT-SCALE-008-store-recovery | PPH-SCALE-009, PPH-SCALE-NFR-002, PPH-SCALE-NFR-003 | backup/restore/rebuild/migration/corruption scan | recovery report | restore/rebuild/legal hold tests | recovered store preserves decisions |
| PPH-PKT-SCALE-009-capacity-benchmark | PPH-SCALE-010, PPH-SCALE-NFR-001 | 1000 repo/1M finding benchmark model and degradation mode | benchmark report | capacity fixture tests | degradation is explicit, not silent pass |

## 7. Parallelization Plan

Recommended two-agent lanes:

| Lane | First packets | Reason |
|---|---|---|
| Lane A | PPH-PKT-EVAL-001,002,003,004 | history/regression depend on roster/run identity |
| Lane B | PPH-PKT-OPS-001,002,003,004 | operating model can proceed independently |

After both lanes pass:

- Lane A continues to PPH-PKT-EVAL-005..008 and PPH-PKT-SCALE-001.
- Lane B continues to PPH-PKT-EXT-001..004 and PPH-PKT-UX-001..002.
- Baseline governance and output safety, PPH-PKT-EVAL-009..010, must land
  before any dashboard or external export claims historical trust.
- RBAC and offline/performance packets, PPH-PKT-UX-008..009, must land before
  hosted/dashboard completion is claimed.
- Store recovery and capacity packets, PPH-PKT-SCALE-008..009, must land before
  large-scale readiness is claimed.

Do not start dashboard rendering before read model resources exist.
Do not start plugin sandbox before manifest and policy resolution are stable.
Do not start scheduler before cache key and run identity are stable.

## 7.1 Immediate Dispatch: Platform CLI and Product-Grade Gate

| Packet ID | Requirements | Scope | Output | Tests | UAT Gate |
|---|---|---|---|---|---|
| PPH-PKT-UX-001A-platform-cli-wrapper | PPH-UX-CLI-001..006 | Add `hate platform run/history/compare/findings/debt/review/policy/report/serve` as an orchestration layer over canonical reports | CLI handlers + projection reports | platform CLI parser/handler tests | commands exist and preserve underlying report semantics |
| PPH-PKT-GRADE-001-product-grade-recalc | PPH-GRADE-001..002 | Recalculate product-grade status from docs, implementation refs, tests, real-data validation, QEG smoke, and residual blockers | product-grade evidence summary with implementation matrix | product-grade status tests | summary is not hard-coded `no_go`; residual blockers keep product_ready false |
| PPH-PKT-DOCS-001-state-freshness | PPH-GRADE-001 | Refresh README state and ledger with current test count, real-repo validation, and platform residuals | README + ledger update | docs link/status test or grep check | stale `93 tests pass` and old product-grade wording absent |

## 8. Definition of Done

For each packet:

- requirements and acceptance IDs named in test file or UAT report
- schema added or explicitly not needed
- applicable physical specification referenced and updated
- positive and negative fixtures added
- unit tests pass
- full `uv run pytest -q` pass
- `uv run python -m compileall src tests` pass
- `uv run python tools/codemap/update.py` run
- docs updated
- no external repo modified unless explicitly owned and requested

For phase completion:

- all packets in the phase pass UAT
- integration UAT for the phase passes
- read model/API/dashboard, if applicable, use canonical projection
- score and readiness claims include explanation and sourceRefs
- No-Go rules in `PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md` are false
