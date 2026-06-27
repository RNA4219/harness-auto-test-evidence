---
intent_id: INT-HATE-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Manual BB Gate: HATE 仕様書

## Intake Status

- status: ok
- feature_id: HATE-SPECIFICATION-GATE
- feature: `docs/process/SPECIFICATION.md` を QEG + workflow-cookbook 様式の正本仕様書として受理できるか
- profile: standard
- primary_view: black
- supplementary_view: white
- assumptions:
  - 本 Gate はアプリ実行ではなく、要件定義に対する仕様書成果物の手動ブラックボックス文書 Gate とする
  - 実装コード、schema 実体、fixture 実体は未実装であり、ここでは仕様書としての受理可否だけを判定する
  - `SPECIFICATION_SHIPYARD_DRAFT.md` は補助ドラフトであり、正本は `SPECIFICATION.md` とする
- blockers: none

## 1. 根拠付き観点

| id | title | view | techniques | source | rationale |
|---|---|---|---|---|---|
| OBS-SPEC-001 | README から仕様書へ辿れる | black | traceability | `README.md:40-45`, `README.md:73-76` | 入口から正本仕様へ辿れないと運用導線が破綻する |
| OBS-SPEC-002 | 仕様書が要件、Scope、I/O、Gate 境界を持つ | black | equivalence_partitioning | `SPECIFICATION.md:13`, `SPECIFICATION.md:56`, `SPECIFICATION.md:100`, `SPECIFICATION.md:246` | 要件定義から実装契約へ落ちているかを見る中核観点 |
| OBS-SPEC-003 | QEG の責務を HATE が再実装しない | black | decision_table | `SPECIFICATION.md:13`, `SPECIFICATION.md:246`, `SPECIFICATION.md:782` | QEG + HATE の責務境界が崩れると後段 Gate と矛盾する |
| OBS-SPEC-004 | workflow-cookbook 接続が Task Seed / Acceptance / Evidence / Birdseye を含む | black | rule_coverage | `SPECIFICATION.md:299`, `SPECIFICATION.md:868` | ユーザー要求の workflow-cookbook 様式の主要契約 |
| OBS-SPEC-005 | Shipyard-cp 接続が advisory evidence に留まる | black | state_transition | `SPECIFICATION.md:933` | Shipyard の state machine / publish approval を置き換えないことが必要 |
| OBS-SPEC-006 | DQ / soft_gap / risk debt / manual-bb bridge が分離される | black | decision_table | `SPECIFICATION.md:201`, `SPECIFICATION.md:995`, `SPECIFICATION.md:1015` | Gate 判定、手動補完、継続リスク追跡の混同を防ぐ |
| OBS-SPEC-007 | Artifact / schema / fixture / adapter / profile の実装契約がある | black | regression_impact | `SPECIFICATION.md:632`, `SPECIFICATION.md:662`, `SPECIFICATION.md:729`, `SPECIFICATION.md:767` | 実装者が次に作る物を特定できるかの観点 |
| OBS-SPEC-008 | Completion Gate が仕様書としての完了条件を持つ | black | acceptance_review | `SPECIFICATION.md:1099` | 完了判定が曖昧なまま進まないための観点 |
| OBS-SPEC-009 | Markdown 構造が壊れていない | white | artifact_validation | `SPECIFICATION.md` code fence count = 44 | fenced block が偶数で閉じ漏れがない |
| OBS-SPEC-010 | Shipyard 方式の補助ドラフトが残っている | white | evidence_review | `SPECIFICATION_SHIPYARD_DRAFT.md` exists | ユーザー指定の低コスト draft → 統合の実施証跡 |

## 2. リスク

| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|
| RISK-SPEC-001 | 仕様書がREADMEから辿れず、実装者が古い資料を正本扱いする | 4 | 2 | D1 C2 X0 P0 A2 | 34 | P3 | README に `SPECIFICATION.md` 参照があるため低減済み |
| RISK-SPEC-002 | QEGのGate policyやapprovalをHATE側が再実装して責務境界が崩れる | 5 | 2 | D2 C2 X0 P0 A2 | 42 | P2 | 仕様書に再実装禁止と QEG export contract が明記されている |
| RISK-SPEC-003 | workflow-cookbook形式の成果物が不足し、Task/Acceptance/Evidenceへ追跡できない | 4 | 3 | D2 C2 X0 P0 A2 | 44 | P2 | `workflow-*` artifact と詳細接続章があるため許容範囲 |
| RISK-SPEC-004 | Shipyard-cp連携がpublish approvalの代替と誤解される | 5 | 2 | D2 C2 X0 P0 A2 | 42 | P2 | `publish_gate_override: false` と advisory ルールで抑制済み |
| RISK-SPEC-005 | DQ / soft_gap / risk debt / manual補完が混同され、Gate判定が甘くなる | 5 | 3 | D2 C2 X0 P0 A2 | 58 | P1 | 章分離済みだが、実装時 fixture がまだないため残余リスクあり |
| RISK-SPEC-006 | schema / fixture 実体が未実装で、仕様が実装可能性だけに留まる | 4 | 3 | D2 C2 X0 P0 A1 | 45 | P2 | 今回は文書Gateなので許容。実装開始時の最初のTaskに回す |
| RISK-SPEC-007 | 長大仕様が後続更新で同期崩れを起こす | 3 | 3 | D2 C2 X0 P0 A1 | 35 | P2 | Completion Gate と更新ルールはあるが、今後のdocs stale checkが必要 |

## 3. 優先度

| priority | 対象 | 対応方針 |
|---|---|---|
| P1 | RISK-SPEC-005 | 実装開始時に DQ / soft_gap / risk debt / manual-bb bridge fixture を最優先で作る |
| P2 | RISK-SPEC-002, RISK-SPEC-003, RISK-SPEC-004, RISK-SPEC-006, RISK-SPEC-007 | 仕様書上は受理可能。Task Seed と acceptance fixture で継続追跡 |
| P3 | RISK-SPEC-001 | README導線で低減済み |

## 4. 手動テストケース

