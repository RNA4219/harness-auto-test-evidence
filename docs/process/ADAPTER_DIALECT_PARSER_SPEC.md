---
intent_id: INT-HATE-ADAPTER-DIALECT-PARSER-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Adapter Dialect Parser Specification

## 1. Purpose

This document defines parser dialect requirements for HATE adapters. A supported adapter must
include parser logic, dialect fixtures, malformed/partial cases, capability manifest, and
conformance results.

## 2. Dialect Matrix

| Adapter family | Dialects | Required cases |
|---|---|---|
| JUnit | Surefire, Gradle, pytest, Jest, Vitest, Playwright, Go junit | pass, fail, error, skipped, parameterized, malformed |
| pytest JSON | pytest-json-report, rerunfailures, xfail/xpass markers | json-only, junit+json merge, conflict, missing path |
| Jest JSON | nested suite, snapshot failure, todo, focused tests | snapshot-only, todo, malformed |
| Vitest JSON | browser/node env, retry, flaky, focused tests | node/browser matrix, malformed |
| Playwright | JSON, JUnit, trace attachments, screenshot/video/log | safe, secret, pii, missing, large |
| Coverage | LCOV, Cobertura, JaCoCo, coverage.py JSON/XML contexts | branch, context, windows path, partial, malformed |
| SARIF | SARIF 2.1.0, CodeQL-like, Sonar-like import | high/critical changed path, suppression, malformed |
| Pact | verification JSON, can-i-deploy summary | pass, failed required contract, version mismatch |
| Stryker | mutation report | killed, survived, timeout, no coverage, malformed |

## 3. Parser Output Requirements

Each parser emits:

- normalized records
- sourceRefs
- parser diagnostics
- capability report
- unsupported dialect warnings
- profile-aware failure impact

## 4. Failure Classes

| Class | Meaning | Required behavior |
|---|---|---|
| required_missing | required input absent | DQ or CLI failure |
| malformed_required | required input parse failure | DQ or CLI failure |
| malformed_optional | optional input parse failure | parserFailures visible |
| unsupported_dialect | dialect detected but not supported | doctor finding |
| partial | parse succeeded with missing optional fields | soft gap/warning |
| unsafe_artifact | artifact unsafe | quarantine/exclusion |

## 5. Conformance Requirement

Adapter conformance passes only when:

- all required dialect fixtures run
- malformed fixtures produce expected failure class
- capability manifest matches actual parser behavior
- sourceRefs are present
- profile impact is deterministic
- no fixture-name branch exists in production code

## 6. P0aの実行座標と識別（FIX-086〜089）

JUnit、pytest JSON、Vitest JSON、Jest JSONは、明示されたretry_index/attempt_index、
retry_count、matrix/matrix_values、shard_index、shard_total/shard_count、flakyを保持する。
JSONでは数値の原表記を確認して整数を判定し、boolean・数字文字列・端数を番号へ変換しない。
JUnitではtestcase属性とpropertyの十進表記を検証し、端数・負数を切り捨てない。
matrixのXML propertyはJSON object、flakyは明示的な真偽値（true/false等）として読む。
番号の範囲とaliasの一致条件は[P1a契約](P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md)と共通とする。

pytestのreruns、Vitest/JestのretryCountはretry_countへ保持する。Vitest/Jestはassertionと
metaの双方を確認し、同一項目の宣言が矛盾する場合は解析失敗とする。
retry回数からretry_indexやflaky=trueを作らない。番号付き履歴が不足していれば、P1aで
reported_retry_history_missingとして記録する。明示されたflaky=falseも省略しない。

JSON adapterのrecord IDはrun・framework・正規化payloadのSHA256全体・同一payloadの出現番号で
識別する。短いtest titleが同じでも、別ファイル・retry・frameworkのrecordを重ねない。
同じpayloadが複数回現れる場合も各観測を残し、P1aがretry/shard座標の重複を診断できるようにする。
IDを確定してからenvelopeのhashを計算する。既存JUnitのindex付きrecord IDは維持する。

JUnitのduplicate診断はcanonical test・matrix・retry番号・shard番号が同じ観測に限定する。
異なるretry/matrix/shardをduplicate_testcase_idとしない。重複した座標のrecordだけに診断を付ける。

存在するtest reportの解析失敗は、他のtest adapterが成功してもHATE-DQ-002へ残す。
このP0a入力ではhard DQ（終了コード2）とし、qeg_export_allowed=falseを出力する。
未指定reportは空の結果を返すため、JSONだけ・JUnitだけの実行は従来どおり利用できる。

この節の修正は明示された実行属性とrecordの識別を対象とする。
test identity・durationの型検証は次節に従う。各dialectの追加メタデータ、
JUnitとJSONの異なるframework表記の統合は別途確認する。

## 7. テスト識別値と実行時間（FIX-101〜102）

