---
intent_id: INT-HATE-PRODUCT-GRADE-IMPLEMENTATION-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# 製品グレード実装仕様

## 1. 目的

本書は `harness-auto-test-evidence` を「動く最小実装」ではなく、
実利用できる製品実装へ進めるための worker-facing specification である。

既存の `SPECIFICATION.md` は HATE の責務境界、record contract、phase contract を定義する。
`PRODUCT_REQUIREMENTS_DEFINITION.md` は製品要件、利用者、業務フロー、受入条件を定義する。
本書はその上に、以下を固定する。

- どの粒度まで作れば product-grade と言えるか
- adapter、fixture、schema、API、UI、store、enterprise control をどれだけ具体化するか
- どの状態を「実装済み」と呼んではいけないか
- 50万行級の実装へ自然に分解できる work package と受入条件
- 実装者が薄い placeholder、単発fixture、手書きexpectedで完了扱いできないようにする禁止条件

要件を実装へ落とす補助正本は `USER_STORY_MAP.md`, `ACCEPTANCE_CRITERIA_MATRIX.md`,
`API_REQUIREMENTS.md`, `UI_WORKFLOW_REQUIREMENTS.md`, `DATA_RETENTION_LEGAL_REQUIREMENTS.md`,
`SCALE_PERFORMANCE_REQUIREMENTS.md`, `IMPLEMENTATION_EPIC_BREAKDOWN.md` とする。

本書は行数目標そのものを品質指標にしない。ただし、製品グレードの実装は
adapter matrix、negative fixture、contract test、API/UI、store、enterprise control、
support/ops を含むため、結果として小規模 prototype の数万行には収まらない。

## 2. Product-Grade の定義

`product-grade` は次を満たす状態である。

| 領域 | Product-grade definition | Prototypeではない条件 |
|---|---|---|
| Adapter | 実フォーマット差分、dialect、失敗系、capability、conformanceを持つ | happy path parserだけでは不可 |
| Evidence | sourceRefs、hash、provenance、artifact safety、profile差分を保持する | JSONを生成するだけでは不可 |
| Store | run/bundle/history/risk debtを再読込・差分比較できる | 出力ディレクトリにファイルを置くだけでは不可 |
| API | read model、pagination、filter、authz、error envelope、stalenessを固定する | HTML/JSONを直接読むだけでは不可 |
| UI | run/risk/evidence/artifact/doctor/releaseを探索できる画面仕様を持つ | 単一dashboard HTMLだけでは不可 |
| Security | secret/PII/path traversal/archive/external URL/redactionを実検査する | `safe=true` の固定値では不可 |
| Enterprise | RBAC/audit/retention/residency/connector/assuranceを artifact として再計算できる | レポート名だけでは不可 |
| Test | golden、negative、contract、property、replay、E2E、migrationを持つ | pytest数十件だけでは不可 |
| Ops | error code、diagnostic bundle、migration、rollback、incident、support handoffを持つ | READMEの手順だけでは不可 |

Product-grade completion は `docs/process/IMPLEMENTATION_TASK_BREAKDOWN.md` の task が
`accepted` になっただけでは足りない。各 product area の acceptance が、現在の code、
schema、fixture、test、runbook、CI evidence で検証されている必要がある。

## 3. 実装規模の設計目安

以下は目標行数ではなく、必要な実装面の厚みを逃がさないための規模レンジである。
実装者は「小さく終える」ためにこの表を下回る設計を選んではならない。

