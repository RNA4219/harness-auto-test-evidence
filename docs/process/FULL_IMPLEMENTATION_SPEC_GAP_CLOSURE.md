---
intent_id: INT-HATE-FULL-SPEC-GAP-CLOSURE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# フル実装仕様不足解消書

## 1. 目的

本書は、`harness-auto-test-evidence` をフル実装へ進めるために不足していた仕様を
実装可能な単位へ閉じる正本である。既存の `SPECIFICATION.md`、`BLUEPRINT.md`、
各 contract 文書は維持しつつ、実装者が迷いやすい以下をここで固定する。

- 何を実装すれば phase complete なのか
- どの入力形式を受け、どの artifact を出すのか
- どの acceptance test / fixture / No-Go で完了判定するのか
- `advisory artifact` と `実装完了` を混同しないための境界
- 仕様書作成済み、fixture 作成済み、コード実装済み、運用実装済みの違い

本書は「未実装を future として逃がすための文書」ではない。各項目は
`IMPLEMENTATION_TASK_BREAKDOWN.md` の実装タスクへ落ち、コード、schema、fixture、
test、docs の5点が揃って初めて完了扱いにする。

ただし、本書の存在は「50万〜100万行級の製品実装に必要な全要件が
未仕様ゼロで閉じた」ことを意味しない。未仕様、浅い仕様、実装packet不足、
fixture不足、runtime/operational不足は `PRODUCT_REQUIREMENTS_GAP_BACKLOG.md`
で管理し、同backlogが閉じるまで product-scale full implementation ready とは
主張しない。

発見済みgapの実装packet化は `PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md` を
正本とする。workflow-cookbook 由来の Task Seed / Acceptance / Evidence /
Birdseye freshness / completion governance は
`WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md` を正本とする。

## 2. 不足解消ステータス

| 領域 | 既存の不足 | 本書で固定する解消内容 | 実装完了条件 |
|---|---|---|---|
| Requirements | 仕様やartifact名はあるが、顧客・業務・受入・段階要件が薄い | `PRODUCT_REQUIREMENTS_DEFINITION.md` でpersona、journey、FR/NFR、data/authz/ops、acceptanceを固定 | 各実装taskが requirement ID と acceptance ID へ trace される |
| Adapter | JUnit/LCOV中心で、多形式 adapter の完了条件が薄い | adapterごとの入力、出力、失敗、fixtureを定義 | adapter manifest、parser、negative fixture、conformance report |
| Coverage | LCOV/Cobertura/JaCoCo/coverage.py context の差が未固定 | format別 canonical payload と path normalization を定義 | 各format fixtureが `coverage_slice` に正規化される |
| Static/SARIF | SARIF finding と risk/test/evidence の結線条件が薄い | finding node、changed_code edge、DQ-010条件を定義 | SARIF fixtureがQEG finding nodeになる |
| Playwright | trace/screenshot/video/log の安全検査が抽象的 | artifact分類、quarantine、test_result添付を定義 | unsafe traceがsummary/QEG/exportから除外される |
| Pact/Stryker | contract/mutation evidence の採用条件が未固定 | record_type、AETE影響、QEG nodeを定義 | pact/stryker fixtureが evidence node と score reason になる |
| AETE | score式はあるが、入力signalとprofile差分が曖昧 | signal source、profile inheritance、dimension reasonを定義 | 同一bundle/profileで deterministic |
| Profile | profile差分がreport contractとして未固定 | DQ/soft_gap/AETE/manual/export policyの差分表を固定 | `profile-report.json` schema、registry、drift test |
| Schema | JSON Schema運用の合否基準が薄い | producer schema、migration、unknown field policyを実装単位化 | schema validationがCIで必須 |
| Storage | local artifact以上の履歴/DBが未定義 | local storeとhosted storeの境界を定義 | run/bundle/historyが再読込可能 |
| Hosted API | read model envelopeだけでAPI仕様が薄い | resource、filter、authz、error、stalenessを定義 | API fixture / contract test |
| Dashboard | HTML reportと実dashboardの境界が未固定 | dashboard view model と必須画面を定義 | API由来のview modelで描画可能 |
| RBAC/Audit | enterprise文書はあるが実装単位が不足 | roles、permissions、audit eventsを固定 | authz matrix test / audit log fixture |
| External Export | optional exportが成功/失敗時に何を壊さないか不足 | exporter contractとnon-gating保証を定義 | failure時もcanonical bundle不変 |
| QEG連携 | QEG runtime接続の実行契約が未固定 | validate/import/gate/record adapterを定義 | QEG CLI/APIのdry-run fixture |
| Shipyard/RanD/manual-bb | advisory artifactとlive連携の境界が曖昧 | live connectorとartifact connectorを分離 | upstream verdictを上書きしないtest |
| Release/Operations | versioning、migration、incident、support artifactが散在 | release gate evidence checklistを固定 | release candidate pack生成 |
| Product-grade depth | prototype完了と製品実装完了の境界が薄い | `PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` で規模レンジ、work package、No-Go、fixture/test minimumを固定 | product-grade evidence reports が揃うまで product-ready と主張しない |

