---
intent_id: INT-HATE-P1A-TRUST-HARDENING-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# P1a Trust Hardening Implementation Contract

## 1. 目的

P1a は、HATE が生成する自動テスト証跡の信頼性を説明可能・再現可能にする層である。
AETE score、adapter capability、profile、canonical identity、retry aggregation、
path normalization、replay / compare / explain / recommend / doctor を実装対象とする。

P1a は release Gate ではない。AETE score は QEG や人間レビューの入力であり、
未校正 score を release approval として扱わない。

## 2. Scope

### In

- AETE 8 dimensions with 0 / 1 / 3 / 5 scale
- profile and calibration metadata
- adapter capability manifest
- canonical test identity and aliases
- matrix / shard / retry aggregation
- path normalization and artifact resolver map
- replay / compare / explain / recommend / doctor command contracts
- risk debt and manual-bb bridge trigger conditions

### Out

- QEG Gate verdict
- waiver / approval / retention / immutability
- manual test execution
- Shipyard acceptance / publish transition

## 3. AETE Score Contract

```yaml
schema_version: HATE/v1
record_type: aete_score
run_id: string
run_attempt: number
commit_sha: string
rubric_version: string
profile_version: string
calibration_status: uncalibrated | provisional | calibrated
score_confidence: low | medium | high
subject:
  subject_type: evidence_item | test_case | suite | change | run
  subject_id: string
dimensions:
  provenance_integrity: 0 | 1 | 3 | 5
  determinism_flakiness: 0 | 1 | 3 | 5
  traceability_lineage: 0 | 1 | 3 | 5
  oracle_strength: 0 | 1 | 3 | 5
  change_relevance: 0 | 1 | 3 | 5
  coverage_adequacy: 0 | 1 | 3 | 5
  cross_signal_corroboration: 0 | 1 | 3 | 5
  freshness_profile_conformance: 0 | 1 | 3 | 5
weighted_score: number
reason_refs: array
source_refs: array
```

Dimension score must include reason refs. A score without reason refs is invalid.

## 4. Scoring Rules

| Dimension | Score 0 | Score 1 | Score 3 | Score 5 |
|---|---|---|---|---|
| provenance_integrity | missing commit/run/hash | partial provenance | run + commit + hash | tamper-resistant provenance |
| determinism_flakiness | unresolved flaky | retry unknown | deterministic single run | stable across retry/matrix |
| traceability_lineage | no sourceRefs | weak refs | requirement/risk/test linked | source-backed full lineage |
| oracle_strength | no assertion | smoke only | specified oracle | mutation/contract backed |
| change_relevance | unrelated | module-level | changed file linked | changed line/risk linked |
| coverage_adequacy | none | file coverage | line coverage | branch/context coverage |
| cross_signal_corroboration | single weak signal | execution only | execution + coverage | execution + coverage + static/artifact |
| freshness_profile_conformance | stale/profile mismatch | unknown | fresh enough | fresh and profile conformant |

Weighted score follows `SPECIFICATION.md#12`. Profile can change thresholds, but cannot change
dimension vocabulary.

### 4.1 申告provenanceと評価の信頼度

P1aはbundleのrunId・createdAt、reportのcommit_sha、各evidence_artifactのdata.sha256を確認する。
commitは7〜64桁の16進文字列、SHA256は64桁の16進文字列（`sha256:`接頭辞を許容）、
日時はtimezoneを持つRFC 3339形式とする。日時の前後空白・改行も不正とする。
reportのcreated_atは省略できるが、宣言された場合は同じ形式検証を行う。
不正値と必須provenanceの欠落は、項目位置を持つprovenanceのhigh/blocking所見へ記録する。

| 入力の状態 | provenance_integrity |
|---|---:|
| bundleに有効なrunIdがない | 0 |
| runIdはあるが情報が部分的、または申告に不正がある | 1 |
| run・日時・commitが有効で、1件以上のartifactの全SHA256形式が有効 | 3 |

artifact nodeが存在しない場合は1点とし、任意のartifactを必須入力として所見を生成しない。
別のartifactに有効なhashがあっても、不正・欠落hashを相殺しない。
hash形式の検証は実ファイルの内容検証や改ざん耐性の証明ではないため、申告だけでは5点を付けない。
dimension signalにartifact件数・有効hash件数と、実体検証・改ざん耐性が未検証であることを記録する。