| Area | Expected implementation mass | 代表成果物 |
|---|---:|---|
| Adapter implementations | 60k-120k LOC equivalent | parser、normalizer、capability、fixtures、conformance |
| Schema and contract validation | 30k-60k LOC equivalent | JSON Schema、cross-record validator、migration test |
| Fixture corpus and golden outputs | 80k-160k LOC equivalent | real-world samples、negative matrix、large-run fixture |
| Local store/history/replay | 25k-60k LOC equivalent | index、bundle store、diff、history、hash chain |
| API/read model | 35k-80k LOC equivalent | resource handlers、filters、authz、errors、contract tests |
| Dashboard/UI | 50k-120k LOC equivalent | views、components、state、accessibility、visual regression |
| Security/privacy/quarantine | 25k-70k LOC equivalent | scanners、redaction、archive policy、quarantine reports |
| Enterprise controls | 50k-120k LOC equivalent | RBAC、audit、retention、residency、connectors、assurance |
| Test harness and CI | 50k-120k LOC equivalent | unit、integration、E2E、property、fuzz、snapshot、mutation |
| Docs/runbook/support | 30k-80k LOC equivalent | admin guide、adapter guide、migration、support playbook |

このレンジは生成行数の水増しを求めるものではない。逆に、以下は禁止する。

- fixture expected を大量に複製して規模を満たしたように見せる
- 実 parser なしに schema と docs だけを増やす
- `TODO`, `future`, `stub`, `placeholder` を受入済み機能として数える
- 実CI、実入力、negative testなしに adapter 対応済みと表現する
- dashboard mock を product surface 実装済みと表現する

## 4. Product Work Package

### 4.1 P0 Adapter Productization

P0 adapter productization は、P0a/P0b の parser を実入力に耐える製品部品にする。

| ID | Work package | Required implementation | Required fixture | Acceptance |
|---|---|---|---|---|
| PG-ADP-001 | JUnit dialect suite | Surefire、Gradle、pytest、Jest、Vitest、Playwright、Go test JUnitの差分吸収 | 7 dialect x pass/fail/error/skip/flaky | canonical `test_result` の差分が説明される |
| PG-ADP-002 | pytest JSON/JUnit merge | nodeid、markers、xfail、rerun、duration、file pathを統合 | json-only、junit-only、both、conflict | conflict policy が doctor finding に出る |
| PG-ADP-003 | JS test result suite | Jest/Vitest nested suite、snapshot、browser matrix、watch artifact除外 | jest/vitest各12ケース以上 | snapshot mismatch と flaky retry を別信号にする |
| PG-ADP-004 | Playwright evidence suite | trace/screenshot/video/log、attachment ref、browser/project matrix | safe/secret/pii/missing/large/archive | unsafe artifactがsummary/QEG/exportへ漏れない |
| PG-ADP-005 | Coverage suite | LCOV、Cobertura、JaCoCo、coverage.py context、branch coverage | normal/partial/windows/container/malformed | coverage-only DQ と context有無を説明する |
| PG-ADP-006 | Static/contract/mutation | SARIF、Pact、Stryker、Sonar-like importを正規化 | high/critical、contract fail、survived mutant | risk/test/evidence edgeへ接続される |
| PG-ADP-007 | Adapter SDK | manifest、parser interface、capability、conformance runner | sample external adapter | SDKだけで新adapterの合否を自己検証できる |

Adapter completion requires:

- parser implementation
- schema-backed output
- capability manifest
- conformance fixture
- negative fixture
- profile-specific failure policy
- cross-record sourceRefs
- product error code
- runbook example

### 4.2 Evidence Graph Productization

Evidence graph は file output ではなく、risk、requirement、test、execution、artifact、
coverage、finding、manual補完を辿れる product domain である。

Required graph nodes:

| Node | Required fields |
|---|---|
| `requirement` | id, title, source_ref, owner, acceptance_refs, upstream_verdict |
| `changed_entity` | path, symbol, diff_hunk, risk_refs, code_owner, language |
| `risk` | severity, category, source, required_layers, manual_policy |
| `test` | canonical_test_id, suite, layer, owner, source_refs, oracle_type |
| `execution_evidence` | status, attempt, duration, retry_index, environment, artifact_refs |
| `coverage_evidence` | file, line/branch, context, test_refs, normalization_result |
| `finding` | tool, rule, level, location, source_refs, suppression_state |
| `artifact` | artifact_id, hash, classification, redaction, safety_checks |
| `risk_debt` | debt_id, status, age, owner, recommended_actions |
| `manual_request` | request_id, gap_type, required_oracle_refs, status |

Required edge types:

