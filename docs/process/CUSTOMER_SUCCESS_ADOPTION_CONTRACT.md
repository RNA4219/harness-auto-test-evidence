---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Customer Success and Adoption Contract

## 1. 目的

HATE の導入、定着、成功判定、更新判断に必要な customer success 契約を定義する。
成熟プロダクトでは、機能が存在するだけでは足りない。顧客が最初の証跡を生成し、
運用へ組み込み、継続的に価値を確認できる導入プロセスが必要である。

この文書は adoption / renewal / enablement の契約であり、HATE precheck decision、
QEG verdict、release approval を変更しない。

## 2. 原則

- onboarding は P0a golden path から開始する
- customer success 指標は canonical evidence を説明する補助であり、証跡判定を上書きしない
- 導入ステータスは source_refs、owner、next_action を持つ
- 未達成の adoption milestone は risk debt ではなく adoption gap として扱う
- training / enablement は customer-facing docs と同じ source contract を参照する

## 3. Adoption Stages

| Stage | 完了条件 | 主な artifact |
|---|---|---|
| Discover | 価値仮説、対象 repo、成功指標が合意される | adoption-plan.json |
| Prove | P0a golden path と1 repo の local precheck が成功する | first-evidence-record.json |
| Integrate | CI / QEG export / summary が team workflow に入る | rollout-record.json |
| Govern | profile、adapter、privacy、retention、docs が運用される | governance-readiness.json |
| Scale | 複数 repo / workspace へ展開され、trend が読める | adoption-health-report.json |
| Renew | 価値、利用、risk reduction、support 状態が説明できる | renewal-readiness.json |

## 4. Success Plan

```json
{
  "schema_version": "HATE/v1",
  "record_type": "adoption_plan",
  "customer_id": "customer-001",
  "workspace_id": "workspace-001",
  "target_repositories": ["repo-a"],
  "success_metrics": [
    {
      "metric": "Time to First Evidence",
      "target": "under 5 minutes",
      "source_refs": ["P0A_GOLDEN_PATH.md"]
    }
  ],
  "milestones": [
    {
      "stage": "prove",
      "owner": "string",
      "due_at": "2026-07-15",
      "acceptance_refs": ["PRG-0"],
      "status": "not_started|in_progress|complete|blocked"
    }
  ],
  "assumptions": [],
  "risks": []
}
```

## 5. Adoption Health

| Signal | 意味 |
|---|---|
| first evidence generated | 初回価値到達 |
| active repositories | 展開済み repo 数 |
| weekly evidence runs | 継続利用 |
| hard DQ resolution time | 証跡品質改善速度 |
| risk debt aging | 未解消 gap の滞留 |
| docs self-service rate | docs / doctor で解決できた比率 |
| support escalation rate | support 依存度 |
| replay success rate | 再計算性 |
| QEG export success rate | 後段接続安定性 |
| renewal risk | 利用低下、未解決 gap、導入停滞の複合 |

## 6. Enablement Assets

| Asset | 対象 | Source contract |
|---|---|---|
| 5 minute quickstart | Evaluator / Developer | `P0A_GOLDEN_PATH.md` |
| CI rollout guide | Developer / QA Lead | `CUSTOMER_DOCUMENTATION_CONTRACT.md` |
| Security review walkthrough | Security Reviewer | `SECURITY_REVIEW_TRUST_CONTRACT.md` |
| Adapter author workshop | Adapter Author | `ADAPTER_SDK_CONTRACT.md` |
| Incident response walkthrough | Support / SRE | `SLO_INCIDENT_RESPONSE_CONTRACT.md` |
| Renewal value brief | Executive / Platform Admin | this contract |

## 7. Adoption Gap

Adoption gap は product / customer success の課題であり、evidence gap とは分ける。

| Gap | 例 | Required action |
|---|---|---|
| onboarding_gap | Quickstart が未完了 | enablement / docs fix |
| integration_gap | CI 導入が未完了 | rollout support |
| governance_gap | profile / retention owner が未設定 | admin setup |
| value_gap | 成功指標が測定できない | metric definition |
| expansion_gap | 複数 repo 展開が止まる | rollout plan update |
| renewal_gap | 価値説明・利用・support 状態が弱い | renewal readiness review |

## 8. Renewal Readiness

renewal readiness は次の証跡を持つ。

- success metrics と実績
- active repositories / active workspaces
- evidence eligibility trend
- risk debt aging trend
- support / incident history
- docs / training usage
- blocked adoption gaps
- customer-owned next actions
- HATE-owned next actions

## 9. Acceptance

- P0a golden path から導入成功を測定できる
- adoption plan が milestone、owner、due date、acceptance_refs を持つ
- adoption gap が evidence gap / risk debt / incident と混同されない
- renewal readiness が metrics、support、incident、risk debt、adoption gaps を説明できる
- customer success artifact は HATE precheck decision / QEG verdict を変更しない