score_confidenceはprovenance不正時にlowとする。それ以外では、bundleまたはreportのcompletenessに
partial・unsupportedClaims・excludedArtifacts・parserFailuresがある場合、またはreport直下に
missing_execution・unsupportedClaims・excludedArtifactsがある場合にmediumとする。
retry集約がinconclusiveの場合もmediumとする。完全な履歴から確認されたflakyのスコアは低くなるが、
その判定が確かであれば信頼度まで一律に下げない。
該当する不足がなければhighとし、スコアが低いという理由だけでは信頼度を下げない。
片方の空配列やpartial=falseで、もう片方の不足を打ち消さない。

HATE precheckのsoft gap（FIX-094）もscore_confidenceをmediumとする。provenance不正のlowを優先する。
対象はkind=gate_verdictかつIDが`hate_precheck:`で始まるnodeであり、外部Gateのdataは解釈しない。
宣言されたsoft_gapsはobjectの配列、reasonsはstringの配列、decisionはstringとして、5入口で出力前に検証する。
不正形式は位置付きTrustError（終了コード1）とし、入力と既存出力を保持する。

- 元のgap object・reasons・node ID・項目位置・sourceRefsを各出力に保持する。
- doctorはprecheckカテゴリのHATE-DOC-PRE-001、medium/non-blocking所見とする。trust/doctor statusはpartialとなる。
- `explain --mode why-soft-gap`と`--mode why-score-changed`に同じ根拠を示す。
- `recommend --gap all`、`--gap precheck`、元のgap_id指定で補完提案を返す。
- 詳細を持たない旧conditionalにはprecheck_soft_gap_details_missingを記録し、gap内容を推測しない。
  旧eligibleに省略されている追加項目は補わず、従来の評価を維持する。

gapのmessageがstringでなければ、元objectを保持したまま共通の説明文を使う。拡張項目を文字列化しない。
decision名がeligibleでも明示的なgapを無視しない。種類ごとの根拠がない一律のdimension減点やrisk debtは生成しない。
この修正はsoft gapの継承を対象とする。P0b入口のexport許可検証と、外部QEGの最終release判断の責務は変えない。
`tests/test_precheck_soft_gaps.py`で実際のstrict profileからの引継ぎ、5入口の形式検証、
旧形式、replay/doctorとの一致、信頼度の優先順位、説明・補完提案を検証する。

### 4.1.1 既存bundleのprecheck許可情報（FIX-095）

P1aにはP0bの最新の入口検証を通っていないbundleも届くため、保持されたHATE precheckの
decision・exit_code・qeg_export_allowedを照合する。対象nodeの識別は4.1節と同じとし、
外部Gateの独自dataを解釈したり、HATE precheckを持たない外部bundleへ新たな必須nodeを要求したりしない。

- qeg_export_allowedはboolean、exit_codeは原表記でJSON整数、dq_hitsはobjectの配列とする。
  宣言済みの型不正は5入口でTrustError（終了コード1）とし、出力先を新設せず既存成果物を保持する。
- decision・exit_code・qeg_export_allowedの欠落、未知のdecision、0/2以外の整数exit_codeは許可不備として診断する。
  0へ丸められる微小な端数や2へ丸められる端数は、整数として受け入れない。
- ineligible/hard_dq、許可フラグfalse、exit_code=2、非空dq_hitsのいずれかがあれば不許可として診断する。
  同じnode内の許可フラグや、別nodeの許可宣言で拒否条件を打ち消さない。

1 nodeにつき1つのhigh/blocking所見へ集約し、violationsに原因ごとの項目位置を残す。
issueは不許可があればprecheck_export_not_allowed、それ以外の許可不備はprecheck_permission_invalidとする。
元のprecheck_payload・reasons・sourceRefsを保持し、欠けた値を入力へ補わない。
旧P0bが保持していなかったdq_hits・soft_gaps・reasonsの省略は、それだけでは拒否条件にしない。

