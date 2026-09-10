# ローカルストアの保存と整合性検査

対象は`src/hate/store/`の`LocalStore` APIと、そのJSON/JSONL保存処理。
CLIの旧ストアAPIや外部ownerの運用機能とは実装が異なる。

## ストアの版情報

`store-version.json`が存在するストアでは、`schema_version=HATE/v1`と`store_version=1.0.0`を
対応版として検証する。未対応のpatch版も推測して受け入れない。created_atはタイムゾーン付き日時、
producer_versionは空白でない文字列を必須とし、厳密なJSON読込も適用する。
既存の正常な版情報、作成日時、追加フィールドは書き換えない。

LocalStoreの初期化・各操作・索引構築APIは、lock取得前と取得後に版情報を確認してから復元へ進む。
オープン済みインスタンスも操作ごとに再確認する。同じ検証済み操作の内部呼出しは範囲を共有するが、
呼出し元が低水準のstore_lockを取得済みというだけでは版検証を省略しない。
版情報が壊れている、読めない、未対応の場合はLocalStoreErrorとしてpathと診断を返し、
lock用ディレクトリーの新設や通常の書込・復元を開始しない。

取り込みtransactionの開始・確定・失敗処理、および直接呼ばれた復元処理も版情報を確認する。
途中で未対応版へ変わった場合は、失敗記録の追記・rollback・索引再読込を止め、
その時点の未確定journalと退避・保存途中のデータを保持する。対応する版情報に戻った後は通常の復元を再開できる。
これは同じOS lockを守る操作の契約であり、排他制御外の同時書換え全般を防ぐものではない。

版情報のない新規・従来ストアは、既存の初期化・索引補完の扱いを維持する。
版情報の欠落から保存データ全体の対応版を判定する保証は追加しない。
新規作成に渡すproducer_versionが不正な場合は、ディレクトリーを作る前に拒否する。

## 入力JSONとbundleの検証

bundle・manifest・JSONL索引の各行・復元journalは、JSONオブジェクト内の重複項目を拒否する。
入れ子の重複も含む。後から出た値を採用して証跡や保持情報を消さない。
NaN・Infinity、浮動小数点のoverflow、非ゼロの入力が0へunderflowする数値、
UTF-8へ戻せない孤立surrogateも拒否する。通常の数値はPythonのint/floatとして扱い、
任意精度の十進小数を保証しない。正しいUnicode文字列・有限の通常値は書き換えない。

保存前に、存在するnodes/edgesが配列であること、各nodeがオブジェクトでkindが空白でないこと、
任意のnode IDが空白でなく重複しないこと、data/payloadがあればオブジェクトであることを確認する。
edgeにはfrom/toと関係種別を要求する。旧形式のrelationship表記も保持する。
同じartifact IDが複数nodeから生じる入力は、ファイルやmanifestを書き始める前に拒否する。
検証済みのartifact一覧とhashをそのまま保存処理へ渡す。source_version、producer_version、
legal hold等のmanifest情報も、公開スキーマとUTF-8 JSONへの保存可能性を先に確認する。
不正入力ではbundle・索引・復元journal・隔離データを作らず、項目付きのLocalStoreErrorを返す。
開始時に未確定journalがある場合は、通常の復元処理を先に行う。

`metadata.qegVersion`または`completeness`を持つ入力は、配布する`qeg-bundle.schema.json`全体で検証する。
必須フィールド、node/edgeの構造、completeness、対応版を検証し、未対応版を黙って現行版へ変換しない。
両フィールドを持たない従来のローカルJSONは構造検証の対象であり、QEGスキーマ適合を示すものではない。
実際のQEG出力と従来の最小JSONの双方を回帰テストに含める。local run IDは保存履歴のIDとして扱い、
元のmetadata.runIdを変更しない。外部anchorの解決や最終QEG判定は、この保存検証の責務に含めない。

通常のbundle読込・整合性検査・replay・索引補完でも同じbundle検証を使う。
旧データの違反は報告して元のファイルを残す。既存のJSONを推測で修正しない。
読込不能なbundleでもdoctorは診断を続け、問題があるファイルのpathを報告する。

## 単一ファイルの保存

`atomic_write_json`と`StoreIndex.save`は、同じバイト保存処理を使う。

1. 同じディレクトリー内の一意な一時ファイルへ全バイトを書き込む。
2. 短い書き込みは残りを続けて書き、進捗ゼロはエラーにする。
3. ファイルの`fsync`とcloseが成功してから、`os.replace`で保存先へ置換する。
4. Unix系では親ディレクトリーも`fsync`する。Windowsではこの操作を省略する。

