---
intent_id: INT-HATE-MANUAL-BB-FULL-IMPL-GATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Manual-bb フル実装ゲート確認

## Intake Status

- status: conditional_go
- profile: standard
- feature: HATE フル実装到達可否
- decision target: P0a / P0b / P1a / P1b / P2 / P3 を含む実装完了までのGo/No-Go
- current evidence:
  - 仕様書正本: `docs/process/SPECIFICATION.md`
  - 受入条件: `docs/process/EVALUATION.md`
  - P0a schema bootstrap: `schemas/HATE/v1/*`
  - P0a golden fixture: `fixtures/golden/p0a-minimal/*`
  - P0a CLI evidence: `docs/process/shipyard-run-evidence-p0a-cli-implementation.json`
  - P0b QEG export and edge evidence: `docs/process/shipyard-run-evidence-p0b-qeg-export.json`
  - P1a trust minimal evidence: `docs/process/shipyard-run-evidence-p1a-trust-minimal.json`
  - P1b workflow mapping evidence: `docs/process/shipyard-run-evidence-p1b-workflow-mapping.json`
  - P2/P3 product readiness evidence: `docs/process/shipyard-run-evidence-p2p3-product-readiness.json`
  - 仕様監査: `docs/process/SPECIFICATION_SHIPYARD_AUDIT.md`
- blockers: none for artifact generation; visible gaps remain for product readiness

## 根拠付き観点

| id | title | view | techniques | source | rationale |
|---|---|---|---|---|---|
| OBS-FULL-01 | フル実装はP0aだけでなくP0b/P1a/P1b/P2/P3までを含む | black | flow / regression | `SPECIFICATION.md#16`, `SPECIFICATION.md#34`, `EVALUATION.md` | 受入条件がphase全体に広がっており、P0aの準備証跡だけでは完了判定できない |
| OBS-FULL-02 | P0aは実行コードとCLI証跡を持つ | black | flow | `src/hate/p0a.py`, `tests/test_p0a.py`, `shipyard-run-evidence-p0a-cli-implementation.json` | P0a単体の実装完了は確認できるが、フル実装完了ではない |
| OBS-FULL-03 | DQの再現性はP0a/P0bで成立し、P1a/P1bではtrust/workflow gapとして継承される | black | boundary / decision_table | `EVALUATION.md`, `P0A_GOLDEN_PATH.md#7` | hard_dq、QEG gap可視化、AETE doctor、workflow unverified acceptance は再現済み |
| OBS-FULL-04 | QEG export互換はP0bの必須ゲート | black | rule / integration | `SPECIFICATION.md#13`, `EVALUATION.md#P0b` | core export、edge hardening、risk debt / manual bridge の生成証跡がある |
| OBS-FULL-05 | AETEとadapter capabilityはP1aの信頼性ゲート | black | decision_table / regression | `SPECIFICATION.md#12`, `EVALUATION.md#P1a` | 8次元score、profile、calibration、doctor、identity、retry、replay、compare、explain、recommend、adapter conformance が実装済み |
| OBS-FULL-06 | workflow / Shipyard / RanD接続はP1bで実artifactが必要 | black | state_transition / rule | `SPECIFICATION.md#29`, `SPECIFICATION.md#30`, `EVALUATION.md#P1b` | `requirement-evidence-alignment.json`、`workflow-*`、`shipyard-run-evidence.json` が生成済み。ただし live Shipyard runtime dispatch ではなく advisory evidence |
| OBS-FULL-07 | P2/P3はP0/P1を阻害しないが、full implementationには検証可能artifactが必要 | black | regression / rule | `EVALUATION.md#P2`, `EVALUATION.md#P3` | `product-readiness-report.json` と enterprise advisory artifacts が生成済み。live SaaS runtime claim ではない |
| OBS-FULL-08 | 後段Gateやpublish approvalをHATEが再実装するとNo-Go | black | state_transition | `SPECIFICATION.md#4`, `SPECIFICATION.md#30`, `GUARDRAILS.md` | QEG / Shipyard / workflow-cookbook の責務境界違反は設計破壊 |

