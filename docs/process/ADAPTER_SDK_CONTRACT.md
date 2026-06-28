---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Adapter SDK Contract

## 1. 目的

HATE adapter を内部実装だけでなく、外部 contributor や enterprise customer が
追加できるようにする。Adapter SDK は ingestion / normalization の拡張点であり、
HATE precheck、QEG verdict、release approval を adapter が直接決めない。

## 2. Adapter Types

| Type | 入力 | 出力 |
|---|---|---|
| test-result | JUnit / Playwright / pytest / Vitest / Jest | `test_result` |
| coverage | LCOV / Cobertura / JaCoCo / coverage.py | `coverage_slice` |
| static | SARIF / tool-specific findings | `evidence_ref` / SARIF |
| artifact | trace / screenshot / video / log / report | `artifact-manifest.json` entries |
| contract | Pact / can-i-deploy | `contract` evidence |
| mutation | Stryker / mutation-testing-elements | `mutation` evidence |
| export | QEG / OTel / Allure / ReportPortal / Codecov | external output |

## 3. Adapter Manifest

各 adapter は `adapter.manifest.json` を持つ。

```json
{
  "adapter_id": "adapter_junit_v1",
  "name": "junit",
  "version": "1.0.0",
  "adapter_type": "test-result",
  "input_formats": ["junit-xml"],
  "output_record_types": ["test_result"],
  "capabilities": {
    "flaky": false,
    "retry": true,
    "matrix": false,
    "artifact_hash": false,
    "coverage_context": false,
    "redaction": false
  },
  "known_limits": [],
  "fixtures": [],
  "profile_support": ["default", "strict", "release"]
}
```

## 4. Required Interface

| Function | 必須 | 説明 |
|---|---|---|
| `detect(input)` | yes | 入力が adapter 対象か判定する |
| `parse(input)` | yes | source artifact を構造化する |
| `normalize(parsed, context)` | yes | common envelope record を生成する |
| `capabilities()` | yes | capability manifest を返す |
| `validate(records)` | yes | schema registry と整合するか検証する |
| `summarize(records)` | no | human summary 用の safe summary を返す |
| `explain(record_id)` | no | 採用 / 除外 / 欠損理由を返す |

## 5. Adapter Failure Contract

| Failure | Error code | 期待挙動 |
|---|---|---|
| input not found | HATE-CLI-002 | adapter 実行前に失敗 |
| unsupported format | HATE-ADP-001 | parse failed として exit 1 |
| malformed input | HATE-ADP-001 | source_refs 付きで失敗 |
| encoding error | HATE-ADP-001 | encoding hint を remediation に出す |
| partial parse | HATE-ADP-004 | partial records + warning または fail を profile で切替 |
| duplicate identity | HATE-ADP-003 | canonical_test_id / aliases を remediation に出す |
| capability missing | HATE-ADP-002 | hidden gap にせず summary / JSON に出す |
| unsafe artifact | HATE-ART-003 | quarantine し export から除外 |
| schema invalid output | HATE-SCH-001 | adapter failure として exit 1 |

## 6. Normalization Rules

- adapter は common envelope を必ず付ける
- `record_id` は deterministic に生成する
- test result は `canonical_test_id`, `identity_components`, `aliases` を可能な範囲で出す
- source path は path normalization 前の raw path と normalized path を区別する
- timestamp は run window と比較できる形式にする
- adapter が知らない情報を成功扱いで補完しない
- redaction / safety が未確認なら `redaction_status=pending` とする

## 7. Conformance Fixtures

各 adapter は最低限、次の fixture を持つ。

```text
fixtures/adapters/<adapter-id>/
  valid-minimal/
  valid-full/
  malformed/
  missing-required/
  duplicate-identity/
  retry-matrix/
  unsafe-artifact/
  expected/
```

## 8. Conformance Report

`adapter-conformance-report.json` は最低限次を持つ。

```json
{
  "adapter_id": "adapter_junit_v1",
  "adapter_version": "1.0.0",
  "schema_version": "HATE/v1",
  "capabilities_verified": [],
  "fixtures": [],
  "failures": [],
  "known_limits": [],
  "conformance_status": "passed|warning|failed"
}
```

## 9. SDK Stability

| Surface | Stability |
|---|---|
| manifest fields | semver |
| required interface | major change required |
| output schema | schema registry に従う |
| capability names | deprecated field policy に従う |
| fixture layout | minor 以上で変更 |

## 10. Acceptance

- adapter manifest が schema registry で validate できる
- required interface の全 function が存在する
- conformance fixtures が expected output と一致する
- capability missing が summary / JSON に明示される
- adapter failure が stable error code と remediation を持つ
- adapter は HATE precheck decision / QEG verdict を直接決めない