置換前に失敗した場合、既存ファイルを保持する。Windowsでも旧ファイルを先に`.bak`へ移動しない。
無関係な`.bak`や固定名の`.tmp`ファイルに触れない。通常の中断時も一時ファイルと記述子を片付ける。
一時ファイルを削除できない場合は残存パスを警告する。強制終了や電源断後の自動復旧は保証しない。

エラーの`phase`は`write`、`fsync`、`rename`を区別する。
置換後のディレクトリー同期だけが失敗した場合は、`diagnostics[].published=true`を返す。
この場合は新しい内容が見えていても永続化を確認できていない。旧内容への復元済みとは扱わない。

JSONはオブジェクト、有限の数値、UTF-8を要求する。JSONLはUTF-8・LFのバイト列を保存し、
返すSHA-256を実際の保存形式に一致させる。以前のCRLF索引も読み込める。

## 完了manifestの公開

`complete_manifest_write`は`runs/<run_id>/<bundle_id>/store-manifest.json`への保存前に、
候補manifest・保存先・ストア版情報を検証する。bundle本体の構造とcanonical ID、manifestとartifact一覧の一致、
必要な各artifactファイルの有無とhashを、保存済みコピーの整合性検査と同じ処理で確認する。
呼出側のbundle_files一覧が空・不完全でも、この検証は省略しない。指定された補助ファイルもストア内の通常ファイルを要求する。
索引全体の検査・復元は呼出側のtransactionの担当とし、低水準の完了writer自身は索引を変更しない。

完了候補は入力辞書と分けて用意し、ファイル公開と同期に成功してから入力辞書を更新して返す。
完了へ遷移しても元のimport_status.diagnosticsと追加情報を保持する。
失敗・中断では入力辞書を変更しない。置換後の同期失敗の場合は、公開されたmanifestと入力辞書の状態が異なり得るため、
AtomicWriteErrorのpublished=trueを確認して扱う。既存ファイルへの自動巻戻しを成功として報告しない。
排他制御と複数ファイルの復元は呼出側が担い、LocalStoreからの呼出しには既存のOS lockとjournalを適用する。

## 索引の再読み込み

索引は全行を検証してからメモリー上のエントリーを入れ替える。削除されたキーをキャッシュに残さず、
壊れた行までの部分的な読込結果を公開しない。JSONの構造不正・不正UTF-8・読込エラーは
`IndexLookupError`として報告する。

`LocalStore`のbundle・manifest読込APIは必要な索引を読み込む。
ストアを開き直した直後も、先に`list_runs`等を呼ぶことなく読み取れる。
bundleやmanifestがJSONオブジェクトとして読めない場合は`LocalStoreError`になる。

## 取り込みの確定と復元

`LocalStore`の操作とreplay・compare・doctorは、`locks/store.lock`のOSファイルロックを取得する。
別プロセスや別スレッドで使用中の場合は待ち続けず`LocalStoreError`になる。
同じスレッドからの入れ子の操作は許可する。プロセス終了時はOSがロックを解放する。
lockファイルの存在だけで使用中とは判断しない。稼働中のlockファイルを削除しない。

取り込みは以下の順で進む。

1. 既存の全索引を`migrations/pending-import/before/`へ退避する。
2. 元の索引の有無・ハッシュ・対象bundleを記録した`journal.json`を公開する。
3. bundle、artifact、索引、完了manifestを保存する。
4. journalを`committed`へ切り替えてから、一時的な退避情報を片付ける。

確定前の通常エラーでは、失敗したbundleを隔離し、既存索引を元のバイト列へ戻す。
初回取り込みで新設した索引は除去する。既存runへ別bundleを追加する場合も、旧索引・旧bundleを保持する。
失敗した取り込みのデータ・索引退避・エラー記録は、一意な`quarantine/import-*/`へ残す。
同名の隔離データを上書きしない。復元後は元の入力で再試行できる。

`KeyboardInterrupt`では復元してから中断を伝える。プロセスが強制終了した場合は、次回のオープンまたは
次の操作で未確定journalを検出し、通常処理に入る前に復元する。manifestだけが完了していても、
journalが未確定なら索引と一緒に戻す。

復元前に全バックアップのハッシュを検証する。破損・読込不能・復元失敗時は退避を残し、
`LocalStoreError`の`recovery_path`を報告して通常操作を止める。原因を解消した後の操作で復元を再開する。
退避ファイルを確認せず削除して処理を続けない。

commit記録の置換後に同期だけが失敗した場合は、旧状態へ復元せず`commit_durability_uncertain`を報告する。
この場合、完了済みbundleとjournalを保持し、次回操作で確定済みとして扱う。
単一のファイルシステムに対する複数ファイルの同時切替や、電源断・媒体故障からの完全復旧は保証しない。
低水準の`StoreIndex`直接操作や手動ファイル編集はこの排他・復元契約の外にある。