## リスク

| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|
| RISK-FULL-01 | P0a準備証跡をフル実装可能性と誤認する | 5 | 4 | D=3 C=3 X=1 P=1 A=0 | 77 | P0 | フルスコープの大半が未実装で、完了主張が重大な誤判定になる |
| RISK-FULL-02 | P0a DQ通過をもってP0b以降のprecheck全体が信用されたと誤認する | 5 | 3 | D=3 C=2 X=0 P=1 A=0 | 59 | P0 | P0b/P1a/P1bの証跡は追加済みだが、P2/P3のproduct readinessまでは証明しない |
| RISK-FULL-03 | P0b partial export をQEG release verdictと誤認する | 5 | 3 | D=2 C=3 X=2 P=1 A=0 | 61 | P0 | P0b は optional evidence producer であり、QEG gate / release approval は出さない |
| RISK-FULL-04 | P1a trust artifact を release Gate と誤認する | 4 | 4 | D=3 C=3 X=1 P=1 A=0 | 66 | P1 | P1aはadvisory evidenceであり、QEG gate / release approvalは出さない |
| RISK-FULL-05 | Shipyard / workflow / RanD連携をlive runtime完了と誤認する | 4 | 3 | D=3 C=3 X=2 P=1 A=0 | 56 | P1 | P1b artifact は advisory evidence であり、Shipyard runtime dispatch / publish approval ではない |
| RISK-FULL-06 | P2/P3 readiness artifactをhosted SaaS availabilityと誤認する | 5 | 3 | D=3 C=3 X=2 P=2 A=0 | 68 | P1 | product readinessはlocal advisory artifactであり、dashboard/API/connector runtimeではない |
| RISK-FULL-07 | HATEがQEG/ShipyardのGate権限を再実装する | 5 | 3 | D=2 C=3 X=1 P=2 A=1 | 60 | P1 | release approval や publish approval の責務境界を壊す |

## 優先度

| priority | 必須対象 | 現状 | full implementation gate |
|---|---|---|---|
| P0 | P0a executable converter / CLI | implemented | pass for P0a |
| P0 | DQ negative fixtures and validation | implemented | pass for P0a |
| P0 | P0b QEG minimal bundle and edge hardening | implemented, partial export | pass |
| P0 | QEG責務境界の実行証跡 | implemented, advisory only | pass |
| P1 | AETE 8 dimensions / profile / calibration | implemented | pass |
| P1 | canonical test identity / path normalization | implemented for current fixture scope | pass |
| P1 | replay / compare / explain / recommend / doctor | implemented | pass |
| P1 | workflow / RanD / Shipyard generated artifacts | implemented, advisory only | pass |
| P2 | productization reports and optional exports | implemented, advisory artifact only; current readiness conditional | conditional |
| P2 | P3 enterprise readiness metrics / artifacts | implemented, advisory artifact only; PRG coverage 6/7 | conditional |

## 手動テストケース