診断を生成できた場合のCLI終了コードは0、trust/doctor statusはpartial、score_confidenceはlowとする。
soft gapによるmediumより優先する。rawのdimension値を一律に書き換えず、許可不備を所見と信頼度に明示する。
`explain --mode why-excluded`と`--mode why-score-changed`ではineligibleの根拠として示し、soft gapへ読み替えない。
`recommend --gap all`、`--gap precheck`、`--gap precheck_permission`で元証跡の確認・修正・再生成を提案する。
release_gate_overrideとpublish_gate_overrideはfalseを維持する。

`tests/test_p1a_precheck_permission.py`とwheel smokeで全32許可組合せ、欠落・型・原表記、
複数nodeの拒否保持、replay/doctorとの一致、説明・補完提案、既存成果物保持を検証する。

### 4.1.2 export metadataと現在のスキーマ検証（FIX-096〜097）

P1aはprecheckに加え、bundle.metadata.debugOnly、report.export_status、
report.qeg_schema_compatibilityの宣言を評価へ接続する。

| 入力に残された状態 | 所見 | score_confidence |
|---|---|---|
| debugOnly=true | export / high / blocking | low |
| export_status=partial | export / medium / non-blocking | medium |
| success/partial以外のexport_status | export / high / blocking | low |
| qeg_schema_compatibility.valid=false、非空errors、または宣言されたobjectにvalidがない | export / high / blocking | low |
| 現在のbundleの公開スキーマ違反 | 既存のschema / high / blocking | low |

export所見のコードはHATE-DOC-EXP-001とし、元の宣言値・検証結果・項目位置・sourceRefsを保持する。
errorsは文字列や構造化された元エラーを配列のまま保存する。valid=trueとエラー記録が矛盾しても、
エラーを打ち消さない。現在のbundleがスキーマに違反すれば、過去のvalid=true申告より現在の検証を優先する。
low条件はpartialやsoft gapのmediumより優先する。診断が完了すれば終了コード0、trust/doctor statusはpartialとなる。

export_statusはstring、qeg_schema_compatibilityはobject、宣言済みvalidはboolean、errorsはarray、
schema参照はstringとして5入口で検証する。debugOnlyのboolean検証は公開bundle schemaに従う。
型不正は出力前にTrustError（終了コード1）とし、既存成果物を更新せず新しい出力先も作らない。
export_statusやqeg_schema_compatibilityを持たない旧reportへ値を補わず、存在する宣言を照合する。

説明では、high条件を`--mode why-excluded`、partialを`--mode why-soft-gap`、
いずれも`--mode why-score-changed`へ接続する。`recommend --gap all`のほか、
export_metadataまたは所見のissue ID、現在のスキーマ違反にはbundle_schemaを指定できる。
exportのpartial宣言と具体的なmissing executionは別の根拠として示すが、新たな障害・risk debt・
未実行テストを推測して増やさない。既存のgap IDで絞り込む補完提案はその対象を維持する。

`tests/test_p1a_export_metadata.py`で36組合せ、5入口の型検証、旧report、元エラー保持、
現在のschema診断と信頼度の一致、replay/doctor・説明・補完提案を検証する。
配布wheelでも同じCLI経路と既存評価結果の保持を確認する。

### 4.2 総合スコアの重みと比較

SPECIFICATION.mdの順に20・15・15・15・15・10・5・5の重みを使用し、
`weighted_score = round(sum(dimension_score * weight) / (5 * sum(weight)), 3)`で算出する。
総合スコアの範囲は従来どおり0〜1とし、現行の4つのprofileは同じ重みを使用する。
score JSONとsignal reportに`dimension_weights`・`aggregation_method=weighted_mean`を記録し、
同じ総合スコアをsummary・replay・CLI結果へ渡す。公開スキーマでは旧成果物を読めるように
追加metadataを省略可能とするが、宣言された場合は現在の重みと集計方法に一致させる。

compareは両入力の8次元、離散値0/1/3/5、総合スコアの有限性・範囲・計算結果との一致を
出力先作成前に検証する。宣言された重みと集計方法も検証する。
booleanや数字文字列、floatへの丸めで離散値に見える端数は数値として受け入れない。
総合スコアが式に一致しない場合は`TrustError(exit_code=1)`とし、既存比較結果を保持する。
単純平均で作成された旧スコアも一致しなければ比較を停止するため、元のbundle/reportから
`hate replay`で再計算してから比較する。過去のfixture・受入記録は再計算せず履歴として維持する。

