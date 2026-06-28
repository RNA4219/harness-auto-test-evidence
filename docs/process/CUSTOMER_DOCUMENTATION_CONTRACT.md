---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Customer Documentation Contract

## 1. 目的

成熟プロダクトでは、README だけでは足りない。導入者、管理者、adapter 作者、
監査担当、support 担当が、それぞれ必要な粒度で同じ契約を理解できる
customer-facing documentation が必要である。

この文書は HATE の顧客向けドキュメント体系、必須ページ、鮮度、検証方法を定義する。

## 2. Audiences

| Audience | 必要な情報 |
|---|---|
| Evaluator | 何ができるか、5分で試せるか、何に依存するか |
| Developer | local / CI でどう実行し、gap をどう直すか |
| QA Lead | risk coverage、manual 補完、AETE をどう読むか |
| Platform Admin | org / repo / profile / adapter / retention をどう運用するか |
| Security Reviewer | data flow、artifact safety、secret / PII、retention、quarantine |
| Auditor | frozen bundle、record、sourceRefs、replay、QEG 接続 |
| Adapter Author | SDK、manifest、conformance fixtures |
| Support Engineer | error code、diagnostic bundle、known issues |

## 3. Required Docs

| Doc | 必須 | 内容 |
|---|---|---|
| Quickstart | P0 | P0a golden path を5分で実行 |
| Concepts | P0 | Evidence, DQ, AETE, profile, QEG, artifact safety |
| CLI Reference | P0 | commands, options, exit codes |
| Schema Reference | P0 | common envelope, record_type, schema registry |
| CI Guide | P0b | GitHub Action, artifact upload, job summary |
| QEG Integration Guide | P0b | qeg-bundle, sourceRefs, compatibility |
| Troubleshooting | P1 | error code, remediation, doctor output |
| Adapter SDK Guide | P1 | manifest, interface, conformance fixtures |
| Security Guide | P1 | privacy, quarantine, redaction, retention |
| Admin Guide | P2 | org / workspace / project / RBAC / audit log |
| API Reference | P2 | hosted read model / REST API |
| Migration Guide | P2 | schema / profile / adapter / CLI migration |
| Support Guide | P2 | diagnostic bundle, incident classes, escalation |
| Compliance Pack | P3 | security review, control mapping, data flow |

## 4. Documentation Artifact Model

```json
{
  "schema_version": "HATE/v1",
  "doc_id": "quickstart",
  "path": "docs/user/quickstart.md",
  "audience": ["Evaluator", "Developer"],
  "product_stage": "P0",
  "last_reviewed_at": "2026-06-28",
  "next_review_due": "2026-07-28",
  "source_contracts": ["P0A_GOLDEN_PATH.md"],
  "verification": {
    "commands": [],
    "fixtures": [],
    "screenshots": []
  }
}
```

## 5. Freshness Policy

| Doc | Review cadence |
|---|---|
| Quickstart | every release |
| CLI Reference | every release |
| Schema Reference | every schema change |
| Adapter SDK Guide | every SDK change |
| Security Guide | every safety policy change |
| Migration Guide | every breaking / deprecation change |
| Compliance Pack | quarterly |
| Troubleshooting | every support taxonomy change |

## 6. Verification

| Doc type | Verification |
|---|---|
| Quickstart | command output and expected artifacts |
| CLI Reference | generated command list or checked examples |
| Schema Reference | schema registry links resolve |
| Adapter SDK Guide | conformance fixture runs |
| Security Guide | privacy / quarantine fixtures |
| API Reference | OpenAPI / response examples validate |
| Migration Guide | migration dry-run evidence |
| Troubleshooting | error code exists in taxonomy |

## 7. Style Requirements

- marketing copy より実行可能な手順を優先する
- P0 local-first と hosted / enterprise-only の差を明記する
- dangerous / destructive / privacy-sensitive operation は warning を持つ
- docs examples は golden fixture または named fixture を参照する
- stale doc は `workflow-docs-stale.json` に required_action を出す
- support / security / migration docs は source contract へリンクする

## 8. Acceptance

- required docs の owner、audience、source_contracts、review date が定義される
- Quickstart が P0a golden path と同じ fixture を使う
- docs stale check が missing / stale / broken reference を検出できる
- examples が実装状態より強い完了表現をしない
- security / support / migration docs が各正本契約と整合する