| Edge | Meaning | No-Go |
|---|---|---|
| `requires_test` | risk or requirement requires a test layer | high risk without edge is hidden gap |
| `executed_by` | test has execution evidence | coverage-only must not create this edge |
| `covered_by` | changed entity covered by coverage evidence | line hit without context is weak evidence |
| `supported_by` | requirement/risk supported by evidence | unsupported claim must be explicit |
| `contradicted_by` | finding/contract/mutation contradicts readiness | must not be dropped from summary |
| `attached_artifact` | evidence has artifact manifest item | unsafe artifact must point to quarantine |
| `requires_manual` | gap requires manual-bb supplement | manual request cannot be waiver |

W07 implementation boundary:

- `src/hate/evidence_graph.py` builds deterministic `evidence_graph` records from validated bundle
  inputs: `requirements`, `risks`, `claims`, `records`, `manual_reviews`, and explicit `edges`.
- `src/hate/readiness_model.py` computes product readiness from graph edges only. A release claim is
  supported only when it derives from a requirement that has `supported_by` or `reviewed_by` evidence.
- Contradiction edges (`contradicted_by`, `blocked_by`) are surfaced in `product-readiness-report.json`
  and block readiness.
- Missing claim requirement refs, orphan evidence, unknown edge kinds, and `requires_test` cycles are
  hard findings.
- `unsupported_claim_marked_ready` is a hard DQ. A ready claim without a supported graph path must not
  pass product readiness.

### 4.3 Store and Replay Productization

Local store is mandatory before hosted/API can be accepted.

```text
.hate/
  store-version.json
  runs/<repo_hash>/<run_id>/<attempt>/
    input-manifest.json
    canonical-bundle/
    derived/
    validation/
    audit/
  indexes/
    runs.jsonl
    bundles.jsonl
    evidence.jsonl
    risk-debt.jsonl
    artifacts.jsonl
    audit-events.jsonl
  locks/
  migrations/
```

Store requirements:

| ID | Requirement | Acceptance |
|---|---|---|
| PG-STO-001 | Atomic write | interrupted write leaves previous bundle readable |
| PG-STO-002 | Immutable bundle | canonical bundle hash changes on content mutation |
| PG-STO-003 | History index | latest run, previous run, baseline run can be resolved |
| PG-STO-004 | Replay | frozen input reproduces derived outputs byte-stably where deterministic |
| PG-STO-005 | Compare | two runs explain changed decision, score, risk debt, parser failures |
| PG-STO-006 | Migration | schema minor migration has before/after fixture |
| PG-STO-007 | Corruption handling | missing index, bad hash, partial bundle produce doctor finding |

No-Go:

- hosted read model before local store replay passes
- baseline comparison based only on filename sorting
- mutating canonical bundle during external export

### 4.4 API Productization

API is a product contract, not a convenience JSON dump.

Required API resources:

| Resource | Methods | Required behaviors |
|---|---|---|
| `/v1/runs` | GET | filter, pagination, sort, staleness, tenant scope |
| `/v1/runs/{run_id}/attempts/{attempt}` | GET | run detail, provenance, decision, profile |
| `/v1/evidence` | GET | filter by run, risk, test, kind, trust score |
| `/v1/risks` | GET | changed entity, severity, required layer, debt |
| `/v1/artifacts` | GET | classification, safety, quarantine, signed URL policy |
| `/v1/doctor/findings` | GET | error code, severity, remediation, sourceRefs |
| `/v1/risk-debt` | GET/PATCH | status transition with audit event |
| `/v1/profiles` | GET/POST | profile diff, policy hash, validation |
| `/v1/bundles/import` | POST | validate, store, index, audit |
| `/v1/exports/{provider}` | POST | non-gating export with before/after hash |

Response envelope:

```yaml
request_id: string
tenant:
  organization_id: string
  workspace_id: string
resource: string
schema_version: HATE/v1
generated_at: ISO-8601
source:
  bundle_hash: string
  run_id: string
  attempt: number
staleness:
  status: fresh | stale | rebuilding
  reason: string | null
pagination:
  limit: number
  cursor: string | null
data: object | array
errors:
  - code: string
    message: string
    remediation: string
```

