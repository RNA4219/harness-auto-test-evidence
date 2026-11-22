---
intent_id: INT-HATE-P0B-QEG-EXPORT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# P0b QEG Export Implementation Contract

## 1. 目的

P0b は、HATE が QEG optional evidence producer として成立するための最小 export 層である。
P0a の run / test / coverage / artifact / precheck / record を入力にし、
`qeg-bundle.json`, `evidence-map.json`, `diff-risk-test.json` を生成する。

HATE は QEG の Gate policy、waiver、approval、retention、immutability、schema migration、
source-backed Gate reason を実装しない。P0b の目的は、QEG が検証できる source-backed
optional evidence を出すことであり、release verdict を出すことではない。

## 2. 入力

| Input | Required | Source | Purpose |
|---|---:|---|---|
| `HATE-run.json` | yes | P0a | run provenance |
| `HATE-test-results.ndjson` | yes | P0a | canonical test nodes |
| `HATE-coverage.ndjson` | yes | P0a | coverage evidence nodes |
| `artifact-manifest.json` | yes | P0a | sourceArtifactIds / safety |
| `precheck-decision.json` | yes | P0a | evidence eligibility |
| `record.json` | yes | P0a | own-output validation |
| `diff-risk-test.json` | yes | code-to-gate / fixture | changed risk -> required test obligations |
| `HATE-static.sarif` | optional | SARIF adapter | finding / risk nodes |
| Playwright trace/screenshot/video/log refs | optional | Playwright adapter | artifact-backed execution evidence |

P0a `precheck-decision.payload.decision` が `hard_dq` の場合、正式な QEG import 用
`qeg-bundle.json` は生成しない。診断用に生成する場合は `metadata.debugOnly=true` とし、
summary に release input 不可を明記する。
現行CLIは診断用bundleも生成せず、不許可の場合は終了コード2とする。
`ineligible`を含む許可条件全体は2.3節に従う。

### 2.1 test-resultの複数実行（FIX-083〜084）

同じcanonical_test_idのrecordは1つのtest nodeへ接続する。retry・matrix・shardが異なる実行は
別々のexecution_evidence nodeとし、各recordのstatus、duration_ms、retry_index/attempt_index、retry_count、
matrix/matrix_values、shard_index、shard_total/shard_count、flakyを保持する。
test nodeには共通のidentity情報を残す。同じcanonical IDでframework・file・identity_components等の
宣言が矛盾する入力は、どちらかを採用せずExportError（終了コード1）とする。

- 単一観測のtest・execution IDは従来どおり。同一testに複数観測がある場合はexecution IDへ
  正規化recordのSHA256全体を追加する。入力順序に依存せず、同じ正規化recordの再掲は一度だけ数える。
- record_idが同じでも内容の異なるrecordは別の実行として残す。retry/shard座標の重複はP1aが
  inconclusiveとして診断する。各executionにsource_record_id（入力にある場合）と
  source_record_sha256を保持する。後者はalias・整数を正規化したrecordを、sort_keys=true、
  ensure_ascii=false、空白なしのJSONとしてUTF-8でSHA256計算した値であり、元ファイルの実バイトhashではない。
- 複数観測のtest.statusは全観測が同じstatusならその値、異なる場合はinconclusiveとする。
  duration_msは各executionで保持し、複数観測をまとめたtest nodeには単一実行の所要時間を置かない。
- test-resultのJSON構文・UTF-8・record/payloadのobject形式・canonical ID・実行座標の型とaliasを
  出力前に検証する。不備はファイル名・行番号付きExportError（終了コード1）とし、既存出力を保持する。
  番号の数値文字列・boolean・端数を拒否し、JSONの原表記で整数を判定する。
  matrixはobject、flakyはbooleanとする。非有限値・floatの範囲を超える数値も読み込み時に診断する。

この契約はP0bに届いたrecordを対象とする。P0aの明示的な実行属性の抽出とflaky申告の解釈は
[adapter契約](ADAPTER_DIALECT_PARSER_SPEC.md)およびP1a契約を参照する。

### 2.2 現在runの識別情報（FIX-090〜092）

HATE-run.jsonを基準とし、test-result、coverage、contract、mutation、evidence-strengthの各record、
precheck-decision、audit record、artifact manifestのrun_id・run_attempt・commit_shaを照合する。
これらは既存HATE/v1 schemaの必須項目であり、欠落を現在runの値で補わない。
run_idは空白だけでないstring、run_attemptは原表記で1以上のJSON整数、commit_shaは7〜64文字のhexとする。
commit比較は大文字・小文字を区別せず、短縮IDと完全IDをprefixだけで同一と推定しない。
出力時の文字表記は元の宣言を保持し、run_attemptは整数へ正規化する。

