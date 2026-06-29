---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Legal and Commercial Contracting Contract

## 1. 目的

HATE の commercial commitment、legal review packet、contract exception、
procurement response の追跡契約を定義する。成熟プロダクトでは、契約・調達・
セキュリティ審査で約束した内容が、実装状態、support、SLO、data residency、
privacy、trust packet と矛盾しないことを説明できる必要がある。

この文書は counsel / commercial owner と連携するための product requirement であり、
法務助言ではない。HATE precheck decision、QEG verdict、release approval を変更しない。

## 2. 原則

- contract commitment は source_refs、owner、verification、expiry を持つ
- 契約上の例外や redline は product capability と support obligation に紐づける
- 未実装機能を customer-facing commitment として扱わない
- security / privacy / residency / SLO commitment は各正本契約へ接続する
- legal hold / deletion / export は canonical evidence の削除や改変ではなく policy として扱う
- contract artifact は customer source code、secret、PII、unsafe artifact を含まない

## 3. Contract Artifact Set

| Artifact | 目的 | Source contract |
|---|---|---|
| commercial-commitment-register.json | customer / segment 向け約束の追跡 | this contract |
| procurement-response-index.json | RFP / security questionnaire / procurement response | `SECURITY_REVIEW_TRUST_CONTRACT.md` |
| support-plan-matrix.json | support target / escalation / incident class | `SLO_INCIDENT_RESPONSE_CONTRACT.md` |
| data-processing-refs.md | privacy / retention / deletion / export refs | `PRIVACY_QUARANTINE_CONTRACT.md` |
| residency-addendum-refs.md | region / deployment / data class routing | `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` |
| entitlement-order-map.json | edition / usage / limits / support plan | `PACKAGING_ENTITLEMENT_CONTRACT.md` |
| contract-exception-register.json | redline / exception / workaround | this contract |
| renewal-risk-brief.md | commercial risk / adoption / support status | `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` |

## 4. Commitment Register

```json
{
  "schema_version": "HATE/v1",
  "record_type": "commercial_commitment",
  "commitment_id": "COM-001",
  "customer_segment": "enterprise|regulated|team|local",
  "source_refs": [],
  "commitment_text": "string",
  "capability_refs": [],
  "source_contracts": [
    "SLO_INCIDENT_RESPONSE_CONTRACT.md"
  ],
  "status": "proposed|approved|implemented|exception|unsupported|expired",
  "owner": "string",
  "verification_refs": [],
  "expiry_at": "2026-12-31",
  "notes": []
}
```

## 5. Contract Exception

| Exception type | 例 | Required handling |
|---|---|---|
| unsupported_feature | 未実装 connector の提供要求 | roadmap / non-goal / workaround |
| stronger_slo | 標準 target より高い応答要求 | support plan / SLO exception |
| data_residency | region / tenant / storage 制約 | residency profile |
| retention_exception | 標準保持と異なる要求 | retention policy / legal hold |
| security_control_gap | trust packet に未対応 control | security finding / roadmap |
| telemetry_restriction | telemetry 禁止 / local only 要求 | telemetry mode |
| accessibility_requirement | specific accessibility target | accessibility report |
| migration_commitment | deprecated field の延長要求 | migration policy exception |

## 6. Procurement Response Rules

- response は source contract と verification_refs に紐づける
- `planned`, `candidate`, `unsupported` を `available` と表現しない
- customer-specific exception は owner、expiry、renewal impact を持つ
- security / privacy / residency の回答は trust packet / privacy / residency 正本と整合させる
- response template は release ごとに freshness check を通す
- procurement / sales / README / release note / API doc の customer-facing claim は
  `commercial-truthfulness-report` を通し、claim id、claim text、surface、
  source contract refs、implementation refs、evidence report refs、sourceRefs、
  release eligibility、blocker state、procurement response text を持つ
- manual review は exception や human decision を記録できるが、unsupported / planned
  capability を implemented evidence に変換しない
- release candidate pack は unsupported commercial claim、missing source contract ref、
  missing evidence report、release pack contradiction を blocker として扱う

## 7. Commercial Risk

| Risk | Trigger | Output |
|---|---|---|
| overcommit_risk | 実装済みでない capability を約束しそう | contract exception + roadmap decision |
| renewal_risk | adoption / support / incident 状態が弱い | renewal risk brief |
| compliance_gap | required control が未対応 | security finding + owner |
| residency_gap | requested deployment mode が未対応 | residency exception |
| support_gap | requested response target が未対応 | support plan exception |
| documentation_gap | customer docs が stale / missing | docs stale action |

## 8. Acceptance

- commercial commitment が source_refs、source_contracts、owner、status、verification_refs を持つ
- procurement response が implemented / planned / unsupported を明確に区別する
- commercial truthfulness report が claim inventory と evidence refs を保持し、
  unsupported / planned capability を customer-facing available として扱わない
- contract exception が owner、expiry、risk、workaround、linked roadmap item を持つ
- unsupported commitment が customer-facing docs や sales response で available と表現されない
- legal / commercial artifact が customer source code、secret、PII、unsafe artifact を含まない
- contract commitment は HATE precheck decision / QEG verdict を変更しない
