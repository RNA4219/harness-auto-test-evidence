---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Workflow Cookbook Integration

## 1. 目的

HATE の実装を `workflow-cookbook` の Task Seed / Acceptance / Evidence /
Birdseye / workflow plugin の運用に接続する。

HATE は自動テスト証跡の normalizer / evaluator であり、実装作業そのものは
`workflow-cookbook` の作業様式で追跡する。これにより、実装タスク、
検収記録、証跡、ドキュメント鮮度、cross-repo 参照を後から再計算できる。

## 2. 接続範囲

| 領域 | workflow-cookbook 側 | HATE 側 |
|---|---|---|
| Task Seed | `TASK.codex.md`, `docs/tasks/*.md` | `TASK.codex.md` と HATE-MVP-* 分解 |
| Acceptance | `docs/acceptance/AC-YYYYMMDD-xx.md` | HATE acceptance fixture / verification result |
| Evidence | `agent-protocols` Evidence JSONL | HATE run / qeg / aete / dq artifact refs |
| Product readiness | Product readiness gate / acceptance | HATE-PROD-* と `product-readiness-report.json` |
| Golden path | `fixtures/golden/*`, acceptance fixture | P0a input / expected / DQ fixture |
| Product supportability | Error / support acceptance | `PRODUCT_ERROR_TAXONOMY.md` と diagnostic bundle fixture |
| Enterprise model | Domain / RBAC / audit acceptance | `ENTERPRISE_DOMAIN_MODEL.md` と read-model fixture |
| Schema / adapter contract | Schema / adapter acceptance | `SCHEMA_REGISTRY_CONTRACT.md` と `ADAPTER_SDK_CONTRACT.md` |
| Risk debt | Gap tracking acceptance | `RISK_DEBT_REGISTER.md` と risk debt fixture |
| Privacy / quarantine | Artifact safety acceptance | `PRIVACY_QUARANTINE_CONTRACT.md` と privacy fixture |
| Hosted read model | API / dashboard acceptance | `HOSTED_READ_MODEL_API.md` と read-model fixture |
| Release / migration | Release acceptance | `RELEASE_MIGRATION_POLICY.md` と release-evidence fixture |
| Packaging / entitlement | Procurement / usage acceptance | `PACKAGING_ENTITLEMENT_CONTRACT.md` と entitlement fixture |
| Customer documentation | Docs freshness acceptance | `CUSTOMER_DOCUMENTATION_CONTRACT.md` と docs index fixture |
| SLO / incident response | Incident / reliability acceptance | `SLO_INCIDENT_RESPONSE_CONTRACT.md` と incident fixture |
| Customer success / adoption | Rollout / renewal acceptance | `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` と adoption fixture |
| Security review / trust | Security review acceptance | `SECURITY_REVIEW_TRUST_CONTRACT.md` と trust packet fixture |
| Product telemetry / analytics | Privacy-safe metrics acceptance | `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` と telemetry fixture |
| Data residency / deployment | Deployment acceptance | `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` と residency fixture |
| Product governance / roadmap | Roadmap acceptance | `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` と roadmap fixture |
| Accessibility / localization | Inclusive UX acceptance | `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` と accessibility fixture |
| Legal / commercial contracting | Contract acceptance | `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` と commitment fixture |
| Audit fixture / assurance | Audit readiness acceptance | `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` と assurance fixture |
| Requirements portfolio | Portfolio acceptance | `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` と portfolio fixture |
| Birdseye / Codemap | `docs/birdseye/index.json`, `caps/*.json` | HATE docs / schema / adapter の依存マップ |
| workflow plugin | task/acceptance sync, docs resolve, stale check | HATE task / acceptance / docs freshness の検証 |

## 3. HATE 追加 artifact

HATE は実装フェーズで次を生成できるようにする。

| artifact | 役割 |
|---|---|
| `workflow-task-seed.json` | HATE-MVP-* を workflow-cookbook Task Seed 互換にした一覧 |
| `workflow-acceptance-record.json` | acceptance record へ転記できる検収結果 |
| `workflow-evidence.jsonl` | agent-protocols Evidence 互換へ写像できる HATE 証跡 |
| `workflow-docs-stale.json` | HATE docs / schema / fixture の stale check 結果 |
| `workflow-birdseye-map.json` | HATE docs / adapters / schemas / fixtures の依存ノード候補 |
| `product-readiness-report.json` | PRG-0..PRG-6 と HATE-PROD-* の達成状況 |
| `entitlement-manifest.json` | edition / entitlement / usage limit / over-limit 状態 |
| `customer-docs-index.json` | required docs / audience / source contract / freshness 状態 |
| `incident-record.json` | incident class / severity / timeline / evidence refs |
| `slo-report.json` | SLO target / breach / status communication 状態 |
| `adoption-plan.json` | onboarding / milestone / owner / acceptance_refs |
| `adoption-health-report.json` | adoption stage / gap / renewal readiness |
| `security-review-record.json` | review scope / trust packet / open findings |
| `trust-packet-index.json` | data flow / controls / SBOM / vulnerabilities |
| `telemetry-event.jsonl` | allowed signal の product telemetry |
| `product-metrics-report.json` | aggregate product / reliability / docs metrics |
| `residency-profile.json` | deployment mode / data class routing / region policy |
| `deployment-topology.json` | data plane / control plane / network / recovery |
| `roadmap-item.json` | roadmap status / source_refs / acceptance_refs |
| `product-decision-record.md` | product decision rationale / impact / rollout |
| `accessibility-report.json` | surface / target / violations / owner |
| `localization-report.json` | locale / message coverage / stale docs |
| `commercial-commitment-register.json` | commitment / source contract / verification |
| `contract-exception-register.json` | redline / exception / workaround / expiry |
| `audit-fixture-manifest.json` | audit fixture / source contract / expected output |
| `assurance-summary.md` | audit scope / limitation / open finding |
| `requirements-portfolio.json` | tier / stage / owner / dependency |
| `portfolio-health-report.json` | WIP / stale / dependency / P0 leak |