## 索引スナップショットの検証

JSONL索引は、各キーを一度だけ記録する現在の参照スナップショットとして扱う。
同じキーの複数行は、値が同一でも破損として拒否する。診断には最初の行と重複行を残し、
ファイルや読込前のキャッシュを変更しない。取り込みAPIによるrun/bundle alias更新は引き続き可能で、
保存時には更新後の一行となる。索引を追記イベントログとして連結しない。

IndexEntryの追加・保存・読込では、キーと参照値が空白のみでないこと、SHA256の形式、metadataが
有限値のみを含むJSONオブジェクトであることを検証する。保存時は辞書のキーとentryのキーも照合する。
不正値を既定値へ置き換えたり、正常な既存索引へ部分保存したりしない。

## 索引参照の検証

`StoreIndex.lookup(verify_record=True)`は拡張子を条件にせず、通常ファイルの実バイトをSHA256で照合する。
JSON、JSONL、拡張子のないファイル、バイナリーも同じ扱いとする。欠損、ディレクトリー等の通常ファイルでない
参照、読込エラー、hash不一致はHardDQFindingにする。保存先スコープ、entryの型・文字列、
辞書内の検索キーとentry.keyの一致は読込時にも検証する。
`verify_record=False`ではファイルの有無・内容hashを検証しないが、参照値とentryの検証は省略しない。
入力文字列がUTF-8へ変換できない場合もキャッシュや索引を書き換えず拒否し、診断上はエスケープ表記で報告する。

LocalStoreのrun/bundle/artifact参照は、さらに`runs/<run_id>/<bundle_id>/`の配置、
`qeg-bundle.json`または`<artifact_id>.json`という参照先、manifestのID、索引metadataを照合する。
artifactの所属とhashもmanifestと照合する。同じ内容を別ファイル名で複製しただけの参照は認めない。
通常のbundle読込は実ファイルhashと完了状態を検証する。manifest読込は診断にも使うため、
bundle本体の有無・hash・完了状態を成功の前提にはせず、配置とID・metadataを照合する。
`verify_integrity`は参照解決に失敗した場合も`integrity_ok=false`と診断を返す。

過去bundleを再取り込みする場合は、その保存コピー・bundle alias・artifact aliasに加えて、
現在のrun aliasが指すコピーも検証する。runが正常な別bundleへ進んでいることはエラーにしないが、
そのコピーが破損していれば成功扱いしない。参照検証と索引補完で同じ照合処理を使う。
検証中のmanifestは操作内で再利用し、artifactごとに同じmanifest全体を読み直さない。

SHA256のhex文字の大文字・小文字は同じdigestとして比較する。元のindex値やファイルを書き換える
正規化は行わない。内容バイトそのものの差は引き続き別hashとして検出する。

## 保存済みbundleの索引補完

`hate.store.indexes.build_indexes_for_bundle(store_root, bundle_dir, manifest)`は、
`runs/<run_id>/<bundle_id>/`に保存済みの完了bundleから、欠けている索引参照を補完する。
runとbundleの参照先はともに`qeg-bundle.json`であり、`run.json`は使用しない。
通常の取り込みと同じ索引生成処理を使う。返す7索引のhashは処理後のファイル内容から計算する。

書込前に保存manifestのスキーマ・完了状態・指定manifestとの一致、bundleとartifactの実体・hashを確認する。
欠損ファイルを飛ばして成功にしない。既存の正常なrun・bundle・artifact aliasは維持し、
破損した既存aliasや矛盾するmetadataを推測で上書きしない。関係しない索引entryも保持する。
manifest本体、元の`index_hashes`、保持情報、証跡ファイルは変更しない。

run aliasが欠けていれば、そのrunの完了manifestの実時刻から最新のコピーを選ぶ。
異なるタイムゾーンも同じ時系列で比較する。同時刻で最新が一意に決まらない場合はエラーとし、
ファイル名順に置き換えない。最新コピーの索引も補完して、古いbundleへの参照だけを復活させない。
正常な既存run aliasがあれば、その参照先を優先する。このAPIは指定コピーとrun参照先に必要な索引を
補完するもので、ストア全履歴の一括修復や壊れた証跡の再生成は行わない。

索引補完も通常のストア操作と同じOSロックを取得し、未確定journalの復元後に進める。
索引専用journalは`version=2, operation=indexes`で記録する。通常取り込みのversion 1も引き続き読める。
旧readerはversion 2を拒否するため、完成済みbundleを取り込み途中のデータとして隔離しない。
確定前の失敗・中断では7索引を処理前へ戻し、完成済みbundleを移動・削除・変更しない。
復元失敗時はバックアップを保持し、次回のストア操作で復元を再開する。commit後の同期不確実性も
通常取り込みと同じく報告する。旧版への切替前には現行版で未確定journalを解消する。

