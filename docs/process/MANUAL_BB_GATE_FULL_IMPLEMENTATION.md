---
intent_id: INT-HATE-MANUAL-BB-FULL-IMPL-GATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Manual-bb フル実装ゲート確認

## Intake Status

- status: blocked
- profile: standard
- feature: HATE フル実装到達可否
- decision target: P0a / P0b / P1a / P1b / P2 / P3 を含む実装完了までのGo/No-Go
- current evidence:
  - 仕様書正本: `docs/process/SPECIFICATION.md`
  - 受入条件: `docs/process/EVALUATION.md`
  - P0a schema bootstrap: `schemas/HATE/v1/*`
  - P0a golden fixture: `fixtures/golden/p0a-minimal/*`
  - P0a CLI evidence: `docs/process/shipyard-run-evidence-p0a-cli-implementation.json`
  - 仕様監査: `docs/process/SPECIFICATION_SHIPYARD_AUDIT.md`
- blockers:
  - P0b `qeg-bundle.json` / `evidence-map.json` / `diff-risk-test.json` がない
  - P1a AETE / replay / compare / explain / recommend / doctor / path normalization がない
  - P1b workflow / RanD / Shipyard runtime mapping artifact がない
  - P2/P3 productization / enterprise readiness は契約文書中心で、実装 artifact / metrics がない

## 根拠付き観点

| id | title | view | techniques | source | rationale |
|---|---|---|---|---|---|
| OBS-FULL-01 | フル実装はP0aだけでなくP0b/P1a/P1b/P2/P3までを含む | black | flow / regression | `SPECIFICATION.md#16`, `SPECIFICATION.md#34`, `EVALUATION.md` | 受入条件がphase全体に広がっており、P0aの準備証跡だけでは完了判定できない |
| OBS-FULL-02 | P0aは実行コードとCLI証跡を持つ | black | flow | `src/hate/p0a.py`, `tests/test_p0a.py`, `shipyard-run-evidence-p0a-cli-implementation.json` | P0a単体の実装完了は確認できるが、フル実装完了ではない |
| OBS-FULL-03 | DQの再現性はP0aで成立したが、full implementationにはP0b以降も必要 | black | boundary / decision_table | `EVALUATION.md`, `P0A_GOLDEN_PATH.md#7` | hard_dqは再現済み。QEG/AETE/workflow側のDQ相当は未実装 |
| OBS-FULL-04 | QEG export互換はP0bの必須ゲート | black | rule / integration | `SPECIFICATION.md#13`, `EVALUATION.md#P0b` | `qeg-bundle.json` がない状態ではQEG optional evidence producerとして完成していない |
| OBS-FULL-05 | AETEとadapter capabilityはP1aの信頼性ゲート | black | decision_table / regression | `SPECIFICATION.md#12`, `EVALUATION.md#P1a` | 8次元score、profile、calibration、未対応粒度が実装されていない |
| OBS-FULL-06 | workflow / Shipyard / RanD接続はP1bで実artifactが必要 | black | state_transition / rule | `SPECIFICATION.md#29`, `SPECIFICATION.md#30`, `EVALUATION.md#P1b` | advisory evidenceだけではruntime refs / acceptance refs / Evidence JSONL の生成を証明できない |
| OBS-FULL-07 | P2/P3はP0/P1を阻害しないが、full implementationには検証可能artifactが必要 | black | regression / rule | `EVALUATION.md#P2`, `EVALUATION.md#P3` | product readiness, trust, telemetry, residency, legal, assurance は文書だけでは実装完了にならない |
| OBS-FULL-08 | 後段Gateやpublish approvalをHATEが再実装するとNo-Go | black | state_transition | `SPECIFICATION.md#4`, `SPECIFICATION.md#30`, `GUARDRAILS.md` | QEG / Shipyard / workflow-cookbook の責務境界違反は設計破壊 |

## リスク

| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|
| RISK-FULL-01 | P0a準備証跡をフル実装可能性と誤認する | 5 | 4 | D=3 C=3 X=1 P=1 A=0 | 77 | P0 | フルスコープの大半が未実装で、完了主張が重大な誤判定になる |
| RISK-FULL-02 | P0a DQ通過をもってP0b以降のprecheck全体が信用されたと誤認する | 5 | 3 | D=3 C=2 X=0 P=1 A=0 | 59 | P0 | P0aのhard_dqは再現済みだが、QEG/AETE/workflow artifactは未証明 |
| RISK-FULL-03 | QEG bundle未実装でoptional evidence producerとして成立しない | 5 | 4 | D=2 C=3 X=2 P=1 A=0 | 76 | P0 | HATEの主目的であるQEG接続が証明できない |
| RISK-FULL-04 | AETE / profile / path normalization未実装で信頼評価が再現不能になる | 4 | 4 | D=3 C=3 X=1 P=1 A=0 | 66 | P1 | P1aの信頼性要件が満たせず、実運用で説明不能になる |
| RISK-FULL-05 | Shipyard / workflow / RanD連携を文書だけで完了扱いする | 4 | 3 | D=3 C=3 X=2 P=1 A=0 | 56 | P1 | external refs と acceptance trace が実artifactで証明されない |
| RISK-FULL-06 | P2/P3 enterprise契約が実装artifactなしで販売可能に見える | 5 | 3 | D=3 C=3 X=2 P=2 A=0 | 68 | P1 | customer-facing / compliance / legal 説明と実装状態が乖離する |
| RISK-FULL-07 | HATEがQEG/ShipyardのGate権限を再実装する | 5 | 3 | D=2 C=3 X=1 P=2 A=1 | 60 | P1 | release approval や publish approval の責務境界を壊す |

