---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-27
next_review_due: 2026-07-27
---

# Evaluation

## Acceptance Criteria

- `BLUEPRINT.md` の In/Out と実装の実体が一致している
- 収集・正規化・相関・AETE の 4 機能が `TASK` 分解で実装済み
- 全 JSON / NDJSON record が共通 envelope（`schema_version`, `record_type`, `record_id`, `run_id`, `run_attempt`, `commit_sha`, `created_at`, `source_tool`, `source_version`, `sha256`, `redaction_status`, `payload`）を持つ
- DQ ルール（最低 HATE-DQ-01, 02, 03, 05, 07, 10, 15）を実装し、`hard_dq` / `soft_gap` の severity と gate への影響が再現可能
- policy の既定 `dq.enabled` に HATE-DQ-01, 02, 03, 05, 07, 10, 15 が含まれている
- `artifact-manifest.json` が存在し、trace/screenshot/video の参照が壊れていない
- `artifact-manifest.json` が trace/screenshot/video/log の `sha256`, `redaction_status`, `retention`, `size_bytes`, `public_exposure` を持つ
- `artifact-manifest.json` が公開可否判断のための `classification`, `redaction_rule_version`, `safe_for_summary` を持つ
- `evidence-map.json` が diff-risk-test エッジを持つ
- QEG export (`qeg-bundle.json`) が最低項目を満たす
- QEG export は minimal valid bundle fixture で互換性を検証できる
- HATE が QEG の Gate policy / waiver / approval / retention / immutability /
  schema migration を再実装していないことを確認できる
- HATE が QEG optional evidence producer / normalizer として、QEG の
  `validate / gate / record` に渡せる成果物を出す
- Allure / ReportPortal / Codecov / SonarQube などの外部 export adapter は non-gating optional として扱われ、未設定でも local-first の gate 判定が完了する
- AETE の 8 次元 rubric が 0 / 1 / 3 / 5 の離散値で実装され、欠損値が DQ か任意証跡の 0 点かを区別できる
- adapter capability manifest により、adapter ごとの未対応粒度（flaky 判定、coverage context、artifact hash など）を summary と JSON に明示できる
- adapter / AETE profile により、DQ、AETE threshold、必須 artifact、manual 補完条件を再現可能に切り替えられる
- matrix / shard / retry aggregation が決定的で、同一 test case の複数結果を
  `stable`, `flaky`, `failed`, `inconclusive` などへ再現可能に集約できる
- path normalization が workspace 相対 path、container path、Windows path、
  package root の差を吸収し、QEG の sourceRefs / artifact metadata に接続できる
- P0a の最小成果物（`HATE-run.json`, `HATE-test-results.ndjson`, `HATE-coverage.ndjson`, `artifact-manifest.json`, `gate-decision.json`, `record.json`）だけで local-first gate 判定が完了する
- RanD `requirements_packet.json` / `requirements_audit_packet.json` を任意入力として受け取り、
  requirement / KPI / acceptance / risk / gate_verdict と HATE evidence を結線できる
- `requirement-evidence-alignment.json` が requirement ごとの
  `testability`, `implementation_alignment`, `evidence_coverage`,
  `unverified_acceptance`, `source_refs` を持つ
- RanD audit の `no_go` / `conditional_go` issue を HATE が独自に上書きせず、
  自動テスト証跡の有無と不足理由だけを出力できる
- shipyard-cp `WorkerResult` / `RunSystemPacket` / task-run-audit refs を任意入力として受け取り、
  `shipyard-run-evidence.json` に HATE artifact refs、AETE summary、DQ summary を添付できる
- shipyard-cp の state machine / publish approval / worker dispatch を HATE が再実装していないことを確認できる
- `workflow-task-seed.json` が HATE-MVP-* を workflow-cookbook Task Seed 互換の
  `task_id`, `objective`, `scope`, `requirements`, `affected_paths`,
  `local_commands`, `acceptance_refs` へ写像できる
- `workflow-acceptance-record.json` が acceptance record 互換の
  `acceptance_id`, `task_id`, `scope`, `acceptance_criteria`,
  `evidence_refs`, `verification_result` を持つ
- `workflow-evidence.jsonl` が HATE の run / qeg / aete / dq artifact refs を
  Evidence 互換の 1 行 1 record として出せる
- `workflow-docs-stale.json` が docs / schema / fixture の freshness を記録し、
  stale の場合に required action を出せる
- `workflow-birdseye-map.json` が HATE docs / adapters / schemas / fixtures の
  node 候補と deps を持つ
- HATE が workflow-cookbook の acceptance checker、workflow plugin host、
  Birdseye/Codemap 生成器を再実装していないことを確認できる

## KPIs

- AETE 計算の再現率: 同一入力で同一 score
- DQ 抜け率: 重要 DQ 対象（coverage-only, execution missing, stale）を 0% へ低減
- Gate 完了ラグ: 主要証跡ファイル生成→ gate 判定まで 5 分以内（ローカル）
- 可読性: summary（Markdown）と機械可読（JSON/NDJSON）の出力共存
- 外部連携非依存率: 外部 SaaS 未設定でも P0 gate 判定が 100% 完了
- artifact 安全性: public summary に secret / token / 未 redaction artifact path が出ない
- adapter 明示性: 未対応 capability が hidden gap にならず 100% manifest に記録される
- QEG 互換性: minimal fixture が HATE/QEG 双方で validate できる
- 責務分離: HATE の出力が QEG の統制入力に従い、HATE 独自の release approval /
  waiver / retention 正本を持たない