| tc_id | priority | title | preconditions | steps | expected | oracle | trace_to | minutes | result |
|---|---|---|---|---|---|---|---|---:|---|
| TC-SPEC-001 | P1 | READMEから仕様書へ辿れる | 変更後READMEが存在 | READMEの参照文書一覧と進行方針を見る | `SPECIFICATION.md` へのリンクと読む順がある | specified: `README.md:40-45`, `README.md:73-76` | OBS-SPEC-001, RISK-SPEC-001 | 4 | pass |
| TC-SPEC-002 | P1 | QEG責務境界が明示されている | `SPECIFICATION.md` が存在 | 目的、QEG Export、QEG Bundle詳細を確認 | HATEがQEGのGate policy/waiver/approvalを再実装しないと読める | specified: `SPECIFICATION.md:13`, `SPECIFICATION.md:246`, `SPECIFICATION.md:782` | OBS-SPEC-003, RISK-SPEC-002 | 8 | pass |
| TC-SPEC-003 | P1 | workflow-cookbook成果物が揃っている | `SPECIFICATION.md` が存在 | Workflow-cookbook章と詳細章を確認 | Task Seed / Acceptance / Evidence / docs stale / Birdseye が定義済み | specified: `SPECIFICATION.md:299`, `SPECIFICATION.md:868` | OBS-SPEC-004, RISK-SPEC-003 | 8 | pass |
| TC-SPEC-004 | P1 | Shipyard-cp接続がadvisoryに限定されている | `SPECIFICATION.md` が存在 | Shipyard-cp接続仕様を確認 | `publish_gate_override: false` と stage別禁止事項がある | specified: `SPECIFICATION.md:933` | OBS-SPEC-005, RISK-SPEC-004 | 8 | pass |
| TC-SPEC-005 | P1 | DQ / soft_gap / manual補完が分離されている | `SPECIFICATION.md` が存在 | DQ、Manual-bb Bridge、Risk Debt章を確認 | hard_dq、soft_gap、risk debt、manual supplement request が別契約になっている | specified: `SPECIFICATION.md:201`, `SPECIFICATION.md:995`, `SPECIFICATION.md:1015` | OBS-SPEC-006, RISK-SPEC-005 | 10 | pass |
| TC-SPEC-006 | P2 | 実装契約の対象物が特定できる | `SPECIFICATION.md` が存在 | Schema Registry、Fixture、Adapter、Profile章を確認 | schema / fixture / adapter / profile の契約と次工程が読める | specified: `SPECIFICATION.md:632`, `SPECIFICATION.md:662`, `SPECIFICATION.md:729`, `SPECIFICATION.md:767` | OBS-SPEC-007, RISK-SPEC-006 | 10 | pass |
| TC-SPEC-007 | P2 | Completion Gateが存在する | `SPECIFICATION.md` が存在 | Completion Gate章を確認 | 仕様書としての完了条件が箇条書きで存在する | specified: `SPECIFICATION.md:1099` | OBS-SPEC-008, RISK-SPEC-007 | 5 | pass |
| TC-SPEC-008 | P2 | Markdownコードフェンスが閉じている | `SPECIFICATION.md` が存在 | fenced block数を確認 | fence count が偶数 | derived: code fence count = 44 | OBS-SPEC-009 | 3 | pass |
| TC-SPEC-009 | P2 | Shipyardドラフト証跡が残っている | draft fileが存在 | `SPECIFICATION_SHIPYARD_DRAFT.md` の存在を確認 | 補助ドラフトが残っている | derived: file exists | OBS-SPEC-010 | 2 | pass |

## 5. 工数

- prep: 8 min
- execution: 58 min equivalent review scope
- evidence: 15 min
- retry buffer: 10 min
- total: 91 min

今回の実測は文書検査中心で、実アプリ操作、schema validation、fixture実行は含めない。

## 6. Gate 判定

- profile: standard
- decision: go
- reasons:
  - READMEから `SPECIFICATION.md` へ辿れる
  - 仕様書が QEG export、workflow-cookbook、Shipyard-cp、manual-bb bridge、DQ、AETE、schema、fixture、acceptance を含む
  - QEG / workflow-cookbook / Shipyard-cp を再実装しない境界が明示されている
  - P0a/P0b/P1a/P1b/P2/P3 の acceptance matrix と Completion Gate がある
  - manual-bb観点のP1/P2ケースはすべて pass
- blocking_risks: none
- waivers: none
- residual_risks:
  - RISK-SPEC-005: DQ / soft_gap / risk debt fixture は実装開始時に必要
  - RISK-SPEC-006: schema / fixture 実体は未実装
  - RISK-SPEC-007: 長大仕様のdocs stale checkを継続する必要あり

## 7. Go/No-Go Brief

- feature: HATE 仕様書の要件定義対応
- decision: go
- top risks:
  - DQ / soft_gap / risk debt / manual-bb bridge は仕様上分離済みだが、実装時のfixture未作成
  - schema / fixture実体は後続Taskで作る必要がある
- evidence:
  - `SPECIFICATION.md` は 36章構成で要件トレース、QEG、workflow-cookbook、Shipyard、manual-bb、acceptanceを含む
  - READMEから仕様書へ導線がある
  - fenced block count は 44 で閉じ漏れなし
  - Shipyard補助ドラフトが存在する
- residual risk: medium, owner required in implementation Task Seed
- required follow-up:
  - `HATE-MVP-001` で common envelope schema と P0a golden fixture を作る
  - `HATE-MVP-004` で QEG minimal bundle fixture を作る
  - `HATE-MVP-005` で workflow artifact fixture と acceptance record を作る