pytestのnodeid、JUnit testcaseのname、Vitest/Jestのsuite.nameとfullNameは、空白だけでない文字列とする。
null・boolean・数値・配列・objectを文字列化してcanonical test IDを作らない。
JUnitのname欠落時もcase_1等の仮名を作らず解析失敗とする。JSONのfullName省略時には既存のtitleを使える。
titleは宣言された場合に文字列、ancestorTitlesは宣言された場合に文字列配列とし、要素の型も確認する。
空のtitleは非空fullNameがある場合に保持し、Unicode名・parameterized名の内容を勝手に書き換えない。
JUnitの任意のfile/classname省略時の既存推定は維持する。framework間での同一test照合の完了を意味しない。

durationは有限かつ0以上の数値とする。JSONのboolean・数字文字列・非数値objectを拒否し、
JUnitのtimeはASCIIの十進表記として検証する。不正なXML値を0へ置き換えない。
負数はミリ秒へ丸める前に拒否し、-0.0001等が0として通過する経路をなくす。
扱える数値範囲は有限floatとして表現でき、非ゼロ値が0へunderflowしない範囲とする。
値の判定・単位変換には元の十進表記を使い、大きな整数や丸め境界でbinary floatの誤差を持ち込まない。
JUnit/pytestは秒、Vitest/Jestはミリ秒として読み、最終duration_msだけを最近接整数へ丸める。
ちょうど半分の場合は偶数丸めとし、従来のJUnit/pytestの丸め方式を維持する。

pytest-json-reportの標準形式にあるsetup/call/teardown.durationは、記録されたstage分を秒で合算し、
最後に一度だけミリ秒へ丸める。test直下のdurationが宣言されている既存形式ではその値を優先し、
stage時間を二重加算しない。この場合も宣言されたstageの型・時間の不正は見逃さない。
stage objectやdurationが省略された場合に、報告されていない実行時間を推測して追加しない。

Vitest/Jestの標準形式で許容されるduration=nullは解析失敗とせず、duration_not_reportedのwarningを残す。
必須整数duration_msには互換用の0を使い、診断のmessageに未報告値の代替であることを記す。
P0bはparser_diagnosticsをexecutionごとに保持し、観測が一つのtestにも同じ診断を保持する。
duration自体が省略された既存入力では、従来の既定値0を維持する。

不正な識別値・実行時間はファイルと項目位置付きのparser failureとし、P0aでHATE-DQ-002・
hard DQ（終了コード2）へ接続する。他のtest adapterが成功しても相殺せず、P0bへの正式exportを禁止する。
公開parse_junit_xmlは値エラーでもtests=[]とparser_diagnostics.errorを返す。
`tests/test_p0a_test_values.py`、既存のdialect corpus、配布wheel smokeで検証する。

標準形式の根拠（2026-09-10確認）:

- [pytest-json-reportのtest stage](https://github.com/numirias/pytest-json-report#test-stage)
- [Jest AssertionResultのduration型](https://github.com/jestjs/jest/blob/main/packages/jest-types/src/TestResult.ts)
- [Vitest JsonAssertionResultと時間の単位](https://github.com/vitest-dev/vitest/blob/main/packages/vitest/src/node/reporters/json.ts)

## 8. 元の状態と未実行の保持（FIX-103〜104）

pytest JSONのoutcome、Jest/Vitestのstatusは、宣言がある場合に非空文字列を要求する。
元の値をsource_statusへ保持し、未指定・未知の文字列はinconclusiveとwarningにする。
pytestのxfail/xfailedはskippedとxfail=true、xpass/xpassedはpassedとxfail=true・xpass=trueにする。
non-strictなxpassを独自にfailedへ変えず、strict設定等によって元からfailedの結果はfailedのまま扱う。
stageのoutcomeと最終outcomeは異なり得るため、両者の単純な一致を要求しない。
Jest/Vitestのpending・todo・disabledはskipped、focusedはinconclusiveへ変換し、todo/onlyの印を残す。

wouldRunは、宣言がある場合にbooleanを要求してfalseも保存する。trueは実行候補として収集された
未実行の宣言であり、元statusがpassedでもinconclusiveとtest_not_executedのwarningにする。
元の値・印・診断をP0bのexecutionへ引き継ぎ、duration_not_reported等の診断とも併存させる。
不正な型は他のadapterの成功で相殺せず、位置付きHATE-DQ-002（終了コード2）にする。

skipped・inconclusive等のrecordは観測記録として保存するが、必要な実行結果の代わりには数えない。
明示されたpassed/failed/error/flakyかつwouldRunがtrueでない観測の存在をP0b/P1aで共通判定する。
この実行要件の充足は、テスト成功やQEGのリリース承認を意味しない。
`tests/test_execution_outcomes.py`と配布wheel smokeで検証する。

状態の根拠（2026-09-10確認）:

- [JestのwouldRun宣言と状態型](https://github.com/jestjs/jest/blob/main/packages/jest-types/src/TestResult.ts)
- [pytest-json-reportの最終outcome生成](https://github.com/numirias/pytest-json-report/blob/master/pytest_jsonreport/plugin.py)
- [VitestのJSON状態型](https://github.com/vitest-dev/vitest/blob/main/packages/vitest/src/node/reporters/json.ts)
