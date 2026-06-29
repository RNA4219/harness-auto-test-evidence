---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# SLO and Incident Response Contract

## 1. 目的

HATE の hosted surface、support、incident response、status communication の
契約を定義する。成熟プロダクトでは、障害時に何を守り、何を通知し、
どの artifact を根拠に復旧判断するかを事前に固定する必要がある。

この文書は運用応答の契約であり、HATE precheck decision、QEG verdict、
release approval を置き換えない。

## 2. 原則

- local CLI / canonical bundle / QEG export は hosted outage に依存しない
- incident response は canonical evidence を削除・改変せず、追跡 record を追加する
- data exposure / unsafe artifact leak は通常障害より高い優先度で扱う
- status communication は実装状態と確認済み事実を区別する
- support target は entitlement / support plan と連動できるが、証跡判定を変更しない

## 3. Service Surfaces

| Surface | SLO 対象 | 備考 |
|---|---|---|
| Local CLI | no | local-first のため hosted SLO から分離 |
| GitHub Action | partial | CI provider failure と HATE failure を分ける |
| Hosted dashboard | yes | read model / cache / auth を含む |
| Hosted REST API | yes | read-only API と admin API を分ける |
| Artifact storage | yes | upload / retention / quarantine |
| External connectors | partial | SIEM / ticketing / warehouse は degradation 表示 |
| Schema / adapter release | yes | breaking change / migration failure を含む |
| Documentation | yes | quickstart / migration / troubleshooting の freshness |

## 4. SLO Targets

| Target | Objective | Measurement |
|---|---|---|
| Hosted API availability | monthly 99.9% target | successful read requests / total read requests |
| Dashboard availability | monthly 99.5% target | successful page loads / total page loads |
| Read model freshness | p95 under 5 minutes | bundle ingest to visible read model |
| Status page update | within 30 minutes of confirmed incident | first public/internal update time |
| Severity 1 acknowledgement | within 15 minutes | support / incident channel ack |
| Severity 2 acknowledgement | within 1 hour | support / incident channel ack |
| Severity 3 acknowledgement | next business day | support / incident channel ack |
| Data incident containment | immediate best effort, tracked separately | unsafe exposure stopped / quarantine enforced |
| Local CLI availability | not hosted-measured | release artifact integrity and runnable quickstart |

SLO breach は customer communication と postmortem の対象になるが、HATE の
historical evidence を書き換える理由にはならない。

## 5. Incident Classes

| Class | 例 | 初期 severity |
|---|---|---|
| INC-1 Data / privacy exposure | unsafe artifact が summary / external export に出た | Sev1 |
| INC-2 Wrong eligibility output | HATE precheck が hard DQ を見落とした | Sev1 |
| INC-3 Evidence corruption | canonical bundle / hash / sourceRefs が壊れた | Sev1 |
| INC-4 Hosted outage | dashboard / API が利用不能 | Sev2 |
| INC-5 Connector degradation | external export / SIEM / ticketing が失敗 | Sev3 |
| INC-6 Schema / adapter regression | migration / adapter release が互換性を壊した | Sev2 |
| INC-7 Documentation regression | quickstart / migration guide が再現不能 | Sev3 |

## 6. Severity Matrix

| Severity | 条件 | 期待対応 |
|---|---|---|
| Sev1 | data exposure、証跡破損、誤った eligibility、広範な利用不能 | immediate containment, owner assignment, frequent updates |
| Sev2 | hosted outage、major adapter/schema regression、重要 connector failure | mitigation, customer update, rollback evaluation |
| Sev3 | degraded connector、docs regression、限定的 UI bug | scheduled fix, known issue update |
| Sev4 | cosmetic / low-impact issue | backlog and release note |

Severity は impact、customer scope、data sensitivity、availability、recoverability で
見直す。support plan は応答速度に影響できるが、data / evidence integrity の
severity を下げる根拠にはしない。