API No-Go:

- returning restricted artifact paths to `viewer`
- changing precheck/QEG result through PATCH endpoints
- returning stale read model without explicit staleness
- accepting bundle import without schema and hash validation

### 4.5 Dashboard Productization

Dashboard must be a read model consumer. It must not compute verdicts.

Required views:

| View | User question | Required interactions |
|---|---|---|
| Run Overview | Why did this run pass/hold/block? | profile switch, decision reasons, previous run compare |
| Risk Coverage | Which changed risks lack evidence? | filter by severity/layer/owner, manual request creation |
| Evidence Graph | Can I trace requirement -> risk -> test -> artifact? | node search, edge filter, sourceRef drawer |
| Adapter Health | Which adapters are weak or failing? | conformance detail, parser failures, known limits |
| Artifact Safety | What was quarantined and why? | classification filter, redaction status, remediation |
| Doctor | What should I fix first? | severity sorting, copyable command, linked docs |
| Risk Debt | What gaps are aging? | lifecycle transition, owner, audit trail |
| Release Pack | Is this release candidate supportable? | pack checklist, missing artifact, QEG result ref |
| Admin | Who can access what? | role matrix, audit log, retention policy |

UI acceptance:

- every view is backed by an API/read model contract
- every decision reason links to sourceRefs or explicit unsupported claim
- color is never the only severity signal
- unsafe/restricted artifact is never linked directly to unauthorized users
- mobile layout may be reduced, but must not hide hard DQ or required manual action

### 4.6 Security, Privacy, and Quarantine Productization

Required scanners and policies:

| Control | Required implementation | Required negative fixture |
|---|---|---|
| Secret scan | token patterns, entropy, provider examples, allowlist | log with fake token |
| PII scan | email, phone, address-like, configured custom regex | screenshot/log metadata sample |
| Path safety | absolute path, traversal, symlink, Windows drive, UNC | `../`, symlink, `C:\Users\...` |
| Archive safety | max file count, max expanded size, nested archive, MIME mismatch | zip bomb-like fixture |
| External URL | allowlist, metadata IP block, redirect policy | localhost/metadata URL |
| Redaction | before/after hash, redaction rule version, pending/failed state | pending redaction fixture |
| Summary safety | safe field allowlist, unsafe field blocklist | unsafe artifact title/path |

Security No-Go:

- public summary includes raw local absolute path
- diagnostic bundle contains customer code or artifact body
- quarantine item can be exported externally by default
- failed redaction is treated as `safe_for_summary=true`
- external URL fetch is allowed without policy

### 4.7 Enterprise Controls Productization

Enterprise controls must be connected to domain model and audit evidence.

| Control | Required records | Acceptance |
|---|---|---|
| RBAC | role, permission, resource scope, deny reason | allow/deny matrix tests |
| Audit log | event_type, actor, target, before/after, sourceRefs | append-only hash chain fixture |
| Retention | policy, classification, legal hold, action | delete/export simulation |
| Residency | deployment mode, region, data class routing | hosted/private/airgap fixture |
| SSO/SCIM | connector config, dry-run result, fallback | unavailable connector non-gating |
| SIEM/Warehouse/Ticket | export request/result, non-gating flag | API failure does not alter canonical bundle |
| Assurance pack | control mapping, evidence room, open limitations | auditor walkthrough fixture |
| Commercial commitments | claim, source contract, support state | unsupported claim flagged |

Enterprise No-Go:

- commercial/procurement docs claim a capability is available without implementation evidence
- retention/delete ignores legal hold
- audit event lacks actor or sourceRefs
- enterprise connector failure changes local precheck

## 5. Test and Fixture Strategy

### 5.1 Test Layers

