# CLIの入力・I/O診断契約

FIX-062〜104の入力検証に関する修正を記録する。機能追加ではなく、既存の診断と証跡識別の修復である。

## 入力JSON

P0aではcontext、record-control、dq-control、artifact-refs、evidence-strength-configの
JSON構文・UTF-8・トップレベルobject形式・読込失敗を`PrecheckError(exit_code=1)`へ変換する。
省略可能な設定が存在しない場合の既定値は従来どおり空objectとする。
adapter内で捕捉してDQを生成する既存経路は、従来のDQ判定を維持する。
test reportの解析失敗は他adapterの成功で消さず、HATE-DQ-002としてhard DQへ残す。
retry/matrix/shardの不正な宣言もこの対象とする。未指定のtest reportはエラーにしない。
JSON test reportのoutcome/statusは宣言時に非空文字列、wouldRunはbooleanを要求する。
不正な型はHATE-DQ-002（終了コード2）へ接続する。P0b recordとP1aのtest/execution dataでは、
status/source_statusとwouldRunを出力前に検証し、それぞれExportError(1)/TrustError(1)にする。
既存成果物と入力を保持し、新規出力先を作成しない。正当な未実行宣言は型エラーにせず、
実行不足とinconclusiveの根拠として扱う。
テスト識別値の不正な型・空値、実行時間の不正な型・符号・数値範囲も項目位置付きでHATE-DQ-002にする。
JUnit/pytest/Vitest/Jestを同じP0aのhard DQ（終了コード2）へ接続する。標準形式の許容値と丸め規則は
[adapter仕様の7節](ADAPTER_DIALECT_PARSER_SPEC.md)に従い、Vitest/Jestのduration=nullは未報告のwarningとして扱う。

P1aのJSON読込では同じ入力不備を`TrustError(exit_code=1)`へ変換する。
ファイル読込・構文解析の元例外は`__cause__`に保持し、診断文に対象ファイルと原因を含める。
`TrustError`のmessage・exit_code初期化と、`PrecheckError`の従来のimport経路を維持する。

| 条件 | 終了コード | stderr |
|---|---:|---|
| P0aの設定JSON入力不備 | 1 | `HATE-E-CLI`と原因 |
| P1aのJSON読込・形式エラー | 1 | コマンド別の`HATE-E-TRUST`等と原因 |
| P0bのJSON/NDJSON読込・run照合・実行座標・同一testのidentity矛盾 | 1 | `HATE-E-EXPORT`と対象位置・原因 |
| P0bのprecheck必須項目・型・decision enum不正 | 1 | `HATE-E-EXPORT`と対象位置・原因 |
| P0bのprecheckによるexport不許可 | 2 | decisionとreasonのJSON |
| P0bの生成bundleのschema不適合 | 1 | `HATE-E-EXPORT`と生成bundleの項目位置・原因 |
| P0bのrisk debt履歴のitems・age_days不正 | 1 | `HATE-E-EXPORT`と入力ファイル・項目位置・原因 |
| P0bの成果物のJSON化・UTF-8化失敗 | 1 | `HATE-E-EXPORT`と出力ファイル名・原因 |
| trust evaluate / replayのbundle・report未存在 | 2 | 従来指定された終了コードとコマンド別診断 |
| compare / doctor / explain / recommendのJSON読込先未存在 | 1 | コマンド別診断 |
| P0aのhard DQ | 2 | 従来のprecheck decision JSON |
| ハンドラーで未捕捉のI/O・文字コードエラー | 1 | `HATE-E-CLI: I/O failure`と原因 |

P0bはprecheckを形式検証した後、decisionがeligible/conditional、許可フラグtrue、exit_code=0、
dq_hits空配列の場合にのみ出力する。不許可と形式不備のどちらでも既存成果物を更新しない。
conditionalのsoft gapだけでは出力を拒否しない。詳細は[P0b契約の2.3節](P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md)を参照する。

## compareのスコア検証