run payloadのciに同じ識別項目が宣言されていれば照合する。diff-risk-testの識別項目と、
native SARIFのrootに追加されたHATE識別項目も、存在する場合に照合する。
履歴資料であるrisk debt lifecycleやescaped defectsの過去runには現在runの値を要求しない。
SARIFのnative run構造や各payloadの全属性について、同一性を検証済みとするものではない。

不一致・欠落・型や形式の不正は出力前にExportError（終了コード1）とする。
照合診断にはファイル名とrecord indexを、NDJSONの構文診断には物理行番号を含める。
P0bのJSON/NDJSON readerは文字コード・読込・JSON object形式の失敗もExportErrorへ変換する。
重複したJSON object keyは同じ値であっても拒否し、後の値で識別情報を隠さない。

検証済みrunのcommit_shaをQEG metadata.commitShaへ、各test-resultのcommit_shaをexecution_evidenceへ
保持する。P1aはbundle・report・現在runのnodeにある宣言を照合できる。
これらの宣言とhashだけでは実体の検証・改ざん耐性の証明にはならない。

### 2.3 precheckのexport許可（FIX-093）

precheck payloadのdecision、exit_code、dq_hits、soft_gaps、reasons、qeg_export_allowedは必須とする。
decisionは既存schemaの4値、exit_codeはJSON整数値の0または2、qeg_export_allowedはboolean、
dq_hitsとsoft_gapsはobjectの配列、reasonsはstringの配列として検証する。
未知のdecision、欠落、型不一致は位置付きExportError（終了コード1）とする。
exit_codeは元のJSON十進表記で検証し、booleanや数値文字列、丸めで0・2になる端数を受け入れない。

正式なexportには次のすべてを必要とする。

- decisionが`eligible`または`conditional`
- qeg_export_allowedが`true`
- exit_codeが`0`
- dq_hitsが空配列

形式検証後、1つでも不許可条件があればExportError（終了コード2）とし、
CLIのstderrへdecisionとreasonのJSONを返す。矛盾する許可宣言で拒否条件を打ち消さない。
従来のhard_dq診断JSONは維持する。形式不備・不許可のどちらでも、新しい出力先を作らず、
既存のbundle・report等の内容とファイル集合を保持する。
conditionalのsoft_gapsは許可を取り消す条件にしない。HATEのexport許可は外部QEGのrelease承認ではない。

`tests/test_p0b_precheck.py`で許可条件の全32組合せ、必須項目・型・数値原表記、
API/CLIの診断と成果物保持を検証する。配布wheelのCLIでも不許可・不正形式を確認する。

### 2.4 precheckのsoft gap引継ぎ（FIX-094）

HATE precheckのgate_verdict.dataへ、元payloadのdq_hits・soft_gaps・reasonsを保持する。
soft gap objectの拡張項目も捨てず、理由とprofile・artifact等の文脈をQEG bundleから参照できるようにする。
summaryにはconditionalまたはgapの申告がある場合に件数を表示する。

soft gapだけではexportを禁止しない。任意のgapをparser failure・missing execution・risk debtへ
読み替えず、種類に根拠のないcompleteness減点も追加しない。P1aはbundleに残したgapを
信頼度・doctor・説明・補完提案へ接続する。詳細はP1a契約4.1節を参照する。

### 2.5 生成bundleのschema検証と保存（FIX-098）

生成したqeg-bundleは、既存の公開QEG compatibility schemaに適合した場合にのみ保存する。
検証結果がvalid=falseの場合はExportError（終了コード1）とし、正式なbundleやreportを生成しない。
CLIはHATE-E-EXPORTと、生成bundleの項目位置・期待する型などをstderrへ返す。
表示は先頭8件と残件数に制限し、APIのExportError.report.qeg_schema_compatibilityには全エラーを保持する。

出力先のmkdirと全成果物の書込みを検証後へ移す。schema不適合を検出した場合は、新しい出力先を作らず、
既存のbundle・evidence map・report・risk debt・manual bridge・summaryの内容とファイル集合を保持する。
成功/partialの区分はevidence completenessの既存契約に従う。schemaに適合するpartial exportを禁止しない。
内部validatorの予期しない例外を、入力エラーや成功結果に置き換える一律捕捉はしない。

この節の保証は書込み開始前のschema不適合検出が対象である。補助成果物の生成については次節に従う。
書込み中のI/O障害について複数成果物を一括復元する仕組みではなく、残る入力payloadの検証完了も意味しない。
`tests/test_p0b_output_validation.py`とwheel smokeで不適合の診断・既存成果物保持・
新規ディレクトリー未作成・有効なpartial出力・内部例外の伝播を検証する。

### 2.6. 補助成果物の生成と再実行

