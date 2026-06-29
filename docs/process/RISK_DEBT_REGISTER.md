---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Risk Debt Register

## 1. 目的

Risk debt は、HATE が検出した soft gap、manual 補完要求、conditional candidate、
未解決の証跡不足を継続追跡するための register である。

HATE は release approval を出さないが、証跡不足を一回の summary で流さず、
owner、age、risk、sourceRefs、次アクションに結びつける必要がある。

## 2. 対象

| Debt type | 例 |
|---|---|
| `missing_execution` | high-risk path に実行証跡がない |
| `coverage_gap` | changed line / branch coverage が不足 |
| `flaky_unresolved` | flaky が profile 閾値を超える |
| `matrix_gap` | browser / OS / version matrix が不足 |
| `artifact_unsafe` | artifact が quarantine され証跡として使えない |
| `manual_required` | manual-bb 補完要求が必要 |
| `contract_gap` | changed contract に Pact / can-i-deploy がない |
| `mutation_gap` | high-risk path に mutation evidence がない |
| `static_unresolved` | high / critical SARIF が未解決 |
| `traceability_gap` | requirement / risk / test / evidence が結線不可 |
| `implementation_test_coupling` | production code が test/fixture 名で分岐 |
| `risk_without_oracle` | high/critical risk に oracle がない |
| `coverage_without_evidence` | coverage percentage が唯一の証跡 |
| `manual_review_required` | coupling / oracle 不足で human decision 必要 |

## 3. Register Artifact

`risk-debt-register.json` は最低限次を持つ。

```json
{
  "schema_version": "HATE/v1",
  "run_id": "1001",
  "run_attempt": 1,
  "commit_sha": "0123456789abcdef0123456789abcdef01234567",
  "profile_version": "HATE/v1",
  "items": []
}
```

## 4. Risk Debt Item

```json
{
  "risk_debt_id": "riskdebt_RISK-001_bundle123",
  "debt_type": "missing_execution",
  "severity": "low|medium|high|critical",
  "status": "open|acknowledged|mitigated|accepted|closed|stale",
  "risk_id": "RISK-001",
  "requirement_id": "REQ-001",
  "owner": "team-platform",
  "created_at": "2026-06-28T00:00:00Z",
  "last_seen_at": "2026-06-28T00:00:00Z",
  "age_days": 0,
  "source_refs": [],
  "evidence_refs": [],
  "recommended_actions": [],
  "blocking_profile": ["release"],
  "qeg_refs": [],
  "manual_bridge_refs": []
}
```

## 5. Status Semantics

| Status | 意味 |
|---|---|
| open | 未対応 |
| acknowledged | owner が認識済み。証跡不足は残る |
| mitigated | 追加証跡または manual 補完で緩和済み |
| accepted | QEG / 上位統制側で sourceRefs 付きの判断がある |
| closed | 追加証跡により gap が解消 |
| stale | baseline / branch / requirement が古くなり再評価が必要 |

`accepted` は HATE が waiver を出したという意味ではない。HATE は acceptance の
sourceRefs を記録するだけで、最終判断は QEG / 上位統制へ委譲する。

## 6. Aging Policy

| Severity | stale threshold | escalation |
|---|---:|---|
| low | 30 days | summary warning |
| medium | 14 days | owner reminder |
| high | 7 days | release review candidate |
| critical | 1 day | hard review candidate |

## 7. Recommendation Link

各 item は `HATE recommend` の出力と接続する。

| debt_type | 推奨 action |
|---|---|
| missing_execution | unit / integration / e2e test の追加 |
| coverage_gap | changed line / branch を通す test の追加 |
| flaky_unresolved | retry history、isolation、external dependency control |
| matrix_gap | browser / OS / runtime matrix の追加 |
| artifact_unsafe | redaction rule、safe artifact 再生成 |
| manual_required | manual-bb bridge で補完要求生成 |
| contract_gap | Pact verification / can-i-deploy |
| mutation_gap | Stryker / mutation evidence |
| static_unresolved | SARIF finding の修正 |
| traceability_gap | requirement / risk / test seed の sourceRefs 補完 |

## 8. Summary Policy

summary に出すもの:

- debt count by severity
- new / recurring / closed count
- high / critical item の safe title
- owner
- recommended next action

summary に出さないもの:

- unsafe artifact path
- secret / PII
- raw stack trace
- private customer URL

## 9. QEG / workflow / manual bridge

| 接続先 | 扱い |
|---|---|
| QEG | risk debt を optional evidence / residual risk candidate として渡す |
| workflow-cookbook | Task Seed / Acceptance / Evidence refs に接続する |
| manual-bb-test-harness | manual_required を manual 補完要求へ変換する |
| shipyard-cp | run / audit refs に advisory evidence として添付する |

## 10. Acceptance

- soft gap / manual 補完要求 / conditional candidate が register に残る
- owner、age、sourceRefs、recommended_actions が欠損しない
- stale threshold が severity ごとに再現可能
- QEG / manual / workflow 接続は sourceRefs を持つ
- HATE は risk debt を waiver / approval として扱わない
- public summary に unsafe detail が出ない
