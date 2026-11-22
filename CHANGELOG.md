# Changelog

## Unreleased

### Fixed

- P0bの各HATE record・manifest・precheck・auditとHATE-runのrun ID・試行番号・commitを照合し、別runの証跡を付け替えない。QEG bundleとexecutionにもcommit宣言を保持する。
- P1aの現在runのnodeとCIにある識別情報、bundle/reportのcommitを照合し、不一致を出力前に診断する。旧形式に任意項目を補わず、履歴nodeの過去runは保持する。
- P0bのJSON/NDJSON読込で数値の原表記と位置付き診断を保持する。P0b入力、P0a context、P1a入力の重複JSON keyによる識別情報の上書きを防ぐ。
- P0aのJUnit/pytest/Vitest/Jestでretry・matrix・shard・flakyを保持し、不正な番号の切り捨てと矛盾する宣言の上書きを防ぐ。JUnitのduplicate診断を同じ実行座標へ限定する。
- JSON adapterのrecord IDがtest titleだけで重複する問題を修正し、別ファイル・retry・frameworkと同じpayloadの複数観測を区別する。
- 正常なtest adapterがあっても、他の入力の解析失敗をHATE-DQ-002へ残す。
- retry回数だけからflakyを作らず、明示的なflakyと不足するretry履歴をP1aでinconclusive・doctor所見へ反映する。不安定性の申告を安定成功として採点しない。
- P0bで同じcanonical testの複数recordを別executionとして保持し、retry・matrix・shardと元recordの識別情報を失わない。入力順序・同じrecordの再掲で結果を変えない。
- P0bのtest-resultの不正な型・数値・alias・identity矛盾を出力前に診断し、既存の証跡を保持する。
- P0bが生成するexecution_evidence→artifactの添付参照をP1aで許容し、正常な証跡のgraphエラーを解消する。
- P0bが生成するtest→artifactのevidenced_byを正規の添付参照として認め、executionへの接続と区別してlineageを評価する。
- retry・shard番号の型・範囲・aliasの矛盾をP1aの出力前に検証し、丸めによる端数の見逃しを防ぐ。
- retry集約をcanonical test・matrix・run attemptでまとめ、異なる環境の上書き、重複edgeの二重計上、実行未接続testの脱落を防ぐ。
- 各retryのshard番号・件数・重複・欠落を確認し、並列shardの失敗をretryのflakyと誤認しない。欠けたretryやunknown/skippedを成功へ集約しない。
- retry集約の根拠をdoctor、determinismスコア、評価の信頼度へ共通化し、不完全な証跡やflakyを安定した実行として採点しない。
- AETE総合スコアの単純平均を仕様の加重平均へ修正し、JSONに8次元の重みと集計方法を記録する。
- compareが不正な次元値・非有限数・総合スコア不整合を処理前に診断する。単純平均の旧スコアはreplayによる再計算を案内し、既存比較結果を保持する。
- P1aのcommit・日時・artifact SHA256の形式不正をprovenanceのblocking所見として記録する。
- hashの申告だけで改ざん耐性を最高評価しない。全artifactのhash形式を確認し、完全な申告provenanceを3点、部分的な情報を1点とする。
- bundle・report双方の証跡不足、除外、parser失敗をscore_confidenceへ反映し、provenance不正をlowとする。
- P1aのnodes・edges・所見の型不一致を出力前に検出し、JSON項目の位置を含む入力診断へ変換する。
- 処理可能なQEGスキーマ違反をdoctorのblocking所見へ記録し、必須項目欠落や不正enumを正常扱いしない。
- 重複node ID、参照先のないedge、主要edgeのnode種別不一致を診断する。
- 空白のsourceRefsや無関係なnodeの存在だけでlineageを高評価せず、宣言されたテスト要求から実行証跡までの接続を確認する。
- run番号のboolean・端数・ゼロ以下を拒否し、P0aのCI数字文字列を正規化してrecord IDとの不一致を防ぐ。
- 未知profileをPrecheckError・TrustErrorとして通知し、入力検証前に出力ディレクトリーを作成しない。
- P1aのbundle・report間でrun IDと試行番号を照合し、別runの混在や両入力にないID・試行番号の生成を防ぐ。
- run IDやmetadataの不正な型を文字列化せず、対象項目を含む入力診断を返す。
- TrustErrorの初期化漏れを修正し、入力不足や未対応モードで診断用例外の生成自体が失敗しないようにする。
- P0a設定・P1a入力JSONの構文、UTF-8、object形式、読込失敗を型付き診断へ変換し、CLIで原因と終了コードを返す。
- CLIの未捕捉I/O失敗を終了コード1と診断へ変換し、出力先の衝突・容量不足を成功扱いしない。
- bundleの短縮IDが一致してもSHA256全体が異なる入力を再利用・追加保存せず、書込み前に衝突を報告する。
- artifactの短縮ID衝突で既存索引を上書きして過去runを壊さない。同一IDの既存参照を検証できない場合も、取り込み前に停止する。
- 集約済みreplay JSONの再集約で差分・所見・移行情報・参照元を失わず、未指定baselineの判定と内容hashを維持する。
- 比較・診断・移行の原因情報を集約へ保持し、doctorの対象ID・期待値・実際値・構造化診断を任意項目として出力する。
- 比較の個別regression/incomparableや悪化件数を正常な集計欄で上書きせず、記録済みhold/hard DQも再集約で弱めない。
- 移行レポートの明示的な非互換・holdフラグをcompatibleラベルで打ち消さない。
- doctorの診断hashから自身のhashと観測時刻を除き、公開JSONから同じ値を再計算できるようにする。
- 診断の所見・ID・パス表記を安定させ、索引行順、ストア配置、Windowsの例外内パスによる内容IDの変化を防ぐ。
- doctorに対象run IDを保持し、同じbundleを別runで保存したコピーの診断を集約で取り違えない。
- 単一bundle診断が使用する索引aliasの参照先・識別情報・実バイトhashを検証し、異常を正常扱いしない。
- 同時刻のbaseline候補をbundle ID順で選ばず、候補ID・日時を含む曖昧性エラーを返す。
- 小数秒をマイクロ秒へ切り捨てず、baseline選択と索引補完の実時刻比較を共通化する。
- 過去bundleの自動比較で後続のコピーをbaselineにせず、同じrunでは対象より前の履歴から選ぶ。
- baseline候補の読込失敗を黙って無視せず、replay・比較へ原因の診断を保持する。
- core・store・任意のbundleの各版を個別に確認し、一つの対応版で他の未対応版が隠れる不具合を修正する。
- 未対応版のbaselineをreplay成功の根拠にせず、比較元を保持したmigration holdと版別診断を返す。
- 通常読込・再取り込み・索引補完・完了保存・保持指定更新にも同じ対応版判定を適用し、未対応の保存コピーを変更しない。
- manifestのcompletedとimport_status.phaseの矛盾を公開スキーマで拒否し、処理中・失敗状態を完了扱いしない。
- 完了manifestの保存前にbundle本体・artifact一覧・hash・配置を検証し、呼出側のファイル一覧から抜けた欠損も検出する。
- manifestの公開・同期が成功するまで入力辞書を完了状態へ変えず、既存の取り込み診断・追加情報を保持する。
- manifest内のSHA256大文字表記も同じdigestとして照合し、完了処理・整合性検査・replayで誤判定しない。
- StoreManifestが取り込み状況・診断を落とす不具合を修正し、legal hold更新時もimport_statusを保持する。
  replayのmanifest指紋にも保存済みのimport_statusを含める。
