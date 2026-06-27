---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-27
next_review_due: 2026-07-27
---

# harness-auto-test-evidence

## 1. 役割

`harness-auto-test-evidence` は、`harness-auto-test-evidence` の主要目的を、`workflow-cookbook` の運用型様式で定義し、実装を段階的に進めるための実装準備用ハブです。

- 変更点
  - CI で得られる自動テスト信号（JUnit/Playwright/coverage/SARIF/etc）を受け取り、正規化
- 目的
  - `code-to-gate` の差分・リスク情報に接続した「証拠連携ハーネス」を構築
- 最終連携
  - `quality-evidence-graph`（QEG）への export、`agent-state-gate` / `agent-gatefield` への Gate 記録を前提

## 1.1 QEG との責務境界

HATE は QEG の前段として、自動テスト証跡を収集・正規化し、AETE と
artifact manifest を付与して QEG が検証できる optional evidence に変換する。

- HATE が担うもの
  - JUnit / coverage / SARIF / Playwright / Pact / Stryker などの ingest
  - flaky / retry / matrix / coverage context / artifact availability の AETE 評価
  - QEG fixture と互換する `qeg-bundle.json` / optional evidence export
- QEG に委譲するもの
  - Gate policy、waiver、approval、retention、immutability、schema migration
  - source-backed Gate reason、DQ 優先、release 判定、record 正本化

## 2. 参照する文書

- [BLUEPRINT.md](docs/process/BLUEPRINT.md)
- [SPECIFICATION.md](docs/process/SPECIFICATION.md)
- [RUNBOOK.md](docs/process/RUNBOOK.md)
- [GUARDRAILS.md](docs/process/GUARDRAILS.md)
- [EVALUATION.md](docs/process/EVALUATION.md)
- [WORKFLOW_COOKBOOK_INTEGRATION.md](docs/process/WORKFLOW_COOKBOOK_INTEGRATION.md)
- [TASK.codex.md](TASK.codex.md)
- [deep-research-report.md](docs/research/deep-research-report.md)

## 3. 進行方針（workflow-cookbook 適合）

- まず `BLUEPRINT.md` で範囲と I/O 契約を固定
- 次に `SPECIFICATION.md` で QEG export / workflow artifact / DQ / AETE の実装契約を確認
- 次に `TASK.codex.md` の Task Seed を順番に消化
- `RUNBOOK.md` の最短実行手順で検証を回し、`EVALUATION.md` で完了判定
- 文書は実運用に耐えるよう最小維持、完了資産は履歴へ移す（完了記録を蓄積する）

## 4. 状態

- 実装前準備: 進行中
- 依存: `workflow-cookbook` 様式に従い、`code-to-gate` と `quality-evidence-graph` の仕様確認を先行