risk debtとmanual bridgeを含む全成果物の構築・JSON化・UTF-8への変換可否の検証を、
mkdirや最初のファイル書込みより前に完了する。JSON化できない値・非有限数・UTF-8化できない文字列は、
対象の出力ファイル名と原因を含むExportError（終了コード1）にする。構築処理の予期しない内部例外は伝播する。
この段階で失敗した場合、既存の成果物の内容・ファイル集合を保持し、新しい出力先を作らない。

任意入力risk-debt-lifecycle.jsonのitemsはobject配列とし、省略時は空配列として扱う。
各項目のage_daysは省略可能な0以上の整数値で、未指定時の既存の既定値0を維持する。
boolean・数字文字列・null・負数・端数を拒否し、8.0等は整数8へ正規化する。
十進表記を使って端数や大きな整数の丸めを防ぎ、入力ファイルを書き換えない。
不正時はファイル名と$.items[index].age_days等の位置を含むExportError（終了コード1）で止める。
この形式検証は現在のmissing executionがない場合や過去のdebtにも適用するが、履歴のrunを現在runへ付け替えない。

出力先直下のrisk-debt-register.jsonとmanual-bb-bridge-requests.jsonlは、現在のmissing executionが
ある場合だけ生成する。再実行でmissing executionが0になった場合は、新しい成果物の書込み後に
この2ファイルを除去する。他のgapによるpartial exportでも同じ規則とし、generatedと実際の補助成果物を一致させる。
別名のファイル・サブディレクトリー内の履歴・入力lifecycleは除去しない。debtの解消・承認を自動判定する処理ではない。

書込み・旧ファイル除去の途中のI/O障害に対する一括復元や、並行writer間の排他はこの修正の対象外である。
成功結果を返さず診断するが、途中まで更新された出力が残り得る。
`tests/test_p0b_output_lifecycle.py`とwheel smokeで再実行・生成失敗・型と数値原表記・出力保持を検証する。

## 3. 出力

| Output | Required | Role |
|---|---:|---|
| `qeg-bundle.json` | yes | QEG import bundle |
| `evidence-map.json` | yes | risk / requirement / test / evidence の中間graph |
| `diff-risk-test.json` | yes | code-to-gate risk と HATE evidence obligation の接続 |
| `qeg-export-report.json` | yes | export validation / unsupported claims / completeness |
| `qeg-export-summary.md` | yes | public-safe summary |

## 4. `qeg-bundle.json` Contract

```yaml
metadata:
  qegVersion: string
  runId: string
  runAttempt: number
  createdAt: ISO-8601
  profile: lean | standard | strict | ipo_controlled
  inputArtifacts: array[artifact_ref]
  debugOnly: boolean
nodes: array[node]
edges: array[edge]
completeness:
  score: number
  partial: boolean
  parserFailures: array
  unsupportedClaims: array
  excludedArtifacts: array
```

### 4.1 Node ID Rules

| Node kind | ID format | Source |
|---|---|---|
| requirement | `requirement:<stable-id>` | RanD / manual-bb / fixture |
| acceptance_criterion | `acceptance:<stable-id>` | RanD / workflow acceptance |
| changed_code | `changed_code:<path>#L<start>-L<end>` | diff-risk-test |
| risk | `risk:<risk-id>` | code-to-gate / SARIF |
| test | `test:<canonical_test_id_hash>` | HATE-test-results |
| execution_evidence | `execution:<run_id>:<canonical_test_id_hash>` | HATE-test-results |
| coverage | `coverage:<path_hash>` | HATE-coverage |
| evidence_artifact | `artifact:<artifact_id>` | artifact-manifest |
| gate_verdict | `hate_precheck:<run_id>:<run_attempt>` | precheck-decision |

### 4.2 Edge Rules

| Edge kind | Required | Meaning |
|---|---:|---|
| `derives_from` | conditional | requirement -> acceptance |
| `touches` | yes when diff exists | changed_code -> risk |
| `requires_test` | yes when risk has obligation | risk -> test or test_placement |
| `evidenced_by` | yes | test -> execution_evidence |
| `supports` | yes when evidence supports risk/requirement | evidence -> risk / acceptance |
| `contradicts` | conditional | SARIF / failure -> claim |
| `decides` | yes | hate_precheck -> qeg export eligibility |

Every edge must have:

```yaml
traceability:
  sourceRefs: non-empty array
  confidence: low | medium | high
  assumptions: array
```

## 5. `evidence-map.json` Contract

`evidence-map.json` は QEG bundle より実装寄りの中間表現である。

```yaml
schema_version: HATE/v1
run_id: string
run_attempt: number
requirements: array
risks: array
tests: array
evidence: array
links:
  requires_test: array
  evidenced_by: array
  supports: array
  contradicts: array
gaps:
  unsupported_claims: array
  missing_execution: array
  missing_coverage: array
  unsafe_artifacts: array
```

