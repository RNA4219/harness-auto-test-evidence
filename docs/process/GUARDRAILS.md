---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-27
next_review_due: 2026-07-27
---

# Guardrails & 行動指針

## 目的

- 設計破綻を避けるため、`harness-auto-test-evidence` 実装時の
  境界・評価軸・破壊的変更を明確化する。
- `coverage` 過信を避け、証跡品質評価（AETE）を主軸に据える。

## 原則

- 小さな差分で進める（1 周期あたり 2 ファイル + 100 行程度を目安）
- `code-to-gate` / `manual-bb-test-harness` / `quality-evidence-graph` を
  置き換えない。接続層として役割分担する。
- QEG が担う Gate policy / waiver / approval / retention / immutability /
  schema migration / source-backed Gate reason を HATE 側で再実装しない。
  HATE は自動テスト証跡の optional evidence producer / normalizer に徹する。
- RanD / KanoMode が出す requirements audit verdict は HATE 側で上書きしない。
  HATE は requirement / acceptance / risk に対する自動テスト証跡の有無、
  不足、AETE 根拠だけを出す。
- shipyard-cp の state machine / worker dispatch / publish approval を HATE 側で
  再実装しない。HATE は `WorkerResult` / `RunSystemPacket` / audit refs へ
  添付できる evidence bundle を出す。
- workflow-cookbook の Task Seed / Acceptance / Evidence / Birdseye / workflow plugin
  checker を HATE 側で再実装しない。HATE は cookbook へ渡せる
  `workflow-*` artifact の生成に留める。
- 全 artifact に以下を必須付与:
  - `schema_version`
  - `commit_sha`
  - `run_id` または `run_attempt`
  - `created_at`
  - `sha256`（可能な範囲）
- 証跡整合を崩す入力は「可視化優先」せず `DQ` または `disqualified` 扱いにする。
- 外部システム連携は任意実装とし、まず local-first を優先する。

## 実装制約

- 既存ドキュメント契約を壊さず追加を優先
- schema 変更は `record` と `acceptance` に追跡可能にする
- 外部 API 利用は最小限とし、secret / パス / token を `record` へ平文保存しない
- `gate-decision.json` の判定ロジックに曖昧なデフォルト値を残さない
- 失敗時は `hard fail` / `soft fail` を分離し、exit code を分かりやすくする
- adapter が取得できない証跡粒度は capability manifest に明示し、
  AETE の欠損を暗黙の成功として扱わない
- DQ、AETE threshold、必須 artifact、manual 補完条件は HATE の
  adapter / AETE profile に束縛し、実行時の雰囲気で判定を変えない。
  最終 Gate policy は QEG に委譲する
- public summary には `safe_for_summary=false` の artifact path や
  redaction 未完了の trace / screenshot / video / log を出さない
- QEG export は minimal valid bundle fixture で互換性を確認してから
  gate / record の正本入力として扱う
- RanD audit packet と結線する場合は、`no_go` / `conditional_go` issue を
  `coverage` や `passed tests` だけで `go` 相当に変換しない
- shipyard-cp へ渡す場合は advisory evidence として扱い、Shipyard 側の
  `acceptance`, `integrate`, `publish` の状態遷移条件を HATE が変更しない
- workflow-cookbook へ渡す場合は、完了表現が実装状態を超えないようにし、
  Task Seed、Acceptance、Evidence の参照連鎖を欠損させない
- matrix / shard / retry aggregation は決定的に実装し、同じ入力で異なる
  aggregate status を出さない
- path normalization は QEG sourceRefs / artifact metadata へ渡す前に完了させる

## 非機能ガード

- 同一入力に対して AETE / gate 判定は決定的（deterministic）であること
- `run_id` 変更時に、同一履歴が混線しないこと
- matrix / shard / retry の順序差で AETE / aggregate status が変わらないこと
- 監査可能な履歴を残すため JSONL / NDJSON を優先採用
- baseline / history index を導入する場合も、run 単位 record と履歴参照を
  混在させない

## 例外条件

- 証跡欠損（artifact hash 不在、coverage 破損、timestamp 破れ）時は即時 DQ
- 重要な risk に対して実行証跡が 0 件のケースは、manual 補完を要求

## リマインダー

- 変更前に `harness-auto-test-evidence/BLUEPRINT.md` の Scope/I/O を再確認すること
- 変更後に `TASK` も update し、`EVALUATION.md` の受入と紐づけること
