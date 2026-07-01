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
| `static_finding` | yes | `schemas/HATE/v1/static-finding.schema.json` |
| `contract_evidence` | yes | `schemas/HATE/v1/contract-evidence.schema.json` |
| `mutation_evidence` | yes | `schemas/HATE/v1/mutation-evidence.schema.json` |
| `evidence_ref` | P0b | `schemas/HATE/v1/evidence-ref.schema.json` |
| `precheck_decision` | yes | `schemas/HATE/v1/precheck-decision.schema.json` |
| `audit_record` | yes | `schemas/HATE/v1/audit-record.schema.json` |
| `aete_score` | P1a | `schemas/HATE/v1/aete-score.schema.json` |
| `aete_signal_report` | P1a | `schemas/HATE/v1/aete-signal-report.schema.json` |
| `profile_report` | P1a | `schemas/HATE/v1/profile-report.schema.json` |
| `doctor_report` | P1a | `schemas/HATE/v1/doctor-report.schema.json` |
| `adapter_registry` | P1a | `schemas/HATE/v1/adapter-registry.schema.json` |
| `adapter_capability_manifest` | P1a | `schemas/HATE/v1/adapter-capability-manifest.schema.json` |
| `adapter_conformance` | P1a | `schemas/HATE/v1/p1a-adapter-conformance.schema.json` |
| `artifact_resolution` | P1a | `schemas/HATE/v1/artifact-resolver-map.schema.json` |
| `canonical_identity_index` | P1a | `schemas/HATE/v1/canonical-identity-index.schema.json` |
| `retry_aggregation` | P1a | `schemas/HATE/v1/retry-aggregation.schema.json` |
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

### 8.1 Common Envelope Validator

`src/hate/schema_validator.py` は adapter output を product claim に入れる前の境界である。
validator は `record_kind` を優先し、既存互換のため `record_type` を fallback として扱う。
`schema_version` は `HATE/v1` のみを受理し、record schema は
`schemas/HATE/v1/schema-registry.json` と同じ record kind matrix に従って dispatch する。

Envelope record は少なくとも次を持つ。

- `schema_version`
- `record_kind` または互換 field `record_type`
- `record_id`
- `producer`
- `parserVersion`
- `sourceRef` または `sourceRefs`
- `source_hash`
- `collected_at` または互換 field `created_at`
- `normalized_path_set`
- `diagnostics`
- `payload`

拒否分類:

| Code | Severity | Meaning |
|---|---|---|
| `missing_record_kind` | hard | `record_kind` / `record_type` がなく schema dispatch できない |
| `unknown_record_kind` | hard | registry が知らない record kind |
| `unknown_schema_version` | hard | `HATE/v1` 以外の schema version |
| `missing_source_ref` | hard | sourceRef/sourceRefs が envelope と payload のどちらにもない |
| `invalid_timestamp` | hard | collected_at/created_at がない、または ISO timestamp として読めない |
| `record_kind_schema_mismatch` | hard | record kind と payload/schema が一致しない |
| `schema_registry_missing_file` | hard | dispatch 先 schema file がない |
| `schema_validation_error` | hard | JSON Schema level の検証失敗 |
| `unredacted_secret` | hard | secret-like token が envelope/payload に残っている |

`schema-validation-report.json` は `accepted` / `rejected` count、`rejection_classes`、
`schema_versions`、record ごとの `sourceRefs` と findings を持つ。ログだけの validator は
不合格であり、hard finding は product-ready 判定へ渡せる構造化 report として残す。

### 8.2 Cross-Record SourceRef/Hash Validator

`src/hate/cross_record_validator.py` は envelope validation 後の records と artifact manifest を
横断し、sourceRef が bundle 内 artifact と整合していることを確認する。`src/hate/source_ref.py`
は Windows path、container path、workspace relative path を同じ `normalized_path` へ揃える。

sourceRef validator が hard rejection とする条件:

| Code | Severity | Meaning |
|---|---|---|
| `hash_mismatch` | hard | record の `source_hash` と artifact の `sha256` が一致しない |
| `missing_source_artifact` | hard | sourceRef が指す artifact/path が bundle に存在しない |
| `path_traversal_source_ref` | hard | sourceRef が `..`、絶対 path、外部 URL など bundle 外を指す |
| `coverage_refers_unknown_test` | hard | coverage context が存在しない canonical test id を参照する |
| `finding_refers_unknown_file` | hard | static finding の file が artifact manifest に存在しない |
| `non_deterministic_record_id` | hard | replay 必須 record の id が sourceRefs/payload から安定再計算できない |

cross-record section は `schema-validation-report.json.cross_record.violations[]` に
`violation_id`、`severity`、`affected_record_ids`、`relation_kind`、`expected`、`observed`、
`sourceRef` を持つ。hash mismatch や bundle 外参照は soft warning ではない。

## 9. Acceptance

- P0a record の 100% が schema registry で validate できる
- invalid fixture が期待通り fail する
- deprecated field が warning と replacement を持つ
- unknown field policy が record_type ごとに明示される
- QEG export schema が minimal fixture で互換検証できる
- schema change は migration guide または release note に残る