## 同一bundleのrun別履歴

同じ内容を別runへ取り込んでも、各runの`runs/<run_id>/<bundle_id>/store-manifest.json`を保持する。
`list_bundles_for_run`はそのrunの完了manifestから一覧を作るため、以前の保存形式にも対応する。
未完了manifestは一覧へ出さず、run IDやbundle IDが配置と矛盾するmanifestはエラーにする。
manifestがスキーマに適合しない場合もエラーにする。doctorはこの完了一覧を使わず、実ディレクトリーから診断する。

`read_manifest_by_bundle(bundle_id, run_id=...)`でrunを指定できる。
省略時は従来どおりbundle索引が指すコピーを読む。runが分かっている処理では明示指定する。
baseline選択・run診断・replayは指定runのmanifestとartifactを使う。
別runの同じbundleも比較baselineにでき、ストア全体の診断では各runのコピーを確認する。

保存コピーの対応版は`schema_versions.core=HATE/v1`、`schema_versions.store=1.0.0`とする。
任意の`schema_versions.bundle`がある場合もHATE/v1を要求し、各項目を独立して検証する。
bundleの対応版でcoreやstoreの未対応版を無視しない。追加のadapter・parser等の版は保持するが、
HATEがその互換性を検証したとは扱わない。対応表は`store.compatibility`で共通管理する。

未対応の版はcomponent・実際の値・対応値を含む`store_schema_version_unsupported`診断にする。
replayはmigration hold、比較はincomparable、doctorはschemaのsoft DQとして報告する。
通常のbundle読込・再取り込み・索引補完・完了保存・保持指定更新は、未対応版を検出したコピーを変更せず拒否する。
診断用のmanifest読込、履歴列挙、物理的なhash・欠損の検査は可能とし、保存版を推測して書き換えない。
完了状態・物理整合性と、現行処理で使える版かどうかは別の判定である。

baselineを指定したreplayも、対象と比較元の両方に対応版を要求する。最新の比較元が未対応でも、
古い対応版のコピーへ暗黙に差し替えない。参照先と実体が正常ならbaseline_validはtrueを保ち、
replay全体のschema_compatible=false、migration_hold=true、artifacts_replayed=0で互換性不足を表す。
baselineの未対応版は`baseline_store_schema_version_unsupported`として区別する。
実体の破損や解決不能もある場合はhard DQを優先し、期待hashの欠落を再生成功として数えない。

## run単位の整合性検査

未確定取り込みがあれば先に復元する。その後の`verify_integrity`自体は索引を保存せず、
ファイル内容・更新時刻を変更しない。

- manifestの完了状態、run IDと索引の対応を確認する。
- canonical bundleの存在、保存バイトのハッシュ、内容から求めたbundle IDを確認する。
- artifact一覧とハッシュ一覧の対応、artifact実体の存在・ハッシュを確認する。
- 対象bundleとartifactの現在の索引参照を確認する。

manifestの`index_hashes`は取り込み時点の索引スナップショットとして保持する。
その後も更新されるストア全体の索引を、この過去のハッシュと一致させることは要求しない。
別runの正常な追加だけでは過去runを不整合にしない。関連エントリーの欠落・不一致は検出する。
同じJSON内容でもキー順が違えば保存バイトやartifact IDが異なり得る。
共有bundle索引は参照先自身の保存ハッシュとcanonical IDを検証し、別runの保存バイトとの一致を要求しない。

公開データ型は`models.py`、検証処理は`integrity.py`へ分離する。
`hate.store`と`hate.store.local_store`からの既存のデータ型importは維持する。

## manifestと再取り込みの検証

`schemas/HATE/v1/store-manifest.schema.json`を保存前・読込時の検証の正本とする。
型・必須情報・ハッシュ書式・日時・空白だけのメタデータを検証する。
artifactのないbundleを扱うため一覧は空にできる。writerが出力する`record_type`と`released_at`をスキーマへ反映する。
`record_type`を省略した既存manifestは引き続き読める。`schema_versions`の追加項目は文字列、
`index_hashes`の追加項目はSHA256値として検証する。