## 3. Phase Complete の厳格定義

### P0a: Collect / Normalize / Precheck

P0a complete は、以下すべてを満たす状態である。

- GitHub Actions context、任意の generic CI context を `run` record に正規化する
- JUnit系結果を `test_result` に正規化する
- LCOV、Cobertura、JaCoCo、coverage.py context を `coverage_slice` に正規化する
- artifact manifest が空、通常、unsafe、missing、external URL、symlink、archive のfixtureを持つ
- `precheck-decision.json` が DQ / soft_gap / profile policy に基づいて決定される
- `record.json` が生成 artifact の own-output validation を保持する
- public summary に secret、PII、絶対パス、unsafe artifact path を出さない

P0a No-Go:

- parser failure を成功扱いで握りつぶす
- coverageだけで execution evidence がない状態を eligible にする
- fixture expected を手書き更新して実装済みにする
- absolute local path を public artifact に出す

### P0b: Correlate / QEG Export

P0b complete は、以下すべてを満たす状態である。

- `diff-risk-test.json` の changed entity、risk、test obligation を読み込む
- SARIF finding を `finding` node としてQEG bundleへ出す
- Playwright artifact refs を test/execution evidence として結線する
- risk -> required test -> execution -> artifact / coverage の edge を生成する
- missing execution、unsupported claim、unsafe artifact を hidden gap にしない
- `risk-debt-register.json` と `manual-bb-bridge-requests.jsonl` を gap発生時に生成する
- QEG validate/import に渡せる minimal bundle contractを満たす

P0b No-Go:

- high-risk missing execution を `success` のまま隠す
- unsafe artifact を QEG / external export へ混入させる
- QEG Gate verdict を HATE が作ったように表現する

### P1a: Trust Hardening

P1a complete は、以下すべてを満たす状態である。

- adapter registry が全adapterのcapability、required input、known limitを持つ
- profile inheritance `default -> strict -> release` が machine-readable に表現される
- AETE 8次元が evidence signal から計算され、reason_refs を持つ
- retry / matrix / shard aggregation が deterministic に動く
- canonical identity が rename、parameterized test、browser matrixを区別できる
- resolver が local path、workspace path、Windows path、container path、artifact URLを正規化する
- replay / compare / explain / recommend / doctor が frozen bundle から再計算できる

P1a No-Go:

- scoreを固定値、fixture名、雰囲気で出す
- profile指定で同一入力の結果が非決定的に変わる
- `calibration_status=uncalibrated` をrelease approval扱いにする

### P1b: External Workflow Integration

P1b complete は、以下すべてを満たす状態である。

