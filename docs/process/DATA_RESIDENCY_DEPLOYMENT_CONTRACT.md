---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Data Residency and Deployment Contract

## 1. 目的

HATE の deployment topology、data residency、regional boundary、private networking、
backup / recovery の契約を定義する。成熟プロダクトでは、local-first の価値を
保ったまま、顧客のデータ所在地、接続制御、運用復旧要件に応える必要がある。

この文書は展開方式とデータ所在地の契約であり、HATE precheck decision、
QEG verdict、release approval を変更しない。

## 2. 原則

- local CLI / frozen bundle / QEG export は hosted deployment に依存しない
- region / residency は evidence eligibility の根拠にしない
- hosted read model は canonical bundle から再構築可能にする
- customer source code と unsafe artifact は既定で hosted service に送らない
- deployment mode ごとの data flow、control owner、residual risk を明示する

## 3. Deployment Modes

| Mode | 対象 | Data plane | Control plane |
|---|---|---|---|
| Local only | 個人 / OSS / sensitive repo | customer machine | none |
| CI attached | team CI | CI workspace / artifact store | HATE CLI / action |
| Hosted read model | team / platform | customer-approved bundle refs | hosted dashboard / API |
| Private tenant | enterprise | dedicated tenant storage | managed hosted control |
| Customer managed | regulated / strict enterprise | customer cloud / storage | limited managed control |
| Air-gapped export | restricted environment | offline bundle | offline validation |

## 4. Residency Profile

```json
{
  "schema_version": "HATE/v1",
  "record_type": "residency_profile",
  "profile_id": "residency-us-001",
  "deployment_mode": "local_only|ci_attached|hosted_read_model|private_tenant|customer_managed|air_gapped_export",
  "allowed_regions": ["us"],
  "disallowed_regions": [],
  "data_classes": {
    "canonical_bundle": "customer_controlled",
    "read_model": "hosted_allowed",
    "artifact_content": "not_uploaded",
    "telemetry": "aggregate_only"
  },
  "key_management": {
    "mode": "provider_managed|customer_managed|external_kms|none",
    "rotation_days": 90
  },
  "network": {
    "public_ingress": false,
    "private_link": true,
    "ip_allowlist": true
  }
}
```

## 5. Data Class Routing

| Data class | Default route | Notes |
|---|---|---|
| canonical bundle | customer controlled | hash / refs can be exported |
| read model | hosted if enabled | derived, rebuildable, access controlled |
| artifact content | local / customer storage | upload requires explicit policy |
| artifact metadata | hosted if enabled | classification / hash / size only |
| telemetry | off or aggregate | prohibited signals blocked |
| support bundle | explicit export | privacy / quarantine checks required |
| audit log | tenant / org scope | immutable record metadata |
| security review packet | redacted export | no customer code / unsafe artifact |

## 6. Connectivity Controls

| Control | 要件 |
|---|---|
| Private networking | private tenant / customer managed は private endpoint を持てる |
| Egress allowlist | external connector は allowlist / denylist を持つ |
| Ingress restriction | admin / API access は RBAC と network policy を併用する |
| Artifact fetch | external URL artifact は SSRF / metadata IP block を通す |
| Connector isolation | SIEM / ticketing / warehouse connector は scoped credentials を使う |
| Offline mode | air-gapped export は signed package / checksum / offline docs を持つ |

## 7. Backup / Recovery

| Asset | Backup | Recovery expectation |
|---|---|---|
| hosted read model | rebuild from canonical bundle | rebuild preferred over manual repair |
| entitlement manifest | backed up by tenant config | restore with audit event |
| audit metadata | immutable / append-only target | restore without rewriting record IDs |
| customer docs index | repo / release artifact | regenerate from docs source |
| trust packet index | release artifact | regenerate from source contracts |
| telemetry aggregate | optional backup | loss does not affect evidence |

RPO / RTO は deployment mode と support plan に依存する。ただし local-first precheck と
frozen bundle replay は hosted recovery の対象外で、顧客側で再実行できることを前提にする。

## 8. Acceptance

- deployment mode ごとに data plane / control plane / owner が定義される
- residency profile が allowed_regions、data_classes、key_management、network を持つ
- customer source code、unsafe artifact、raw path は既定で hosted service に送られない
- hosted read model は canonical bundle から再構築できる
- private tenant / customer managed / air-gapped mode が P0a local-first を壊さない
- backup / recovery は evidence record を削除・改変せず audit event として追跡される