| Layer | Required coverage |
|---|---|
| Unit | parser, normalizer, validator, policy, mapper |
| Contract | JSON Schema, API envelope, adapter SDK, external exporter |
| Golden | P0a/P0b/P1a/P1b/P2/P3 expected outputs |
| Negative | malformed, missing required, unsafe artifact, unsupported claim |
| Property | deterministic ids, path normalization, hash stability |
| Fuzz | XML/JSON parser resilience and archive safety bounds |
| Replay | frozen bundle byte-stability |
| Migration | schema and store version transitions |
| E2E | CLI -> store -> API -> dashboard view model |
| UAT | manual black-box checklist and Go/No-Go brief |

### 5.2 Fixture Corpus Minimum

Product-grade minimum fixture corpus:

| Corpus | Minimum |
|---|---:|
| CI contexts | 20 |
| test result dialects | 80 |
| coverage dialects | 50 |
| artifact safety cases | 60 |
| SARIF/contract/mutation cases | 50 |
| risk/test/evidence graph cases | 40 |
| profile decision cases | 30 |
| store/replay/migration cases | 30 |
| API contract cases | 60 |
| dashboard view model cases | 30 |
| RBAC/audit/retention cases | 50 |
| release/assurance cases | 30 |

Each fixture must declare:

```yaml
fixture_id: string
purpose: string
phase: P0a | P0b | P1a | P1b | P2 | P3
input_refs: array
expected_refs: array
negative: boolean
expected_decision: string | null
expected_errors: array
source_requirement_refs: array
```

### 5.3 Acceptance Evidence Rule

No task may be accepted without all of:

- code path exercised by test
- fixture input
- machine-readable expected output
- negative or failure case
- docs/runbook reference
- product error code for user-facing failure
- CI command proving the test scope
- test integrity signal coverage when tests, risk evidence, or oracle behavior changed

## 6. Test Integrity and AI-Implementation Abuse Signals

Product-grade HATE must detect test-quality regressions introduced by AI or automation.
These signals are not release verdicts by themselves, but they must affect doctor findings,
AETE oracle strength, risk debt, manual review routing, and product readiness.

| signal_id | Detects | Required inputs | Required behavior |
|---|---|---|---|
| `test_skip_detected` | changed test files introduced or increased `skip`, `xfail`, `only`, `todo`, disabled suites, or framework-specific pending tests | test result records, changed files, optional AST/text scan | emit doctor finding; harden to `hold` when high-risk required tests are skipped or `only` narrows execution |
| `mock_abuse_detected` | excessive mocks, empty stubs, always-success fakes, or mocks inside non-boundary code | test source refs, dependency boundary map, changed files | mark oracle strength weak; require manual review when mocks replace the behavior under test |
| `assertion_quality` | tests execute code without meaningful assertions, assert only truthiness, snapshots only, or only check that no exception is raised | test source refs, framework parser, mutation/contract corroboration | lower AETE `oracle_strength`; emit remediation with expected oracle shape |
| `implementation_test_coupling` | production code branches on test names, fixture names, env flags, CI markers, or golden fixture paths | production diff, test/fixture names, env var references | create high-severity doctor finding; `hold` when runtime behavior changes only for tests/fixtures |
| `risk_without_oracle` | changed risk has execution or coverage but no explicit expected value, contract, property, mutation, or manual oracle | risk graph, test obligations, evidence graph | `hold` for high/critical risk; otherwise create risk debt and manual-bb request |
| `coverage_without_evidence` | coverage exists without meaningful execution evidence, assertions, or traceable oracle | coverage slices, test results, assertion_quality, evidence graph | soft gap by default; hard DQ only for release profile when it is the only evidence for required high risk |
| `manual_review_required` | suspicious AI-style avoidance code, fixture-name coupling, broad mocks, missing oracle, or impossible-to-verify claim | all signals, doctor findings, sourceRefs | route to human review; must not be auto-waived by HATE |

### 6.1 Signal Output Contract

Each signal must be emitted as a machine-readable finding.

