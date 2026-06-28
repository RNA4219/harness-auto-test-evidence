---
intent_id: INT-HATE-MANUAL-BB-IMPL-GATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Manual-bb 実装ゲート確認

## Intake Status

- status: degraded
- profile: standard
- feature: HATE P0a/P0b 実装着手可否
- scope:
  - P0a: schema / golden fixture / local-first precheck 実装着手
  - P0b: QEG minimal bundle / SARIF / Playwright / diff-risk-test 拡張
  - P1b: Shipyard-cp / workflow-cookbook / manual-bb bridge 接続
- assumptions:
  - 実装対象の最初の slice は `HATE-MVP-001` から `HATE-MVP-003` までとする
  - Shipyard-cp は local advisory evidence として使い、実 runtime API 連携は P1b まで要求しない
  - QEG runtime、外部 SaaS、dashboard、SSO は P0a の前提にしない
- blockers:
  - full completion には QEG minimal bundle、AETE、P1b workflow artifacts が未実装
  - P0a は実行可能 CLI と DQ negative fixture の証跡が揃ったが、P0b以降の完成証跡ではない

## 根拠付き観点

| id | title | view | techniques | source | rationale |
|---|---|---|---|---|---|
| OBS-FLOW-01 | P0a golden path が外部依存なしで成立する | black | flow / equivalence | `P0A_GOLDEN_PATH.md`, `SPECIFICATION.md#25`, `fixtures/golden/p0a-minimal` | P0a の最短実装は input/expected が固定されているため着手可能 |
| OBS-RULE-01 | precheck decision enum と exit code が固定されている | black | decision_table | `SPECIFICATION.md#10`, `EVALUATION.md#P0a` | `eligible/conditional/ineligible/hard_dq` と failure exit code を分離できる |
| OBS-DATA-01 | common envelope と record schema が最小実装の oracle になる | white | equivalence / schema | `schemas/HATE/v1/*`, `SCHEMA_REGISTRY_CONTRACT.md` | 実装者が出力差分を schema と fixture で確認できる |
| OBS-REG-01 | artifact manifest safety field が P0a から必要 | black | regression / rule | `P0A_GOLDEN_PATH.md#8`, `EVALUATION.md#P0a` | public summary への漏えい防止が P0a の実装必須条件になっている |
| OBS-STATE-01 | Shipyard stage はHATEが進めず、advisory evidenceだけ添付する | black | state_transition | `SPECIFICATION.md#30`, `SPECIFICATION_SHIPYARD_AUDIT.md` | acceptance / publish の上書きはNo-Go級の責務逸脱 |
| OBS-TRACE-01 | QEG / workflow / manual-bb の責務境界を壊さない | black | rule / regression | `GUARDRAILS.md`, `SPECIFICATION.md#4`, `SPECIFICATION.md#36` | 実装が後段Gateや手動テストを再実装すると設計目的を破壊する |
| OBS-GAP-01 | DQ negative fixture が追加され、hard_dq を再現できる | black | boundary / negative | `fixtures/golden/p0a-minimal/dq-*`, `tests/test_p0a.py` | P0aのDQ-001/002/003/008/015は実行証跡で固定済み |
| OBS-GAP-02 | P0a CLI の実行成功証跡がある | black | flow / regression | `src/hate/p0a.py`, `docs/process/shipyard-run-evidence-p0a-cli-implementation.json` | golden input から required outputs を生成し `eligible` になる |

## リスク

| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|
| RISK-01 | P0a実装完了をP0b以降の実装完了と誤判定する | 4 | 4 | D=3 C=2 X=0 P=1 A=1 | 58 | P1 | P0a CLIは通ったが、後続のQEG接続は別ゲート |
| RISK-02 | DQ fixture が増えてもQEG export未実装のままoptional evidence producerと誤認する | 4 | 3 | D=2 C=2 X=0 P=1 A=0 | 48 | P1 | hard_dqは再現済みだが、P0bのbundle妥当性は未証明 |
| RISK-03 | QEG / Shipyard / workflow-cookbook の責務をHATEが再実装する | 5 | 3 | D=2 C=3 X=1 P=1 A=1 | 58 | P1 | release gate / publish approval の上書きは設計上の重大逸脱 |
| RISK-04 | artifact safety field不足で unsafe artifact がsummaryへ漏れる | 5 | 3 | D=2 C=2 X=1 P=3 A=1 | 61 | P1 | secret / PII / restricted path 漏えいの影響が大きい |
| RISK-05 | path normalization未実装でWindows/CI/QEG sourceRefsがずれる | 3 | 4 | D=2 C=2 X=1 P=0 A=0 | 45 | P2 | Windows環境とCI環境の差で再現性が落ちる |
| RISK-06 | P0b/QEG bundleまで同時に広げてP0aが肥大化する | 3 | 4 | D=1 C=3 X=2 P=0 A=1 | 44 | P2 | 最短local-first precheckの完成が遅れる |

## 優先度

| priority | 対象 | 判定 | 理由 |
|---|---|---|---|
| P1 | `HATE-MVP-001..003` | 今すぐ着手可 | schema / fixture / decision / manifest の oracle がある |
| P1 | DQ negative fixture | 完了 | hard_dq 再現テストが通過 |
| P1 | artifact safety | P0a実装内で必須 | summary safety とQEG export eligibilityに直結 |
| P2 | JUnit / LCOV adapter | P0a最小実装済み | golden fixtureを実出力に変換できる |
| P2 | CLI / command contract | P0a最小実装済み | `python -m hate p0a` で実行可能 |
| P2 | QEG minimal bundle | P0bへ分離 | P0a着手の前提にはしない |
| P3 | Shipyard runtime API連携 | P1bへ分離 | local advisory evidenceで当面十分 |

