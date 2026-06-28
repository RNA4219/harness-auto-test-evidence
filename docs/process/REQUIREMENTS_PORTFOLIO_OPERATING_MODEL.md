---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Requirements Portfolio Operating Model

## 1. 目的

HATE の肥大化した要件群を、実装可能な portfolio、workstream、stage gate、
WIP limit、dependency に圧縮する運営モデルを定義する。成熟プロダクト水準の
要件は広くなりがちだが、実装順を誤ると P0/P1 の local-first 証跡契約が薄まる。

この文書は requirements portfolio の運用契約であり、個別要件の正本を置き換えない。

## 2. 原則

- P0a / P0b の local-first evidence loop を最優先に守る
- P2/P3 productization は canonical bundle から派生する補助層として扱う
- すべての requirement は owner、stage、acceptance_refs、dependencies を持つ
- WIP を増やす前に dependency と acceptance を閉じる
- roadmap / customer commitment / audit finding は portfolio item として一元管理する

## 3. Portfolio Tiers

| Tier | 目的 | Exit condition |
|---|---|---|
| Core Evidence | collect / normalize / precheck / QEG export | P0a/P0b fixture passes |
| Trust Hardening | schema / adapter / safety / replay / explain | deterministic replay and conformance |
| Workflow Integration | RanD / shipyard / workflow-cookbook / manual bridge | traceable workflow artifacts |
| Product Operations | support / privacy / release / docs / incident | operational reports and guardrails |
| Enterprise Adoption | packaging / trust / residency / adoption / telemetry | product readiness evidence |
| Governance Scale | roadmap / contract / audit / accessibility | decision and assurance artifacts |

## 4. Stage Model

| Stage | 意味 | Required evidence |
|---|---|---|
| proposed | 候補 | source_refs, problem statement |
| shaped | 実装可能な粒度 | scope, non-goals, dependencies |
| accepted | 着手可能 | acceptance_refs, owner, fixture plan |
| active | 実装中 | task refs, risk, status |
| verified | 受入済み | verification result, evidence refs |
| adopted | 運用に入った | docs, runbook, support / ownership |
| retired | 廃止 | migration / deprecation record |

## 5. Portfolio Item

```json
{
  "schema_version": "HATE/v1",
  "record_type": "requirements_portfolio_item",
  "item_id": "REQ-PORT-001",
  "title": "P0a golden path",
  "tier": "core_evidence|trust_hardening|workflow_integration|product_operations|enterprise_adoption|governance_scale",
  "stage": "proposed|shaped|accepted|active|verified|adopted|retired",
  "source_contracts": [],
  "acceptance_refs": [],
  "dependencies": [],
  "owner": "string",
  "wip_class": "now|next|later|blocked",
  "risk": "low|medium|high|critical",
  "next_action": "string"
}
```

## 6. WIP Policy

| Workstream | WIP limit | Notes |
|---|---|---|
| Core Evidence | 2 | P0a/P0b を優先 |
| Trust Hardening | 2 | schema / adapter / replay の事故防止 |
| Workflow Integration | 2 | cross-repo dependency を制限 |
| Product Operations | 3 | docs / support / incident / release |
| Enterprise Adoption | 3 | packaging / trust / residency / telemetry |
| Governance Scale | 2 | contract / audit / roadmap / accessibility |

WIP limit は目安であり、blocked item を増やすための口実にしない。

## 7. Prioritization Rules

1. P0a golden path を壊す変更を最優先で止める
2. QEG export compatibility を壊す変更を次に止める
3. security / privacy / unsafe artifact leak を P0/P1 より優先して扱う
4. customer commitment / audit finding は source contract と owner がある場合だけ昇格する
5. P2/P3 の dashboard / governance / commercial artifact は local-first loop を塞がない
6. roadmap item は `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` の decision record を持つ
7. legal / commercial commitment は `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` の register を持つ

## 8. Portfolio Health Report

| Metric | 意味 |
|---|---|
| accepted_without_owner | owner 不在の accepted item |
| active_over_wip | WIP limit 超過 |
| dependency_blocked | dependency 未解消 item |
| acceptance_missing | acceptance_refs 不足 |
| stale_contract | review due 超過 |
| p0_dependency_leak | P0 が P2/P3 に依存している状態 |
| unverified_commitment | commercial / roadmap commitment の未検証 |
| audit_finding_aging | open finding の滞留 |

## 9. Acceptance

- requirement portfolio item が tier、stage、owner、acceptance_refs、dependencies を持つ
- P0a/P0b が P2/P3 productization に依存していないことを検出できる
- WIP limit 超過、owner 不在、acceptance 不足、stale contract を report できる
- customer commitment / audit finding / roadmap item が portfolio item に紐づく
- prioritization rule が HATE precheck decision / QEG verdict を変更しない
