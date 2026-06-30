---
intent_id: INT-HATE-IMPLEMENTATION-TASK-BREAKDOWN-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# フル実装タスク分解

## 1. 目的

本書は `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md` を実装作業へ落とすための
worker-facing task backlog である。各タスクは、コード、schema、fixture、test、docs
が揃ったときだけ `done` にできる。

50万行級の product-grade 実装へ展開する epic / worker packet の入口は
`IMPLEMENTATION_EPIC_BREAKDOWN.md` を正本とする。

PRD gap から横断実装packetへ展開する入口は
`PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md` を正本とする。特に
HATE-GAP-001..026 は、フェーズ別タスクだけでなく gap packet ID、
acceptance、fixture、UAT evidence へ必ず紐づける。

## 2. Done の共通条件

全タスク共通で、以下を満たす。

- 実装コードが存在する
- 入力fixtureとexpected artifactが存在する
- negative fixtureまたはfailure testが存在する
- `uv run pytest` または対象pytestが通る
- `uv run python -m compileall src tests` が通る
- README / RUNBOOK / SPECIFICATION の参照が必要に応じて更新される
- `advisory`, `optional`, `future` の文言で実装不足を隠していない
- `PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` が要求する completion claim taxonomy に従い、
  docs-only / fixture-only / report-only の作業を `implemented` と呼ばない
- `PRODUCT_REQUIREMENTS_DEFINITION.md` の requirement ID、user journey、acceptance ID の
  いずれにも紐づかない task を product-ready work として扱わない

## 3. P0a Tasks

| task_id | title | affected paths | acceptance |
|---|---|---|---|
| HATE-P0A-001 | generic CI context adapter | `src/hate`, `fixtures/adapters/ci` | GitHub以外のCI fixtureがrun recordになる |
| HATE-P0A-002 | pytest/vitest/jest result adapter | `src/hate`, `fixtures/adapters/test-results` | 3形式がtest_resultになる |
| HATE-P0A-003 | coverage.py context adapter | `src/hate`, `fixtures/adapters/coveragepy` | contextがcoverage_slice.contextsへ入る |
| HATE-P0A-004 | Cobertura/JaCoCo hardening | `src/hate`, `fixtures/adapters/coverage` | malformed/partial/windows path fixtureがある |
| HATE-P0A-005 | artifact safety engine | `src/hate`, `fixtures/adapters/artifacts` | secret/url/symlink/archiveがquarantineされる |
| HATE-P0A-006 | JSON Schema validation | `schemas/HATE/v1`, `src/hate/schema` | invalid generated recordでDQ/adapter failure |
| HATE-P0A-007 | profile-aware precheck | `src/hate/profile`, `tests` | default/strict/releaseで同一fixtureのdecision差分が説明される |

## 4. P0b Tasks

| task_id | title | affected paths | acceptance |
|---|---|---|---|
| HATE-P0B-001 | SARIF full finding mapping | `src/hate`, `fixtures/adapters/sarif` | rule, level, location, sourceRefsがQEG findingになる |
| HATE-P0B-002 | Playwright artifact evidence | `src/hate`, `fixtures/adapters/playwright` | trace/screenshot/video/logがtest/executionへ結線 |
| HATE-P0B-003 | Pact contract evidence | `src/hate`, `fixtures/adapters/pact` | failed required contractがgapになる |
| HATE-P0B-004 | Stryker mutation evidence | `src/hate`, `fixtures/adapters/stryker` | survived mutantがoracle strength reasonになる |
| HATE-P0B-005 | QEG schema compatibility | `schemas/HATE/v1/qeg-bundle.schema.json`, `tests` | QEG minimal schema validation test |
| HATE-P0B-006 | risk debt lifecycle | `src/hate`, `fixtures/golden/p0b-qeg-minimal` | open/ack/mitigated/stale transition fixture |
| HATE-P0B-007 | manual-bb bridge contract | `src/hate`, `fixtures/manual-bb` | missing high-risk executionからmanual request生成 |

## 5. P1a Tasks

| task_id | title | affected paths | acceptance |
|---|---|---|---|
| HATE-P1A-001 | adapter registry | `src/hate/registry`, `fixtures/registry` | 全adapter manifestがreportに出る |
| HATE-P1A-002 | adapter conformance runner | `src/hate/registry`, `tests` | adapterごとのfixture結果がconformance reportになる |
| HATE-P1A-003 | profile inheritance | `src/hate/profile`, `fixtures/profile` | profile-report.jsonとdrift test |
| HATE-P1A-004 | signal-based AETE scoring | `src/hate/aete`, `fixtures/aete` | 8次元がsignalから計算される |
| HATE-P1A-005 | canonical identity hardening | `src/hate/identity`, `fixtures/identity` | rename/parameterized/matrix aliasを保持 |
| HATE-P1A-006 | retry/matrix/shard aggregation | `src/hate/aggregate`, `fixtures/retry` | deterministic aggregate |
| HATE-P1A-007 | artifact resolver | `src/hate/resolver`, `fixtures/path` | Windows/container/workspace/artifact URL normalize |
| HATE-P1A-008 | replay/compare/explain/recommend hardening | `src/hate`, `tests` | frozen bundle hashがdeterministic |
| HATE-P1A-009 | doctor finding taxonomy | `src/hate/doctor`, `docs/process/PRODUCT_ERROR_TAXONOMY.md` | finding category/error code/remediation |

