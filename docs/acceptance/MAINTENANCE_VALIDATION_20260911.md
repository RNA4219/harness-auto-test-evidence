# 証跡整合性の修正・検証記録（2026-09-11）

Bridge、LocalStore、P0a/P0b/P1aの不具合修正を検証し、mainへ統合した時点の記録です。
製品全体の監査完了や本番利用の承認を示すものではありません。
`product_ready=false`と外部QEGの最終判断は維持します。

## 対象

- [PR #12](https://github.com/RNA4219/harness-auto-test-evidence/pull/12)
- CI検証対象コミット: `4a0358f62e4f1c388361e3d9f75cc9b1515148d9`
- mainへのマージコミット: `f76f1b90772bc609094ca568cd44ca161593349f`
- マージ日時: 2026-09-11 03:31:06 JST
- 修正内容・残る調査範囲: [MAINTENANCE_FINDINGS.md](../process/MAINTENANCE_FINDINGS.md)のFIX-001〜104

CI対象とマージ後のソースツリーが一致することを確認しました。
既存のv0.3.0 GitHub Release assetは、この修正では再公開していません。

## 検証結果

| 環境・検査 | 結果 |
|---|---|
| ローカルWindows / Python 3.13.7の全体テスト | 4,029 passed、396.55秒 |
| 元status・未実行・実行要件に関する回帰テスト | 86 passed |
| Ruff / mypy / compileall / diff検査 | 通過、mypy対象65ファイル |
| schema・責務境界・文書鮮度・生成文書・Birdseye・サイズ検査 | 通過 |
| sdist/wheelビルド・独立環境へインストールしたwheelの検証 | 通過 |
| GitHub Actions | push / pull_requestの各7ジョブ、計14チェックが成功 |

GitHub Actionsは、static、unit-contract（Python 3.11・3.12・3.13）、windows-process、
package、e2e-releaseを実行しました。すべての完了と対象コミットを確認してからマージしています。

- [pushのCI実行](https://github.com/RNA4219/harness-auto-test-evidence/actions/runs/34514083923)
- [pull_requestのCI実行](https://github.com/RNA4219/harness-auto-test-evidence/actions/runs/34514100921)

## 互換性と残る範囲

- 入力の型・宣言・保存内容の検証強化により、以前は通過していた不正な入力を拒否します。
- [CLI入力・I/O診断契約](../process/CLI_INPUT_ERRORS.md)に終了コードと既存出力の保護範囲を記載しています。
- [LocalStore契約](../process/LOCAL_STORE_IO_CONTRACT.md)に保存復元の保証範囲、
  [Bridge契約](../process/BRIDGE_REQUEST_CONTRACT.md)に旧依頼との互換性を記載しています。
- 未調査項目は修正記録へ残しています。この検証結果を「不具合が存在しない」証明として扱いません。