```yaml
test_integrity_signal:
  signal_id: test_skip_detected | mock_abuse_detected | assertion_quality | implementation_test_coupling | risk_without_oracle | coverage_without_evidence | manual_review_required
  severity: info | low | medium | high | critical
  status: present | absent | inconclusive
  affected_refs:
    - kind: test | source | fixture | risk | evidence | coverage
      path: string
      symbol: string | null
  reason: string
  recommended_action: string
  product_effect:
    aete_dimension: string | null
    decision_impact: none | soft_gap | conditional | hold | hard_dq
    manual_review: boolean
```

### 6.2 Test Integrity No-Go

Product-ready must be blocked when any of the following is true:

- `only` or equivalent focused-test marker is introduced in committed tests
- high/critical changed risk has `risk_without_oracle`
- production code contains `implementation_test_coupling`
- required evidence is only `coverage_without_evidence`
- `mock_abuse_detected` affects the behavior under test rather than an external boundary
- `manual_review_required=true` is unresolved

The detector must distinguish legitimate external-boundary mocks from abuse. A mock is allowed when
it replaces network, filesystem, clock, random, secrets, third-party API, or unavailable platform
boundaries and the expected behavior is asserted through a domain oracle.

### 6.3 Strict Signal Gate Matrix

The default posture is fail-closed for release/product claims. A signal may be downgraded only when
the report contains sourceRefs, explicit justification, expiry, and owner.

| Signal | default profile | strict profile | release/product profile | Allowed exception |
|---|---|---|---|---|
| `test_skip_detected` for `only` / focused run | `hold` | `hold` | `hard_dq` | none |
| `test_skip_detected` for new skip/xfail/todo in changed required tests | `conditional` | `hold` | `hold` | linked issue, owner, expiry, non-high-risk |
| `mock_abuse_detected` at external boundary with domain oracle | `soft_gap` | `conditional` | `conditional` | boundary declared in manifest |
| `mock_abuse_detected` replacing behavior under test | `hold` | `hold` | `hard_dq` | none |
| `assertion_quality` weak assertion in non-risk code | `soft_gap` | `conditional` | `conditional` | mutation/contract/manual oracle corroborates |
| `assertion_quality` no meaningful oracle for required risk | `hold` | `hold` | `hard_dq` | none |
| `implementation_test_coupling` in production code | `hold` | `hard_dq` | `hard_dq` | none |
| `risk_without_oracle` for high/critical risk | `hold` | `hold` | `hard_dq` | manual-bb evidence already linked |
| `coverage_without_evidence` as supplementary signal | `soft_gap` | `soft_gap` | `conditional` | execution evidence and oracle exist |
| `coverage_without_evidence` as sole evidence for required risk | `hold` | `hold` | `hard_dq` | none |
| `manual_review_required` unresolved | `conditional` | `hold` | `hold` | human review record attached |

### 6.4 Anti-Evasion Rules

The detector must not rely only on test result summaries. It must compare the changed files,
test source, production source, fixture names, environment variables, and generated evidence.

Required anti-evasion checks:

- Treat `it.only`, `test.only`, `describe.only`, `fit`, `fdescribe`, pytest `-k` narrowing in CI config,
  Jest/Vitest focused tests, Playwright focused tests, and framework pending markers as focused/skip signals.
- Treat renamed wrappers around skip/focus helpers as suspicious when they call known skip/focus APIs.
- Treat production references to fixture paths, golden fixture names, test names, `PYTEST_CURRENT_TEST`,
  `JEST_WORKER_ID`, `VITEST`, `PLAYWRIGHT_TEST`, `CI=true` special branches, or `NODE_ENV=test`
  behavior changes as implementation-test coupling unless explicitly declared in a test harness boundary.
- Treat empty stubs, `return true`, `pass`, no-op callbacks, always-success fake clients, and mocks returning
  fixture-shaped success as mock abuse when they replace the behavior under test.
- Treat tests with no assertions, assertion count zero, only smoke execution, only snapshot approval,
  only type/import checks, or only "does not throw" as weak oracle unless another evidence type supplies the oracle.
- Treat coverage lines, branch hit counts, and executed test counts as insufficient unless connected to a
  test oracle, contract, property, mutation kill, manual case result, or explicit expected value.

### 6.5 Required Fixture Matrix