base/headのaete-score.jsonは、8次元の離散値、総合スコアの有限性・0〜1の範囲、
仕様の加重平均との一致を出力前に検証する。追加の重み・集計方法が宣言された場合も照合する。
数値はJSONの原表記を使い、端数がfloatの丸めで有効値へ変わることを防ぐ。
不整合は`TrustError(exit_code=1)`、CLIでは`HATE-E-COMPARE`と対象ファイル・項目を通知する。
既存のcompare-report.jsonを上書きしない。旧単純平均スコアが一致しない場合は、
元のbundle/reportから`hate replay`で再計算する。
この検証はscore入力が対象であり、compareの全補助レポートの構造検証完了を意味しない。

## CLI境界

`main`はdispatchからの`OSError`と`UnicodeError`を捕捉する。
出力ディレクトリー位置に既存ファイルがある場合、そのファイルを置換せず失敗を報告する。
書込み容量不足等も成功JSONを返さず、終了コード1で停止する。
内部ロジックの`ValueError`・`RuntimeError`やargparseの終了処理を一律には捕捉しない。

この修正は複数の出力ファイルを一括で復元する仕組みではない。
P0bでは生成bundleのschema検証をmkdir・書込みより前に完了し、不適合なら既存成果物を保持する。
診断表示を先頭8件と残件数に制限し、APIのExportError.reportには全schemaエラーを残す。
補助成果物の構築・全出力のJSON化・UTF-8検証も書込み前に終え、生成段階の失敗で既存成果物を変更しない。
risk debt履歴のitems・age_days不正は読込段階で止め、正確な0以上の整数だけを経過日数として使う。
正常な再実行でmissing executionが0になった場合、出力先直下の古いrisk debtとmanual bridgeを除去する。
途中の書込み失敗では、それまでに生成済みのファイルが残り得るため、終了コードと診断を確認する。
項目ごとの型・値検証は各処理の契約に従い、今回のJSON読込修正だけで全入力検証の完了とはしない。

## run識別とprofile

run番号は1以上の整数値とし、boolean・非有限数・端数・ゼロ以下を拒否する。
JSON Schemaのintegerに対応する`2.0`等は整数2として扱う。
入力の十進表記を保持して検証し、`1.00000000000000001`がfloatの1へ丸められて通過したり、
大きな整数値が別の試行番号へ丸められたりすることを防ぐ。
P0aのcontextではCI入力としてASCIIの数字文字列も受け入れ、前後空白と先頭ゼロを取り除いた
整数へ一度だけ正規化する。record ID、共通項目、payload、profile、retryで同じ試行番号を使用する。
P1aのbundle/reportでは公開JSONの整数型契約に従い、数字文字列は受け入れない。

P0aのrun IDは空白のみでない文字列、またはCIの整数IDを受け入れる。
P1aのrun IDは空白のみでない文字列とし、null・boolean・配列・object等の文字列化でIDを生成しない。
P1aのmetadataはobject、指定されたcreatedAt・profile・created_at・commit_shaは文字列とする。
欠けたcommitや日時を補ってprovenanceを改善する処理は行わない。

trust evaluate・replay・doctor・explain・recommendはbundleとreportのrun ID・試行番号を照合する。
双方で宣言された値が異なる場合、または両方に識別値がない場合は`TrustError(exit_code=1)`で停止する。
一方だけに有効な識別値がある場合は出力の識別に使うが、元bundleへ値を埋めず、
欠けたprovenanceのscore根拠を変更しない。

未知profileは`UnknownProfileError`（ValueError派生）とし、P0a/P1aの公開APIでは
`PrecheckError`/`TrustError`の終了コード1へ変換する。CLIのp0aは従来のargparse choicesも維持する。
入力不備で既存出力を更新せず、P0aとtrust evaluateは出力内容を準備してから出力先を作成する。

## retry・shard・matrixの宣言