## 6. P1b Tasks

| task_id | title | affected paths | acceptance |
|---|---|---|---|
| HATE-P1B-001 | RanD requirements packet ingest | `src/hate/integrations/rand`, `fixtures/rand` | requirements/KPI/acceptanceを読む |
| HATE-P1B-002 | RanD audit no-overwrite | `src/hate/integrations/rand`, `tests` | no_goをgoに変えない |
| HATE-P1B-003 | requirement evidence alignment | `src/hate/integrations/rand` | requirement-risk-test-evidence link |
| HATE-P1B-004 | Shipyard WorkerResult ingest | `src/hate/integrations/shipyard`, `fixtures/shipyard` | run/audit refsを保持 |
| HATE-P1B-005 | Shipyard no-overwrite test | `tests` | publish_gate_override=false固定 |
| HATE-P1B-006 | workflow-cookbook evidence mapping | `src/hate/integrations/workflow`, `fixtures/workflow` | task/acceptance/evidence/birdseyeを生成 |

## 7. P2 Tasks

| task_id | title | affected paths | acceptance |
|---|---|---|---|
| HATE-P2-001 | local store and history index | `src/hate/store`, `.hate fixture` | run/bundle/history再読込 |
| HATE-P2-002 | hosted read model API | `src/hate/api`, `tests/api` | envelope/resource/filter/error contract |
| HATE-P2-003 | dashboard view model | `src/hate/read_model`, `fixtures/dashboard` | required viewsのJSON生成 |
| HATE-P2-004 | PR annotation export | `src/hate/exporters/github_pr` | changed high-risk path annotation |
| HATE-P2-005 | artifact budget report | `src/hate/reports` | size/retention/exposure limit |
| HATE-P2-006 | attestation report | `src/hate/reports` | bundle hash/provenance material |
| HATE-P2-007 | Allure/ReportPortal/Codecov/SonarQube exporters | `src/hate/exporters` | exporter failure non-gating |
| HATE-P2-008 | support diagnostic bundle | `src/hate/support` | no secret/PII/customer code |

## 8. P3 Tasks

| task_id | title | affected paths | acceptance |
|---|---|---|---|
| HATE-P3-001 | domain model implementation | `src/hate/domain` | org/workspace/project/repo/run/bundle model |
| HATE-P3-002 | RBAC matrix | `src/hate/authz`, `tests/authz` | role/permission allow/deny tests |
| HATE-P3-003 | audit event log | `src/hate/audit`, `fixtures/audit` | required audit event fixtures |
| HATE-P3-004 | retention/legal hold/export/delete | `src/hate/governance` | artifact classification linked |
| HATE-P3-005 | SSO/SCIM connector contract | `src/hate/connectors` | dry-run connector fixtures |
| HATE-P3-006 | SIEM/warehouse/ticket connector contract | `src/hate/connectors` | export failure non-gating |
| HATE-P3-007 | trust packet/security review | `src/hate/security` | control mapping/vulnerability fixture |
| HATE-P3-008 | residency/deployment report | `src/hate/enterprise` | local/hosted/private/airgap modes |
| HATE-P3-009 | commercial/legal commitment register | `src/hate/enterprise` | unsupported claim flagged |
| HATE-P3-010 | assurance pack/evidence room | `src/hate/assurance` | auditor walkthrough fixture |
| HATE-P3-011 | release candidate pack | `src/hate/release` | pack contains required reports |

## 9. 実装順のロック

実装順は P0a -> P0b -> P1a -> P1b -> P2 -> P3 を原則とする。
ただし、schema validation、artifact safety、adapter registry は横断基盤なので、
P0a/P0bの途中で先に入れてよい。

## 10. Completion Dashboard

各タスクは以下の状態だけを持つ。

| status | 意味 |
|---|---|
| `planned` | 仕様とacceptanceがある |
| `in_progress` | コード実装中 |
| `implemented` | コードとfixtureがある |
| `verified` | 自動テストとcompileが通る |
| `accepted` | docs/runbook/evidenceまで更新済み |
| `blocked` | 外部依存または仕様矛盾で停止 |

`implemented` 以前の状態を完了扱いしない。

## 11. Product-Grade Expansion Tasks

本節は `PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` を実装 work package へ落とす。
P0a-P3 の既存 task が prototype/minimal acceptance を満たしていても、本節の task が
未完了なら product-ready ではない。