## 優先度

| priority | 必須対象 | 現状 | full implementation gate |
|---|---|---|---|
| P0 | P0a executable converter / CLI | implemented | pass for P0a |
| P0 | DQ negative fixtures and validation | implemented | pass for P0a |
| P0 | P0b QEG minimal bundle | missing | block |
| P0 | QEG責務境界の実行証跡 | docs only | block |
| P1 | AETE 8 dimensions / profile / calibration | missing | block |
| P1 | canonical test identity / path normalization | partial fixture only | block |
| P1 | replay / compare / explain / recommend / doctor | missing | block |
| P1 | workflow / RanD / Shipyard generated artifacts | advisory only | block |
| P2 | productization reports and optional exports | docs only | block for full |
| P2 | P3 enterprise readiness metrics / artifacts | docs only | block for full |

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
| TC-FULL-011 | P2 | external exportがprecheck/QEG verdictを変えない | P2実装済み | export enabled/disabledで同一bundleを比較 | canonical decisionが不変 | specified: `HATE-NFR-007` | RISK-FULL-06 | 20 |
| TC-FULL-012 | P2 | P3 readinessがPRG-0..PRG-6をartifact/metricで証明する | P3 artifact実装済み | product-readiness-reportを検査 | 各PRGがmetric/evidence refsを持つ | specified: `EVALUATION.md#P3` | OBS-FULL-07,RISK-FULL-06 | 30 |
| TC-FULL-013 | P0 | HATEがQEG/ShipyardのGate権限を再実装しない | 全phase実装後 | 出力artifactとAPI surfaceを確認 | release/publish approvalを書き換えるfield/commandがない | specified: `SPECIFICATION.md#4`, `SPECIFICATION.md#30` | OBS-FULL-08,RISK-FULL-07 | 20 |

## 工数

- prep: 1.0〜1.5日
  - 実装entrypoint、schema validator、fixture runner、expected diff方針を固定
- P0a execution: 3〜4日
  - converter / CLI / JUnit / LCOV / manifest / precheck / record / summary / DQ negative fixture
- P0b execution: 3〜5日
  - qeg-bundle / evidence-map / diff-risk-test / SARIF / Playwright artifact safety
- P1a execution: 6〜10日
  - AETE / profile / retry aggregation / identity / path normalization / replay / compare / explain / recommend / doctor
- P1b execution: 4〜7日
  - RanD alignment / Shipyard runtime mapping / workflow-* artifacts / manual-bb bridge
- P2/P3 execution: 8〜15日
  - optional exports / hosted read model contracts / product readiness / enterprise reports / assurance artifacts
- evidence and retry buffer: 4〜7日
- total: 29〜49日

この見積もりは単独実装者のmanual-bb標準ゲート基準であり、既存ライブラリや生成支援で短縮可能。ただし、Gate上は証跡が出るまで短縮扱いしない。

## Gate

- profile: standard
- decision: no_go
- scope_decision:
  - P0a implementation start: go
  - P0a implementation completion: go
  - P0b implementation completion: no_go
  - P1a/P1b implementation completion: no_go
  - P2/P3 full product implementation completion: no_go
  - full implementation claim: no_go
- reasons:
  - P0aに必要な実行可能CLI、JUnit/LCOV最小adapter、DQ negative fixture、実行証跡は存在する
  - full implementationに必要なQEG bundle、AETE、workflow artifactsが存在しない
  - P0b以降は文書契約が中心で、生成artifactと検証ログがない
  - P2/P3は契約文書として整理されているが、artifact/metricによるProduct Readiness証明がない
- blocking_risks:
  - `RISK-FULL-01`
  - `RISK-FULL-02`
  - `RISK-FULL-03`
- waivers:
  - none
- minimum_go_conditions:
  - P0a CLIがgolden fixtureからrequired outputsを生成する
  - DQ negative fixtureが期待decision/exit codeを再現する
  - P0b qeg-bundle/evidence-map/diff-risk-testが生成される
  - P1a AETE/profile/path/replay系の最低fixtureが通る
  - P1b workflow/Shipyard/RanD artifactが生成される
  - P2/P3はfull claimに含めるならproduct-readiness-reportとPRG metricを生成する

## Go/No-Go Brief

- feature: HATE full implementation
- decision: no_go
- answer: 現段階ではフル実装まで完成すると確認できない。P0aの着手は可能だが、full implementation gateは未達。
- top risks:
  - P0a実装完了証跡をフル実装証跡と誤認するリスク
  - QEG export未実装リスク
  - DQ/AETE未実装による誤判定リスク
  - P2/P3契約文書をproduct implementationと誤認するリスク
- evidence:
  - `docs/process/SPECIFICATION.md`
  - `docs/process/EVALUATION.md`
  - `docs/process/P0A_GOLDEN_PATH.md`
  - `schemas/HATE/v1/*`
  - `fixtures/golden/p0a-minimal/*`
  - `docs/process/SPECIFICATION_SHIPYARD_AUDIT.md`
- residual risk:
  - high。P0b以降の生成artifactが存在しないため、full implementation completionは証明不能。
- required follow-up:
  1. P0b qeg-bundle / evidence-map / diff-risk-test を実装する
  2. P1a AETE / profile / identity / path / replay 系をfixture付きで実装する
  3. P1b workflow / RanD / Shipyard runtime mapping artifact を実装する
  4. P2/P3をfull claimに含めるならProduct Readiness artifactとmetricを実装する