## 手動テストケース

| tc_id | priority | title | preconditions | steps | expected | oracle | trace_to | minutes |
|---|---|---|---|---|---|---|---|---:|
| TC-IMPL-001 | P1 | P0a golden fixtureからrequired outputsを生成できる | P0a converter実装後、fixture inputあり | `fixtures/golden/p0a-minimal/input` を指定して実行 | expected 7成果物が生成され、差分が説明可能 | specified: `P0A_GOLDEN_PATH.md#4` | OBS-FLOW-01,RISK-01 | 15 |
| TC-IMPL-002 | P1 | precheck decision enum以外を拒否する | precheck実装後 | invalid decision fixtureを投入 | schema / validation failureになり、decisionとして扱わない | specified: `SPECIFICATION.md#10` | OBS-RULE-01,RISK-02 | 10 |
| TC-IMPL-003 | P1 | commit_sha欠落は hard_dq になる | `dq-01-sha-missing` fixture作成後 | commit_sha欠落入力で実行 | `HATE-DQ-001`, `hard_dq`, exit 2 | specified: `P0A_GOLDEN_PATH.md#7` | OBS-GAP-01,RISK-02 | 10 |
| TC-IMPL-004 | P1 | JUnit parse failureはadapter failureまたはhard_dqになる | `dq-02-junit-malformed` fixture作成後 | 壊れたJUnit XMLで実行 | exit 1 または `hard_dq`。理由がstable codeで説明される | specified: `P0A_GOLDEN_PATH.md#7` | OBS-GAP-01,RISK-02 | 12 |
| TC-IMPL-005 | P1 | artifact safetyがsummary漏えいを防ぐ | unsafe artifact fixture作成後 | `safe_for_summary=false` のartifactを含めて実行 | summaryにpath/detailが出ず、manifestにquarantine理由が残る | specified: `P0A_GOLDEN_PATH.md#9` | OBS-REG-01,RISK-04 | 15 |
| TC-IMPL-006 | P2 | Windows pathをworkspace相対pathへ正規化する | Windows path fixture作成後 | `C:\...` を含むcoverage/artifact入力で実行 | QEG/sourceRefs向けpathが安定形式になる | specified: `SPECIFICATION.md#7` | RISK-05 | 12 |
| TC-IMPL-007 | P1 | Shipyard publish approvalをHATEが上書きしない | shipyard evidence生成後 | `shipyard-run-evidence.json` を確認 | `publish_gate_override=false`、acceptance/publish verdictを持たない | specified: `SPECIFICATION.md#30` | OBS-STATE-01,RISK-03 | 8 |
| TC-IMPL-008 | P2 | QEG bundleはP0bまで生成しない/分離する | P0a実装後 | P0a command実行結果を確認 | P0aはprecheckまで。`qeg-bundle.json` 未生成でも成功可能 | specified: `SPECIFICATION.md#16` | RISK-06 | 8 |

## 工数

- prep: 0.5日
  - DQ fixture tree作成、CLI名/entrypoint決定、schema validation手段決定
- execution: 2.0日
  - P0a converter、JUnit/LCOV最小adapter、manifest/precheck/record/summary生成
- evidence: 0.5日
  - expected diff、manual-bb execution evidence、Shipyard run evidence更新
- retry buffer: 0.5日
  - Windows path、XML方言差、hash/summary safety修正
- total: 3.5日

P0b/QEG bundle、SARIF、Playwright、diff-risk-test まで含める場合は別途 3〜5日を見込む。

## Gate

- profile: standard
- decision: conditional_go
- scope_decision:
  - P0a implementation start: go
  - P0a implementation completion: go
  - P0b以降を含む完成断言: no_go
- reasons:
  - P0a の仕様、schema、golden fixture、Shipyard advisory evidence、CLI実行証跡が揃っている
  - DQ negative fixture と hard_dq 再現テストが通過している
  - P0a implementation completion は Go だが、P0b以降のcompletion claimはNo-Go
  - P0b/QEG bundle と P1b Shipyard runtime接続は現時点のP0a実装着手条件から分離すべき
- blocking_risks:
  - full completion claim: `RISK-01`, `RISK-02`
- waivers:
  - `WV-IMPL-001`: Shipyard runtime API投入は P1b まで延期。owner=RNA4219、containment=local advisory evidence、due=P1b

## Go/No-Go Brief

- feature: HATE P0a/P0b 実装着手
- decision: conditional_go
- top risks:
  - P0a完了をP0b以降の完成と誤認するリスク
  - QEG bundle未実装リスク
  - 後段Gate責務の再実装リスク
  - artifact safety漏えいリスク
- evidence:
  - `docs/process/SPECIFICATION.md`
  - `docs/process/P0A_GOLDEN_PATH.md`
  - `docs/process/EVALUATION.md`
  - `docs/process/SPECIFICATION_SHIPYARD_AUDIT.md`
  - `schemas/HATE/v1/*`
  - `fixtures/golden/p0a-minimal/*`
- residual risk:
  - P0a完了は許容範囲
  - P0b以降の完成は、QEG bundleとdiff-risk-test実装証跡が出るまで未達
- required follow-up:
  1. P0b/QEG bundleはP0a completion後に別ゲートで確認する
  2. diff-risk-test / evidence-map を実装する
  3. AETE / doctor / replay 系を P1a として実装する
  4. Shipyard runtime mapping は P1b で別ゲートにする
