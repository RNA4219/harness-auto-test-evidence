---
intent_id: INT-HATE-GLM5-PROMPT-PLAN-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# GLM5 実装プロンプトプラン

## 1. 目的

この文書は、Shipyard-cp の GLM5 worker に HATE のフル実装を段階的に進めさせるための
プロンプト計画である。

現在の状態:

- 仕様書完成 claim: `go`
- P0a 実装 slice: `go`
- フル実装完了 claim: `no_go`
- 次の実装対象: P0b QEG export

GLM5 には、まず P0b の `qeg-bundle.json`, `evidence-map.json`,
`diff-risk-test.json`, `qeg-export-report.json`, `qeg-export-summary.md` を実装させる。

## 2. Shipyard-cp 前提

GLM5 は Shipyard-cp の logical Claude worker として扱う。

推奨設定:

```env
CLAUDE_WORKER_BACKEND=glm
CLAUDE_MODEL=glm-5
Alibaba_CodingPlan_MODEL=glm-5
Alibaba_CodingPlan_API_ENDPOINT=https://coding-intl.dashscope.aliyuncs.com/v1
Alibaba_CodingPlan_KEY=YOUR_SECRET_KEY
```

Shipyard stage:

| stage | GLM5 の役割 |
|---|---|
| plan | 対象契約を読み、実装範囲と禁止事項を再確認する |
| dev | 小さく実装し、P0aを壊さない |
| acceptance | pytest、P0a CLI、P0b export、JSON parse、diff check を実行する |
| integrate | RUNBOOK / Shipyard evidence / completion audit に実装証跡を追加する |
| publish | publish approval は出さず、WorkerResult だけ返す |

## 3. GLM5 共通ガードレール

GLM5 への全プロンプトに含める。

```text
あなたは Shipyard-cp の GLM5 worker です。
対象 repo は C:\Users\ryo-n\Codex_dev\harness-auto-test-evidence です。
日本語で作業ログと最終報告を書いてください。

絶対条件:
- HATE は QEG の Gate policy、waiver、approval、retention、immutability、schema migration を再実装しない。
- HATE は Shipyard-cp の state machine、worker dispatch、acceptance verdict、publish approval を再実装しない。
- HATE は workflow-cookbook の checker、plugin host、Birdseye generator を再実装しない。
- P0a CLI と DQ fixture を壊さない。
- P2/P3 productization を P0b/P1a の必須依存にしない。
- 仕様書完成 claim とフル実装完了 claim を混同しない。
- 実装完了を主張する前に、実行コマンドと生成 artifact を証跡に残す。

編集方針:
- 既存パターンを優先する。
- 変更は対象 phase に閉じる。
- 生成物、fixture、テスト、RUNBOOK、Shipyard evidence を同時に更新する。
- 期待出力を手で都合よく書き換えて成功扱いにしない。
- 失敗したコマンドは隠さず、原因と次の処置を書く。
```

## 4. 初回プロンプト: P0b QEG Export 実装

GLM5 に最初に渡すプロンプト。

