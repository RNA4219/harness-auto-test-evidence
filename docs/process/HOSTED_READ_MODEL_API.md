---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Hosted Read Model and API Contract

## 1. 目的

Hosted dashboard / REST API / admin console は、HATE の canonical evidence bundle から
派生する read model である。この文書は hosted surface の domain、API、cache、
authorization、consistency の契約を定義する。

Hosted read model は HATE precheck decision や QEG verdict の正本ではない。
不整合がある場合は canonical bundle と QEG record を優先する。

## 2. Surfaces

| Surface | 用途 | 優先度 |
|---|---|---|
| REST API | run / bundle / evidence / artifact / risk debt の query | P2 |
| Dashboard | evidence map、risk matrix、trend、artifact budget | P2 |
| Admin console | org、repo、profile、adapter、retention、audit log | P2/P3 |
| Webhook | DQ / risk debt / unsafe artifact event 配信 | P3 |
| Warehouse export | BI / governance 向け read-only export | P3 |

## 3. Read Model Sources

| View | Source artifact |
|---|---|
| run list | `HATE-run.json`, `record.json` |
| precheck status | `precheck-decision.json` |
| evidence map | `evidence-map.json`, `qeg-bundle.json` |
| risk coverage matrix | `risk-coverage-matrix.json` |
| artifact budget | `artifact-manifest.json` |
| privacy / quarantine | `privacy-report.json`, `artifact-manifest.json` |
| risk debt | `risk-debt-register.json` |
| adapter health | `adapter-conformance-report.json` |
| schema health | `schema-registry.json` |
| product readiness | `product-readiness-report.json` |
| audit log | audit events |

## 4. API Resource Model

| Resource | Path |
|---|---|
| organizations | `/v1/orgs` |
| workspaces | `/v1/orgs/{org_id}/workspaces` |
| projects | `/v1/workspaces/{workspace_id}/projects` |
| repositories | `/v1/projects/{project_id}/repositories` |
| runs | `/v1/repositories/{repo_id}/runs` |
| attempts | `/v1/runs/{run_id}/attempts` |
| bundles | `/v1/bundles/{bundle_id}` |
| evidence | `/v1/bundles/{bundle_id}/evidence` |
| artifacts | `/v1/bundles/{bundle_id}/artifacts` |
| risk debt | `/v1/projects/{project_id}/risk-debt` |
| profiles | `/v1/projects/{project_id}/profiles` |
| adapters | `/v1/projects/{project_id}/adapters` |
| audit events | `/v1/orgs/{org_id}/audit-events` |

## 5. API Response Envelope

```json
{
  "schema_version": "HATE/v1",
  "request_id": "req_123",
  "data": {},
  "errors": [],
  "pagination": {
    "next_cursor": null
  },
  "source": {
    "bundle_id": "bundle_sha256_...",
    "record_id": "REC-001",
    "generated_at": "2026-06-28T00:00:00Z"
  }
}
```

## 6. Consistency Rules

- API は canonical bundle から再構築可能である
- dashboard cache は stale marker を持つ
- read model の値で canonical bundle を変更しない
- profile / adapter / retention の admin change は audit event を生成する
- failed external export は hosted view に warning として表示し、local precheck を壊さない

## 7. Authorization

| Resource | Admin | Maintainer | Developer | Auditor | Viewer |
|---|---|---|---|---|---|
| org settings | write | read | none | read | none |
| project settings | write | write | read | read | read |
| run summary | read | read | read | read | read |
| raw artifact | read | read | conditional | read with policy | none |
| quarantine release | write | write | none | none | none |
| audit log | read | read | none | read | none |
| profile change | write | write | none | read | none |

## 8. API Errors

API errors は `PRODUCT_ERROR_TAXONOMY.md` の category と対応する。

| HTTP | HATE category | 例 |
|---:|---|---|
| 400 | CLI / CFG / SCH | invalid query |
| 401 | SEC | unauthenticated |
| 403 | SEC | forbidden resource |
| 404 | SYS | not found |
| 409 | CFG / SCH | version conflict |
| 422 | DQ / ART / ADP | invalid bundle state |
| 500 | SYS | internal error |

## 9. Pagination / Filtering

最低限、次を support する。

- cursor pagination
- run status filter
- decision filter
- DQ severity filter
- risk debt status filter
- artifact classification filter
- created_at range
- commit_sha / branch / PR ref

## 10. Acceptance

- hosted read model は canonical bundle から再構築できる
- API response は source bundle / record を参照する
- stale cache は stale と表示される
- RBAC が raw artifact と quarantine release を制御する
- API error が stable error code と remediation を持つ
- hosted dashboard は HATE precheck decision / QEG verdict を上書きしない
