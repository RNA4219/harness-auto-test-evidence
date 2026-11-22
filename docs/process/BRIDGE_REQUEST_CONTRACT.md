# Bridge依頼契約

## 担当先と契約名

`src/hate/bridge/routes.py` は橋渡し対象の全leaf commandと担当先・契約名を定義する。
CLI責務台帳の生成と実行時ルーティングは、この定義を共有する。
`governance/responsibility-registry.json` のCLI欄を手作業で変更しない。

`tools/ci/responsibility_scope_gate.py` はCLIの登録漏れに加え、台帳と実行定義の
担当先・契約名の不一致を検出する。未登録のコマンドは推測で担当先へ送らず、exit 2となる。
HATE/v1 record typeの既存の担当先分類、compat-v0.2の処理内容、外部の最終判断権限は維持する。

## 実行オプション

新たに生成する`HATE-bridge/v1`依頼は`command_options`を含む。

- キーはargparseのdestination名とする。例: `retry_limit`、`source_version`。
- 値は文字列、数値、真偽値、null、またはこれらの配列とする。
- 既定値、false、空配列、nullも保存する。繰り返し指定の配列順を保持する。
- Path引数は`path_arguments`、存在する入力・ストアの指紋は`input_refs`へ保存する。
- `command`と各subcommandの選択は`original_command`へ保存する。
- ローカルの`out`、`manifest_out`、provider選択は実行オプションへ含めない。
- 未対応の値型は欠落させず、依頼生成をエラーにする。

依頼IDはコマンド、担当先、契約名、入力参照、パス指定、実行オプション、期待する出力種別から生成する。
同じ入力・同じ実効オプションなら同じIDになり、実行条件が変わればIDも変わる。
既定値の明示指定や、入力外にあるローカル出力先の変更だけではIDは変わらない。

例えば`platform schedule --retry-limit 3 --force`は、入力ファイルの参照に加えて
`retry_limit=3`と`force=true`を依頼へ保存する。受信側は依頼JSONから実行条件を読める。

## 旧依頼と移行

スキーマ上の`command_options`と`path_arguments`は省略可能とし、修正前の依頼も読み取り・materializeできる。
省略は「元のオプション情報がない」を意味する。既定値で実行された証明にはならない。
元の実行条件が必要な場合は、元のCLIオプションを指定して依頼を生成し直す。

`path_arguments`の省略はパスの用途・未存在パスの指定が復元できないことを意味する。
修正後の依頼IDにはオプション・契約名・パス指定が加わるため、修正前のIDとは変わる。
既存の依頼・結果の組はそのまま保持する。旧結果を新しい依頼へ流用せず、
新しい依頼IDに対応する結果を受信側で作成する。

修正前のHATEスキーマは追加プロパティを拒否するため、新しい依頼を読み込むHATEも
更新する。受信側が独自の厳密なスキーマを持つ場合は、`command_options`と`path_arguments`の受理と
実行処理での利用を確認する。HATEは外部サービスを起動せず、依頼JSONだけを生成する。

## 入力パスと依頼の保存先

`routes.py`は全33コマンドのPath引数を列挙する。`out`と`manifest_out`はローカル出力とし、
それ以外は以下の用途に分類する。登録されていないPath引数は黙って省略せずexit 2とする。

| role | 用途 | 存在条件 |
|---|---|---|
| `input` | 通常の入力。任意フラグでも指定した場合は対象を読む。 | 指定されたパスがなければexit 2。 |
| `optional-input` | `platform schedule --history-store`。履歴なしでの計画を許可する。 | 未存在も保存。既存ならファイルまたはディレクトリーを読む。 |
| `destination` | `real-repo history-ingest --store`。受信側が作成・更新するストア。 | 未存在を許可し、既存ならディレクトリーに限る。 |

`path_arguments`のキーはargparseのdestination名、値は`path`（絶対パス）、`role`、
`exists`（生成時の存在状態）とする。既定値のPathも保存し、未指定の任意Pathは省略する。
Pathを`command_options`へ混在させない。既存のPathは`input_refs`へ指紋を記録し、
更新先ストアについても更新前の内容を識別する。未存在パスにSHA-256や`sourceRefs`は付けない。
保存先ストアの変更、未存在から既存への変化、既存ストアの内容変更は依頼IDを変える。

