# 継続調査・修正記録

対象はHATEの現在の作業ツリー。機能追加、既存契約の不具合修正、保守性改善を区別して記録する。
これは完了済みの全体監査ではなく、継続調査の現在位置である。

## 修正した項目

| ID | 区分 | 問題と対応 | 検証 |
|---|---|---|---|
| FIX-001 | 不具合 | CLI責務台帳とルーターの担当先・契約名を一元化。全33コマンドを照合する。 | `tests/test_responsibility_architecture.py` |
| FIX-002 | 不具合 | handoffの実行オプション欠落を修正し、実効値を依頼IDにも反映する。 | `tests/test_bridge_options.py` |
| FIX-003 | 不具合 | 結果取り込みの重複名・相対パス・不正UTF-8を検証し、途中の書き込み失敗時に元のファイルを復元する。 | `tests/test_bridge_materialization.py` |
| FIX-004 | 不具合 | 出力の種類を拡張子から推測せず、空白を含む入力パスと重複参照URIを正しく扱う。 | `tests/test_bridge_paths.py` |
| FIX-005 | 不具合 | 自身の依頼を入力の指紋へ取り込む循環を除き、除外規則を依頼に明示する。依頼の一時ファイル名も一意にする。 | `tests/test_bridge_paths.py` |
| FIX-006 | 不具合 | サイズ検査の未使用警告閾値と、golden fixture限定の例外を有効にする。 | `tests/test_check_file_size.py` |
| FIX-007 | 不具合 | 未存在Pathの欠落を修正。全33コマンドの入力・未存在を許す履歴・更新先ストアを分類し、指定を保存・検証する。 | `tests/test_bridge_path_contract.py` |
| FIX-008 | 不具合 | ストアの短い書き込み・Windowsの置換失敗・中断時の一時ファイルを処理し、失敗段階を区別する。 | `tests/test_store_atomic_failures.py` |
| FIX-009 | 不具合 | 索引の保存ハッシュと実バイトを一致させ、再読込時の古いキー・部分読込状態を残さない。 | `tests/test_store_index_io.py` |
| FIX-010 | 不具合 | ストア再オープン直後の読込とJSON読込エラーを修正。整合性検査を書込なしにし、過去runの誤判定とcanonical bundleの検査漏れを修正する。 | `tests/test_store_integrity.py` |
| FIX-011 | 不具合 | 取り込み失敗時の複数索引復元、途中終了後の復元再開、OSロックによる操作の排他を実装する。 | `tests/test_store_transactions.py`、`tests/test_store_recovery_process.py` |
| FIX-012 | 不具合 | 同一bundleのrun別履歴・manifest参照・baseline・診断・replayを修正し、過去runとの関連を保持する。 | `tests/test_store_run_history.py` |
| FIX-013 | 不具合 | 保存manifestと公開スキーマの不一致を修正。必須情報・型・日時・legal holdの申告値を保存前と読込時に検証し、未完了bundleの通常読込を拒否する。 | `tests/test_store_manifest_validation.py` |
| FIX-014 | 不具合 | 再取り込みで既存データと索引を検査し、破損したコピーを成功扱いしない。bundle本体からartifact一覧の欠落を検出し、JSONキー順だけの差で過去runを不整合にしない。 | `tests/test_store_manifest_validation.py`、`tests/test_store_integrity.py` |
| FIX-015 | 不具合 | doctorが実際のruns構造と全7索引を照合する。未完了・未登録・読込不能なコピーを検出し、一部索引の破損でも診断を続ける。 | `tests/test_store_doctor_inventory.py` |
| FIX-016 | 不具合 | 索引の重複キーを行番号付きで拒否し、後勝ちによる参照の消失を防ぐ。追加・保存・読込で空白キー、不正ハッシュ、非有限JSON値、辞書キーとの矛盾を検証する。 | `tests/test_store_index_io.py` |
| FIX-017 | 不具合 | replayの検証を保存実体の共通検査へ接続し、bundle本体・artifact一覧の欠損を検出する。未対応schemaを再生済みartifactとして数えない。 | `tests/test_store_replay_validation.py` |
| FIX-018 | 不具合 | baselineを実際のmanifestと保存内容から検証して解決結果を保持する。タイムゾーンが異なるmanifestも実時刻で並べる。 | `tests/test_store_replay_validation.py` |
| FIX-019 | 不具合 | replay集約時に各失敗フラグ・個別hard DQ・移行の非互換やhard DQを保持し、壊れた補助レポートを黙って捨てない。 | `tests/test_store_replay_readiness.py` |
| FIX-020 | 不具合 | replay・compareの時刻混入と自己hashの再帰を修正。既定のJSONを決定的にし、独立したhash再計算・別プロセス・異なるhash seed・配置変更後の再生を検証する。 | `tests/test_store_report_determinism.py` |
| FIX-021 | 不具合 | compareの両コピーを実ファイルで検証し、破損や未対応schemaをno_change扱いしない。明示runのコピーとbaseline情報を保持する。 | `tests/test_store_compare_semantics.py` |
| FIX-022 | 不具合 | 内容由来artifact IDと項目IDを区別し、既知のテスト結果・coverage・契約・mutation・severityを比較する。失敗→成功の誤ったregression判定を修正し、未知の変化は比較不能にする。 | `tests/test_store_compare_semantics.py`、`tests/test_store_replay_compare.py` |
| FIX-023 | 不具合 | P0b実出力のtest・coverage・findingがartifactとして保存されない不一致を修正する。元のnode内容と種別は保存時に改変しない。 | `tests/test_store_export_kinds.py` |
| FIX-024 | 不具合 | replay・比較・doctor・baseline証拠の識別子が矛盾する集約を拒否し、別の対象で検証した結果を混用しない。 | `tests/test_store_replay_readiness.py` |
| FIX-025 | 不具合 | 索引構築APIのrun.json前提と欠損ファイルの黙認を修正する。現行保存構造と検証済みmanifestを使い、通常取り込みと索引生成を共通化する。 | `tests/test_store_index_builder.py` |
| FIX-026 | 不具合 | 索引補完の途中失敗・別プロセス競合を処理する。索引専用journalで復元し、完成済みbundleを隔離・変更しない。 | `tests/test_store_index_builder.py`、`tests/test_store_index_builder_process.py` |
| FIX-027 | 不具合 | 過去bundleの索引補完で現在のaliasを上書きしない。run参照が欠ける場合は実時刻で最新履歴を選び、時刻同順位や破損した既存aliasは拒否する。 | `tests/test_store_index_builder.py` |
| FIX-028 | 不具合 | JSONオブジェクト内の重複項目を後勝ちで解釈しない。数値のoverflow・非ゼロ値のunderflow・UTF-8へ戻せない文字列も検出し、bundle・manifest・索引・journalの読込を揃える。 | `tests/test_store_bundle_input.py`、`tests/test_store_strict_json.py` |
| FIX-029 | 不具合 | node構造、node IDとartifact IDの重複、メタデータの保存可能性をtransaction前に検証する。保存計画のhashとartifact一覧をそのまま書込へ渡す。 | `tests/test_store_bundle_input.py` |
| FIX-030 | 不具合 | metadata.qegVersionまたはcompletenessを持つbundleへ公開QEGスキーマを適用する。読込・再取り込み・整合性検査にも適用し、旧形式のrelationshipや補助nodeは内容を改変せず保持する。 | `tests/test_store_bundle_input.py`、既存storeテスト、wheel smoke |
| FIX-031 | 不具合 | bundle読込不能・schema違反の診断にpathがあるとdoctorが引数衝突で停止する不具合を修正し、実ファイルの場所を保持する。 | `tests/test_store_strict_json.py`、`tests/test_store_bundle_input.py` |
| FIX-032 | 不具合 | 索引のhash検証が.json拡張子だけに限られる不具合を修正する。通常ファイル・実バイト・キャッシュ内キー・保存可能な文字列を検証し、読込エラーと不正文字の診断を返せるようにする。 | `tests/test_store_reference_validation.py` |
| FIX-033 | 不具合 | 通常読込・manifest参照・索引補完・整合性検査で、保存先とID・metadataの照合を共通化する。artifact aliasの矛盾もdoctorで検出する。 | `tests/test_store_reference_validation.py`、既存storeテスト |
| FIX-034 | 不具合 | 過去コピーだけを検査して再取り込みを成功扱いしない。現在のrun参照先の実体も検証し、別bundleへの履歴更新とその後の破損を区別する。 | `tests/test_store_reference_validation.py` |
| FIX-035 | 不具合 | 許可済みSHA256の大文字hexを別のdigestと誤認しない。読込・再取り込み・doctorの比較を統一し、元の索引ファイルは書き換えない。 | `tests/test_store_reference_validation.py` |
| FIX-036 | 不具合 | store-version.jsonの構造・対応版・日時・producerを初期化前と各操作で検証する。未知の版を開いてディレクトリーを追加せず、新規producerの不正値も書込前に拒否する。 | `tests/test_store_version.py` |
| FIX-037 | 不具合 | 版検証より先にpending journalを復元する経路を修正する。transaction中に版情報が変わった場合も、commit・失敗追記・復元・索引再読込を止め、対応版へ戻した後に復元できる状態を保持する。 | `tests/test_store_version.py`、既存transaction・別プロセス復元テスト |
| FIX-038 | 不具合 | StoreManifestの往復変換でwriterが保存したimport_statusを消さない。保持指定の更新でも取り込み状況・診断を残し、replayのmanifest指紋へ含める。項目のない旧manifestには追加しない。 | `tests/test_store_hold_updates.py`、wheel smoke |
| FIX-039 | 不具合 | none・pending・releasedからactiveへの遷移で保持開始日時を記録し直す。activeのまま理由を更新する場合は既存の開始日時を保持する。 | `tests/test_store_hold_updates.py` |
| FIX-040 | 不具合 | releasedの再申告で元の解除日時・承認証跡を上書きしない。旧記録に存在しない解除証跡も推測して補わない。 | `tests/test_store_hold_updates.py` |
| FIX-041 | 不具合 | 完了フラグと取り込みphaseの矛盾を公開スキーマで拒否する。phaseのない旧manifestは維持し、妥当な未完了状態は診断用に読める。 | `tests/test_store_completion.py`、既存manifest・doctor・baselineテスト |
| FIX-042 | 不具合 | 完了writerが呼出側のファイル一覧だけを信頼しない。bundleのcanonical ID・構造・artifact一覧・hashと保存先を共通検証し、欠損を完了扱いする前に取り込みを復元する。 | `tests/test_store_completion.py`、既存transactionテスト |
| FIX-043 | 不具合 | manifest保存失敗・中断で入力辞書を完了済みに変えない。置換後の同期不確実性も区別し、成功時は既存の取り込み診断・追加情報を残す。 | `tests/test_store_completion.py` |
| FIX-044 | 不具合 | manifestのcontent_hashesに許可済みの大文字hexがある場合も同じdigestとして検証する。bundleから導出した一覧との比較・完了・replayを一致させ、保存値は正規化しない。 | `tests/test_store_completion.py` |
| FIX-045 | 不具合 | bundle版の優先でcore・storeの未対応版が隠れる不具合を修正する。replay・両側の比較・doctorで各版を個別に照合し、component・実際の値・対応値を診断する。 | `tests/test_store_compatibility.py`、wheel smoke |
| FIX-046 | 不具合 | baselineの版確認漏れを修正する。参照先と実体が正常でも未対応版ならreplay全体をmigration holdにし、最新の比較元を勝手に古い版へ差し替えない。実体破損はhard DQを維持する。 | `tests/test_store_compatibility.py` |
| FIX-047 | 不具合 | 通常読込・再取り込み・索引補完・完了保存・保持指定更新で未対応版を黙認しない。診断用manifest読込と物理整合性検査は維持し、互換性を推測した書換えを行わない。 | `tests/test_store_compatibility.py`、既存storeテスト |
| FIX-048 | 不具合 | 同時刻のbaseline候補をbundle IDで順位付けして日時選択と報告する不具合を修正する。候補一覧付きの曖昧性エラーとし、明示bundle参照で解決できる。 | `tests/test_store_baseline_selection.py` |
| FIX-049 | 不具合 | baseline選択と索引補完の小数秒切捨てを修正する。UTCの整数秒と精度を保った小数部で比較し、桁数やUTCオフセットだけが異なる同一時刻も認識する。 | `tests/test_store_baseline_selection.py`、既存日時・索引テスト |
| FIX-050 | 不具合 | 過去bundleの自動比較で将来の履歴をbaselineにしない。既定選択と同run参照は対象より前に限定し、明示bundle指定・別run指定は保持する。 | `tests/test_store_baseline_selection.py` |
| FIX-051 | 不具合 | baseline候補の再読込失敗を無視して古い候補へ切り替えない。原因と候補情報をreplay・比較へ保持し、診断パスをストア相対へ揃える。 | `tests/test_store_baseline_selection.py` |
| FIX-052 | 不具合 | doctorのhashが自身のhashと観測時刻を含み、再計算・再実行で変わる問題を修正する。時刻を任意出力に分け、公開JSONから検証できる内容hashへ揃える。 | `tests/test_store_doctor_reports.py`、wheel smoke |
| FIX-053 | 不具合 | doctorの所見順・ID・パスが索引行順やストア配置に依存する問題を修正する。Windows例外内のエスケープされたパスとストアルート自身も相対表記にする。 | `tests/test_store_doctor_reports.py`、既存証跡再現性テスト |
| FIX-054 | 不具合 | doctorのrun ID欠落により別runの正常診断を集約へ混在させる問題を修正する。単一・run診断に対象を保持し、全体診断と対象不明の旧入力は区別する。 | `tests/test_store_doctor_reports.py`、wheel smoke |
| FIX-055 | 不具合 | 単一bundle診断が使用した索引aliasの異常を見逃す問題を修正する。参照先名・識別情報・hashを照合し、保存コピー側の異常も併せて報告する。 | `tests/test_store_doctor_reports.py` |
| FIX-056 | 不具合 | 集約済みreplay JSONの再入力で差分・所見・移行情報が消え、baseline未指定の判定や参照元が変わる問題を修正する。保存済みの内容とhashを保持する。 | `tests/test_store_replay_aggregation.py`、wheel smoke |
| FIX-057 | 不具合 | 集約の判定に使った補助診断を失う問題を修正する。doctorの対象ID・期待値・実際値・構造化診断を任意項目で保持し、比較・移行の原因にも由来を付ける。 | `tests/test_store_replay_aggregation.py`、公開スキーマ、wheel smoke |
| FIX-058 | 不具合 | 比較の個別悪化・比較不能・悪化件数を古い正常集計で上書きする問題を修正する。保存済みhold/hard DQも再集約だけでは弱めない。 | `tests/test_store_replay_aggregation.py` |
| FIX-059 | 不具合 | 移行の明示的なschema_compatible=false・migration_hold=trueをcompatibleラベルで見逃す問題を修正する。外部所有の移行実装は変更せず、集約時にフラグを引き継ぐ。 | `tests/test_store_replay_aggregation.py` |
| FIX-060 | 不具合 | 短縮bundle IDだけで別内容を同一視する問題を修正する。既存索引の参照先と入力のcanonical SHA256全体を比較し、同runの再利用・別runの追加保存前に衝突を拒否する。 | `tests/test_store_import_identity.py` |
| FIX-061 | 不具合 | 別bundle間のartifact短縮ID衝突で索引を上書きし、過去runの整合性を壊す問題を修正する。同一IDの既存参照と完全hashを検証し、衝突・検証不能ならtransaction開始前に停止する。 | `tests/test_store_import_identity.py`、既存取り込み・履歴テスト |
| FIX-062 | 不具合 | TrustErrorのdataclass指定漏れにより、入力不足・非object JSON・未対応モードで例外生成自体がTypeErrorになる問題を修正する。既存のmessage・exit_code契約を復元する。 | `tests/test_cli_input_errors.py`、wheel smoke |
| FIX-063 | 不具合 | P0aのcontext・制御設定とP1a入力の不正JSON・UTF-8・読込失敗が型付き例外を迂回する問題を修正する。設定JSON読込を共有し、元の原因と対象を保持する。 | `tests/test_cli_input_errors.py`、既存P0a/P1aテスト、wheel smoke |
| FIX-064 | 不具合 | CLIの出力先衝突・書込み失敗が未処理例外になる問題を修正する。未捕捉OSError・UnicodeErrorを診断と終了コード1へ変換し、業務判定・内部ロジック例外とは区別する。 | `tests/test_cli_input_errors.py`、既存CLIテスト |
| FIX-065 | 不具合 | boolean・端数のrun番号をintで別の試行へ変える問題を修正する。JSONの元の十進表記で整数性を検証し、P0aのCI数字文字列を一度だけ正規化してrecord IDと共通項目を一致させる。 | `tests/test_run_input_validation.py`、wheel smoke |
| FIX-066 | 不具合 | 未知profileが業務例外を迂回する問題を修正する。専用のValueError派生型をP0a/P1aの入力診断へ変換し、検証前の出力ディレクトリー作成を止める。 | `tests/test_run_input_validation.py`、既存profile契約テスト |
| FIX-067 | 不具合 | 別run・別試行のreportでtrust評価が成功する問題を修正する。5コマンドで入力を共通照合し、両入力で欠けた識別値を空ID・試行1として生成しない。 | `tests/test_run_input_validation.py`、wheel smoke |
| FIX-068 | 不具合 | run IDのnull・object・boolean等を文字列化し、metadataの不正な型で例外終了する問題を修正する。入力元と項目を診断に含め、既存出力を変更しない。 | `tests/test_run_input_validation.py`、既存P0a/P1aテスト |
| FIX-069 | 不具合 | nodes・edges・sourceRefs・所見等の型不一致が例外終了や誤処理になる問題を修正する。5つのP1aコマンドで構造を検証し、既存出力を保持した入力診断へ揃える。 | `tests/test_p1a_graph_validation.py`、wheel smoke |
| FIX-070 | 不具合 | doctorが公開QEGスキーマの必須項目欠落・不正enum等を報告しない問題を修正する。処理可能な違反をschema分類のhigh/blocking所見へ保持する。 | `tests/test_p1a_graph_validation.py`、公開doctorスキーマ |
| FIX-071 | 不具合 | 重複node ID・未解決edge・node種別と関係種別の矛盾を正常扱いする問題を修正する。正規のqeg_export参照を維持し、曖昧な関連付けを所見とスコアへ反映する。 | `tests/test_p1a_graph_validation.py`、wheel smoke |
| FIX-072 | 不具合 | 空文字・空白のsourceRefsや無関係なnodeの存在でlineageが最高点になる問題を修正する。宣言されたrisk→test→executionの全経路を確認し、一部未実行・test_placementを最高点にしない。変更との関連も実在するtouchesで評価する。 | `tests/test_p1a_graph_validation.py`、既存P1a/replayテスト |
| FIX-073 | 不具合 | commit・日時・artifact SHA256の形式不正や欠落を正常扱いする問題を修正する。公開の形式条件を確認し、位置付きprovenance high/blocking所見を返す。 | `tests/test_p1a_provenance.py`、wheel smoke |
| FIX-074 | 不具合 | hash欄の存在だけで改ざん耐性を最高評価する問題を修正する。run・commit・日時と全artifactのhash形式が揃う申告を3点とし、実体検証・改ざん耐性は未検証と明示する。 | `tests/test_p1a_provenance.py`、wheel smoke |
| FIX-075 | 不具合 | report側のunsupportedClaimsや両入力の除外・parser失敗をscore_confidenceが無視する問題を修正する。証跡不足をmedium、不正provenanceをlowへ反映する。 | `tests/test_p1a_provenance.py`、CLI/replay同値検証 |
| FIX-076 | 不具合 | AETEの8次元を単純平均し、仕様の重みを無視する問題を修正する。0〜1の加重平均をscore・signal・summary・replayへ反映し、重みと集計方法もJSONに保存する。 | `tests/test_p1a_weights.py`、全profile・実入力の比較、wheel smoke |
| FIX-077 | 不具合 | compareが不正な次元値・総合スコア・重みや、保存スコアの不整合を受け入れる問題を修正する。数値の原表記を確認して出力前に停止し、旧単純平均スコアにはreplayを案内する。 | `tests/test_p1a_weights.py`、既存出力保持・CLI診断、wheel smoke |
| FIX-078 | 不具合 | retry/shard番号のboolean・端数・負数・不正aliasが切り捨てや例外になる問題を修正する。5コマンドで原表記と型を検証し、aliasを同じ整数へ正規化する。 | `tests/test_p1a_retry_aggregation.py`、既存出力保持、wheel smoke |
| FIX-079 | 不具合 | 異なるmatrix環境を上書きし、同じcanonical testを分断する問題を修正する。完全な集約キーでまとめ、重複edgeを除き、実行未接続testをinconclusiveへ残す。 | `tests/test_p1a_retry_aggregation.py`、入力順序反転・node alias検証 |
| FIX-080 | 不具合 | shardの件数だけで成功を判定し、並列結果をflakyと誤認する問題を修正する。retryごとに番号・重複・欠落を確認してから履歴を集約し、retry欠測や不明statusを成功にしない。 | `tests/test_p1a_retry_aggregation.py`、大きな期待件数、wheel smoke |
| FIX-081 | 不具合 | 不完全なretry証跡やflakyがdeterminismの標準点・正常statusになる問題を修正する。同じ集約結果をdoctor・score・confidenceへ渡し、欠損と不安定性を可視化する。 | `tests/test_p1a_retry_aggregation.py`、API/replay/doctor同値検証 |
| FIX-082 | 不具合 | P0bの正規のtest→artifact参照をgraph検証が不正扱いする問題を修正する。添付を許容し、lineageの実行接続にはexecution_evidenceだけを数える。 | `tests/test_p1a_graph_validation.py`、添付のみの場合の未実行判定、wheel smoke |
| FIX-083 | 不具合 | P0bが同じcanonical testの複数recordを重複node IDへ変換し、retry・matrix・shardを失う問題を修正する。testを共有し、各実行を正規化record hashで区別して元recordへ追跡できるようにする。 | `tests/test_p0b_execution_history.py`、P0a→P0b→P1a、順序反転・再掲・record ID重複、wheel smoke |
| FIX-084 | 不具合 | P0bのtest-resultで不正な実行座標やaliasが後段へ流れる問題を修正する。JSON数値の原表記・record形式・identity矛盾を出力前に検証し、位置付きExportErrorへ変換する。 | `tests/test_p0b_execution_history.py`、API/CLI・既存出力保持、wheel smoke |
| FIX-085 | 不具合 | P0bが実際に生成するexecution_evidence→artifact参照をP1aが不正扱いする問題を修正する。許容するnode種別の組を限定し、execution同士の誤接続は引き続き診断する。 | `tests/test_p0b_execution_history.py`の実export→trust、`tests/test_p1a_graph_validation.py` |
| FIX-086 | 不具合 | P0aのretry番号の切り捨て・実行属性の取りこぼしを修正する。JUnit/pytest/Vitest/Jestで番号・matrix・shard・flakyの宣言を検証して保持し、JUnitのduplicate診断を同じ実行座標に限定する。 | `tests/test_p0a_execution_metadata.py`、全4adapter→P0b→P1a、数値原表記・alias矛盾 |
| FIX-087 | 不具合 | JSON adapterで同じtitleから同じrecord IDができる問題を修正する。framework・payload hash・出現番号で別ファイル・retry・同一観測を区別し、確定したIDからenvelope hashを計算する。 | `tests/test_p0a_execution_metadata.py`、順序反転・framework混在、wheel smoke |
| FIX-088 | 不具合 | 正常なtest adapterがあると他adapterの解析失敗が消える問題を修正する。存在する入力の解析失敗を常にHATE-DQ-002へ残し、QEG exportを許可しない。 | `tests/test_p0a_execution_metadata.py`、正常入力との混在・CLI終了コード、wheel smoke |
| FIX-089 | 不具合 | retry回数からflakyを推測し、逆に明示的なflakyや未提示のretry履歴を安定成功扱いする問題を修正する。申告回数・不安定性・実履歴を区別して保持し、doctor・confidence・determinismへ反映する。 | `tests/test_p0a_execution_metadata.py`、`tests/test_p1a_retry_aggregation.py`、replay/doctor同値、wheel smoke |
| FIX-090 | 不具合 | P0bが別run・attempt・commitのrecordを現在runへ付け替える問題を修正する。現在runのHATE record headerとmanifest・precheck・audit等を照合し、bundleとexecutionにcommit宣言を保持する。 | `tests/test_run_scope.py`、9入力種別・欠落・型・数値原表記・既存出力保持、wheel smoke |
| FIX-091 | 不具合 | P1aがnode内の別run情報やbundle/report間のcommit不一致を無視する問題を修正する。現在runのnodeとCI宣言を5入口で照合し、無効commitは位置付きprovenance所見へ残す。 | `tests/test_run_scope.py`、旧形式・過去defect・API/CLI、wheel smoke |
| FIX-092 | 不具合 | P0bのJSON/NDJSONで数値の原表記と入力診断が失われ、重複keyがrun情報を上書きする問題を修正する。P0b読込とP0a context/P1a入力で重複keyを拒否し、位置付きの型別エラーへ変換する。 | `tests/test_run_scope.py`、JSON/NDJSON・文字コード・同値/異値の重複key |
| FIX-093 | 不具合 | P0bがineligible・許可フラグfalse・終了コード2・DQ検出を無視して正式bundleを出力する問題を修正する。precheckの必須項目・型・enum・数値原表記を検証し、許可条件がすべて揃う場合だけ出力する。 | `tests/test_p0b_precheck.py`、全32許可組合せ・API/CLI・既存出力保持、wheel smoke |
| FIX-094 | 不具合 | precheckのsoft gap・理由がQEG exportで脱落し、P1aが所見なし・信頼度high・説明/補完0件とする問題を修正する。元objectをbundleへ保持し、doctor・confidence・explain・recommendに同じ根拠を接続する。 | `tests/test_precheck_soft_gaps.py`、strict profile・旧形式・5入口・replay同値・wheel smoke |
| FIX-095 | 不具合 | P1aが既存bundleのineligible・許可フラグfalse・終了コード2・DQ検出・未知decisionを所見なし/highとする問題を修正する。型不正は出力前に止め、許可不備をhigh/blocking所見・low confidence・説明・補完提案へ接続する。 | `tests/test_p1a_precheck_permission.py`、全32組合せ・5入口・元証跡保持・複数node・wheel smoke |
| FIX-096 | 不具合 | P1aがdebugOnly・export時のschema検証失敗/エラー・partial/未知statusを所見なし/highとする問題を修正する。宣言を型検証し、用途制限と証跡不足を区別してdoctor・confidence・説明・補完提案へ接続する。 | `tests/test_p1a_export_metadata.py`、36組合せ・5入口・元エラー保持・旧report・wheel smoke |
| FIX-097 | 不具合 | 現在のbundleにschemaのblocking所見があってもscore_confidence=highになる問題を修正する。検証結果をdoctor・信頼度・説明・補完提案で共通利用し、reportのvalid=trueでも現在の違反を打ち消さない。 | `tests/test_p1a_export_metadata.py`、必須metadata欠落・未知version・空profile・lowの優先順位・wheel smoke |
| FIX-098 | 不具合 | P0bが生成bundleのschema valid=falseを無視して成功を返し、以前の正式成果物を上書きする問題を修正する。保存前にExportError(1)で停止し、項目付き診断とAPIの全エラーを残す。 | `tests/test_p0b_output_validation.py`、API/CLI・全既存成果物保持・新規出力先未作成・有効partial・wheel smoke |
| FIX-099 | 不具合 | P0bの再実行で古いrisk debt・manual bridgeが残る問題と、補助成果物の構築・JSON化・文字コードエラーで出力が混在する問題を修正する。全生成を保存前に完了し、現在のmissing executionが0なら所有する旧補助成果物だけを除去する。 | `tests/test_p0b_output_lifecycle.py`、API/CLI・再実行・内部例外・全既存成果物保持・新規出力先未作成・wheel smoke |
| FIX-100 | 不具合 | risk debt履歴の不正なitemsを無視し、age_daysをbooleanや端数から整数へ変えたり未捕捉例外を返す問題を修正する。読込時に構造と正確な非負整数を検証し、位置付きExportError(1)へ接続する。 | `tests/test_p0b_output_lifecycle.py`、現在/過去debt・数値原表記・大きな整数・入力保持・wheel smoke |
| FIX-101 | 不具合 | P0aがnull・boolean・object等のテスト識別値を文字列化し、JUnitのname欠落に仮名を付けて正常証跡を作る問題を修正する。nodeid・fullName・suite/name・title/ancestorsを型検証し、位置付きHATE-DQ-002へ接続する。 | `tests/test_p0a_test_values.py`、4 adapter・有効adapter併存・API/CLI・export拒否・入力保持・wheel smoke |
| FIX-102 | 不具合 | 不正な実行時間が0や整数へ化ける問題、pytestのstage時間を無視する問題、Vitest/Jestの正当なnull durationを解析失敗にする問題を修正する。十進表記の検証・合算・丸めを共通化し、未報告の診断をQEGまで保持する。 | `tests/test_p0a_test_values.py`、負数・型・丸め境界・大きな整数・標準stage形式・nullable duration・wheel smoke |
| FIX-103 | 不具合 | pytestの期待失敗を通常成功へ変換し、Jest等の未実行宣言・元statusを失う問題を修正する。source_statusと期待失敗等の印を保持し、wouldRun=trueをinconclusiveとして診断する。不正な宣言型はhard DQへ接続する。 | `tests/test_execution_outcomes.py`、3 JSON adapter・元状態・null時間診断の併存・API/CLI・wheel smoke |
| FIX-104 | 不具合 | P0bがskip等のrecordの存在だけで実行要件を満たし、P1aが未実行を高信頼の成功・実行根拠へ数える問題を修正する。実行結果の判定を共通化し、明示canonical refを照合し、不足をrisk debt・manual bridge・説明・補完提案へ残す。 | `tests/test_execution_outcomes.py`、直接record/既存bundle・実行済み観測との併存・信頼度/lineage/oracle・全5入口の型検証・既存出力保持・wheel smoke |
| IMP-001 | 保守性・性能 | 入力の指紋と結果の検証をストリームで処理し、サイズ検査では依存キャッシュを探索前に除外する。 | 関連テストとCIのサイズ検査 |
| IMP-002 | 保守性 | ローカルストアのデータ型・整合性検査を分離し、公開import経路を維持する。対象をRuff・型検査・wheel smokeへ追加する。 | 既存保存・replayテスト、CI |

