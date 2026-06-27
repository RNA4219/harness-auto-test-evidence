---
task_id: HATE-IMPLEMENTATION-PREP
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-27
next_review_due: 2026-07-27
---

# HATE 実装準備 Task Seed

## メタデータ

```yaml
task_id: HATE-IMPLEMENTATION-PREP
repo: https://github.com/RNA4219/harness-auto-test-evidence
base_branch: main
priority: P1
langs: [multi]
```

## Objective

`workflow-cookbook` 様式に沿って、`harness-auto-test-evidence` の実装に入れる
最小文書構造とタスク分解を作成し、MVP 実装に直結する状態を作る。

## Scope

- In
  - `README.md`, `BLUEPRINT.md`, `GUARDRAILS.md`, `RUNBOOK.md`, `EVALUATION.md`
  - `TASK.codex.md` 内の作業分解
  - `deep-research-report (9).md` と実装準備資産の整合
- Out
  - 実際のアダプタ実装（収集/変換/export のコード）
  - CI 設定ファイル更新

## Requirements

- Behavior
  - ドキュメントが日本語で統一されていること
  - 文書間で scope / I/O / 受入条件の矛盾がないこと
  - 主要 KPI と DQ をタスクとして明記すること
- I/O Contract
  - Input: 事前調査結果、既存要件、依存 repo 方針
  - Output: 実装準備済みの workflow-cookbook 5点セット + Task Seed
- Constraints
  - 既存資料を壊さない（ファイル追加中心）
  - 受入条件は EVALUATION と一致させる

## Affected Paths

- README.md
- BLUEPRINT.md
- GUARDRAILS.md
- RUNBOOK.md
- EVALUATION.md
- TASK.codex.md

## Local Commands

- `git status --short`
- 文書差分確認（`git diff -- README.md BLUEPRINT.md ...`）

## Plan

1. ドキュメント間の役割を固定し、共通参照を追加
2. P0→P1→P2 の実装順を BLUEPRINT に明記
3. DQ / AETE / Gate を TASK で粒度分解
4. 実装前に受入条件を EVALUATION へ反映
5. MVP を P0a / P0b に分割し、最小 local-first 判定から実装できるようにする
6. adapter capability / adapter-AETE profile / artifact safety / QEG fixture を追加タスク化する
7. QEG が担う Gate policy / waiver / approval / retention / immutability /
   schema migration を HATE 側で再実装しない責務境界を固定する
8. RanD / KanoMode の requirements packet / audit packet を任意入力として扱い、
   要件妥当性・検収可能性・外部証跡に対する自動テスト裏付けを出せるようにする
9. shipyard-cp の WorkerResult / RunSystemPacket / run-audit refs へ HATE の
   evidence bundle を添付できるようにし、acceptance / integrate 前の客観証跡にする
10. workflow-cookbook の Task Seed / Acceptance / Evidence / Birdseye / workflow plugin
    へ接続できる `workflow-*` artifact を定義する

## Notes

- 実装に進む前に、以下の初期タスクを `TASK-HATE-*.md` などとして分解する
  - HATE-MVP-001: provenance と共通 record envelope 整備
  - HATE-MVP-002: JUnit / LCOV の canonical 化
  - HATE-MVP-003: artifact-manifest + gate-decision + record.json の P0a 導線
  - HATE-MVP-004: SARIF / Playwright artifact / diff-risk-test の P0b 拡張
  - HATE-MVP-005: QEG export と minimal valid bundle fixture の監査整合
  - HATE-MVP-006: adapter capability manifest の定義と未対応粒度の可視化
  - HATE-MVP-007: adapter / AETE profile（default / strict / release / experimental）の定義
  - HATE-MVP-008: artifact safety（classification / redaction rule / safe_for_summary）の導入
  - HATE-MVP-009: baseline / history index の最小設計
  - HATE-MVP-010: evidence explain / gap recommendation の設計
  - HATE-MVP-011: QEG 責務境界（Gate policy / waiver / approval / retention /
    immutability / schema migration は QEG に委譲）の fixture / docs 検証
  - HATE-MVP-012: matrix / shard / retry aggregation の決定的集約
  - HATE-MVP-013: coverage / SARIF / JUnit / Playwright artifact の path normalization
  - HATE-MVP-014: RanD `requirements_packet.json` /
    `requirements_audit_packet.json` ingest と schema 最小 validation
  - HATE-MVP-015: `requirement-evidence-alignment.json` の設計
    （requirement / KPI / acceptance / risk / gate_verdict と HATE evidence の結線）
  - HATE-MVP-016: RanD Requirement Definition Gate verdict を HATE が上書きしない
    責務境界 fixture の追加
  - HATE-MVP-017: shipyard-cp `WorkerResult` / `RunSystemPacket` mapping と
    `shipyard-run-evidence.json` の設計
  - HATE-MVP-018: shipyard-cp state machine / publish approval / worker dispatch を
    HATE が再実装しない責務境界 fixture の追加
  - HATE-MVP-019: `workflow-task-seed.json` と
    `workflow-acceptance-record.json` の設計
  - HATE-MVP-020: `workflow-evidence.jsonl` の設計
    （HATE run / qeg / aete / dq artifact refs を Evidence 互換へ写像）
  - HATE-MVP-021: `workflow-docs-stale.json` と
    `workflow-birdseye-map.json` の設計
  - HATE-MVP-022: workflow-cookbook の checker / plugin host /
    Birdseye 生成器を HATE が再実装しない責務境界 fixture の追加
- 追加後は必要に応じて `workflow-cookbook` 既存の Task seed 形式へ展開