任意の`import_status`もStoreManifestの読込・JSON出力・保持指定の更新で保持する。
writerが記録したphase、diagnostics、スキーマ上許される追加情報を消さない。
項目がない旧manifestには作り足さず、空オブジェクトが記録されていた場合もその存在を維持する。
phaseが明示されている場合、completed=trueにはphase=completed、completed=falseにはそれ以外の既知phaseを要求する。
この関係を公開スキーマに定義し、完了判定・読込・診断で同じ矛盾を検出する。
以前読めていた矛盾したmanifestも不正として報告し、自動的にフラグやphaseを書き換えない。
phaseが省略された旧manifestや空のimport_statusは引き続き受け入れる。

legal holdのstatusは`none`、`active`、`released`、`pending`に限定し、reasonとauthorized_byは空白のみを許さない。
held_sinceとreleased_atはタイムゾーンを含むdate-timeとする。これは申告メタデータの妥当性検証であり、
外部の本人確認・権限確認を実施したことを意味しない。元から無効だった値を新しい日時やactorへ自動置換しない。

`update_legal_hold(run_id, ...)`は、対象runの現在の索引が指すmanifestを更新する。
同じbundleを持つ別runや、そのrunの過去bundleは変更しない。bundle本体・artifact・索引・
取り込み状況・保持指定以外のmanifest情報を保持し、manifest一件を原子的に置き換える。
置換前の失敗・中断では旧manifestを保持する。置換後の同期失敗は通常のatomic write契約に従う。

none・pending・releasedからactiveになるときは、その時点のUTC日時をheld_sinceへ記録する。
activeのまま理由を修正する場合は元の開始日時を保持する。activeへの切替では過去の解除情報を外す。
releasedへ遷移したときは解除日時と申告された承認者を記録する。
releasedのまま理由・申告者を修正する場合は、既存のreleased_atとrelease_authorizationを保持する。
旧manifestにそれらがない場合も、実際の解除日時や承認情報を推測して補わない。
このAPIは現在の状態を更新するもので、全状態遷移の監査履歴を生成するものではない。

`is_complete_manifest`はスキーマ適合と`completed=true`を確認する。実ファイルの整合性は別途検査する。
通常のbundle読込は、対応するmanifestが妥当で完了していることを要求する。
manifest読込APIは診断用に妥当な未完了状態も返せる。

同じrun・bundleを再取り込みするときは、保存済みmanifest・bundle本体・artifact・関連索引を確認してから
`bundle_already_exists`を返す。artifact一覧とハッシュが両方欠落した場合も、bundle本体の対象nodeから検出する。
履歴上の古いbundleを再取り込みしても、runの最新索引をそのコピーへ戻さない。
既存データの破損時はエラーを返して元データを保持する。新しい入力による上書きや自動削除は行わない。

bundle IDとartifact IDの16桁のhash部分は、保存・索引用の短縮キーとして維持する。
取り込み前にbundles/artifacts索引を読み、同じIDの既存参照があれば完了manifest・識別情報・実バイトhashを検証する。
同じ保存コピーのmanifestは一回の事前検証内で共有し、artifactごとに全manifestを再読込しない。
bundleは入力と既存コピーのcanonical JSONのSHA256全体を比較する。artifactは保存形式のSHA256全体を比較する。
衝突はbundle_id_collision/artifact_id_collisionとして、既存値と入力値の完全hashを含むLocalStoreErrorを返す。
transaction・索引更新・新規コピー保存の前に拒否するため、衝突で既存履歴を書き換えたり隔離ファイルを増やしたりしない。
同一IDの既存参照を検証できない場合も停止し、新しい取り込みでその参照を黙って置き換えない。
JSONのキー順だけが異なる同じcanonical bundleや、同じ完全hashのartifactを別bundleで共有する取り込みは維持する。
索引にない旧コピーの全探索・自動修復は行わず、旧データの未登録・破損はdoctorで診断する。

## doctorの診断と旧データ

doctorのrun・全体診断は、`runs/<run_id>/<bundle_id>/`と各索引を別々に調査する。
全7索引を個別に読み、一つが壊れていても他の索引と保存実体を診断する。
未完了・未登録・manifest欠落・不正JSON・不正UTF-8・索引の参照先欠落やハッシュ不一致はhard DQとなる。
索引が指すコピーと履歴上のコピーを区別し、正常なruns・locks・migrationsを未登録bundle扱いしない。

単一bundle診断も、通常の破損や参照失敗を例外終了せずDoctorReportとして返す。
runを省略した場合は既存のbundle索引aliasを使い、索引がないコピーを直接調べる場合はrunを指定する。
aliasを使用した診断では、参照先がcanonical bundleファイルであること、索引のbundle/run識別情報、
実バイトのhashを検証する。aliasが壊れていても、解決できた保存コピー側の所見を併せて返す。
runを指定した直接診断は指定コピーを対象とし、別コピーを指す共有aliasの検証はrun・全体診断で行う。
診断結果には対象path、run、原因を残す。既知の未確定journalがあれば診断前に通常の復元処理が走る。
それ以外の診断はファイル内容・更新時刻を変更しない。

