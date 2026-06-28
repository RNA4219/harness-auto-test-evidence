---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Packaging and Entitlement Contract

## 1. 目的

HATE の edition、entitlement、usage meter、feature boundary を定義する。
成熟プロダクトでは、どの機能が local-first の無償・OSS 相当で保証され、
どの機能が team / enterprise / regulated 向けの運用機能なのかを明確にする必要がある。

この文書は価格表ではない。契約、調達、support、実装スコープの境界を固定する。

## 2. 原則

- P0a local-first precheck と canonical schema は edition に依存しない
- hosted dashboard / enterprise connector / admin console は canonical bundle から派生する
- entitlement は HATE precheck decision や QEG verdict を変更しない
- over-limit は evidence を隠さず、usage / budget warning として扱う
- regulated / enterprise 機能が未設定でも local bundle は再計算できる

## 3. Editions

| Edition | 対象 | 含むもの | 含まないもの |
|---|---|---|---|
| Local | 個人 / OSS / single repo | CLI, schema, P0a golden path, local precheck | hosted dashboard, SSO, org RBAC |
| Team | team CI | GitHub Action, job summary, QEG export, adapter registry | SSO / SCIM, legal hold |
| Enterprise | platform org | org/workspace/project, RBAC, audit log, retention, hosted read model | regulated attestation pack |
| Regulated | 高監査領域 | legal hold, attestation metadata, extended audit, private artifact storage | release approval の代替 |

## 4. Feature Boundary

| Feature | Local | Team | Enterprise | Regulated |
|---|---|---|---|---|
| P0a golden path | yes | yes | yes | yes |
| canonical JSON / NDJSON | yes | yes | yes | yes |
| QEG export | yes | yes | yes | yes |
| GitHub Action summary | optional | yes | yes | yes |
| adapter SDK | yes | yes | yes | yes |
| hosted dashboard | no | optional | yes | yes |
| org / workspace model | no | optional | yes | yes |
| RBAC | no | basic | yes | yes |
| audit log | local record | project | org | extended |
| retention policy | local metadata | project | org | legal hold |
| SSO / SCIM | no | no | yes | yes |
| SIEM / warehouse connector | no | optional | yes | yes |
| private artifact storage | no | optional | optional | yes |
| attestation metadata | optional | optional | optional | yes |

## 5. Entitlement Model

```json
{
  "schema_version": "HATE/v1",
  "edition": "local|team|enterprise|regulated",
  "entitlements": {
    "hosted_read_model": false,
    "org_rbac": false,
    "sso": false,
    "extended_retention": false,
    "private_artifact_storage": false
  },
  "limits": {
    "repositories": null,
    "runs_per_month": null,
    "artifact_storage_gb": null,
    "retention_days": null
  }
}
```

## 6. Usage Meters

| Meter | 用途 |
|---|---|
| repositories | org / project usage |
| runs | CI / local run count |
| evidence bundles | generated bundles |
| artifact storage | trace / screenshot / video / report size |
| retention days | storage and policy |
| adapter executions | heavy adapter usage |
| hosted API calls | dashboard / REST usage |
| external exports | connector usage |

Usage meter は product analytics / billing / capacity planning 用であり、
HATE precheck decision を変更しない。

## 7. Over-Limit Policy

| Condition | Behavior |
|---|---|
| local usage high | warning only |
| artifact budget exceeded | artifact budget report + risk debt candidate |
| hosted storage exceeded | upload blocked, local bundle remains valid |
| API rate limit | HTTP 429, retry-after, local CLI unaffected |
| retention exceeded | deletion candidate, audit metadata retained |
| connector unavailable | external export warning, QEG/local artifacts preserved |

## 8. Procurement / Contract Artifacts

| Artifact | 目的 |
|---|---|
| edition matrix | 調達時の機能境界 |
| entitlement manifest | customer / org に有効な機能 |
| usage report | renewal / capacity planning |
| security pack refs | security review |
| support plan refs | support / incident SLA |
| data processing refs | privacy / retention |

## 9. Acceptance

- edition 境界が P0a local-first を壊さない
- entitlement が HATE precheck decision / QEG verdict を変更しない
- over-limit 時も canonical bundle は失われない
- usage meter が artifact budget / hosted API / external export を説明できる
- regulated 機能は release approval の代替にならない
- procurement artifact が security / support / data processing refs に接続できる