FIX-003は通常のI/Oエラー時の復元を対象とする。複数ファイルの同時切替、並行writer、OS障害時の
自動復旧までを保証しない。復元失敗時の扱いは[Bridge依頼契約](BRIDGE_REQUEST_CONTRACT.md)を参照する。

## 次の調査・修正対象

1. **旧ストアの修復手順**: 診断後の復元には信頼できる入力・索引スナップショットが必要。
   journalのない旧データを自動修復するには、復元元の選択と履歴・保持情報を保存する契約が必要となる。
2. **ストアの復元・移行との接続**: backup・restore・migrationの既存report生成は台帳上workflow-cookbook所有の
   compat機能であり、LocalStoreの実ファイル復元とは異なる。今回coreの版検証漏れを修正した。
   外部実行結果との接続や保持情報の引継ぎは、担当先の契約を踏まえて引き続き確認する。
3. **警告領域のファイル分割**: `REFACTORING_PLAN.md`の履歴と現在の行数を照合し、
   coreの変更頻度・責務境界を踏まえて対象を選ぶ。凍結済み互換機能の新規ロジック追加は行わない。
4. **残課題の担当先整理**: Post-PoCのlocal acceptedとproduct openを維持し、
   HATE内部の修正と外部ownerの運用課題を明示する。
