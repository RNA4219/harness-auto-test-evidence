---
intent_id: INT-HATE-IMPLEMENTATION-ROADMAP-CHECKLIST-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# 実装ロードマップ / チェックリスト

## 1. 目的

本書は、`IMPLEMENTATION_TASK_BREAKDOWN.md` を日々の実装進行に使える
チェックリストへ落とした実行管理表である。仕様正本は以下とする。

- フル実装仕様不足解消: `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md`
- 実装タスク正本: `IMPLEMENTATION_TASK_BREAKDOWN.md`
- P0b詳細: `P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md`
- P1a詳細: `P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md`

`accepted` は、コード、schema、fixture、test、docs、UAT または自動検収が揃った状態だけを指す。

## 2. 状態凡例

| status | 意味 |
|---|---|
| `[x] accepted` | 実装、fixture、test、docs、UAT/検収が完了 |
| `[~] verified` | 実装と自動テストは通過。docs/UAT/evidenceの残あり |
| `[>] next` | 次に着手する |
| `[ ] planned` | 未着手 |
| `[!] blocked` | 仕様矛盾または外部依存で停止 |

## 3. Current Baseline

直近の確認済み baseline:

- `uv run pytest -q`: 1046 tests pass
- `uv run python -m compileall src tests tools`: pass
- `git diff --check`: pass
- Gap closure expected report: HATE-GAP-001..026 are `implemented`, `hold_count=0`, `checker_ready_count=0`
- Birdseye: 966 nodes / 313 edges

完了済み:

- [x] HATE-P0A-001 generic CI context adapter
- [x] HATE-P0A-002 pytest / vitest / jest result adapter
- [x] HATE-P0A-003 coverage.py context adapter
- [x] HATE-P0A-004 Cobertura / JaCoCo hardening
- [x] HATE-P0A-005 artifact safety engine
- [x] HATE-P0A-006 JSON Schema validation
- [x] HATE-P0A-007 profile-aware precheck
- [x] HATE-GAP-001..026 product requirement gap closure implementation

実装済みだが後続 hardening 対象:

- [~] LCOV / Cobertura / JaCoCo parser 初期実装
- [~] SARIF minimal finding mapping
- [~] artifact manifest safety 初期実装

## 4. Milestone Roadmap

### M0: P0a Adapter Completion

目的: P0a を多形式 adapter の安定した入口にする。

Exit criteria:

- P0aが JUnit / pytest / vitest / jest / LCOV / Cobertura / JaCoCo / coverage.py を受けられる
- malformed / partial / no-junit / windows path / missing context のfixtureが揃う
- artifact safety が missing / secret / url / symlink / archive を分類する
- profile未導入部分はP0a hard DQとsoft gapの仕様差分として明記する

Tasks:

- [x] HATE-P0A-001 generic CI context adapter
- [x] HATE-P0A-004 Cobertura / JaCoCo hardening
- [x] HATE-P0A-005 artifact safety engine
- [x] HATE-P0A-006 JSON Schema validation
- [x] HATE-P0A-007 profile-aware precheck

### M1: P0b Evidence Graph Completion

目的: P0a証跡を QEG optional evidence として欠落なく見える化する。

Exit criteria:

- SARIF finding が rule / level / location / changed_code edge を持つ
- Playwright trace / screenshot / video / log が test / execution / artifact nodeへ結線される
- Pact / Stryker が contract / mutation evidence として表現される
- high-risk missing execution、unsafe artifact、unsupported sourceRefs が hidden gap にならない
- QEG schema compatibility test がある
- manual-bb bridge request が manual_supplement_request 契約で source_refs / oracle / case seed を持つ

Tasks:

- [x] HATE-P0B-001 SARIF full finding mapping
- [x] HATE-P0B-002 Playwright artifact evidence
- [x] HATE-P0B-003 Pact contract evidence
- [x] HATE-P0B-004 Stryker mutation evidence
- [x] HATE-P0B-005 QEG schema compatibility
- [x] HATE-P0B-006 risk debt lifecycle
- [x] HATE-P0B-007 manual-bb bridge contract
- [x] HATE-P1A-001 adapter registry

### M2: P1a Trust Hardening Foundation

目的: AETEと診断を固定値ではなく実signal由来にする。

Exit criteria:

- adapter registry / conformance runner が全adapterを列挙する
- profile inheritance が machine-readable になる
- AETE 8次元が reason_refs 付きでsignalから算出される
- identity / retry / matrix / resolver が deterministic

Tasks:

- [x] HATE-P1A-001 adapter registry
- [x] HATE-P1A-002 adapter conformance runner
- [x] HATE-P1A-003 profile inheritance
- [x] HATE-P1A-004 signal-based AETE scoring
- [x] HATE-P1A-005 canonical identity hardening
- [x] HATE-P1A-006 retry / matrix / shard aggregation
- [x] HATE-P1A-007 artifact resolver
- [x] HATE-P1A-008 replay / compare / explain / recommend hardening
- [x] HATE-P1A-009 doctor finding taxonomy

### M3: P1b External Workflow Integration

目的: RanD / Shipyard / workflow-cookbook / manual-bb と、判定上書きなしで結線する。

Exit criteria:

- RanD requirements/audit packet を読み、`no_go` を上書きしない
- requirement -> risk -> test -> evidence alignment が生成される
- Shipyard WorkerResult / RunSystemPacket refs を保持する
- workflow task / acceptance / evidence / birdseye artifact が生成される

Tasks:

- [x] HATE-P1B-001 RanD requirements packet ingest
- [x] HATE-P1B-002 RanD audit no-overwrite
- [x] HATE-P1B-003 requirement evidence alignment
- [x] HATE-P1B-004 Shipyard WorkerResult ingest
- [x] HATE-P1B-005 Shipyard no-overwrite test
- [x] HATE-P1B-006 workflow-cookbook evidence mapping

### M4: P2 Product Surface

目的: canonical bundle から product/read model/export surface を派生する。

Exit criteria:

- local store / history index から run / bundle / risk debt を再読込できる
- hosted read model API contract test がある
- dashboard view model が必須画面分を出す
- external exporter failure で canonical decision が変わらない

Tasks:

- [x] HATE-P2-001 local store and history index
- [x] HATE-P2-002 hosted read model API
- [x] HATE-P2-003 dashboard view model
- [x] HATE-P2-004 PR annotation export
- [x] HATE-P2-005 artifact budget report
- [x] HATE-P2-006 attestation report
- [x] HATE-P2-007 Allure / ReportPortal / Codecov / SonarQube exporters
- [x] HATE-P2-008 support diagnostic bundle

### M5: P3 Enterprise Readiness

目的: enterprise controls と release candidate pack を実装し、調達/監査に耐える状態にする。

Exit criteria:

- domain model、RBAC、audit、retention、legal hold がartifact classificationと連動する
- connector contract が dry-run fixture を持つ
- release candidate pack が必須レポートを含む

Tasks:

- [x] HATE-P3-001 domain model implementation
- [x] HATE-P3-002 RBAC matrix
- [x] HATE-P3-003 audit event log
- [x] HATE-P3-004 retention / legal hold / export / delete
- [x] HATE-P3-005 SSO / SCIM connector contract
- [x] HATE-P3-006 SIEM / warehouse / ticket connector contract
- [x] HATE-P3-007 trust packet / security review
- [x] HATE-P3-008 residency / deployment report
- [x] HATE-P3-009 commercial / legal commitment register
- [x] HATE-P3-010 assurance pack / evidence room
- [x] HATE-P3-011 release candidate pack

## 5. Next Sprint Checklist

次の1スプリントは M0 を完了させ、P0bへ安定して入る準備を作る。

### Sprint Goal

P0a adapter foundation を閉じる。特に Cobertura / JaCoCo、artifact safety、schema validation を
「仕様上ある」から「fixtureとテストで落ちる」状態へ進める。

### Task 1: HATE-P0A-004 Cobertura / JaCoCo hardening

Acceptance checklist:

- [x] `fixtures/adapters/coverage/cobertura/input` を追加
- [x] `fixtures/adapters/coverage/cobertura/malformed` を追加
- [x] `fixtures/adapters/coverage/cobertura/partial` を追加
- [x] `fixtures/adapters/coverage/cobertura/windows-path` を追加
- [x] `fixtures/adapters/coverage/jacoco/input` を追加
- [x] `fixtures/adapters/coverage/jacoco/malformed` を追加
- [x] `fixtures/adapters/coverage/jacoco/partial` を追加
- [x] `fixtures/adapters/coverage/jacoco/windows-path` を追加
- [x] Cobertura class filename / package fallback を正規化する
- [x] JaCoCo package/sourcefile を workspace相対pathへ正規化する
- [x] malformed required input は DQ-002 または adapter failure として明示
- [x] partial coverage は default profile で eligible または conditional のどちらかを仕様化
- [x] `tests/test_p0a.py` にCLI黒箱相当の受入テストを追加
- [x] `RUNBOOK.md` に実行例を追加