## 7. Incident Record

```json
{
  "schema_version": "HATE/v1",
  "record_type": "incident_record",
  "incident_id": "INC-20260628-001",
  "class": "INC-1|INC-2|INC-3|INC-4|INC-5|INC-6|INC-7",
  "severity": "sev1|sev2|sev3|sev4",
  "status": "investigating|identified|mitigating|monitoring|resolved|postmortem_required",
  "started_at": "2026-06-28T00:00:00Z",
  "detected_at": "2026-06-28T00:03:00Z",
  "acknowledged_at": "2026-06-28T00:10:00Z",
  "affected_surfaces": ["hosted_api", "artifact_storage"],
  "affected_artifacts": [],
  "customer_scope": "single_customer|multiple_customers|all_customers|unknown",
  "data_sensitivity": "none|internal|confidential|restricted|unknown",
  "containment_actions": [],
  "rollback_refs": [],
  "evidence_refs": [],
  "status_updates": [],
  "owner": "string",
  "postmortem_due_at": "2026-07-05T00:00:00Z"
}
```

## 8. Communication Policy

- confirmed incident は severity、affected surface、known workaround を明示する
- confirmed でない推測は customer-facing update に含めない
- Sev1 / Sev2 は status update cadence を incident record に残す
- data exposure の可能性がある場合は privacy / quarantine policy と support escalation を接続する
- local CLI workaround がある場合は hosted outage と分けて案内する
- resolved update には再発防止の追跡先または postmortem 予定を含める

## 9. Containment / Rollback

| Incident | Containment |
|---|---|
| Unsafe artifact leak | quarantine, export revoke, summary regeneration, affected refs audit |
| Wrong eligibility output | disable affected profile / adapter, mark bundles for replay, publish advisory |
| Evidence corruption | freeze ingestion, restore from canonical bundle, hash reconciliation |
| Hosted outage | fail over read model, disable noncritical views, preserve local workflow |
| Connector degradation | pause connector, keep local/QEG export, issue external export warning |
| Schema / adapter regression | rollback release, publish migration note, run compatibility fixture |
| Documentation regression | mark stale, publish correction, attach verified fixture |

Ops connector dry-run failures for SIEM / warehouse / ticketing / support are
non-gating unless they attempt live network calls, destructive actions, or unsafe
artifact export. Unsafe artifact export is treated as INC-1 data/privacy exposure
and must be blocked before payload generation; ordinary connector outage remains
INC-5 degradation and must not mutate canonical bundles or QEG export.

### 9.1 Safe Diagnostic Incident Evidence

Support incident evidence は `safe-diagnostic-bundle` を参照できるが、raw artifact、
customer source、secret、PII、private URL、full environment を含めてはならない。
unsafe input が存在する場合は excluded_artifacts と redaction_log に safe metadata
だけを残し、incident timeline には stable error code、remediation、owner_action、
sourceRefs を接続する。

Unknown error code は incident を pass にしない。`unknown_error_code` hold として
taxonomy 更新または support owner action を要求する。

## 10. Postmortem Requirements

Sev1 / Sev2 は postmortem を必須とする。最低限、以下を含める。

- customer impact / affected surfaces
- root cause と contributing factors
- detection signal と missed signal
- containment / rollback timeline
- evidence integrity impact
- privacy / quarantine impact
- corrective actions with owner / due date
- fixture / docs / schema / adapter change required

## 11. Acceptance

- hosted outage が local CLI / canonical bundle / QEG export を壊さない
- incident record が severity、class、surface、owner、timeline、evidence_refs を持つ
- Sev1 / Sev2 の containment、customer communication、postmortem が追跡できる
- unsafe artifact leak は privacy / quarantine contract に接続される
- wrong eligibility output は affected bundle replay と advisory を要求する
- status update は確認済み事実と未確認推測を分離する
- SLO breach は product readiness report へ反映できる