- 保持の開始・再開時にheld_sinceを更新し、保持中の理由修正では既存の開始日時を維持する。
- 解除済み状態の再申告で解除日時と承認証跡を作り直さず、元の記録を保持する。
- store-version.jsonの構造と対応版を初期化・通常操作・復元より先に検証し、未知の版や不正metadataを黙認しない。
- 処理中にストアの版情報が変わった場合はcommitと復元を止め、未確定journal・退避データをそのまま保持する。
- 索引参照のhashを拡張子によらず実バイトで検証し、読込不能・ディレクトリー参照・不正なキャッシュをhard DQにする。
- LocalStoreの読込・索引補完・整合性検査で、参照先の配置・ID・metadataを共通検証する。
- 過去bundleの再取り込み時も現在のrunが指す保存コピーを確認し、破損を成功扱いしない。
- SHA256の16進表記の大文字・小文字だけの違いをhash不一致と誤判定しない。
- JSON内の重複項目、非有限数・浮動小数点の範囲超過、保存できないUnicode文字列を読込時に拒否する。
- bundleのnode構造・重複ID・artifact一覧とmanifestメタデータを保存前に検証し、不正入力で取り込み途中のデータを作らない。
- QEG形式を明示したbundleには配布スキーマを適用し、読込・整合性検査・replayでも同じ違反を検出する。
- 壊れたbundleの診断でpath引数が衝突してdoctorが停止する不具合を修正する。
- 索引構築APIの`run.json`前提を現行の`qeg-bundle.json`へ修正し、通常取り込みと生成処理を共通化する。
- 保存実体・manifestを検証してから欠けた索引参照を補完し、過去bundleの再処理で現在のaliasを巻き戻さない。
- 索引補完をOSロックと復元journalで保護し、途中終了や復元失敗でも完成済みbundleと保持情報を保持する。
- replay・compareの既定出力を再現可能にし、実行時刻と自己hashを内容hashから除く。実行時刻は属性または`include_observation=True`で取得できる。
- compareで保存実体を検証し、同じ項目の失敗→成功を削除・追加と誤認して悪化扱いする不具合を修正する。
- 実際のP0b出力である`test`・`coverage`・`finding`をartifact保存・検証の対象に含める。
- 異なるrun・bundle・baselineのレポートが混在した集約をhard DQとして検出する。
- 重複キーを含む索引を後勝ちで読み込まず、破損として検出する。保存前にもキー・ハッシュ・有限JSON値を検証する。
- replayがbundle本体やartifact一覧の破損を見落とす不具合を修正し、baselineの実在・内容と時刻順を検証する。
- replay集約時に整合性・legal hold・baseline・移行の失敗がpassや軽い判定へ変わる不具合を修正する。
- 保存manifestを公開スキーマで検証し、完了フラグだけのデータや不正なメタデータを正常扱いしない。
- doctorが未完了・未登録の保存データを見落とす不具合と、正常なストア構造を破損扱いする不具合を修正する。
  一つの索引が壊れていても他の索引・保存実体の診断を続ける。