5. **CLIの入力値検証**: contextの残る属性、node.data内の型、compare・P0b等の読込経路を
   個別に確認する。入力値の問題を一律のValueError捕捉で隠さない。
6. **P1aの評価根拠**: 残るdimensionと入力間の意味上の整合性を確認し、所見とスコアの根拠を揃える。
   現在runのnodeに宣言されたrun/attempt/commitの照合はFIX-091で追加した。
7. **P0a/P0bの残る入力契約**: 明示的な実行属性とrecord ID、flaky申告の接続はFIX-083〜089で修正した。
   P0aのfile/classname推定やdialect固有の追加属性・JSON重複key、JUnitとJSON間の同一testの扱い、
   P0bのpayloadの残る形式と補助成果物間の意味上の整合性、P1aの残る入力間の意味上の整合性を引き続き確認する。
   record headerのrun照合はFIX-090、P0bのprecheck許可条件はFIX-093、soft gapの引継ぎはFIX-094、
   P1aに届いた既存bundleのprecheck許可診断はFIX-095で追加した。
   export metadataと現在のschema診断の信頼度への接続はFIX-096〜097で追加した。
   P0bの生成bundleがschema不適合でも保存する経路はFIX-098で修正した。
   補助成果物の保存前生成・再実行時の残存とrisk debt履歴の構造・経過日数はFIX-099〜100で修正した。
   P0aのテスト名・時間の型検証と標準時間形式の取込みはFIX-101〜102で修正した。
   元status・wouldRunの保持と実行要件・信頼度評価への接続はFIX-103〜104で修正した。
   その他のnative marker、strictな期待失敗方針等の追加文脈は、reportの宣言と仕様を確認して扱う。

ストアの今回の保証範囲と残る範囲は[保存・整合性検査契約](LOCAL_STORE_IO_CONTRACT.md)を参照する。
CLIの今回の対象と終了コードは[入力・I/O診断契約](CLI_INPUT_ERRORS.md)を参照する。

## 検証の環境

Windowsの既定uvキャッシュへ書き込めない場合は、作業ツリー内の`tmp/bridge-fix-uv-cache`を使う。
依存導入済みの`.venv`で、`UV_NO_SYNC=true`、`UV_OFFLINE=true`、`PYTHONUTF8=1`を設定して実行する。
依存関係そのものを変更した場合は、別途同期・配布パッケージ検証を行う。