```text
あなたは Shipyard-cp の GLM5 worker です。
対象 repo は C:\Users\ryo-n\Codex_dev\harness-auto-test-evidence です。
この task は HATE P0b QEG export の実装です。

目的:
P0a の生成 artifact を入力にして、P0b の QEG optional evidence export を実装してください。
生成対象は次です。

- qeg-bundle.json
- evidence-map.json
- diff-risk-test.json
- qeg-export-report.json
- qeg-export-summary.md

必ず最初に読む正本:
- README.md
- docs/process/SPECIFICATION.md
- docs/process/P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md
- docs/process/P0A_GOLDEN_PATH.md
- docs/process/SPECIFICATION_COMPLETION_AUDIT.md
- docs/process/SPECIFICATION_SHIPYARD_AUDIT.md
- docs/process/GUARDRAILS.md
- docs/process/RUNBOOK.md
- src/hate/p0a.py
- tests/test_p0a.py

実装範囲:
- `python -m hate export qeg` 相当の CLI サブコマンドを追加する。
- P0b fixture tree `fixtures/golden/p0b-qeg-minimal/` を追加する。
- P0a output を P0b input fixture にコピーまたは生成できる形にする。
- `diff-risk-test.json` fixture を追加し、high-risk changed path 1件、evidence present 1件、missing execution 1件を含める。
- `evidence-map.json` を生成する。
- `qeg-bundle.json` を生成する。
- `qeg-export-report.json` に completeness、unsupportedClaims、missing_execution、excludedArtifacts を出す。
- `qeg-export-summary.md` を public-safe に生成する。
- hard_dq の P0a precheck から正式な QEG import 用 bundle を生成しない。診断生成する場合は `debugOnly=true` とする。
- QEG verdict、release approval、waiver は実装しない。

推奨ファイル配置:
- src/hate/cli.py
- src/hate/p0b.py
- tests/test_p0b.py
- fixtures/golden/p0b-qeg-minimal/input/
- fixtures/golden/p0b-qeg-minimal/expected/
- docs/process/shipyard-run-evidence-p0b-qeg-export.json

受入条件:
1. 既存 P0a テストが壊れない。
2. `uv run pytest` が pass する。
3. `uv run python -m hate p0a --input fixtures/golden/p0a-minimal/input --out C:\tmp\hate-p0a-check --source-version dev --fixture-path-prefix fixtures/golden/p0a-minimal/input` が `decision=eligible` で pass する。
4. P0b export コマンドが `qeg-bundle.json`, `evidence-map.json`, `diff-risk-test.json`, `qeg-export-report.json`, `qeg-export-summary.md` を生成する。
5. `qeg-bundle.json` の nodes / edges / completeness が `P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md` の契約を満たす。
6. high-risk changed path の missing execution が hidden gap にならず、`evidence-map.json.gaps.missing_execution` または export report に出る。
7. `publish_gate_override=false` を維持し、HATE が Shipyard publish approval を出さない。
8. `git diff --check` が空白エラーなしで通る。

検証コマンド:
- uv run pytest
- uv run python -m hate p0a --input fixtures/golden/p0a-minimal/input --out C:\tmp\hate-p0a-check --source-version dev --fixture-path-prefix fixtures/golden/p0a-minimal/input
- uv run python -m hate export qeg --fixture fixtures/golden/p0b-qeg-minimal/input --out C:\tmp\hate-p0b-check
- uv run python -m compileall src tests
- git diff --check

成果物:
- 実装コード
- fixture
- pytest
- RUNBOOK 更新
- Shipyard evidence JSON
- 必要なら SPECIFICATION / EVALUATION の参照更新。ただし仕様の意味を変えない。

最後に WorkerResult として次を報告してください。

worker_result:
  task_id: HATE-MVP-005-P0B-QEG-EXPORT
  phase: P0b
  status: success | failed | needs_manual_review
  changed_paths: [...]
  generated_artifacts: [...]
  validation_commands:
    - command: ...
      result: pass | fail
      summary: ...
  open_risks: [...]
  source_refs:
    - docs/process/P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md
    - docs/process/SPECIFICATION.md
  publish_gate_override: false
```

## 5. 二回目プロンプト: P0b Manual/Edge Fixture Hardening

P0b初回実装が通った後に渡す。

```text
前回の P0b QEG export 実装を hardening してください。

対象:
- missing-source-ref
- missing-required-artifact
- unsafe-artifact-required
- high-risk-no-execution

追加すること:
- negative fixtures
- pytest
- qeg-export-report の unsupportedClaims / excludedArtifacts / missing_execution の検証
- qeg-export-summary.md が unsafe artifact path を漏らさない検証
- docs/process/shipyard-run-evidence-p0b-qeg-export.json の更新

禁止:
- QEG Gate verdict をHATE側で出さない
- missing execution を隠して completeness だけを高く見せない
```

## 6. 三回目プロンプト: P1a Trust Hardening

P0bがShipyard acceptanceを通った後に渡す。

```text
HATE P1a trust hardening を実装してください。

正本:
- docs/process/P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md
- docs/process/SPECIFICATION.md
- docs/process/EVALUATION.md
- docs/process/GUARDRAILS.md

対象:
- aete-score.json
- adapter-capability.json
- profile-report.json
- artifact-resolver-map.json
- doctor-report.json
- replay / compare / explain / recommend の最小CLI

必須:
- AETE score は 0/1/3/5 の離散値
- rubric_version, profile_version, score_confidence, calibration_status を持つ
- 未校正 score を release Gate 正本のように表示しない
- path normalization と canonical test identity を決定的にする
- P0a/P0b テストを壊さない
```

## 7. 実行順

1. P0b QEG export 実装
2. P0b negative / edge fixture hardening
3. P1a trust hardening
4. P1b RanD / Shipyard / workflow-cookbook artifact integration
5. P2 optional export / product reports
6. P3 enterprise readiness reports

## 8. 完了判定

各GLM5 taskは、実装完了 claim ではなく phase completion claim を返す。

| phase | completion claim |
|---|---|
| P0b | QEG optional evidence export が生成・検証できる |
| P1a | trust hardening artifact が生成・再計算できる |
| P1b | downstream integration artifact が生成できる |
| P2 | optional export が canonical decision を変えない |
| P3 | product readiness artifact と metric が生成できる |

フル実装完了 claim は、P0b〜P3 の全phaseが Shipyard acceptance を通った後にだけ評価する。