No hidden gap is allowed. If a changed high-risk path has no execution evidence, it must appear in
`gaps.missing_execution` and either `risk-debt-register.json` or `manual-bb-bridge-requests.jsonl`.

## 6. `diff-risk-test.json` Contract

```yaml
schema_version: HATE/v1
source_tool: code-to-gate | fixture | manual
commit_sha: string
changed_entities:
  - entity_id: string
    path: string
    ranges: array
    risk_refs: array
risks:
  - risk_id: string
    severity: low | medium | high | critical
    title: string
    required_test_layers: array
    source_refs: array
test_obligations:
  - obligation_id: string
    risk_id: string
    expected_test_refs: array
    required_evidence_kinds: array
```

P0b fixture では、少なくとも high-risk changed path 1 件、required test 1 件、
evidence present 1 件、evidence missing 1 件を含める。

## 7. Completeness Calculation

P0b completeness score は QEG verdict ではない。HATE export の充足度である。

```text
base = 1.0
- 0.20 if required artifact missing
- 0.15 per parser failure affecting required evidence
- 0.10 per unsupported high-risk claim
- 0.10 if path normalization incomplete
- 0.10 if artifact safety excludes required evidence
floor at 0
```

`partial=false` にできる条件:

- required P0a artifact がすべて存在
- precheck decision が `eligible` または `conditional`
- required sourceRefs が non-empty
- high-risk changed path の missing execution が 0、または manual bridge / risk debt に接続済み
- unsafe artifact が export から除外済み

## 8. Fixture Contract

```text
fixtures/golden/p0b-qeg-minimal/
  input/
    p0a/
      HATE-run.json
      HATE-test-results.ndjson
      HATE-coverage.ndjson
      artifact-manifest.json
      precheck-decision.json
      record.json
    diff-risk-test.json
    HATE-static.sarif
    artifacts/
  expected/
    qeg-bundle.json
    evidence-map.json
    qeg-export-report.json
    qeg-export-summary.md
```

Negative fixtures:

| Fixture | Expected |
|---|---|
| `missing-source-ref` | export report unsupported claim |
| `missing-required-artifact` | `hard_dq` or export failure |
| `unsafe-artifact-required` | quarantine + partial export |
| `high-risk-no-execution` | risk debt + manual-bb bridge |

## 9. CLI Contract

```text
HATE export qeg --fixture fixtures/golden/p0b-qeg-minimal/input --out .hate/out/p0b
HATE qeg validate --bundle .hate/out/p0b/qeg-bundle.json
HATE qeg explain --bundle .hate/out/p0b/qeg-bundle.json --unsupported
```

Exit codes:

| Exit | Meaning |
|---:|---|
| 0 | valid export |
| 1 | CLI / parser / schema failure |
| 2 | HATE hard DQ or required evidence not exportable |

## 10. Shipyard Acceptance

| Stage | Required evidence |
|---|---|
| plan | task packet references this contract and `SPECIFICATION.md#13` |
| dev | changed paths include qeg exporter, schemas, fixtures |
| acceptance | qeg export command, validation result, manual-bb gap review |
| integrate | QEG compatibility report and no reimplementation assertion |
| publish | release candidate may reference qeg export, but HATE does not approve release |

## 11. Go Criteria

RanD KanoMode can treat P0b QEG export specification as `go` when:

- this contract exists and is referenced by `SPECIFICATION.md`
- fixture tree, output schema, failure behavior, and CLI contract are specified
- No-Go triggers are explicit
- HATE/QEG responsibility boundary is explicit
- implementation completion remains gated by actual generated artifacts

## 12. 実行要件と観測の区別（FIX-104）

expected_test_refsは明示canonical test IDで照合し、従来の無prefixなJUnit参照も受け付ける。
frameworkを越えた同名testの推定照合はしない。対応するtest nodeが存在しても、そこへ結ばれた
execution_evidenceにpassed/failed/error/flakyかつwouldRunがtrueでない観測が必要となる。
skip・収集のみ・未知の状態ではmissing_executionを残し、partial・risk debt・manual bridgeへ接続する。
testとrequires_test edge、未実行の観測自体は保持する。実行済みの観測も存在する場合は実行要件を満たす。
failed/errorによる実行要件の充足はテスト成功を意味せず、品質の最終判断はQEGに委ねる。

payloadのstatus/source_statusは宣言時に非空文字列、wouldRunはbooleanを要求する。
不正な宣言は入力ファイル・行・項目付きExportError(1)とし、出力作成・上書き前に停止する。
元の状態、期待失敗等の印、wouldRun、parser_diagnosticsをexecution dataへ保持する。
