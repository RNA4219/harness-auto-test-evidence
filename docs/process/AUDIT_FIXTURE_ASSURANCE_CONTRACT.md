---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Audit Fixture and Assurance Contract

## 1. 目的

HATE の audit fixture、assurance pack、auditor walkthrough、evidence room の
契約を定義する。成熟プロダクトでは、顧客や監査担当が「同じ入力から同じ判断を
再計算できる」ことを、説明資料ではなく fixture と証跡で確認できる必要がある。

この文書は audit readiness の契約であり、QEG の Gate policy、waiver、approval、
immutability 正本を置き換えない。

## 2. 原則

- audit fixture は synthetic / redacted / safe-to-share を既定とする
- fixture は expected output、verification command、source contract を持つ
- auditor walkthrough は canonical evidence を改変せず再計算する
- assurance pack は customer source code、secret、PII、unsafe artifact を含まない
- audit finding は owner、due date、source_refs を持つ

## 3. Audit Fixture Set

| Fixture | 目的 | Source contract |
|---|---|---|
| p0a-golden | 最小 local-first precheck | `P0A_GOLDEN_PATH.md` |
| qeg-export-minimal | QEG optional evidence compatibility | `BLUEPRINT.md` |
| privacy-quarantine | unsafe artifact leak prevention | `PRIVACY_QUARANTINE_CONTRACT.md` |
| schema-migration | deprecated / breaking change validation | `SCHEMA_REGISTRY_CONTRACT.md` |
| adapter-conformance | adapter minimum compliance | `ADAPTER_SDK_CONTRACT.md` |
| incident-sev1 | incident record / containment / postmortem | `SLO_INCIDENT_RESPONSE_CONTRACT.md` |
| trust-packet | security review evidence | `SECURITY_REVIEW_TRUST_CONTRACT.md` |
| residency-profile | deployment / region / data routing | `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` |
| telemetry-privacy | prohibited signal blocking | `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` |
| accessibility-localization | stable id and color-only status check | `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` |
| commercial-commitment | overcommit and exception handling | `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` |

## 4. Fixture Manifest

```json
{
  "schema_version": "HATE/v1",
  "record_type": "audit_fixture_manifest",
  "fixture_id": "audit-p0a-golden",
  "fixture_version": "2026.06",
  "source_contracts": ["P0A_GOLDEN_PATH.md"],
  "input_refs": [],
  "expected_output_refs": [],
  "verification_commands": [],
  "safe_to_share": true,
  "redaction_status": "not_required|redacted|failed",
  "owner": "string",
  "next_review_due": "2026-07-28"
}
```

## 5. Assurance Pack

| Artifact | 目的 |
|---|---|
| audit-fixture-manifest.json | fixture 一覧と source contract |
| auditor-walkthrough.md | 再計算手順 |
| expected-output-index.json | expected artifacts / hashes |
| verification-log.jsonl | fixture 実行結果 |
| evidence-room-index.json | 提出可能 artifact と access policy |
| audit-finding-register.json | finding / owner / due date |
| assurance-summary.md | scope、limitations、open finding |

## 6. Evidence Room Rules

- access は auditor / security reviewer / support owner に限定できる
- artifact は classification と safe_to_share を持つ
- unsafe artifact は evidence room に入れない
- finding は削除ではなく status transition で追跡する
- expired fixture は stale として required_action を出す
- assurance summary は open finding と limitation を隠さない

## 7. Audit Finding

| Status | 意味 |
|---|---|
| open | 修正・説明が必要 |
| accepted_risk | owner と expiry 付きで受容 |
| remediated | 修正済み、verification pending |
| verified | fixture / evidence で確認済み |
| obsolete | scope 変更で対象外 |

## 8. Acceptance

- audit fixture が source_contracts、input_refs、expected_output_refs、verification_commands を持つ
- fixture は synthetic / redacted / safe_to_share の状態を明示する
- auditor walkthrough から expected output を再計算できる
- evidence room が access policy、classification、finding status を持つ
- assurance pack が open finding と limitation を隠さない
- audit fixture / assurance pack は HATE precheck decision / QEG verdict を変更しない