`DoctorReport.run_id`には、単一診断で選んだコピーのrun、run診断で要求されたrunを保持する。
所見のない正常な診断や対象未存在の診断にも保持する。全体診断とrun未解決の診断はnullとする。
同じbundle IDでもrunが異なるdoctorをreplayへ集約した場合は、識別子矛盾としてhard DQにする。
run情報を持たない従来の手作りレポートから、検証済みのrunを推測して補完しない。

journalなしで残された旧データは診断対象に含めるが、自動修復しない。
不完全コピーや索引を保存し、検証済みの原本または索引スナップショットから復元する必要がある。
再取り込みだけで保持情報や履歴を推測して再構築することは保証しない。

## replayの検証と集約

replayはmanifestだけでなく、選択したコピーのbundle本体・内容由来ID・artifact一覧・artifact実体を
共通の整合性検査で確認する。構造の不整合がある場合、正常に再生したartifactとして数えない。
破損内容はhard DQ diagnosticsに残り、`integrity_ok=false`となる。
manifestを解決できない場合は、実際のmanifestまたは索引のpathを示すHardDQFindingを返す。
未対応schemaはmigration holdを維持し、artifactを再生済みとして数えない。

baselineを指定しない再生は引き続き可能。指定時は`bundle:<bundle_id>`または`run:<run_id>`を使う。
空文字・未対応の参照形式・存在しない参照・不完全な保存内容を有効なbaselineとして扱わない。
解決したbundle ID、run ID、manifest時刻、選択方法、検証結果を`baseline_resolution`へ保存する。
runの時刻順はタイムゾーンを考慮した実時刻で判定する。baseline選択と索引補完では共通の日時キーを使い、
小数秒をマイクロ秒やfloatへ丸めない。末尾ゼロやUTCオフセットの表記だけが異なる同一時刻は同率になる。
選択対象の最新時刻に複数コピーがある場合は、bundle ID順で一つを選ばず`ambiguous_baseline_timestamp`を返す。
候補IDと元の日時を診断に残し、明示のbundle参照で選べる。診断の候補一覧は表示の安定性のためID順とする。
最新でない候補同士の同率は、一意な最新候補の選択を妨げない。

`compare_bundle_to_baseline`の既定選択と同じrunへの参照では、比較対象より前の履歴を選ぶ。
同時刻・後続のコピーは候補にしない。対象より前のコピーがなければ比較不能とし、将来の履歴で代用しない。
別runの明示参照はそのrunの最新コピー、明示bundle参照は指定したコピーを使用する。
`select_baseline_by_timestamp(..., before_created_at=...)`で厳密な日時上限を指定でき、
省略時は従来どおり指定runの最新を探す。exclude_bundle_idの既存引数も維持する。

候補の読込失敗や日時の解釈失敗は選択エラーとして返し、古い候補へ黙って切り替えない。
replay・比較では失敗元の構造化診断をvalidationへ引き継ぎ、ファイルの修復や日時の書換えは行わない。

集約関数`build_store_replay_report`は従来のimport経路を維持し、実装を`replay_report.py`へ分離する。
`integrity_ok`、`legal_hold_preserved`、`baseline_valid`のfalse、個別hard DQ、doctorの不健全状態、
移行のhard DQを最終集約のhard DQへ引き継ぐ。schema非互換はholdとなり、別レポートのcompatibleだけで上書きしない。
比較不能はholdとし、辞書に変換できない補助レポートを黙って無視しない。
比較の集計がno_changeでも、個別差分のregression/incomparableや正のregressions件数があればholdとする。
比較の不正なfilename選択などhard DQがあれば、移行holdや保存済みholdより優先する。
移行レポートのschema_compatible=false、migration_hold=trueも維持し、compatibleラベルで打ち消さない。
これらはHATEの証跡の判定であり、外部QEGによる承認を代行しない。

集約済みJSONを再入力した場合、別の補助レポートを指定しなければ既存の差分・所見・移行状態・参照元を保持する。
selection_method=noneでIDが空のbaseline未指定状態も維持する。既定出力をJSONへ保存・再読込して再集約しても、
同じ内容とhashを得る。観測時刻の任意出力と入力不変の契約は同じである。
補助レポートを改めて指定すると該当節を更新するが、入力JSONに記録済みのhold/hard DQは再集約で弱めない。
失敗を解消した判定を作るには、対象を再検証した元のreplayと必要な補助レポートから新しく集約する。