- RanD `requirements_packet.json` / `requirements_audit_packet.json` を読み、verdictを保持する
- `requirement-evidence-alignment.json` が requirement / KPI / acceptance / risk / evidence を結ぶ
- manual-bb補完要求が high-risk gap から生成される
- Shipyard `WorkerResult` / `RunSystemPacket` refs へ HATE artifact を添付できる
- workflow-cookbook Task Seed / Acceptance / Evidence / Docs stale / Birdseye map を生成する
- upstream verdict、Shipyard state、workflow checker verdictを上書きしない

P1b No-Go:

- RanD `no_go` を HATE 側で `go` に変える
- Shipyard publish approval を HATE artifact で代替する
- workflow-cookbook checkerやBirdseye generatorを再実装する

### P2: Product Surface

P2 complete は、以下すべてを満たす状態である。

- hosted read model が canonical bundle から再構築できる
- REST API contract が resource、filter、pagination、authz、error envelopeを持つ
- dashboard view model が run、evidence、risk debt、artifact quarantine、doctor finding を表示できる
- PR annotation、artifact budget、attestation、external export が canonical decisionを変更しない
- product error catalog と support diagnostic bundle が安全に共有できる

P2 No-Go:

- hosted/dashboardがないのにSaaS availableと表現する
- external exporter failureでprecheck/QEG exportを変える
- diagnostic bundleにcustomer code、secret、PII、unsafe artifactを入れる

### P3: Enterprise Readiness

P3 complete は、以下すべてを満たす状態である。

- org / workspace / project / repo / run / bundle / profile のdomain modelが実装と一致する
- RBAC、audit log、retention、legal hold、export/delete requestの契約がある
- SSO/SCIM、SIEM、warehouse、ticketing connector はconnector contractとfallbackを持つ
- SLO、incident、security review、trust packet、residency、commercial commitmentがartifact化される
- assurance pack、audit fixture、portfolio health が release candidate pack に含まれる

P3 No-Go:

- sales / procurement claim が実装状態を超える
- retention / deletion / legal hold がartifact classificationと連動しない
- audit fixtureなしでcompliance readinessを主張する

## 4. Adapter 実装仕様

| adapter_id | 入力 | canonical output | required fixture | failure contract |
|---|---|---|---|---|
| `adapter.junit.v1` | JUnit XML | `test_result` | pass/fail/error/skipped, malformed, parameterized | malformed required input は DQ-002 |
| `adapter.pytest.v1` | pytest JUnit XML / json report | `test_result` | nodeid, duration, xfail, rerun | unknown status は soft_gap |
| `adapter.vitest.v1` | JUnit XML / json | `test_result` | browser/node env, flaky retry | missing file path は doctor finding |
| `adapter.jest.v1` | JUnit XML / json | `test_result` | snapshot failure, suite nesting | snapshot-only は oracle weak gap |
| `adapter.playwright.v1` | JUnit / JSON / trace / screenshot / video | `test_result`, `evidence_ref`, `artifact_manifest` | trace-safe, trace-secret, matrix browser | unsafe artifact quarantine |
| `adapter.lcov.v1` | `lcov.info` | `coverage_slice` | multi-file, branch, windows path | malformed required input は DQ-002 |
| `adapter.cobertura.v1` | Cobertura XML | `coverage_slice` | package/class/file, missing lines | partial parse warning or DQ by profile |
| `adapter.jacoco.v1` | JaCoCo XML | `coverage_slice` | package/sourcefile/branch | partial parse warning or DQ by profile |
| `adapter.coveragepy.v1` | coverage.py JSON/XML context | `coverage_slice` | context per test, no context | missing context lowers AETE |
| `adapter.sarif.v1` | SARIF 2.1.0 | `finding`, `static_evidence` | high/critical changed path, warning only | high/critical changed path triggers DQ-010 |
| `adapter.pact.v1` | Pact verification JSON | `contract_evidence` | can-i-deploy pass/fail | failed required contract is hard gap |
| `adapter.stryker.v1` | Stryker mutation report | `mutation_evidence` | survived/killed/no coverage | mutation gap lowers oracle strength |
| `adapter.allure.v1` | Allure results | external export/read model | missing history, attachments | optional failure non-gating |
| `adapter.reportportal.v1` | ReportPortal API/export | external export/read model | API unavailable | optional failure non-gating |
| `adapter.codecov.v1` | Codecov API/export | coverage corroboration | API unavailable | optional failure non-gating |
| `adapter.sonarqube.v1` | SonarQube issues/coverage | finding/corroboration | API unavailable | optional failure non-gating |