- 再取り込み時に既存データを検証し、同一JSON内容のキー順が違う場合の整合性検査の誤判定を修正する。
- ストア取り込み失敗時に複数索引を復元し、途中終了後の復元再開と操作の排他制御を追加する。
- 同じbundleを複数runに保存した際の履歴欠落・別runのmanifest参照を修正する。
- replayのbundle ID・artifactパス・schema参照を修正し、過去runの同一内容も比較baselineとして扱う。
- ストア保存で短い書き込みを完了させ、Windowsの置換失敗でも旧ファイルを保持する。
- 索引の保存ハッシュ・再読込キャッシュと、ストア再オープン直後の読込を修正する。
- 整合性検査が索引を書き直す不具合、別run追加後の誤判定、canonical bundleの検査漏れを修正する。
  データ型と検証処理を分離し、[保存・整合性検査契約](docs/process/LOCAL_STORE_IO_CONTRACT.md)に範囲を記録する。
- handoffで未存在Pathが欠落する不具合を修正し、必須入力・未作成の履歴・新規ストア保存先を区別する。
- bridge結果の取り込みで、途中のI/Oエラーや重複名により一部だけ更新される不具合を修正する。
- handoffのパス・URI・出力種別を正しく扱い、入力内の依頼JSONを再生成するとIDが変わる不具合を修正する。
- ファイルサイズの警告とgolden fixture限定の例外を適用し、キャッシュの不要な走査を除く。
- CLI責務台帳と実行時ルーティングの担当先・契約名を一元化し、全33コマンドの不一致を検出する。
- handoffでprofile、retry、forceなどの実行オプションが欠落する不具合を修正し、依頼IDにも反映する。
- 旧依頼の読み取りは維持する。修正後の依頼IDと受信側スキーマの扱いは
  [Bridge依頼契約](docs/process/BRIDGE_REQUEST_CONTRACT.md)を参照する。

## 0.2.0 - 2026-07-11

### Added

- Packaged HATE/v1 schemas and isolated wheel smoke validation.
- Draft 2020-12 JSON Schema validation.
- Canonical Post-PoC gap registry and generated status tables.
- Explicit local plugin execution consent and bounded process execution.
- Parallel CI lanes and OSS governance files.

### Changed

- Local subprocess plugins are denied by default and require
  --allow-local-exec plus signed/trusted external evidence.
- Release and regulated profiles always deny local subprocess plugins.
- Previously ignored JSON Schema constraints are now enforced.

### Known limitations

- Plugin signatures are external evidence, not cryptographically verified.
- Local subprocess mode does not provide filesystem or network isolation.
- product_ready remains false and final release authority remains external.

## 0.3.0 - 2026-07-11

### Added

- Machine-readable responsibility registry for every leaf CLI and HATE/v1 record type.
- HATE-bridge/v1 request/result schemas, explicit handoff, and fail-closed materialization.
- Scope and architecture gates for the P0a/P0b/P1a responsibility freeze.
- product-ops-evidence and owner-side consumer contract fixtures.

### Changed

- Post-P1a public handlers dispatch only through the bridge router.
- v0.2 behavior is isolated behind the frozen compat-v0.2 provider.
- Post-P1a schema entries carry canonical owner and removal-window metadata.

### Compatibility

- P0a/P0b/P1a interfaces remain unchanged.
- Post-P1a CLI names, options, output files, required fields, and normal exit codes remain available through v1.
- product_ready remains false and release authority remains external.

### Distribution

- v0.3.0 wheel and source distribution are published as GitHub Release assets.
- PyPI is intentionally not used as a HATE distribution channel.