`HATE-PG-013` cannot be accepted until these fixtures exist.

| Fixture | Expected signal | Expected decision impact |
|---|---|---|
| focused-test-only | `test_skip_detected` | `hard_dq` in release/product |
| new-xfail-high-risk | `test_skip_detected` + `manual_review_required` | `hold` |
| new-todo-low-risk-with-expiry | `test_skip_detected` | `conditional` |
| boundary-mock-with-oracle | `mock_abuse_detected=absent` or low | no stronger than `soft_gap` |
| behavior-under-test-mocked | `mock_abuse_detected` | `hold` or `hard_dq` |
| no-assertion-smoke-test | `assertion_quality` | `conditional` |
| snapshot-only-risk-test | `assertion_quality` | `hold` when required risk |
| production-branches-on-fixture | `implementation_test_coupling` | `hard_dq` |
| high-risk-execution-no-oracle | `risk_without_oracle` | `hold` or `hard_dq` |
| coverage-only-required-risk | `coverage_without_evidence` | `hold` or `hard_dq` |
| suspicious-ai-avoidance-code | `manual_review_required` | `hold` |

### 6.6 Review Record Requirement

Human review can clear `manual_review_required` only with a source-backed review record.

```yaml
manual_review_record:
  review_id: string
  reviewer: string
  reviewed_at: ISO-8601
  signals_reviewed: array
  decision: accepted | rejected | changes_required
  rationale: string
  source_refs: array
  expiry: ISO-8601 | null
```

HATE must not synthesize this record on behalf of a human reviewer. Missing review record keeps
the signal unresolved.

## 7. Completion Claim Taxonomy

| Claim | Allowed only when |
|---|---|
| `specified` | product-grade requirement, input, output, failure, acceptance, No-Go are written |
| `designed` | data model, API/schema, state transitions, security policy, migration are written |
| `implemented` | production code exists and is reachable by CLI/API/UI |
| `verified` | unit/contract/golden/negative tests pass in CI |
| `operationalized` | runbook, diagnostic, error code, migration/rollback, support handoff exist |
| `product-ready` | implementation, verification, operations, UAT, release pack all pass |

Forbidden claims:

- `implemented` for docs-only or fixture-only work
- `product-ready` for local CLI-only implementation
- `enterprise-ready` without RBAC/audit/retention/residency/assurance evidence
- `release-ready` without QEG result ref and release candidate pack

## 8. Implementation Roadmap Lock

The implementation roadmap must be expanded into work packages, not single broad tasks.

Required breakdown:

1. Adapter corpus and conformance
2. Cross-record schema validator
3. Evidence graph and risk coverage matrix
4. Artifact safety and quarantine engine
5. Local store, immutable bundle, replay
6. Profile policy engine and AETE signal scoring
7. Test integrity and AI-implementation abuse detector
8. Large-scale fixture and performance validation
9. API read model and contract tests
10. Dashboard view models and UI
11. RBAC, audit, retention, residency
12. External exporters and connector dry-runs
13. Lifecycle migration and compatibility
14. Commercial truthfulness gate
15. Release candidate pack and assurance pack
16. Support, incident, customer docs

Every roadmap item must include:

- requirement IDs from `PRODUCT_REQUIREMENTS_DEFINITION.md`
- owner role
- affected paths
- input formats
- output artifacts
- schema refs
- fixture refs
- negative cases
- CI commands
- UAT checks
- No-Go conditions

## 9. Product Spec Completion Gate

This specification expansion is complete only when:

- `PRODUCT_REQUIREMENTS_DEFINITION.md` defines stakeholders, journeys, functional/non-functional requirements, data/authz/ops requirements, acceptance, and release stages
- `SPECIFICATION.md` lists this document as priority 1 or 2 source
- `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md` maps product-grade gaps to this document
- `IMPLEMENTATION_TASK_BREAKDOWN.md` has product-grade tasks or explicitly references this breakdown
- acceptance matrix distinguishes `specified`, `designed`, `implemented`, `verified`, `product-ready`
- no document claims current implementation is product-ready solely because prototype tests pass