各 adapter は以下を出す。

```yaml
adapter_manifest:
  adapter_id: string
  adapter_version: string
  input_formats: array
  output_record_types: array
  required_inputs: array
  optional_inputs: array
  capabilities: object
  known_limits: array
  conformance_fixtures: array
```

## 5. Profile 実装仕様

| profile | DQ policy | soft_gap policy | manual policy | export policy |
|---|---|---|---|---|
| `default` | P0a hard DQのみ厳格 | P1a/P1b不足はvisible gap | high-risk gapはrecommended | QEG partial allowed |
| `strict` | high-risk missing execution、unsafe required artifactをhard | weak oracle、missing contextをconditional | manual補完要求をrequired | QEG partial allowed with warning |
| `release` | strict + unresolved SARIF high/critical + open manual requiredをhard | uncalibrated scoreをconditional | unresolved manual request blocks eligibility | QEG export only if no hard DQ |
| `experimental` | required input以外はwarning中心 | adapter開発用にsoft化 | manual補完はrecommendation | export is debug/non-release |

Profile結果は `profile-report.json` に出す。

```yaml
profile_report:
  profile: string
  effective_chain: array
  effective_rules: object
  effective_policies: object
  policy_table: object
  rule_diffs: array
  drift_checks: array
  profile_hash: string
  deterministic: true
```

## 6. Storage / Read Model 仕様

Local store:

```text
.hate/
  runs/<run_id>/<attempt>/
    inputs/
    p0a/
    p0b/
    p1a/
    p1b/
    p2/
    manifest.json
  index/
    runs.jsonl
    bundles.jsonl
    risk-debt.jsonl
    history.jsonl
```

Hosted store は local store と同じ logical model を持つ。違いは authz、tenant scope、
retention、audit log、cache stalenessだけであり、canonical bundleの意味を変えない。

Read model resources:

| resource | source artifact | primary key | required filters |
|---|---|---|---|
| `runs` | `HATE-run.json`, `record.json` | `run_id:attempt` | repo, branch, commit, status |
| `evidence` | `qeg-bundle.json`, `evidence-map.json` | evidence id | run, risk, test, kind |
| `artifacts` | `artifact-manifest.json` | artifact_id | run, classification, safe_for_summary |
| `risk-debt` | `risk-debt-register.json` | debt_id | status, severity, owner |
| `trust` | `aete-score.json`, `doctor-report.json` | run_id:attempt | profile, finding_count |
| `product-readiness` | `product-readiness-report.json` | run_id:attempt | prg, status |

## 7. Hosted API 仕様

API は canonical bundle から派生した read model を返す。API failure は P0/P1
canonical artifact を変更しない。

| method | path | purpose |
|---|---|---|
| GET | `/v1/runs` | run list |
| GET | `/v1/runs/{run_id}/attempts/{attempt}` | run detail |
| GET | `/v1/runs/{run_id}/attempts/{attempt}/evidence` | evidence list |
| GET | `/v1/runs/{run_id}/attempts/{attempt}/artifacts` | artifact manifest |
| GET | `/v1/runs/{run_id}/attempts/{attempt}/risk-debt` | risk debt |
| GET | `/v1/runs/{run_id}/attempts/{attempt}/trust` | AETE / doctor |
| GET | `/v1/product-readiness` | latest product readiness read model |
| POST | `/v1/bundles/import` | bundle import, validation only |
| POST | `/v1/exports/{provider}` | optional external export |