handoffはストアを作成・更新しない。依頼の保存が未存在のパス引数を作ってしまう配置
（例: 未存在の`--history-store`内へ`--out`を置く）は、生成前にexit 2とする。
パスの内容形式や業務上の妥当性は受信側が検証し、存在情報を将来の実行時の保証とは扱わない。

保存先はコマンドの出力契約に従う。ディレクトリー出力では`--out`の内部、ファイル出力では
そのファイルの隣へ`bridge-request.json`を保存する。拡張子から出力の種類を推測しない。
`--out`等がない場合は`.hate/bridge/<bridge_id>/bridge-request.json`を使う。

`sourceRefs`はpercent encodingを施したfile URIとする。同じファイルを複数引数へ指定した場合、
引数ごとの`input_refs`を保持し、`sourceRefs`のURIは重複させない。

ディレクトリーの指紋は、相対パスと各ファイルのSHA-256を順に結合して算出する。
ファイル本体はストリームで読み込む。自身が生成する依頼と一時ファイルを指紋から除外し、
除外規則を`input_refs[].excluded_paths`へ記録する。各`path`は入力ルートからの相対パスである。

- `file`: 指定した依頼ファイルだけを除外する。
- `directory`: 指定したディレクトリー以下を除外する。既定の`.hate/bridge`が対象。
- `temporary-files`: 指定したディレクトリー直下の`.hate-bridge-*.tmp`を除外する。

この除外により、入力内に保存した依頼の再生成だけではIDが変わらない。入力本体の変更は検出する。
依頼は一意な名前の一時ファイルへ書いてから置換し、書き込み失敗時は旧依頼を保持する。

## 結果の取り込みと復元

出力参照の相対パスは`bridge-result.json`の所在ディレクトリーを基準に解決する。
出力名の重複は大文字・小文字を区別せず事前に拒否する。既存ディレクトリーと衝突する出力も拒否する。
全ファイルを一時領域へコピーし、そのコピーのSHA-256を検証してから出力先を更新する。
元のファイルを検証後に読み直して、未検証の内容を取り込むことを避ける。

通常のI/Oエラーで反映に失敗した場合、既存ファイルを復元し、新規ファイルを除去してexit 2とする。
復元にも失敗した場合は、エラーに示す一時領域の`backups/`と`recovery.json`を残す。
`recovery.json`には出力先、対象ファイル、元のファイルの有無を記録する。内容を確認して復元してから再試行する。
無関係な既存ファイルは保持する。復元完了後の一時ファイル削除に失敗した場合は、残存場所を警告する。

これは通常の失敗時の復元であり、複数ファイルを同時に切り替えるファイルシステム機能ではない。
同じ出力先へ並行書き込みしない。プロセスの強制終了・OS障害時は残った復元情報を確認する。

## 検証

- 全33コマンドの台帳とルーティングの担当先・契約名が一致する。
- 台帳の担当先または契約名だけを変更するとscope gateが失敗する。
- profile、source version、retry、cache TTL、force、繰り返しfilterの指定が保存される。
- 条件を変えた依頼、同じ条件の再生成、既定値の明示、出力先変更のIDを検証する。
- 旧依頼の読み取り、未対応のオプション構造の拒否、既存materializeの動作を検証する。
- パスの空白・拡張子・相対参照、入力と出力の重なり、重複名、途中失敗・復元失敗を検証する。
- 全Path引数の登録、必須入力欠落、未存在ストアの保持、ストア状態とIDの対応を検証する。
- wheel smokeでもリポジトリー外から依頼を生成し、パッケージ内のスキーマと未存在ストアを検証する。

```powershell
uv run pytest -q tests/test_bridge_router.py tests/test_bridge_options.py tests/test_responsibility_architecture.py
uv run pytest -q tests/test_bridge_path_contract.py tests/test_bridge_paths.py tests/test_bridge_materialization.py
uv run python tools/ci/responsibility_scope_gate.py
uv run python tools/docs/render_responsibility_docs.py
```
