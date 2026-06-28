---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Product Telemetry and Analytics Contract

## 1. 目的

HATE の product telemetry、usage analytics、privacy boundary、metric governance の
契約を定義する。成熟プロダクトでは、導入・性能・障害・価値を測る必要があるが、
customer code、artifact content、secret、PII を収集してはならない。

この文書は product improvement / capacity planning / adoption insight の契約であり、
HATE precheck decision、QEG verdict、customer evidence の正本を変更しない。

## 2. 原則

- telemetry は opt-in / configurable / documented とする
- customer source code、test names、artifact paths、raw logs、PII、secret は収集しない
- default local CLI は telemetry なしでも完全に動作する
- analytics は aggregate / pseudonymous / minimum necessary を基本にする
- telemetry event は schema version、purpose、retention、redaction_status を持つ

## 3. Allowed Signals

| Signal | 目的 | 禁止事項 |
|---|---|---|
| command usage | feature adoption | command args に path / token を含めない |
| stage duration | performance / reliability | file names を送らない |
| error code | support deflection | raw stack / customer path を送らない |
| adapter type | compatibility planning | repo name / project name を送らない |
| schema version | migration planning | bundle content を送らない |
| DQ category count | product quality | individual test name を送らない |
| artifact size bucket | capacity planning | artifact path / content を送らない |
| hosted API status | reliability | customer data payload を送らない |
| docs page category | docs improvement | user identity の不要な追跡をしない |

## 4. Prohibited Signals

- source code
- test title / test body / assertion text
- artifact content
- trace / screenshot / video / log 本体
- raw file path / workspace path
- repository name unless explicitly configured
- secret / token / credentials
- PII / customer personal data
- raw SARIF finding text when it contains source excerpts
- QEG verdict details beyond aggregate counts unless customer-owned export

## 5. Telemetry Event

```json
{
  "schema_version": "HATE/v1",
  "record_type": "telemetry_event",
  "event_id": "tel_001",
  "event_name": "precheck_completed",
  "event_version": "1.0",
  "created_at": "2026-06-28T00:00:00Z",
  "install_id": "pseudonymous-id",
  "workspace_hash": "optional-hash",
  "purpose": "product_improvement|reliability|capacity|docs",
  "redaction_status": "not_required|redacted|failed",
  "payload": {
    "schema_major": "HATE/v1",
    "duration_bucket": "0-30s",
    "adapter_types": ["junit", "lcov"],
    "dq_counts": {"hard_dq": 0, "soft_gap": 1},
    "error_code": null
  }
}
```

## 6. Consent / Configuration

| Mode | Behavior |
|---|---|
| off | no telemetry emitted |
| local_only | local analytics file only |
| aggregate | aggregate safe signals only |
| support_bundle | explicit diagnostic export for support |
| enterprise_managed | org policy controls telemetry mode |

Telemetry mode は summary に表示し、support bundle / diagnostic bundle へ含める場合は
明示的な customer action を要求する。

## 7. Retention and Access

| Data | Retention | Access |
|---|---|---|
| aggregate usage | 13 months target | product / platform |
| error code counts | 13 months target | product / support |
| performance buckets | 90 days target | engineering |
| docs analytics | 13 months target | docs / product |
| support bundle export | support case duration | support / security |
| local analytics file | customer controlled | local user |

## 8. Analytics Outputs

| Output | 用途 |
|---|---|
| adoption-health-report.json | customer success / rollout |
| product-metrics-report.json | product readiness / roadmap |
| capacity-report.json | hosted API / artifact storage planning |
| docs-improvement-report.json | docs stale / missing guidance |
| error-trend-report.json | support / remediation catalog |
| privacy-telemetry-report.json | allowed / blocked signal audit |

## 9. Acceptance

- telemetry off でも local CLI / precheck / QEG export が完了する
- telemetry event が allowed signal だけを含む
- prohibited signal が送信前 safety check で拒否される
- telemetry mode、purpose、retention、redaction_status が記録される
- support bundle export は明示的 action と privacy / quarantine policy に従う
- analytics は customer evidence / QEG verdict / release approval を変更しない