| tc_id | priority | title | preconditions | steps | expected | oracle | trace_to | minutes |
|---|---|---|---|---|---|---|---|---:|
| TC-FULL-001 | P0 | P0a CLIがgolden inputから全required outputsを生成する | converter/CLI実装済み | P0a inputを指定してCLI実行 | expectedとの差分がゼロ、または許容差分が説明される | specified: `P0A_GOLDEN_PATH.md#4` | OBS-FULL-02,RISK-FULL-01 | 20 |
| TC-FULL-002 | P0 | DQ-001/002/003/008/015が再現できる | DQ fixture実装済み | 各negative fixtureを実行 | 期待DQ、decision、exit codeが一致 | specified: `P0A_GOLDEN_PATH.md#7` | OBS-FULL-03,RISK-FULL-02 | 30 |
| TC-FULL-003 | P0 | P0b qeg-bundleがQEG minimal schema互換を満たす | P0b実装済み | qeg exportを実行しschema検証 | nodes/edges/completeness/sourceRefsがvalid | specified: `SPECIFICATION.md#13` | OBS-FULL-04,RISK-FULL-03 | 25 |
| TC-FULL-004 | P0 | diff-risk-testとevidence-mapがhigh-risk changed pathを辿れる | P0b fixture実装済み | high-risk diff fixtureを実行 | risk -> required test -> evidence のedgeが存在 | specified: `EVALUATION.md#P0b` | OBS-FULL-04,RISK-FULL-03 | 20 |
| TC-FULL-005 | P1 | AETE 8次元scoreがprofileとcalibrationを持つ | P1a実装済み | AETE scoring fixtureを実行 | 8次元、0/1/3/5、confidence、calibrationが出る | specified: `SPECIFICATION.md#12` | OBS-FULL-05,RISK-FULL-04 | 25 |
| TC-FULL-006 | P1 | matrix/shard/retry aggregationが決定的 | P1a retry fixture実装済み | 同一fixtureを複数回実行 | aggregate statusが同一 | specified: `EVALUATION.md#P1a` | RISK-FULL-04 | 20 |
| TC-FULL-007 | P1 | Windows/container/workspace pathがsourceRefsへ正規化される | path fixture実装済み | path差分fixtureを実行 | summary/manifest/QEG refsが同一規則で解決 | specified: `HATE-NFR-006` | RISK-FULL-04 | 20 |
| TC-FULL-008 | P1 | replay/compare/explain/recommend/doctorがfrozen bundleで再現可能 | P1a command実装済み | 各commandをfrozen bundleに対して実行 | deterministic outputと説明可能なfindingが出る | specified: `HATE-FR-013` | RISK-FULL-04 | 40 |
| TC-FULL-009 | P1 | Shipyard runtime refsからshipyard-run-evidenceを生成できる | P1b fixture実装済み | WorkerResult / RunSystemPacket fixtureを投入 | artifact refs、DQ/AETE summary、publish override falseが出る | specified: `SPECIFICATION.md#30` | OBS-FULL-06,RISK-FULL-05 | 20 |
| TC-FULL-010 | P1 | workflow artifactsがTask SeedからEvidenceへ辿れる | P1b workflow実装済み | workflow-*生成を実行 | task -> acceptance -> evidence refs が連結 | specified: `SPECIFICATION.md#29` | OBS-FULL-06,RISK-FULL-05 | 25 |
| TC-FULL-011 | P2 | external/product readinessがprecheck/QEG verdictを変えない | P2/P3 artifact実装済み | product readiness生成後に境界fieldを確認 | release/publish override false、local_first_dependency false | specified: `HATE-NFR-007` | RISK-FULL-06 | 20 |
| TC-FULL-012 | P2 | P3 readinessがPRG-0..PRG-6をartifact/metricで証明する | P3 artifact実装済み | product-readiness-reportを検査 | 各PRGがmetric/evidence refsを持つ | specified: `EVALUATION.md#P3` | OBS-FULL-07,RISK-FULL-06 | 30 |
| TC-FULL-013 | P0 | HATEがQEG/ShipyardのGate権限を再実装しない | 全phase実装後 | 出力artifactとAPI surfaceを確認 | release/publish approvalを書き換えるfield/commandがない | specified: `SPECIFICATION.md#4`, `SPECIFICATION.md#30` | OBS-FULL-08,RISK-FULL-07 | 20 |

## 工数

- prep: 1.0〜1.5日
  - 実装entrypoint、schema validator、fixture runner、expected diff方針を固定
- P0a execution: 3〜4日
  - converter / CLI / JUnit / LCOV / manifest / precheck / record / summary / DQ negative fixture
- P0b execution: complete for current local fixture scope
  - qeg-bundle / evidence-map / diff-risk-test / missing-source-ref / unsafe-artifact / risk-debt / manual-bb bridge
- P1a execution: complete for current local fixture scope
  - AETE / profile / doctor / identity / retry / replay / compare / explain / recommend / adapter conformance implemented