例えばprovenanceが3→1、coverageが3→5で他次元が同じ場合、単純平均の差分は0だが、
仕様の重みでは総合スコアが0.04下がる。この差を比較結果のregressionへ反映する。

## 5. Adapter Capability Manifest

```yaml
adapter_id: string
adapter_version: string
kind: test_result | coverage | static | contract | mutation | artifact | upstream
input_formats: array
output_record_types: array
capability:
  execution_result: boolean
  retry: boolean
  matrix: boolean
  flaky_history: boolean
  coverage_context: boolean
  artifact_hash: boolean
  source_refs: boolean
  redaction: boolean
known_limits: array
conformance_fixtures: array
profile_support:
  default: supported | partial | unsupported
  strict: supported | partial | unsupported
  release: supported | partial | unsupported
```

Any unsupported capability that affects AETE must become a soft gap, risk debt, or doctor finding.

## 6. Canonical Test Identity

```yaml
canonical_test_id: string
identity_components:
  framework: string
  package: string
  file: string
  classname: string
  name: string
  parameters: object
  matrix: object
aliases:
  - previous_id: string
    reason: rename | parameter_change | framework_migration | path_normalization
    valid_from: string
```

ID generation:

```text
canonical_test_id = <framework>:<normalized_file>::<classname>::<name>[::<stable_parameter_hash>]
```

Matrix values that do not change the logical test must be stored in `matrix`, not in `name`.

## 7. Retry / Matrix Aggregation

| Raw results | Aggregate status | Rule |
|---|---|---|
| all passed | stable_passed | deterministic success |
| pass after fail | flaky_passed | soft gap unless profile makes it hard |
| fail after pass | flaky_failed | hard or conditional depending profile |
| all failed | failed | evidence exists but contradicts claim |
| missing shard | inconclusive | soft gap or hard DQ for release profile |
| parser failure | adapter_failed | exit 1 or DQ based requiredness |

Aggregation key:

```text
canonical_test_id + normalized matrix group + run_attempt
```

The same input must produce the same aggregate status.

### 7.1 集約の順序と入力条件

集約の前に、解決済みrun ID・run attemptと各nodeの宣言を照合する。
対象はrun、gate_verdict、test、execution_evidence、coverage、contract_evidence、mutation_evidence、
evidence_strength、evidence_artifactのdata.run_id・data.run_attempt、およびrun.data.ciの同じ項目とする。
不正な型・番号、不一致はTrustError（終了コード1）で出力前に停止する。
run.data.ciが存在する場合はobjectであることを要求する。

metadata.commitSha、report.commit_sha、上記nodeのdata.commit_shaとrun.data.ci.commit_shaは、
有効なhex表記が宣言されている場合に大文字・小文字を区別せず一致を要求する。
有効なcommit同士の不一致は入力エラーとし、無効な文字列表記は従来どおりprovenanceの
high/blocking所見として保持する。commitの型がstringでない場合は入力エラーとする。
短縮IDと完全IDの同一性をprefix一致だけで推測しない。

旧bundleに任意のcommitShaやnode内識別項目がない場合、その値は追加しない。
既存のbundle/reportによるrun解決とprovenanceの不足判定を維持する。
escaped_defect等の履歴nodeに現在runを要求しない。P1a入力の重複JSON keyは読み込み時に診断する。

retry_index・attempt_index・retry_count・shard_indexは0以上のJSON整数、shard_total・shard_countは1以上の
JSON整数とする。原表記で確認し、boolean・数字文字列・端数を受け入れない。
retry_index/attempt_index、shard_total/shard_count、matrix/matrix_valuesの両方を宣言する場合は
値を一致させる。matrixはobject、flakyはbooleanとする。不正入力は出力前にTrustError(exit_code=1)で停止する。

集約は次の順に行う。

1. canonical test・各executionの実効matrix・run attemptでグループを作る。
   testのmatrixを既定値として各executionの値を反映し、別環境の値で他のexecutionを上書きしない。
   canonical identityを確定できないtest node同士はまとめない。
2. 同じexecutionを指す重複edgeを除き、同じcanonical testのnode aliasから来る証跡をまとめる。
   実行が未接続のtestもinconclusiveとして残す。曖昧な重複node IDを選択して利用しない。