Validation:

- [x] `uv run pytest tests/test_p0a.py -q`
- [x] `uv run pytest -q`
- [x] `uv run python -m compileall src tests`

### Task 2: HATE-P0A-005 artifact safety engine

Acceptance checklist:

- [x] `fixtures/adapters/artifacts/safe` を追加
- [x] `fixtures/adapters/artifacts/secret` を追加
- [x] `fixtures/adapters/artifacts/external-url` を追加
- [x] `fixtures/adapters/artifacts/path-traversal` を追加
- [x] `fixtures/adapters/artifacts/symlink` を追加
- [x] `fixtures/adapters/artifacts/archive` を追加
- [x] `artifact-manifest.json` に `security_checks` を安定出力
- [x] unsafe artifact は `safe_for_summary=false`
- [x] summaryに unsafe path / secret / URL が漏れない
- [x] P0bで unsafe required artifact が excludedArtifacts / unsafe_artifacts gap になる
- [x] quarantine report のP0a/P0bどちらで出すかを仕様化

Validation:

- [x] `uv run pytest tests/test_p0a.py tests/test_p0b.py -q`
- [x] CLI UAT: safe / secret / url / path traversal fixture

### Task 3: HATE-P0A-006 JSON Schema validation

Acceptance checklist:

- [x] `schemas/HATE/v1` の既存schemaと生成物を対応づける
- [x] schema validation helper を追加
- [x] valid P0a output が schema pass
- [x] invalid decision enum が DQ-015
- [x] missing required envelope field が DQ-015
- [x] unknown field policy を `SCHEMA_REGISTRY_CONTRACT.md` と一致
- [x] CI / pytest に schema validation regression を追加

Validation:

- [x] `uv run pytest tests/test_p0a.py -q`
- [x] `uv run pytest -q`

### Task 4: HATE-P0A-007 profile-aware precheck

Acceptance checklist:

- [x] `src/hate/profile` または同等moduleを追加
- [x] `default`, `strict`, `release`, `experimental` を定義
- [x] CLI `hate p0a --profile` を追加
- [x] same fixtureでprofile差分が説明される
- [x] `profile-report.json` を生成
- [x] `RUNBOOK.md` にprofile実行例を追加
- [x] QEG Gate policyではないことをsummaryに明記

Validation:

- [x] `uv run pytest tests/test_p0a.py -q`
- [x] CLI UAT: default / strict / release

## 6. Per-Task Done Checklist

各タスク完了報告には以下を必ず含める。

- [ ] task_id
- [ ] 変更ファイル
- [ ] 追加fixture
- [ ] 追加/変更テスト
- [ ] 生成artifactの例
- [ ] 実行コマンドと結果
- [ ] UAT結果、またはUAT不要な理由
- [ ] 残リスク
- [ ] 次タスク

## 7. GLM Handoff Prompt

次の実装者には以下を渡す。

```text
対象: HATE-P0A-004 Cobertura / JaCoCo hardening

最初に読む:
- docs/process/IMPLEMENTATION_ROADMAP_CHECKLIST.md
- docs/process/IMPLEMENTATION_TASK_BREAKDOWN.md
- docs/process/FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md
- docs/process/RUNBOOK.md

実装する:
1. fixtures/adapters/coverage/cobertura/{input,malformed,partial,windows-path}
2. fixtures/adapters/coverage/jacoco/{input,malformed,partial,windows-path}
3. Cobertura / JaCoCo path normalization hardening
4. malformed / partial / windows path の受入テスト
5. RUNBOOK実行例

完了条件:
- uv run pytest tests/test_p0a.py -q
- uv run pytest -q
- uv run python -m compileall src tests
- CLI UATでinput/malformed/partial/windows-pathの期待exitとartifact内容を確認

禁止:
- expected fixture手書き更新だけで完了扱いにしない
- malformed coverageを握りつぶさない
- Windows absolute pathをpublic summaryへ出さない
```
