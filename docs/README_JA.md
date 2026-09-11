# HATE: harness-auto-test-evidence

HATE はJUnit、coverage、pytest、Vitest、Jest、実リポジトリの検証結果を
ローカルでHATE/v1 JSON証跡へ変換するCLIです。release approval、waiver、
immutability、retention、最終Go/No-Go・公開判断はQEG側の責務です。

## 何ができるか

- 自動テスト結果と coverage を HATE/v1 artifact に変換する
- QEG optional evidence bundle を生成する
- trust / AETE / DQ / replay / compare / explain / recommend / doctor の補助証跡を出す
- workflow連携・product readiness・release candidateの補助証跡を生成する
- platform CLIで実リポジトリの検証、履歴、findings、risk debt、手動レビューを扱う

## 重要な現在地

- PoC完了済み。`product_ready=false`です。
- 主要 OSS 10本の二周検証では、最終 cycle が 5 pass / 5 hold、22,171 records で安定しました。
- frozen corpus に対する `hate platform verdict` は 10/10 matched、precision / recall / accuracy が 1.0 です。
- `hate platform triage` は 5件の Hold と、pytest compile smoke subset の 1件 soft gap を運用キューへ出します。

## 2026-09-11の不具合修正

Bridge、LocalStoreの保存・復旧、P0a/P0bの入力検証、P1aの信頼度評価を修正しました。
未実行やskipは実行要件に数えず、不足をrisk debt・補完依頼へ残します。
詳細と未調査項目は[FIX-001〜104](process/MAINTENANCE_FINDINGS.md)に記載しています。

修正時の全体テストは**4,029件通過**、マージ前のCIは全14チェック成功。
対象コミットとCIへのリンクは[検証記録](acceptance/MAINTENANCE_VALIDATION_20260911.md)を参照してください。

## インストールと実行

Python 3.11以上とuvを使います。今回の修正は`main`にあり、既存のv0.3.0配布物は
再公開していません。修正版をソースから導入する場合:

    git clone https://github.com/RNA4219/harness-auto-test-evidence.git
    cd harness-auto-test-evidence
    uv sync --dev --frozen
    uv run python -m hate --help

配布済みv0.3.0は[GitHub Release](https://github.com/RNA4219/harness-auto-test-evidence/releases/tag/v0.3.0)
のwheelをダウンロードして導入します（PyPIでは配布しません）:

    uv tool install ./harness_auto_test_evidence-0.3.0-py3-none-any.whl
    hate --help

ソースからwheelを作る場合は`uv build`を使います。HATE/v1・HATE-bridge/v1のschemaは同梱済みです。
local subprocess pluginは既定で拒否され、実行には`--allow-local-exec`が必要です。
任意コード実行を伴い、filesystem/network isolationは提供しません。release/regulated profileでは
実行不可です。移行・実行境界の詳細は[CHANGELOG](../CHANGELOG.md)と[SECURITY](../SECURITY.md)を参照してください。

P0a の最小golden path:

    uv run python -m hate p0a --input fixtures/golden/p0a-minimal/input --out tmp/p0a-smoke --source-version local-smoke

## Platform CLI

`hate platform` は、人間が運用しやすい形で証跡を読み直すための入口です。

- `run`: real-repo roster を実行する
- `history`: run history を問い合わせる
- `compare`: base/head report を比較する
- `schedule`: cache TTL、retry、resume token を含む実行計画を作る
- `findings`: finding を抽出する
- `debt`: risk debt を抽出する
- `review`: manual review request を抽出する
- `assign`: owner、due date、SLA の assignment queue を作る
- `score`: freshness、regression、manual debt、oracle confidence を合成した説明可能 score を出す
- `verdict`: 期待 verdict corpus と実行結果を突合し、precision / recall を出す
- `triage`: Hold と subset gap を運用キューへ変換する
- `history-analytics`: 長期履歴から flake rate、debt age、baseline drift、manual review latency を集計する
- `history-materialize`: 履歴集計を差分 materialization し、再利用可能な manifest を作る
- `notify route`: owner / team / SLA breach から通知先と escalation を決める
- `notify deliver`: 通知試行、retry、dead-letter、payload safety を証跡化する
- `baseline review`: baseline 昇格候補を人間レビュー用packetへ変換する
- plugin run: 既定拒否。明示許可されたtrusted local pluginを実行し、未強制controlを含むreportを作る
- `policy explain`: platform policy の有効設定を説明する
- `report html`: offline HTML report を生成する

主要 OSS corpus の例:

```powershell
uv run python -m hate platform verdict `
  --input tmp/major-oss-two-cycle/cycle-2 `
  --corpus docs/process/real-repo-verdict-corpus/major-oss-expected-verdicts-20260704.json `
  --out tmp/platform-verdict.json

uv run python -m hate platform triage `
  --input tmp/major-oss-two-cycle/cycle-2 `
  --out tmp/platform-triage.json
```

## 読むべき文書

- [ルート README](../README.md): エージェント向け入口
- [BLUEPRINT](process/BLUEPRINT.md): 範囲と責務境界
- [SPECIFICATION](process/SPECIFICATION.md): HATE/v1 の主要仕様
- [PRODUCT_REQUIREMENTS_DEFINITION](process/PRODUCT_REQUIREMENTS_DEFINITION.md): 要件定義
- [PRODUCT_GRADE_IMPLEMENTATION_SPEC](process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md): product-grade の完了条件
- [RUNBOOK](process/RUNBOOK.md): 実行手順
- [EVALUATION](process/EVALUATION.md): 受入条件
- [PoC completion](acceptance/POC_COMPLETION_20260703.md): PoC 完了証跡
- [Major OSS two-cycle validation](acceptance/MAJOR_OSS_TWO_CYCLE_20260704.md): 実データ検証

## リリース前チェック

```powershell
uv run pytest -q
uv run python -m compileall src tests
uv run python tools/codemap/update.py --check
git diff --check
```

表明を更新した場合は、関連文書・検証記録・schema・product-grade statusとの整合を確認してください。

## v0.3.0 Responsibility Freeze / Bridge-Only

新規開発はP0a/P0b/P1a、schema/adapter/plugin、local evidence history/replayが対象です。
P1b以降のCLIはthin bridgeで、既定のcompat-v0.2 providerがv0.2互換動作を維持します。

leaf commandの`--bridge-provider handoff`または`HATE_BRIDGE_PROVIDER`（CLI優先）で、外部process/networkを
起動せずbridge-request.jsonを生成します。外部結果は`hate bridge materialize`で検証し、
ID・owner・SHA-256・sourceRefs・schemaの不一致は終了コード2で拒否します。

HATE/v1はv1まで維持し、P1b+はdeprecated_since=0.3.0、remove_after=1.0.0です。

## ライセンス

MIT License。[LICENSE](../LICENSE)を参照してください。
