---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Security Review and Trust Contract

## 1. 目的

HATE の security review、trust packet、control mapping、vulnerability handling、
supply chain evidence の契約を定義する。成熟プロダクトでは、機能や SLO だけでなく、
顧客のセキュリティ審査・調達・監査に提出できる一貫した証跡が必要である。

この文書は trust / review / security operations の契約であり、QEG の Gate policy、
waiver、approval、retention 正本を置き換えない。

## 2. 原則

- trust packet は canonical bundle から派生する説明資料であり、証跡を改変しない
- customer source code、artifact 本体、secret、PII は提出資料へ含めない
- control mapping は source_refs と evidence_refs を持つ
- unresolved critical security issue は release / customer communication へ接続する
- vulnerability handling は incident response と release / migration policy に接続する

## 3. Trust Packet Contents

| Artifact | 目的 |
|---|---|
| data-flow.md | データの入力、保存、出力、外部送信を説明 |
| security-controls.json | control mapping と evidence_refs |
| privacy-summary.md | classification、redaction、quarantine、retention |
| subprocessors.md | 外部サービス / connector / hosting provider |
| sbom.json | runtime / package / adapter dependency の一覧 |
| vulnerability-report.json | known vulnerabilities、severity、status |
| pen-test-summary.md | 実施範囲、日付、修正状況 |
| attestation-summary.json | signed evidence / build provenance / release refs |
| deletion-export-policy.md | customer export / deletion / legal hold の扱い |
| support-security-escalation.md | security issue / data issue の escalation |

## 4. Security Review Record

```json
{
  "schema_version": "HATE/v1",
  "record_type": "security_review_record",
  "review_id": "SEC-REV-20260628-001",
  "customer_id": "customer-001",
  "scope": ["hosted_read_model", "artifact_storage", "github_action"],
  "requested_at": "2026-06-28T00:00:00Z",
  "status": "draft|in_review|approved|conditional|blocked|expired",
  "trust_packet_refs": [],
  "control_mappings": [],
  "open_findings": [],
  "assumptions": [],
  "expiry_at": "2026-12-28T00:00:00Z",
  "owner": "string"
}
```

## 5. Control Mapping

| Control area | HATE evidence |
|---|---|
| Access control | RBAC, service account, audit log |
| Data protection | classification, redaction, quarantine, retention |
| Change management | release gates, migration guide, compatibility matrix |
| Incident management | incident record, status update, postmortem |
| Vulnerability management | dependency scan, SBOM, vulnerability report |
| Logging / monitoring | audit event, SLO report, hosted API logs |
| Supplier management | subprocessors, external connector inventory |
| Business continuity | hosted outage policy, local-first fallback |
| Evidence integrity | sha256, provenance, frozen bundle, replay |
| Secure development | adapter conformance, schema registry, release validation |

## 6. Vulnerability Handling

| Severity | Target behavior |
|---|---|
| Critical | immediate triage, containment, customer advisory when applicable |
| High | owner assigned, fix plan, release / mitigation target |
| Medium | tracked in vulnerability report with due date |
| Low | backlog or scheduled remediation |

Security finding は hidden backlog にせず、status、owner、due date、affected surface、
customer exposure、mitigation を持つ。

## 7. Trust Center Freshness

| Document | Freshness |
|---|---|
| Data flow | every architecture change |
| Security controls | every control / policy change |
| SBOM | every release |
| Vulnerability report | every dependency or scan change |
| Subprocessors | before provider / connector change |
| Pen-test summary | after each assessment |
| Privacy summary | every classification / retention change |
| Incident summary | after Sev1 / Sev2 closure |

## 8. Acceptance

- trust packet が data flow、controls、privacy、SBOM、vulnerability、subprocessor を含む
- security review record が scope、status、trust_packet_refs、open_findings、expiry を持つ
- critical / high finding が owner、due date、mitigation を持つ
- trust packet が customer source code、secret、PII、unsafe artifact を含まない
- control mapping が source_refs / evidence_refs を持つ
- security review は QEG Gate policy / waiver / approval を置き換えない