- 集約再現性: matrix / shard / retry が同一入力で同一 aggregate status になる
- path 解決率: Gate 関連 sourceRefs へ渡す path が 100% 正規化済みになる
- 要件裏付け率: RanD audit packet 内の `go` / `conditional_go` 要件について、
  acceptance criteria と自動テスト evidence の結線率を記録できる
- 監査上書き率: RanD `no_go` issue を HATE が `go` 相当に上書きするケースが 0%
- Shipyard 添付率: HATE の主要 artifact refs が `shipyard-run-evidence.json` に
  100% 記録され、run / audit refs と結線される
- Workflow traceability: HATE-MVP-* の 100% が Task Seed 互換 artifact から
  acceptance / evidence refs へ辿れる
- Workflow stale 可視性: HATE の主要 docs / schema / fixture の stale 状態が
  `workflow-docs-stale.json` に 100% 記録される

## Test Outline

- 単体:
  - 正規化 adapter の変換単体
  - AETE スコア集計ロジック
  - DQ 判定ルール
  - 共通 envelope validation
  - artifact manifest の hash / redaction / retention validation
  - adapter capability manifest の validation
  - adapter / AETE profile の threshold / DQ 切替
  - matrix / shard / retry aggregation
  - path normalization
  - RanD requirements packet / audit packet の schema 最小 validation
  - requirement-evidence alignment の生成
  - shipyard-cp WorkerResult / RunSystemPacket mapping
  - workflow-task-seed / workflow-acceptance-record / workflow-evidence の schema 最小 validation
  - workflow-docs-stale / workflow-birdseye-map の生成
- 結合:
  - Run→Collect→Normalize→Gate→Export のパイプライン
  - QEG export fixture による node / edge 最低項目の検証
  - HATE optional evidence を QEG fixture に取り込み、QEG `validate / gate / record`
    相当で破綻しないこと
  - P0a 最小入力だけでの local-first gate 判定
  - RanD audit packet fixture を入力し、要件ごとの evidence gap が再現可能に出ること
  - shipyard RunSystemPacket fixture に HATE artifact refs を添付し、advisory evidence として保存可能な JSON が出ること
  - workflow-cookbook 接続 fixture から Task Seed / Acceptance / Evidence の参照連鎖が生成されること
- 補助:
  - 変更ファイルなし run の再現チェック（deterministic）
  - 不正な入力を与えた場合の `disqualified` 判定
  - 外部 adapter 未設定時にも local-first gate が完了すること
  - high-risk path に実行証跡が 0 件のとき `no_go` または manual 補完要求になること
  - public summary に `safe_for_summary=false` の artifact 参照が出ないこと

## 検証チェックリスト

- [ ] `TASK.codex.md` の Task Seed が実装順で消化されている
- [ ] 主要出力（`HATE-*.json`, `qeg-bundle.json`, `record.json`）が生成される
- [ ] 主要 JSON / NDJSON record が共通 envelope を満たす
- [ ] DQ 発生時と non-DQ 時の判定差分が明確
- [ ] `hard_dq` / `soft_gap` の挙動が policy と一致している
- [ ] AETE 8 次元 rubric の採点根拠が `aete-score.json` に残る
- [ ] artifact manifest に hash / redaction / retention / exposure 情報が残る
- [ ] artifact manifest に classification / redaction rule / summary 公開可否が残る
- [ ] adapter capability manifest が未対応粒度を明示している
- [ ] adapter / AETE profile ごとの DQ / AETE / manual 補完条件が fixture で検証されている
- [ ] matrix / shard / retry aggregation が fixture で検証されている
- [ ] path normalization が QEG sourceRefs / artifact metadata と整合している
- [ ] QEG minimal valid bundle fixture が検証されている
- [ ] QEG が担う Gate policy / waiver / approval / retention / immutability /
      schema migration を HATE が重複実装していない
- [ ] RanD `requirements_audit_packet.json` と HATE evidence map の結線が検証されている
- [ ] RanD の Requirement Definition Gate verdict を HATE が上書きしていない
- [ ] `requirement-evidence-alignment.json` が requirement ごとの未検証 acceptance と source_refs を持つ
- [ ] shipyard-cp `RunSystemPacket` / `WorkerResult` fixture から `shipyard-run-evidence.json` を生成できる
- [ ] HATE が shipyard-cp の state machine / publish approval / worker dispatch を重複実装していない
- [ ] `workflow-task-seed.json` から HATE-MVP-* と acceptance refs を辿れる
- [ ] `workflow-acceptance-record.json` が acceptance record 必須 field を満たす
- [ ] `workflow-evidence.jsonl` が HATE artifact refs と DQ / AETE summary を保持する
- [ ] `workflow-docs-stale.json` が stale docs / schema / fixture を検出できる
- [ ] `workflow-birdseye-map.json` が HATE docs / schema / fixture の依存候補を出せる
- [ ] HATE が workflow-cookbook の checker / plugin host / Birdseye 生成器を重複実装していない
- [ ] P0a 最小成果物だけで local-first 判定が完了する
- [ ] 外部 SaaS adapter 未設定でも P0 の local-first 判定が通る
- [ ] `RUNBOOK.md` の手順が最新化されている
- [ ] レビューで `coverage` が単独評価になっていないことを確認