3. retry_index順に、各retry内のshardを確認する。shard indexは0から期待件数−1までとし、
   同じretry・shardに複数executionがある場合はinconclusiveとする。
   期待件数の矛盾、shard番号の範囲外・欠損、期待件数不明もinconclusiveとする。
   別retryのshardを足して欠落を埋めない。期待件数分の配列を生成せず、実際の観測から欠落件数を求める。
4. 全shardが揃ったretryでは一つでもfailed/errorがあればそのretryをfailedとし、
   全てpassedの場合にpassedとする。並列shardをretry履歴として並べない。
5. 0から最終retryまでの連続した履歴を集約する。retry_index省略時の既定値は0であり、
   node ID順や配列順から連番を作らない。重複・欠測した順序、skipped・unknown等はinconclusiveとする。
   完全なpassed/failed履歴だけをstable_passed・failed・flaky_passed・flaky_failedに分類する。

retry_countが申告されている場合、少なくともその番号までの履歴が必要となる。
履歴が足りなければreported_retry_history_missingでinconclusiveとし、回数から架空の実行を作らない。
flaky=trueがあるのに手元の履歴で失敗と成功の両方を確認できない場合もinconclusiveとし、
declared_flaky_without_mixed_historyを残す。明示的な不安定性の申告を安定成功へ変更しない。
完全な履歴から確認できたflakyは従来のflaky_passed/flaky_failedとする。

aggregateのdeclared_flaky・declared_retry_count、およびsummaryのdeclared_flaky_countは申告値の記録である。
flaky_countは実際の完全な混在履歴から確認できた件数を示す。retry_attemptsにも各実行の
flaky/retry_countが宣言されていれば保持する。申告と履歴を照合できない場合のscore_confidenceはmediumとする。

retry_attemptsには正規化した実際の番号、attempt_resultsにはretry単位の結果、issuesには原因を残す。
shards.observedは全観測番号の一覧であり、完全性はretry単位で確認する。
retryのissuesはdoctorのretryカテゴリ（HATE-DOC-RETRY-001、medium）として記録し、
trust statusをpartialへ反映する。HATEの集約結果自体は最終release approvalを生成しない。

determinism_flakinessは同じ集約を根拠にする。

| 状態 | score |
|---|---:|
| testがない、確認されたflakyがある、または実行にflaky=trueの申告がある | 0 |
| 実行の未接続、retry/shardの欠測・曖昧性、reportのmissing_executionがある | 1 |
| 全グループの実行が判定可能で、反復成功の条件に達しない | 3 |
| 全グループで2回以上の完全なretryが全てpassed | 5 |

failedはテスト結果の失敗であり、完全な単一実行をそれだけで不安定と判定しない。
P1aは渡されたgraph上の証跡を評価するため、P0a/P0bの属性引継ぎ・重複record処理は別途検証が必要となる。

## 8. Path Normalization and Resolver

```yaml
artifact_resolver_map:
  schema_version: HATE/v1
  run_id: string
  entries:
    - original: string
      normalized: string
      root_kind: workspace | package | container | windows | url
      resolution_status: resolved | unresolved | unsafe
      source_refs: array
```

Rules:

- Windows separators become `/`
- absolute workspace paths become workspace-relative paths
- container paths must resolve to workspace or package root
- `..` traversal, symlink escape, and unsafe URL become `unsafe`
- unresolved path is a doctor finding and may become soft gap

## 9. Command Contracts

```text
HATE replay --bundle <bundle> --profile <profile>
HATE compare --base <bundle> --head <bundle>
hate explain --bundle <bundle> --report <report> --out <out> --mode why-excluded
HATE recommend --bundle <bundle> --gap <gap_id>
HATE doctor --fixture <path> --profile <profile>
```

Outputs:

| Command | Output |
|---|---|
| replay | `replay-report.json`, deterministic recalculation hash |
| compare | `compare-report.json`, trust delta / DQ delta / risk coverage delta |
| explain | `explain-report.json`, source-backed reason tree |
| recommend | `recommendation-report.json`, next evidence / test layer / manual bridge |
| doctor | `doctor-report.json`, adapter / schema / path / provenance / QEG findings |