corruption_findingsには、doctorが持つbundle_id・run_id・artifact_id・expected・actual・diagnosticsを保持する。
runは所見に明示された値、所見のdiagnostics、単一/run診断の対象情報から取り、識別できない値を推測しない。
これらは公開スキーマの任意項目であり、従来の最小所見を含むJSONも検証できる。
比較・移行のdiagnostics/findings、doctorの補足diagnosticsは、集約diagnosticsにreport・field・detailを付けて保持する。
同じ補助レポートを再入力しても同一の診断を重複追加しない。

`integrity_ok`はスキーマ上の任意項目として追加し、以前の保存レポートも引き続き検証できる。
新しい出力を読む側は更新後のスキーマを使用する。新規フィールドや検証結果の変化により、以前の出力hashとの一致は要求しない。

集約ではcurrentのrun/bundleとbaselineの識別子を、replay・compare・doctor・明示baseline情報の間で照合する。
明示された識別子が矛盾すればhard DQとなり、別runの成功結果で検証済み扱いしない。

## 決定的な証跡出力と観測時刻

`ReplayReport.to_dict()`、`ComparisonReport.to_dict()`、`DoctorReport.to_dict()`、`build_store_replay_report()`の既定出力は、
実行時刻を含めない正規の証跡JSONとする。辞書のキーと比較項目の出力順を安定させ、同じ保存内容・baseline・
検証状態・補助レポートから同じバイト列を得る。証跡に含まれる内容や検証結果が変わればhashも変わる。
doctorの`diagnosis_hash`は対象の識別情報・集計・所見など診断結果の内容hashであり、
ストア全体のファイル一覧や全バイトのチェックサムではない。ファイルの存在・hash検証は各診断処理で行う。
ストア配下の診断パスは`<store>/...`、ルート自体は`<store>`として記録し、配置の違いで同じ破損の内容IDを変えない。
Windows例外内のエスケープされたパスも対象とする。doctorの所見は正規化後の内容で並べてからIDを付け、
意味が同じ索引の行順変更で所見番号を変えない。各所見のpathは診断対象のストアルートを基準に解決できる。
doctorのパス正規化は`DoctorReport.to_dict()`の出力へ適用し、所見オブジェクトの絶対pathは既存APIどおり保持する。

実際の実行時刻はオブジェクトの`replayed_at`、`compared_at`、`diagnosed_at`に保持する。
必要なときは`to_dict(include_observation=True)`でJSONに含められる。
集約でも`include_observation=True`によりreplayの観測時刻を含められる。
この観測値を含めたJSON全体にはバイト一致を要求しない。新しい日時を保存元の日時に偽装しない。

内容hashは、自身の`replay_hash`、`comparison_hash`または`diagnosis_hash`と、そのレポートの観測時刻だけを除外した
JSONから求める。UTF-8、辞書キーのソート、最小区切り、非ASCII文字をそのまま使うSHA256とし、
NaNなどの非有限値は受け付けない。`report_serialization.report_hash`で保存済みJSONから再計算できる。
既にhashが埋まっていても再計算結果は変わらない。baselineの保存時刻など、入力由来の時刻は除外しない。
従来の`source_bundle_hash`フィールドはmanifestモデルの内容指紋として維持し、辞書順序に依存しない計算へ統一する。
保存済みのimport_statusも含むため、その診断内容の変化を指紋へ反映する。
import_statusを落としていた旧実装の指紋とは異なる場合があるが、canonical bundleのIDと保存内容は変更しない。

スキーマでは`replayed_at`を任意項目とし、以前の時刻入りJSONも読み取れる。
新しい既定出力を使う側は更新後のスキーマとhash契約を使用する。
以前の実装で作られたhashと新規算出hashの一致は保証せず、古い証跡を新契約で検証済みと読み替えない。

## compareの保存実体と結果指標

compareは両コピーのmanifest・bundle本体・artifactの整合性を確認してから比較する。
破損時はhard DQ diagnostics付きの`incomparable`となり、比較数ゼロの`no_change`にはしない。
manifest自体が解決できない入口ではHardDQFindingを返す。未対応schemaも比較不能とする。
`compare_bundle_to_baseline(..., run_id=...)`、
`compare_bundles_direct(..., run_id_a=..., run_id_b=...)`で比較する保存コピーを指定できる。

項目の同一性は種別と項目ID（testはcanonical_test_idがあれば優先）で照合し、
その項目の保存バイトを示すartifact IDとは区別する。IDがない場合は同一内容だけを対応付ける。
同じ項目IDが複数の異なるartifactに現れる曖昧な場合はhard DQとする。
結果には両方のartifact IDとhashを残し、追加・削除・比較数は対応付けた項目単位で数える。

