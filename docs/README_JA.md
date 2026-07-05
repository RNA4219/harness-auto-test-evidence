# HATE: harness-auto-test-evidence

HATE は、自動テストと実リポジトリ検証の結果を local-first に収集し、
HATE/v1 の JSON 証跡へ正規化する CLI ツールです。JUnit、coverage、pytest、
Vitest、Jest、real-repo 実行結果などを、人間と QEG が読める形へ変換します。

HATE は「最後の承認ゲート」ではありません。HATE の役割は、QEG や周辺の
workflow tool が判断できる材料を揃えることです。release approval、waiver、
immutability、retention、最終 Go/No-Go は QEG 側の責務です。

## 何ができるか

- 自動テスト結果と coverage を HATE/v1 artifact に変換する
- QEG optional evidence bundle を生成する
- trust / AETE / DQ / replay / compare / explain / recommend / doctor の補助証跡を出す
- RanD、Shipyard、workflow-cookbook 向けの workflow artifact を作る
- product readiness と release candidate pack の advisory artifact を生成する
- 実リポジトリを roster で実行し、timeout、record count、regression、hold を保存する
- platform CLI で findings、risk debt、manual review、assignment、score、verdict、triage を扱う
- 主要 OSS 10本の期待 verdict corpus を使い、precision / recall を測る

## 重要な現在地

- PoC は完了済みです。
- `product_ready` は false のままです。
- HATE 単体は production release authority ではありません。
- 主要 OSS 10本の二周検証では、最終 cycle が 5 pass / 5 hold、22,171 records で安定しました。
- frozen corpus に対する `hate platform verdict` は 10/10 matched、precision / recall / accuracy が 1.0 です。
- `hate platform triage` は 5件の Hold と、pytest compile smoke subset の 1件 soft gap を運用キューへ出します。

## インストールと実行

Python 3.11 以上と `uv` を使います。

```powershell
git clone https://github.com/RNA4219/harness-auto-test-evidence.git
cd harness-auto-test-evidence
uv run pytest -q
```

CLI は次の形で実行します。

```powershell
uv run python -m hate --help
uv run python -m hate platform --help
```

P0a の最小 golden path:

```powershell
uv run python -m hate p0a `
  --input fixtures/golden/p0a-minimal/input `
  --out tmp/p0a-smoke `
  --source-version local-smoke
```

## Platform CLI

`hate platform` は、人間が運用しやすい形で証跡を読み直すための入口です。

主なコマンド:

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
- `plugin run`: manifest-driven plugin を subprocess で実行し、sandbox report を作る
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

claim を更新した場合は、README、acceptance、Birdseye、schema registry、
product-grade status が矛盾していないことを確認してください。

## ライセンス

MIT License。詳細は [LICENSE](../LICENSE) を参照してください。