Response envelope:

```yaml
request_id: string
resource: string
generated_at: ISO-8601
source_bundle_ref: string
staleness:
  status: fresh | stale | rebuilding
  max_age_seconds: number
data: object | array
errors: array
```

## 8. RBAC / Audit 仕様

Roles:

| role | permissions |
|---|---|
| `viewer` | read safe summaries and read model |
| `developer` | import local bundles, run precheck, view non-restricted artifacts |
| `qa_lead` | manage risk debt, manual-bb requests, acceptance evidence |
| `security_reviewer` | view quarantine, security findings, trust packet |
| `org_admin` | manage workspace, retention, integrations, RBAC |
| `auditor` | read immutable evidence room, audit logs, assurance pack |

Audit events:

| event_type | required fields |
|---|---|
| `bundle.imported` | actor, workspace, repo, run_id, bundle_hash |
| `precheck.generated` | actor/tool, profile, decision, dq_hash |
| `qeg.exported` | actor/tool, bundle_ref, completeness |
| `artifact.quarantined` | artifact_id, reason, policy_version |
| `risk_debt.updated` | debt_id, old_status, new_status, actor |
| `external_export.started` | provider, bundle_ref, non_gating=true |
| `external_export.failed` | provider, error_code, canonical_unchanged=true |
| `retention.policy_applied` | artifact_id, policy, action |
| `access.denied` | actor, resource, permission |

## 9. External Export 仕様

External exporter は canonical bundle の consumer であり、producer ではない。

Exporter contract:

```yaml
export_request:
  provider: allure | reportportal | codecov | sonarqube | github_pr
  source_bundle_ref: string
  dry_run: boolean
  non_gating: true
  redact_before_export: true
export_result:
  status: success | partial | failed
  exported_refs: array
  skipped_refs: array
  errors: array
  canonical_bundle_hash_before: string
  canonical_bundle_hash_after: string
```

Acceptance:

- exporter failure でも `precheck-decision.json` は変わらない
- exporter failure でも `qeg-bundle.json` は変わらない
- unsafe / restricted artifact はexport対象外
- external URLやremote API errorは product error code `HATE-EXP-*` へ写像する

## 10. QEG Live 連携仕様

QEG live connector は次の順序だけを実行する。

1. HATE canonical bundle を読む
2. QEG schema validate を呼ぶ
3. QEG import dry-run を呼ぶ
4. QEG gate / record は QEG 側の結果を保存する
5. HATE は QEG verdict を改変しない

QEG connector output:

```yaml
qeg_integration_result:
  qeg_endpoint: string
  validate_status: pass | fail
  import_status: pass | fail
  qeg_verdict_ref: string | null
  qeg_record_ref: string | null
  hate_bundle_ref: string
  verdict_modified_by_hate: false
```

## 11. Dashboard 仕様

Dashboard は read model consumer であり、判定正本ではない。

必須画面:

| view | required data |
|---|---|
| Run Overview | run, precheck, completeness, AETE, doctor |
| Evidence Graph | QEG nodes/edges, sourceRefs |
| Risk Coverage | changed path, risk, required tests, execution status |
| Artifact Safety | manifest, quarantine, classification |
| Risk Debt | open/acknowledged/mitigated/stale debts |
| Adapter Health | conformance, parser failures, known limits |
| Product Readiness | PRG coverage, unsupported claims, release migration |

## 12. Release Candidate Pack 仕様

Release candidate pack は次を含む。

```text
release-candidate-pack/
  manifest.json
  p0a/
  p0b/
  p1a/
  p1b/
  product/
  schema-validation-report.json
  adapter-conformance-report.json
  qeg-integration-result.json
  external-export-report.json
  risk-debt-register.json
  privacy-quarantine-report.json
  support-diagnostic-bundle.json
  release-migration-report.json
  assurance-summary.md
```

