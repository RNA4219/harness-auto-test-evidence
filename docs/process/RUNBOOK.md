---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-27
next_review_due: 2026-07-27
---

# Runbook

## 0. 準備

- 対象リポジトリ: `harness-auto-test-evidence`
- 実行環境: local / CI を想定
- 前提: `manual-bb-test-harness` / `code-to-gate` / `quality-evidence-graph` 参照可

## 1. 実装フロー（最短）

1. `BLUEPRINT.md` で In/Out と I/O を固定
2. `TASK.codex.md` の順番で Task を実装
3. 各 Task ごとに `record.json` 互換の検証メモを残す
4. `EVALUATION.md` の受入項目を満たして完了判定

## 2. ローカル実行（準備）

- リポジトリの状態確認（文書整合含む）
- CI 連携の dry run 設定（GitHub metadata mock）
- テスト素材（JUnit/LCOV/SARIF/trace）1セットを用意
- RanD 接続を確認する場合は `requirements_audit_packet.json` の fixture を用意
- shipyard-cp 接続を確認する場合は `WorkerResult` / `RunSystemPacket` の fixture を用意
- workflow-cookbook 接続を確認する場合は Task Seed / Acceptance / Evidence /
  docs stale / Birdseye map の fixture を用意

## 3. 想定コマンド（実装着手後）

※ 現在は設計・実装準備段階のため、実体が追加された時点で更新。

- テスト:
  - 実装言語別のデフォルトに従う（Python/TS/Go いずれか）
- 受入検証:
  - まず `record.json` スキーマ整合
  - 次に `gate-decision.json` の再現性確認
- 監査:
  - `artifact-manifest.json` と `evidence-map.json` のノード参照整合を確認

## 4. 受理前確認

- DQ 条件（HATE-DQ-01〜15）が未解消のまま判定に進んでいないか
- Diff-risk-test で `changed high-risk path` と `execution` の接続欠損がないか
- AETE スコアが計算不能なら `disqualified` 明示になるか
- HATE が QEG の Gate policy / waiver / approval / retention / immutability /
  schema migration を重複実装していないか
- RanD の Requirement Definition Gate verdict を HATE が上書きしていないか
- `requirement-evidence-alignment.json` が requirement / acceptance / risk ごとの
  自動テスト証跡と不足理由を説明できるか
- `shipyard-run-evidence.json` が Shipyard の run / audit refs と HATE artifact refs を
  結線し、Shipyard の state machine を変更していないか
- `workflow-task-seed.json` から HATE-MVP-* と acceptance refs を辿れるか
- `workflow-acceptance-record.json` が acceptance record 必須 field を満たすか
- `workflow-evidence.jsonl` が HATE artifact refs、AETE summary、DQ summary を保持するか
- `workflow-docs-stale.json` と `workflow-birdseye-map.json` が docs freshness /
  依存候補を説明できるか
- HATE が workflow-cookbook の checker / plugin host / Birdseye 生成器を
  重複実装していないか
- matrix / shard / retry aggregation が同一入力で同一結果になるか
- coverage / SARIF / JUnit / Playwright artifact の path が QEG の sourceRefs /
  artifact metadata に渡せる形へ正規化されているか
- HATE optional evidence を QEG minimal fixture に接続しても `validate / gate / record`
  の前提を壊さないか

## 5. ロールバック方針（文書中心）

- 誤判定や schema 破綻が見つかった場合
  - その Task を未完了に戻し、受入条件を更新
  - 影響を受ける証跡出力を削除ではなく再生成で置換

## 6. 最新メモ

- 直近: 2026-06-27 `workflow-cookbook` の書式で実装準備文書を追加
- 次点: Task ベース実装へ移行