| task_id | title | affected paths | acceptance |
|---|---|---|---|
| HATE-PG-001 | adapter corpus and conformance expansion | `src/hate/adapters`, `fixtures/adapters`, `tests/adapters` | JUnit/pytest/Jest/Vitest/Playwright/Coverage/SARIF/Pact/Stryker の dialect/negative/conformance が report化される |
| HATE-PG-002 | cross-record schema validator | `src/hate/schema`, `schemas/HATE/v1`, `tests/schema` | generated artifacts と invalid fixture が schema/cross-ref/hash validation を通る |
| HATE-PG-003 | evidence graph domain implementation | `src/hate/graph`, `fixtures/graph`, `tests/graph` | requirement/risk/test/execution/artifact/coverage/finding/manual node と edge が辿れる |
| HATE-PG-004 | artifact safety and quarantine engine | `src/hate/security`, `fixtures/security`, `tests/security` | secret/PII/path/archive/external URL/redaction の negative fixture が quarantine される |
| HATE-PG-005 | immutable local store and replay | `src/hate/store`, `fixtures/store`, `tests/store` | atomic write、hash、history、replay、compare、migration、corruption handling が report化される |
| HATE-PG-006 | profile policy and AETE signal engine | `src/hate/profile`, `src/hate/aete`, `fixtures/profile`, `fixtures/aete` | fixed scoreではなく signal source と reason refs から deterministic に計算される |
| HATE-PG-007 | API read model and contract tests | `src/hate/api`, `fixtures/api`, `tests/api` | resource/filter/pagination/authz/error/staleness の contract test が通る |
| HATE-PG-008 | dashboard view model and UI UAT | `src/hate/dashboard`, `fixtures/dashboard`, `tests/dashboard` | required views が API/read model 由来で、unsafe artifact を直接露出しない |
| HATE-PG-009 | RBAC/audit/retention/residency controls | `src/hate/authz`, `src/hate/audit`, `src/hate/governance`, `fixtures/enterprise` | allow/deny、audit hash chain、legal hold、deployment mode fixture が通る |
| HATE-PG-010 | enterprise connector dry-runs | `src/hate/connectors`, `fixtures/connectors`, `tests/connectors` | SSO/SCIM/SIEM/warehouse/ticket exporter failure が canonical bundle を変えない |
| HATE-PG-011 | support/ops/migration closure | `src/hate/support`, `docs/process/RUNBOOK.md`, `fixtures/support` | diagnostic bundle、error code、migration、rollback、incident handoff が揃う |
| HATE-PG-012 | release candidate and assurance pack | `src/hate/release`, `fixtures/release`, `tests/release` | required product reports、QEG result refs、open risk、assurance refs が pack に含まれる |
| HATE-PG-013 | test integrity and AI-abuse detector | `src/hate/test_integrity`, `fixtures/test-integrity`, `tests/test_integrity` | strict signal gate matrix、anti-evasion rules、required fixture matrix、manual review record requirement を満たし、skip/xfail/only/todo 増加、mock abuse、assertion quality、implementation-test coupling、risk without oracle、coverage without evidence、manual review required が product readiness を降格する |
| HATE-PG-014 | scale and performance validation | `src/hate/performance`, `fixtures/scale`, `tests/performance` | 100k test / 10M coverage / 100k artifact metadata の設計fixture、latency/memory/pagination/aggregation budget が report化される |
| HATE-PG-015 | lifecycle migration compatibility | `src/hate/migrations`, `fixtures/migrations`, `tests/migrations` | schema/store/API/profile/adapter/view-model の before/after/rollback/deprecation fixture が通る |
| HATE-PG-016 | commercial truthfulness gate | `src/hate/commercial`, `fixtures/commercial`, `tests/commercial` | unsupported/planned/contracted claim が実装証跡へ trace され、unsupported claim は product-ready を block する |

各 `HATE-PG-*` は `PRODUCT_REQUIREMENTS_DEFINITION.md` の `FR-*`, `NFR-*`, `AC-REQ-*`
へ trace できなければ `accepted` にできない。

## 12. Product-Grade Done Rules

各 `HATE-PG-*` は、以下を満たすまで `accepted` にできない。

| Done evidence | Required |
|---|---|
| implementation code | yes |
| schema or API contract | yes when artifact/API exists |
| fixture input | yes |
| machine-readable expected output | yes |
| negative fixture | yes |
| contract/golden/unit test | yes |
| product error code | yes for user-facing failure |
| runbook/admin/support docs | yes |
| CI command evidence | yes |
| UAT or manual-bb gate | yes for UI/release/enterprise |

禁止:

- `tests passed` だけで `product-ready` にする
- report生成だけで RBAC/audit/retention を実装済みにする
- dashboard view model だけで dashboard UI 実装済みにする
- API schema だけで hosted API 実装済みにする
- connector dry-run なしに enterprise connector 実装済みにする
- release candidate pack に missing report がある状態で release-ready とする
- test integrity signal が未実装または unresolved の状態で product-ready とする
