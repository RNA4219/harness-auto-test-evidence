---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-27
next_review_due: 2026-07-27
---

# Workflow Cookbook Integration

## 1. 目的

HATE の実装を `workflow-cookbook` の Task Seed / Acceptance / Evidence /
Birdseye / workflow plugin の運用に接続する。

HATE は自動テスト証跡の normalizer / evaluator であり、実装作業そのものは
`workflow-cookbook` の作業様式で追跡する。これにより、実装タスク、
検収記録、証跡、ドキュメント鮮度、cross-repo 参照を後から再計算できる。

## 2. 接続範囲

| 領域 | workflow-cookbook 側 | HATE 側 |
|---|---|---|
| Task Seed | `TASK.codex.md`, `docs/tasks/*.md` | `TASK.codex.md` と HATE-MVP-* 分解 |
| Acceptance | `docs/acceptance/AC-YYYYMMDD-xx.md` | HATE acceptance fixture / verification result |
| Evidence | `agent-protocols` Evidence JSONL | HATE run / qeg / aete / dq artifact refs |
| Birdseye / Codemap | `docs/birdseye/index.json`, `caps/*.json` | HATE docs / schema / adapter の依存マップ |
| workflow plugin | task/acceptance sync, docs resolve, stale check | HATE task / acceptance / docs freshness の検証 |

## 3. HATE 追加 artifact

HATE は実装フェーズで次を生成できるようにする。

| artifact | 役割 |
|---|---|
| `workflow-task-seed.json` | HATE-MVP-* を workflow-cookbook Task Seed 互換にした一覧 |
| `workflow-acceptance-record.json` | acceptance record へ転記できる検収結果 |
| `workflow-evidence.jsonl` | agent-protocols Evidence 互換へ写像できる HATE 証跡 |
| `workflow-docs-stale.json` | HATE docs / schema / fixture の stale check 結果 |
| `workflow-birdseye-map.json` | HATE docs / adapters / schemas / fixtures の依存ノード候補 |

これらは HATE の品質判定正本ではない。実装運用を追跡するための
workflow-cookbook 接続 artifact である。

## 4. 生成規則

- `workflow-task-seed.json`
  - `task_id`, `objective`, `scope`, `requirements`, `affected_paths`,
    `local_commands`, `acceptance_refs` を持つ。
  - HATE-MVP-* は 0.5 日程度の作業単位へ分割する。
- `workflow-acceptance-record.json`
  - `acceptance_id`, `task_id`, `scope`, `acceptance_criteria`,
    `evidence_refs`, `verification_result` を持つ。
  - 完了を実装状態より強く表現しない。
- `workflow-evidence.jsonl`
  - 1 行 1 Evidence record とし、HATE の `record_id`, `run_id`,
    `commit_sha`, `artifact_refs`, `dq_summary`, `aete_summary` を含める。
  - `agent-protocols` Evidence へ写像可能な field 名を保つ。
- `workflow-docs-stale.json`
  - `doc_ref`, `last_reviewed_at`, `next_review_due`, `stale_status`,
    `required_action` を持つ。
- `workflow-birdseye-map.json`
  - `node_id`, `path`, `role`, `deps_out`, `risk` を持つ。
  - HATE 自身で Birdseye 正本を持たず、workflow-cookbook 形式へ渡す候補に留める。

## 5. CLI 連携案

```text
HATE workflow task-seeds     # HATE-MVP-* を Task Seed 互換 artifact にする
HATE workflow acceptance     # 検収結果を acceptance record 互換 artifact にする
HATE workflow evidence       # HATE artifact refs を Evidence JSONL へ写像する
HATE workflow docs-stale     # docs freshness / stale check 用 artifact を出す
HATE workflow birdseye       # HATE docs/schema/fixture の依存マップ候補を出す
```

## 6. 責務境界

- HATE は workflow-cookbook の checker / plugin host を再実装しない。
- HATE は Task Seed / Acceptance / Evidence に渡せる artifact を生成する。
- Acceptance record の正本は workflow-cookbook 形式の `docs/acceptance/` に置く。
- Evidence 契約の正本は `agent-protocols` に委譲する。
- docs resolve / stale check の正本は workflow plugin / memx-resolver に委譲する。

## 7. 最小 fixture

実装時は次の fixture を用意する。

- `fixtures/workflow/task-seed.sample.json`
- `fixtures/workflow/acceptance-record.sample.json`
- `fixtures/workflow/evidence.sample.jsonl`
- `fixtures/workflow/docs-stale.sample.json`
- `fixtures/workflow/birdseye-map.sample.json`

これらは P1 の workflow-cookbook 接続を検証するための最小契約であり、
P0a の local-first gate 判定を妨げない。