これらは HATE の品質判定正本ではない。実装運用を追跡するための
workflow-cookbook 接続 artifact である。

## 4. 生成規則

- `workflow-task-seed.json`
  - `task_id`, `objective`, `scope`, `requirements`, `affected_paths`,
    `local_commands`, `acceptance_refs` を持つ。
  - HATE-MVP-* は 0.5 日程度の作業単位へ分割する。
- `workflow-acceptance-record.json`
  - `acceptance_id`, `task_id`, `scope`, `acceptance_criteria`,
    `evidence_refs`, `verification_result` を持つ。
  - 完了を実装状態より強く表現しない。
- `workflow-evidence.jsonl`
  - 1 行 1 Evidence record とし、HATE の `record_id`, `run_id`,
    `commit_sha`, `artifact_refs`, `dq_summary`, `aete_summary` を含める。
  - `agent-protocols` Evidence へ写像可能な field 名を保つ。
- `workflow-docs-stale.json`
  - `doc_ref`, `last_reviewed_at`, `next_review_due`, `stale_status`,
    `required_action` を持つ。
- `workflow-birdseye-map.json`
  - `node_id`, `path`, `role`, `deps_out`, `risk` を持つ。
  - HATE 自身で Birdseye 正本を持たず、workflow-cookbook 形式へ渡す候補に留める。
- `product-readiness-report.json`
  - `readiness_gate`, `status`, `evidence_refs`, `metric_refs`,
    `missing_requirements`, `owner`, `next_action` を持つ。
  - PRG-0..PRG-6 の状態を sales 表現ではなく artifact / metric で説明する。
- `entitlement-manifest.json`
  - `edition`, `entitlements`, `limits`, `usage`, `over_limit_actions` を持つ。
  - entitlement により precheck decision / QEG verdict を変更しない。
- `customer-docs-index.json`
  - `doc_id`, `path`, `audience`, `source_contracts`, `review_due`,
    `verification_result` を持つ。
  - stale / broken reference / overclaim を workflow-docs-stale と接続する。
- `incident-record.json` / `slo-report.json`
  - `incident_id`, `class`, `severity`, `status`, `timeline`, `evidence_refs`,
    `slo_target`, `breach_status` を持つ。
  - incident response は canonical evidence を改変せず追跡 record として残す。
- `adoption-plan.json` / `adoption-health-report.json`
  - `stage`, `milestones`, `owner`, `acceptance_refs`, `adoption_gaps`,
    `renewal_readiness` を持つ。
  - adoption gap は evidence gap や risk debt と混同しない。
- `security-review-record.json` / `trust-packet-index.json`
  - `scope`, `trust_packet_refs`, `control_mappings`, `open_findings`,
    `freshness_status` を持つ。
  - trust packet は customer source code、secret、PII、unsafe artifact を含まない。
- `telemetry-event.jsonl` / `product-metrics-report.json`
  - `event_name`, `purpose`, `telemetry_mode`, `redaction_status`,
    `allowed_signal_refs` を持つ。
  - telemetry off でも local-first precheck と QEG export を妨げない。
- `residency-profile.json` / `deployment-topology.json`
  - `deployment_mode`, `data_classes`, `regions`, `network`, `recovery`,
    `owner` を持つ。
  - region / deployment mode により precheck decision / QEG verdict を変更しない。
- `roadmap-item.json` / `product-decision-record.md`
  - `source_refs`, `personas`, `decision_status`, `acceptance_refs`,
    `rollout_plan` を持つ。
  - roadmap communication は released でない機能を available と表現しない。
- `accessibility-report.json` / `localization-report.json`
  - `surface`, `target`, `locale`, `message_catalog_version`, `violations`,
    `missing_messages` を持つ。
  - localization は stable code / schema field / record_id を変えない。
- `commercial-commitment-register.json` / `contract-exception-register.json`
  - `commitment_id`, `source_contracts`, `status`, `owner`, `verification_refs`,
    `expiry` を持つ。
  - unsupported / planned capability を available と表現しない。