Pack No-Go:

- open hard DQ
- required schema validation failure
- unsafe artifact leak
- QEG validate failure
- release profileで unresolved manual required
- unsupported customer-facing claim

## 13. 完了主張ルール

| 主張 | 必須根拠 |
|---|---|
| `specification complete` | 本書、`SPECIFICATION.md`、正本表、acceptance matrix |
| `product-grade specified` | `PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` の work package、No-Go、fixture/test minimum、completion claim taxonomy |
| `P0a implemented` | code + schema + fixtures + tests + runbook |
| `P0b implemented` | QEG bundle + SARIF/Playwright + risk debt + tests |
| `P1a implemented` | adapter registry + profile + AETE + replay/doctor tests |
| `P1b implemented` | RanD/Shipyard/workflow/manual-bb fixtures + no-overwrite tests |
| `P2 implemented` | read model/API/dashboard/export/product reports + contract tests |
| `P3 implemented` | RBAC/audit/retention/enterprise connectors + assurance tests |
| `release ready` | release candidate pack + QEG result + open risk review |

仕様書やfixtureだけでは `implemented` と言わない。
prototype の acceptance が通っていても、local store replay、API/read model、dashboard、
RBAC/audit/retention、security quarantine、enterprise control、support/ops evidence が
揃っていない場合は `product-ready` と言わない。

### 13.1 Product-Grade Evidence Reports

製品実装完了を主張するには、少なくとも以下の evidence report が必要である。

| Report | Required source | Blocks product-ready when missing |
|---|---|---|
| `adapter-conformance-report.json` | adapter SDK / conformance fixture | yes |
| `schema-validation-report.json` | schema registry / invalid fixture | yes |
| `store-replay-report.json` | local store / frozen bundle | yes |
| `api-contract-report.json` | hosted read model API contract tests | yes |
| `dashboard-uat-report.json` | dashboard view model / UI UAT | yes |
| `test-integrity-report.json` | skip/xfail/only/todo、mock abuse、assertion quality、test coupling、risk/oracle/coverage signal | yes |
| `security-quarantine-report.json` | artifact safety / redaction / export exclusion | yes |
| `enterprise-control-report.json` | RBAC / audit / retention / residency / connectors | yes for enterprise-ready |
| `scale-performance-report.json` | large-run fixture / memory / latency / pagination / aggregation budgets | yes |
| `migration-compatibility-report.json` | schema/store/API/profile/adapter/view-model migration and rollback | yes |
| `commercial-truthfulness-report.json` | customer-facing and commercial claims mapped to implementation evidence | yes |
| `support-ops-report.json` | error catalog / diagnostic bundle / migration / rollback | yes |
| `release-candidate-pack.json` | all required product reports and QEG result refs | yes for release-ready |

これらが生成されていない領域は、`specified` または `designed` として扱い、
`implemented` に昇格させない。

## 14. 次に実装へ渡す順序

実装順は以下を正とする。

1. P0a adapter expansion: Cobertura / JaCoCo / coverage.py / pytest / Vitest / Jest
2. P0b evidence expansion: SARIF finding / Playwright artifact / Pact / Stryker
3. Artifact safety: quarantine report / redaction policy / path resolver
4. Adapter registry and conformance suite
5. Profile inheritance and profile report
6. AETE signal-based scoring
7. Schema registry validation in CI
8. Local store and history index
9. QEG live connector dry-run
10. Hosted read model API
11. Dashboard view model
12. External exporters
13. RBAC / audit / retention
14. Release candidate pack
15. Product-grade evidence reports and dashboard/API UAT
16. Support/ops/migration/incident/customer-docs closure

この順序を変更する場合は、`IMPLEMENTATION_TASK_BREAKDOWN.md` と `RUNBOOK.md` を同時に更新する。
