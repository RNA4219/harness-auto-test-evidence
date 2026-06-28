---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Schema Registry Contract

## 1. 目的

HATE の JSON / NDJSON / bundle / report schema を、実装者・adapter 作者・QEG 連携先が
同じ契約として検証できるようにする。Schema registry は QEG の schema hardening を
再実装せず、HATE が生成する optional evidence の互換性を保つための前段契約である。

## 2. Scope

### In

- `HATE/v1` JSON Schema
- common envelope
- record_type ごとの required / optional / nullable / default
- additionalProperties policy
- deprecated field policy
- fixture compatibility matrix
- QEG export compatibility metadata

### Out

- QEG 本体 schema migration の正本
- release Gate policy
- waiver / approval schema
- external SaaS の独自 schema

## 3. Registry Artifact

`schema-registry.json` は最低限次を持つ。

```json
{
  "schema_version": "HATE/v1",
  "registry_version": "2026-06-28",
  "records": [],
  "bundles": [],
  "compatibility": {},
  "deprecated_fields": [],
  "qeg_export": {}
}
```

## 4. Record Schema Matrix

| record_type | P0 必須 | Schema artifact |
|---|---|---|
| `run` | yes | `schemas/HATE/v1/run.schema.json` |
| `test_result` | yes | `schemas/HATE/v1/test-result.schema.json` |
| `coverage_slice` | yes | `schemas/HATE/v1/coverage-slice.schema.json` |
| `evidence_ref` | P0b | `schemas/HATE/v1/evidence-ref.schema.json` |
| `precheck_decision` | yes | `schemas/HATE/v1/precheck-decision.schema.json` |
| `audit_record` | yes | `schemas/HATE/v1/audit-record.schema.json` |
| `aete_score` | P1a | `schemas/HATE/v1/aete-score.schema.json` |
| `risk_debt` | P1a | `schemas/HATE/v1/risk-debt.schema.json` |

Bundle / report schema:

| artifact | Phase | Schema artifact |
|---|---|---|
| `artifact-manifest.json` | P0a | `schemas/HATE/v1/artifact-manifest.schema.json` |
| `qeg-bundle.json` | P0b | `schemas/HATE/v1/qeg-bundle.schema.json` |
| `product-readiness-report.json` | P2 | `schemas/HATE/v1/product-readiness-report.schema.json` |

## 5. Field Policy

| Field type | Policy |
|---|---|
| required | missing なら schema invalid |
| optional | 欠損可。summary では欠損を成功扱いしない |
| nullable | `null` の意味を schema description に必ず書く |
| default | producer が明示し、consumer は暗黙補完しない |
| unknown | P0a は保持可。P1a 以降は record_type ごとに allow / warn / reject を固定 |
| deprecated | `deprecated_since`, `remove_after`, `replacement` を持つ |

## 6. Version Policy

| Change | Version impact | Required action |
|---|---|---|
| optional field 追加 | minor | fixture 追加 |
| enum value 追加 | minor または major | consumer impact を明記 |
| required field 追加 | major | migration guide 必須 |
| field rename | major | alias window と deprecated field 必須 |
| semantic change | major | replay compatibility note 必須 |
| typo / description 変更 | patch | release note |

`schema_version` は record の構造互換性を示し、`registry_version` は registry artifact の
発行単位を示す。AETE rubric や profile の version と混同しない。

## 7. Fixture Matrix

| Fixture type | 目的 |
|---|---|
| valid-minimal | required field だけで通る |
| valid-full | optional field を含めて通る |
| invalid-missing-required | required 欠損で落ちる |
| invalid-enum | enum 不正で落ちる |
| invalid-additional-property | unknown field policy を検証する |
| deprecated-field | deprecated warning と replacement を検証する |
| qeg-compat | QEG minimal import と互換 |

## 8. CLI / Validation

推奨 command:

```text
HATE schema validate --record HATE-run.json
HATE schema validate --bundle qeg-bundle.json
HATE schema diff --from HATE/v1 --to HATE/v1.1
HATE schema explain --field precheck_decision.payload.decision
```

## 9. Acceptance

- P0a record の 100% が schema registry で validate できる
- invalid fixture が期待通り fail する
- deprecated field が warning と replacement を持つ
- unknown field policy が record_type ごとに明示される
- QEG export schema が minimal fixture で互換検証できる
- schema change は migration guide または release note に残る