- P1b execution: complete for current local advisory fixture scope
  - RanD alignment / Shipyard advisory mapping / workflow-* artifacts / manual-bb bridge
- P2/P3 execution: complete for current local advisory artifact scope
  - hosted read model index / product readiness / enterprise metrics / docs / support / privacy / governance artifacts
- evidence and retry buffer: 4〜7日
- total: 29〜49日

この見積もりは単独実装者のmanual-bb標準ゲート基準であり、既存ライブラリや生成支援で短縮可能。ただし、Gate上は証跡が出るまで短縮扱いしない。

## Gate

- profile: standard
- decision: conditional_go
- scope_decision:
  - P0a implementation start: go
  - P0a implementation completion: go
  - P0b implementation completion: go
  - P1a implementation completion: go
  - P1b implementation completion: go
  - P2/P3 full product implementation completion: conditional_go
  - full implementation claim: conditional_go
- reasons:
  - P0aに必要な実行可能CLI、JUnit/LCOV最小adapter、DQ negative fixture、実行証跡は存在する
  - P0bに必要なQEG export、edge hardening、risk-debt/manual-bb bridge、検証ログは存在する
  - P1aに必要な AETE score、doctor report、resolver map、identity、retry、replay、compare、explain、recommend、adapter conformance は存在する
  - P1bに必要な RanD alignment、workflow artifacts、Shipyard advisory evidence、manual-bb bridge 継承は存在する
  - P2/P3に必要な product readiness、hosted read model index、enterprise metrics、customer docs、support diagnostic、privacy telemetry、governance portfolio artifacts は存在する
  - current fixture は doctor finding と unverified acceptance を保持するため product readiness は `conditional` / `6/7`
  - full implementation claim は local/advisory artifact implementation scope に限定し、hosted SaaS runtime availability は主張しない
- blocking_risks:
  - `RISK-FULL-01`
  - `RISK-FULL-02`
  - `RISK-FULL-03`
- waivers:
  - none
- minimum_go_conditions:
  - P0a CLIがgolden fixtureからrequired outputsを生成する
  - DQ negative fixtureが期待decision/exit codeを再現する
  - hosted SaaS runtimeをfull claimに含めるなら dashboard/API/connector runtime evidence を別途生成する

## Go/No-Go Brief

- feature: HATE full implementation
- decision: conditional_go
- answer: local/advisory artifact implementation scope では P0a/P0b/P1a/P1b/P2/P3 の生成artifactと検証ログが揃った。ただし P0b/P1b の visible gap と P1a doctor finding を保持するため、P2/P3 readiness は conditional。hosted SaaS runtime、dashboard/API server、enterprise connector runtime、Shipyard publish approval は対象外。
- top risks:
  - P0a実装完了証跡をフル実装証跡と誤認するリスク
  - P0b optional evidence exportをQEG release verdictと誤認するリスク
  - P1b advisory evidenceをlive Shipyard runtime完了と誤認するリスク
  - P2/P3 readiness artifactをhosted SaaS availabilityと誤認するリスク
- evidence:
  - `docs/process/SPECIFICATION.md`
  - `docs/process/EVALUATION.md`
  - `docs/process/P0A_GOLDEN_PATH.md`
  - `schemas/HATE/v1/*`
  - `fixtures/golden/p0a-minimal/*`
  - `docs/process/SPECIFICATION_SHIPYARD_AUDIT.md`
  - `docs/process/shipyard-run-evidence-p1b-workflow-mapping.json`
  - `docs/process/shipyard-run-evidence-p2p3-product-readiness.json`
- residual risk:
  - medium。local/advisory artifact は生成済みだが、current fixture の product readiness は conditional。hosted SaaS runtime / dashboard / REST server / enterprise connector は実装対象外。
- required follow-up:
  1. hosted SaaS runtimeを売り物の範囲に含めるなら dashboard/API/connector を別ゲートで実装する
  2. live Shipyard runtime dispatch を要求する場合は、Shipyard-cp側のrun/audit refsで別途検証する