- `audit-fixture-manifest.json` / `assurance-summary.md`
  - `source_contracts`, `expected_output_refs`, `verification_commands`,
    `safe_to_share`, `open_findings` を持つ。
  - assurance pack は open finding / limitation を隠さない。
- `requirements-portfolio.json` / `portfolio-health-report.json`
  - `tier`, `stage`, `owner`, `acceptance_refs`, `dependencies`, `wip_status` を持つ。
  - P0a/P0b が P2/P3 productization に依存する状態を検出する。

## 5. CLI 連携案

```text
HATE workflow task-seeds     # HATE-MVP-* を Task Seed 互換 artifact にする
HATE workflow acceptance     # 検収結果を acceptance record 互換 artifact にする
HATE workflow evidence       # HATE artifact refs を Evidence JSONL へ写像する
HATE workflow docs-stale     # docs freshness / stale check 用 artifact を出す
HATE workflow birdseye       # HATE docs/schema/fixture の依存マップ候補を出す
HATE workflow product-ready  # PRG-0..PRG-6 の product readiness 状態を出す
HATE workflow entitlement    # edition / entitlement / usage 状態を出す
HATE workflow docs-index     # customer-facing docs の鮮度と検証状態を出す
HATE workflow incident       # incident record / SLO report を出す
HATE workflow adoption       # adoption plan / health / renewal readiness を出す
HATE workflow trust          # security review / trust packet 状態を出す
HATE workflow telemetry      # privacy-safe telemetry / product metrics を出す
HATE workflow residency      # deployment / residency / recovery 状態を出す
HATE workflow roadmap        # roadmap / decision record 状態を出す
HATE workflow accessibility  # accessibility / localization 状態を出す
HATE workflow contracts      # commercial commitment / exception 状態を出す
HATE workflow assurance      # audit fixture / assurance pack 状態を出す
HATE workflow portfolio      # requirements portfolio / health 状態を出す
```

## 6. 責務境界

- HATE は workflow-cookbook の checker / plugin host を再実装しない。
- HATE は Task Seed / Acceptance / Evidence に渡せる artifact を生成する。
- HATE は product readiness gate を追跡するが、商用 readiness を release Gate
  正本や QEG approval の代替にしない。
- Acceptance record の正本は workflow-cookbook 形式の `docs/acceptance/` に置く。
- Evidence 契約の正本は `agent-protocols` に委譲する。
- docs resolve / stale check の正本は workflow plugin / memx-resolver に委譲する。

## 7. 最小 fixture

実装時は次の fixture を用意する。

- `fixtures/workflow/task-seed.sample.json`
- `fixtures/workflow/acceptance-record.sample.json`
- `fixtures/workflow/evidence.sample.jsonl`
- `fixtures/workflow/docs-stale.sample.json`
- `fixtures/workflow/birdseye-map.sample.json`
- `fixtures/workflow/product-readiness-report.sample.json`
- `fixtures/workflow/error-taxonomy.sample.json`
- `fixtures/workflow/domain-model.sample.json`
- `fixtures/workflow/schema-registry.sample.json`
- `fixtures/workflow/adapter-conformance-report.sample.json`
- `fixtures/workflow/risk-debt-register.sample.json`
- `fixtures/workflow/privacy-report.sample.json`
- `fixtures/workflow/hosted-read-model.sample.json`
- `fixtures/workflow/release-evidence.sample.json`
- `fixtures/workflow/entitlement-manifest.sample.json`
- `fixtures/workflow/customer-docs-index.sample.json`
- `fixtures/workflow/incident-record.sample.json`
- `fixtures/workflow/slo-report.sample.json`
- `fixtures/workflow/adoption-plan.sample.json`
- `fixtures/workflow/adoption-health-report.sample.json`
- `fixtures/workflow/security-review-record.sample.json`
- `fixtures/workflow/trust-packet-index.sample.json`
- `fixtures/workflow/telemetry-event.sample.jsonl`
- `fixtures/workflow/product-metrics-report.sample.json`
- `fixtures/workflow/residency-profile.sample.json`
- `fixtures/workflow/deployment-topology.sample.json`
- `fixtures/workflow/roadmap-item.sample.json`
- `fixtures/workflow/product-decision-record.sample.md`
- `fixtures/workflow/accessibility-report.sample.json`
- `fixtures/workflow/localization-report.sample.json`
- `fixtures/workflow/commercial-commitment-register.sample.json`
- `fixtures/workflow/contract-exception-register.sample.json`
- `fixtures/workflow/audit-fixture-manifest.sample.json`
- `fixtures/workflow/assurance-summary.sample.md`
- `fixtures/workflow/requirements-portfolio.sample.json`
- `fixtures/workflow/portfolio-health-report.sample.json`
- `fixtures/golden/p0a-minimal/input/*`
- `fixtures/golden/p0a-minimal/expected/*`
- `fixtures/golden/p0a-minimal/dq-*`

これらは P1 の workflow-cookbook 接続を検証するための最小契約であり、
P0a の local-first precheck 判定を妨げない。