| 種別 | 比較する指標 |
|---|---|
| test_result / test | passed・passとfailed・fail・errorの遷移。skippedなど順位を定義しない変化は比較不能。 |
| contract_evidence | 成功・失敗の遷移。 |
| mutation_evidence | survivedとkilledの遷移。timeoutやignoredへの変化を改善と決めつけない。 |
| coverage_slice / coverage | coverage_percent、または同じ測定行集合での実行有無。行集合・未対応branch情報が変わる場合は比較不能。 |
| static_finding / finding | note、warning、error、criticalの既知severity。未知の尺度は比較不能。 |

新しい検証可能な証跡の追加は数値指標の上昇とは区別して記録する。追加された失敗テストやfindingは悪化とする。
findingの消失だけでは解消と断定せず比較不能とし、その他の証跡の削除は悪化とする。
未知の内容変化をno_changeとして処理しない。既知の悪化が一つでもあれば全体はregressionとし、
悪化がなくても比較不能な項目が残ればincomparableとする。これは対応する指標の比較であり、任意のpayloadの完全な意味解析ではない。

P0bが実際に出力する`test`、`coverage`、`finding`も、従来の論理種別と同じくartifactとして保存・検証する。
元nodeの種別や内容は改変しない。executionなどの補助nodeもbundle本体には保持する。
旧版がこれらを個別artifactとして保存していない場合は、不足を報告して元データを保持する。
その旧コピーを自動的に書き換える修復処理は、現在の契約に含めない。

## 検証と残る範囲

`tests/test_store_atomic_failures.py`、`tests/test_store_index_io.py`、`tests/test_store_integrity.py`で
失敗注入、再読込、過去run、欠損ファイルを検証する。既存の保存・replay・compareテストも実行する。
`tests/test_store_transactions.py`、`tests/test_store_recovery_process.py`、`tests/test_store_run_history.py`で
複数索引の復元、実プロセスの途中終了・競合、runをまたぐ同一bundleを検証する。
wheel smokeはインストール先で保存・再読込・整合性検査・run別履歴・replayを実行する。
`tests/test_store_manifest_validation.py`と`tests/test_store_doctor_inventory.py`で、入力拒否・既存破損・
未登録コピー・部分的な索引破損・診断中のデータ不変を検証する。wheel smokeにもmanifest検証とdoctorを含める。
`tests/test_store_doctor_reports.py`では、公開hashの再計算、異なる時刻・プロセス・配置・索引行順での再現性、
実際の破損と復元による内容hashの変化、runの取り違え拒否、単一診断のalias検証を確認する。
`tests/test_store_replay_aggregation.py`では、保存JSONの再集約、実際の比較悪化と破損診断の保持、
集計と個別所見の矛盾、移行フラグ、入力不変、補助診断の重複防止、公開スキーマへの適合を確認する。
`tests/test_store_import_identity.py`では、ID生成の差替えで短縮IDの衝突を模擬し、完全hashの比較、書込前の拒否、
履歴・索引の不変、同一内容の共有、既存参照の検証不能を確認する。実際のSHA256衝突を生成した試験ではない。
`tests/test_store_replay_validation.py`と`tests/test_store_replay_readiness.py`で、破損の再生拒否、
baseline解決と実時刻の比較、集約時の失敗保持を検証する。wheel smokeも再生とbaseline集約を確認する。
`tests/test_store_report_determinism.py`では異なる実行時刻・プロセス・hash seed、JSONからの独立hash再計算、
ストア配置変更を検証する。`tests/test_store_compare_semantics.py`と`tests/test_store_export_kinds.py`では、
比較元の破損、同一項目の結果遷移、未知の指標、P0b実出力との接続を検証する。
`tests/test_store_index_builder.py`と`tests/test_store_index_builder_process.py`では、
現行配置からの索引補完、履歴参照の維持、入力拒否、索引書込・復元・commit時の失敗、
実プロセスの途中終了と排他、復元中の証跡不変を検証する。wheel smokeにも索引補完を含める。
`tests/test_store_bundle_input.py`と`tests/test_store_strict_json.py`では、曖昧なJSONの拒否、
保存前検証、公開QEGスキーマと実出力の一致、旧保存データの違反検出、診断時の不変性を確認する。
wheel smokeではQEG形式を明示したbundleを読み込み、インストール先のスキーマを使う。
`tests/test_store_reference_validation.py`では、拡張子によらないhash検証、キャッシュ不整合、
参照先・metadata矛盾、過去コピーの再取り込み、hex表記差、読込エラーの診断を検証する。

旧バージョンがjournalなしで残した不完全なデータの修復手順と、索引・replayの残る契約は、
[継続調査記録](MAINTENANCE_FINDINGS.md)で引き続き追跡する。
