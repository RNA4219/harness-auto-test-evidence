---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Product Governance and Roadmap Contract

## 1. 目的

HATE の roadmap、product decision、customer request、deprecation、compatibility、
advisory process の統制契約を定義する。成熟プロダクトでは、機能追加の速度だけでなく、
なぜ採択したか、何を先送りしたか、顧客影響をどう説明したかを追跡できる必要がある。

この文書は product governance の契約であり、HATE precheck decision、
QEG verdict、release approval を置き換えない。

## 2. 原則

- roadmap item は customer value、risk reduction、evidence impact、support cost を持つ
- customer request は source_refs と affected personas を持つ
- strategic decision は decision record と acceptance evidence を持つ
- deprecation / migration は `RELEASE_MIGRATION_POLICY.md` と接続する
- roadmap status は実装済み表現を過大にしない

## 3. Governance Artifacts

| Artifact | 目的 |
|---|---|
| roadmap-item.json | product / platform roadmap item |
| product-decision-record.md | 採択・却下・延期の理由 |
| customer-request-register.json | request / customer impact / source_refs |
| advisory-feedback-log.json | customer advisory / security review / support 由来の feedback |
| deprecation-decision.json | deprecation / migration / compatibility decision |
| roadmap-health-report.json | delivery, risk, dependency, customer impact |

## 4. Roadmap Item

```json
{
  "schema_version": "HATE/v1",
  "record_type": "roadmap_item",
  "item_id": "RM-001",
  "title": "private tenant deployment",
  "status": "candidate|committed|in_progress|released|deferred|rejected",
  "horizon": "now|next|later",
  "personas": ["Platform Admin", "Security Reviewer"],
  "source_refs": [],
  "value_hypothesis": "string",
  "risk_reduction": "string",
  "evidence_impact": "string",
  "dependencies": [],
  "acceptance_refs": [],
  "owner": "string"
}
```

## 5. Prioritization Dimensions

| Dimension | 説明 |
|---|---|
| customer impact | 顧客数、重要度、導入阻害度 |
| evidence integrity | canonical bundle / QEG export への影響 |
| security / privacy | data exposure、control gap、review blocker |
| support burden | support case、doctor / docs での解決可能性 |
| revenue / retention | adoption、expansion、renewal への影響 |
| implementation risk | schema、adapter、migration、backward compatibility |
| operational cost | hosted cost、artifact storage、incident risk |
| strategic fit | product surface、personas、non-goals との整合 |

## 6. Decision Record

Decision record は次を持つ。

- problem statement
- considered options
- selected option
- rejected options and rationale
- customer / persona impact
- compatibility / migration impact
- security / privacy review
- evidence / QEG impact
- rollout plan
- success metrics
- review date

## 7. Customer Request Register

| Field | Required |
|---|---|
| request_id | yes |
| customer_segment | yes |
| source_refs | yes |
| affected_personas | yes |
| requested_outcome | yes |
| current_workaround | no |
| adoption_or_renewal_impact | no |
| security_or_compliance_impact | no |
| linked_roadmap_items | no |
| decision_status | yes |

## 8. Roadmap Communication

- committed と candidate を明確に分ける
- released でないものを customer docs で利用可能と表現しない
- deprecation は migration guide と compatibility matrix を持つ
- security / privacy impact がある場合は trust packet freshness と接続する
- incident / support 起点の roadmap item は postmortem / support case と接続する

## 9. Acceptance

- roadmap item が source_refs、personas、value、risk、acceptance_refs、owner を持つ
- product decision record が採択・却下・延期の理由を説明できる
- customer request が roadmap item または explicit non-goal に紐づく
- roadmap status が docs / release notes / customer communication と矛盾しない
- deprecation decision が migration / release policy と接続される
- product governance artifact は HATE precheck decision / QEG verdict を変更しない