## 10. Doctor Finding Taxonomy

| Category | Examples | Default severity |
|---|---|---|
| adapter | unknown dialect, partial parse | medium |
| schema | missing required, invalid enum | high |
| path | unresolved path, unsafe traversal | high |
| provenance | missing commit/run/hash | high |
| retry | missing retry/shard, ambiguous execution, flaky history | medium |
| qeg_fixture | unsupported claim, missing sourceRefs | high |
| artifact_safety | unsafe URL, secret scan fail | critical |
| profile | unsupported capability for profile | medium |

### 10.1 Graphの整合性とlineage

nodes・edges等の型不一致は入力エラーとし、出力前に停止する。
処理可能な公開QEGスキーマ違反はschemaのhigh/blocking所見へ記録する。
重複node ID、参照先の欠損・曖昧性、主要関係のnode種別不一致をqeg_fixture所見へ記録する。
P0bのgate_verdict→当該runのqeg_exportへのdecidesは、nodeを持たない正規の外部参照として扱う。
test→evidence_artifactとexecution_evidence→evidence_artifactのevidenced_byも
P0bの正規の添付参照として扱う。execution_evidence→execution_evidenceは許可しない。
添付への接続はtest→execution_evidenceの実行接続を代替せず、retry履歴にも数えない。

traceability_lineageは実在する関係に基づく。

| 状態 | score |
|---|---:|
| node/edgeの有効なsourceRefsがない | 0 |
| 参照元が不完全、graphに不整合、またはrisk→実在するtestの接続がない | 1 |
| risk→testは存在するが、要求された一部の実行が未接続、またはtest_placementが残る | 3 |
| 全sourceRefsとgraphが有効で、宣言された全テスト要求に実行証跡が接続されている | 5 |

無関係なexecution nodeの存在だけを接続の根拠にしない。
dimension signalにはgraphの整合性、全テスト要求の実行接続、未実行の参照先を含める。
change_relevanceの高得点には実在するchanged_code→riskのtouchesも必要とする。
これは証跡の評価であり、最終release approvalを意味しない。

## 11. Fixture Contract

```text
fixtures/trust/
  aete-score-minimal/
  aete-score-low-confidence/
  retry-matrix-flaky/
  retry-matrix-stable/
  canonical-identity-rename/
  path-normalization-windows/
  path-normalization-container/
  replay-deterministic/
  compare-trust-delta/
  explain-soft-gap/
  recommend-manual-bridge/
  doctor-path-unsafe/
```

Each fixture must include:

- `input/`
- `expected/`
- `README.md` with purpose and oracle
- source refs to this contract and `SPECIFICATION.md`

## 12. Shipyard Acceptance

| Stage | Required evidence |
|---|---|
| plan | P1a task packet references this contract |
| dev | AETE, identity, resolver, command modules changed |
| acceptance | fixture results for aete, retry, identity, path, replay, doctor |
| integrate | QEG export and risk debt references remain consistent |
| publish | no release approval emitted by HATE |

## 13. Go Criteria

RanD KanoMode can treat P1a trust hardening specification as `go` when:

- AETE schema, dimension score table, and metadata are specified
- adapter capability and profile support are specified
- canonical identity and aggregation rules are specified
- replay / compare / explain / recommend / doctor command contracts are specified
- fixture tree and failure taxonomy are specified
- implementation completion remains gated by executable fixture results

## 14. 未実行を実行根拠へ数えない（FIX-104）

既存bundleでもwouldRun=trueはstatus=passedに優先する。retry集約ではinconclusiveと
test_not_executed所見へ接続し、通常の成功やscore_confidence=highへ変えない。
実行結果のないexecution nodeはoracle_strength・cross_signal_corroborationの実行信号や、
traceability_lineageの実行要件充足に数えない。構造上のedgeと観測recordは保持する。
より重大な既存所見によるlow判定は優先する。

5入口でtest/execution dataのstatus/source_statusとwouldRunの宣言型を出力前に検証する。
不正値は位置付きTrustError(1)とし、元bundleと以前の成果物を保持し、新規出力先を作成しない。
P0bが生成したmissing_executionは既存のexplain/recommend経路へ渡す。
元の状態だけから、reportに存在しない実行履歴・strict方針・リリース許可を補わない。