P1aの5コマンドはexecutionのretry_index/attempt_index、shard_index、shard_total/shard_countを
原表記で検証する。retry/shard番号は0以上、期待shard数は1以上とし、boolean・端数・数字文字列を拒否する。
alias同士の矛盾、test/executionの不正なmatrix型、executionの不正なstatus型も入力エラーとする。
診断には`nodes[index].data.field`を含め、既存出力を保持する。
値の型として処理可能なretry欠測・shard不足・不明status等はinconclusiveの集約とdoctor所見へ残す。
詳細は[P1a集約契約](P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md#71-集約の順序と入力条件)を参照する。

## 検証

P0bは`HATE-test-results.ndjson`のJSON・UTF-8・record/payload形式、canonical ID、
retry/matrix/shardの型・範囲・aliasを出力前に検証する。
詳細と正規化recordの識別方法は[P0b入力契約](P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md)を参照する。
HATE-runを基準とする各recordのrun ID・試行番号・commit照合を追加した。
P0bのJSON/NDJSON reader、P0aのcontext reader、P1aの入力readerでは重複JSON keyも入力エラーとする。
これらはrunの整合性と読込境界の修正であり、各payloadの全項目の検証完了を意味しない。


`tests/test_cli_input_errors.py`で公開API・CLIの入力不足、不正JSON、非UTF-8、配列、
ディレクトリー入力、読込権限エラー、出力先衝突、書込み容量不足を検証する。
既存のhard DQのJSONと終了コード2、内部ロジック例外の伝播も確認する。
`python -m hate`の実プロセスとインストール済みwheelでも、入力失敗時の診断を確認する。
`tests/test_run_input_validation.py`で識別値の型・正規化・欠落・入力間の不一致、未知profile、
入力ファイルと既存出力の保持、有効な片側識別値を使う場合のprovenanceを検証する。

## P1aのgraphと所見

trust evaluate・replay・doctor・explain・recommendは、公開QEGスキーマに定義された
nodes・edges・metadata・completeness等の型を検証する。reportのunsupportedClaims、
excludedArtifacts、missing_executionはobjectの配列とし、使用するreason・risk_id等の型も確認する。
型不一致は入力位置を示した`TrustError(exit_code=1)`とし、既存出力を更新しない。
HATE precheck nodeの宣言済みsoft_gaps・reasons・decisionも5入口の共通検証対象とする。
qeg_export_allowedのboolean、exit_codeのJSON整数、dq_hitsのobject配列も宣言時に検証する。
soft gapはmedium/non-blocking所見と信頼度・説明・補完提案に残し、QEG export禁止へ読み替えない。
既存bundleのprecheck不許可・許可情報の欠落・未知enumは、処理可能ならhigh/blocking所見へ記録する。
この場合は診断完了の終了コード0を保ち、trust/doctor statusはpartial、score_confidenceはlowとする。
P0b入口のexport不許可（終了コード2）とは、診断対象と段階が異なる。
reportのexport_statusとqeg_schema_compatibilityの型も共通検証する。宣言済みの診断専用指定や
export検証失敗はhigh/blocking所見・信頼度low、partial宣言はmedium/non-blocking所見へ接続する。
現在のbundleにスキーマ違反がある場合も信頼度はlowとし、reportの検証成功申告で打ち消さない。
型不正は終了コード1で既存出力を保持し、処理可能な宣言・schema診断は終了コード0で所見を出力する。
入力の内容全体を診断文へ埋め込まず、項目の位置と期待する型を通知する。

型として処理可能な必須項目欠落・不正enum等はdoctorのschema所見（high/blocking）へ記録する。
評価処理が完了した場合の終了コードは0のまま、trust/doctor statusはpartialとなる。
重複node ID、存在しないか曖昧な参照先、touches・requires_test・evidenced_byの種別矛盾も
qeg_fixture所見へ記録する。gate_verdictから当該runの`qeg_export:<run_id>`へのdecides参照は
P0bの契約上の外部参照として認める。

空graph、空文字・空白だけのsourceRefsを完全なlineageの根拠にしない。
高得点には実在するrisk→test→execution_evidenceの接続を必要とし、宣言済みのテスト要求に
未実行またはtest_placementが残る場合は最高点にしない。
詳細は[P1a契約](P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md#101-graphの整合性とlineage)を参照する。
`tests/test_p1a_graph_validation.py`とwheel smokeで構造診断、スキーマ所見、参照整合性、
一部未実行、外部参照と拡張edgeの正常系を検証する。
