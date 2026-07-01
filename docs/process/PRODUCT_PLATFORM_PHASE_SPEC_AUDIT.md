---
intent_id: INT-HATE-PRODUCT-PLATFORM-PHASE-SPEC-AUDIT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Product Platform Phase Specification Audit

本書は `PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md`、
`PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md`、
`PRODUCT_PLATFORM_PHASE_IMPLEMENTATION_PACKETS.md` の抜け漏れ監査記録である。

## 1. Audit Method

確認観点:

- requirement ID が acceptance ID と packet ID に落ちているか
- NFR が packet や UAT gate に落ちているか
- 既存正本 `API_REQUIREMENTS.md`、`HOSTED_READ_MODEL_API.md`、
  `DATA_RETENTION_LEGAL_REQUIREMENTS.md`、`SECURITY_REVIEW_TRUST_CONTRACT.md`、
  `SLO_INCIDENT_RESPONSE_CONTRACT.md` と矛盾しないか
- external repo を修正対象にしていないか
- dashboard/API/HTML が canonical store projection として扱われているか
- 会社利用時に必要な RBAC、retention、legal hold、baseline governance、
  plugin trust、backup/restore が acceptance まで落ちているか

## 2. Findings

| Finding ID | Severity | Initial Gap | Resolution |
|---|---|---|---|
| PPH-AUD-001 | high | NFR の一部が packet に落ちていなかった | PPH-PKT-EVAL-010、OPS-009、UX-009、SCALE-008 等を追加 |
| PPH-AUD-002 | high | baseline approval/freeze/expiry が評価基盤要件になかった | PPH-EVAL-009 と baseline event 仕様を追加 |
| PPH-AUD-003 | high | redaction/deterministic normalization が明示不足 | PPH-EVAL-010 と output redaction pipeline を追加 |
| PPH-AUD-004 | high | operating model に notification/SLA breach がなかった | PPH-OPS-009 と notification event を追加 |
| PPH-AUD-005 | high | retention/legal hold 後の projection rebuild が薄かった | PPH-OPS-010 と store recovery requirement を追加 |
| PPH-AUD-006 | high | plugin semver/migration/trust が packet 化されていなかった | PPH-EXT-009、PPH-EXT-010 を追加 |
| PPH-AUD-007 | high | 利用面の RBAC が API 文書依存で phase acceptance にない | PPH-UX-009 と RBAC decision record を追加 |
| PPH-AUD-008 | medium | offline HTML/read-model performance/schema compatibility が packet 化されていなかった | PPH-UX-010 と PPH-PKT-UX-009 を追加 |
| PPH-AUD-009 | high | backup/restore/schema migration/corruption detection が大規模化に不足 | PPH-SCALE-009 と recovery report を追加 |
| PPH-AUD-010 | medium | 1000 repo/100万 finding の capacity degradation mode が弱かった | PPH-SCALE-010 と capacity benchmark packet を追加 |

## 3. Coverage After Fix

| Phase | Requirement Coverage | Spec Coverage | Packet Coverage | Remaining Spec Risk |
|---|---|---|---|---|
| 評価基盤 | PPH-EVAL-001..010 | roster v2, run history, score, regression, baseline, redaction, store schema link | PPH-PKT-EVAL-001..010 | physical store and output safety specs connected |
| 運用基盤 | PPH-OPS-001..010 | operating model, lifecycle, readiness, tracker, notification, rebuild, store schema link | PPH-PKT-OPS-001..009 | connector sync and store rebuild specs connected |
| 拡張基盤 | PPH-EXT-001..010 | manifest, policy config, sandbox, normalization, compatibility, trust | PPH-PKT-EXT-001..009 | policy config and plugin sandbox specs connected |
| 利用面 | PPH-UX-001..010 | CLI, read model, API, HTML, dashboard wireframes, RBAC, offline/performance | PPH-PKT-UX-001..009 | RBAC and dashboard wireframe specs connected |
| 大規模化 | PPH-SCALE-001..010 | cache, parallel, incremental, scheduler, artifact store, recovery, benchmark fixtures | PPH-PKT-SCALE-001..009 | store recovery and benchmark fixture specs connected |

## 4. No-Go Checklist

The platform phase specifications are not complete if any item below is true:

- Any PPH requirement lacks an acceptance ID.
- Any PPH requirement lacks at least one implementation packet.
- Any NFR lacks a packet, UAT gate, or explicit performance/security check.
- Baseline promotion can happen without actor, reason, approval, and sourceRef.
- Score can be emitted without score_breakdown and decision_basis.
- External repo hold can be reported as HATE implementation failure without classification evidence.
- Operating records can be changed by external tracker state without canonical event.
- Accepted debt can expire without readiness impact.
- Manual review can unblock release without owner, reviewer, decision reason, expiry, and evidence_refs.
- Plugin output can bypass canonical finding normalization.
- Release/regulated profile can run unsigned or unallowlisted plugins.
- API/dashboard can expose raw unsafe artifact body, secret, PII, or restricted path.
- RBAC denial can leak restricted resource body.
- Cache hit can be used after policy/tool/input incompatibility.
- Incremental scan can claim full-suite readiness without explicit fresh full evidence.
- Backup/restore/migration can lose legal hold, retention, or audit events.

## 5. Physical Specification Closure

The following physical specifications were promoted from follow-up appendix
candidates to required specification inputs:

| Specification | Trigger Packet | Closure |
|---|---|---|
| `PLATFORM_STORE_SCHEMA_SPEC.md` | PPH-PKT-EVAL-003, OPS-002, SCALE-008 | physical tables, indexes, event ordering, migration, backup/restore defined |
| `PLATFORM_POLICY_CONFIG_SPEC.md` | PPH-PKT-EXT-003, EXT-004 | JSON policy shape, profile rules, thresholds, plugin trust, retention, scheduler budget defined |
| `PLATFORM_RBAC_MATRIX_SPEC.md` | PPH-PKT-UX-008 | role/resource/action matrix, tenant scope, raw artifact approval defined |
| `PLATFORM_DASHBOARD_WIREFRAME_SPEC.md` | PPH-PKT-UX-005 | view inventory, layout, state matrix, view model contracts defined |
| `PLATFORM_BENCHMARK_FIXTURE_SPEC.md` | PPH-PKT-SCALE-009 | deterministic dataset classes, distributions, metrics, degradation modes defined |
| `PLATFORM_CONNECTOR_SYNC_SPEC.md` | PPH-PKT-OPS-007, OPS-008 | connector payload, mirror boundary, idempotency, inbound ack denial defined |
| `PLATFORM_PLUGIN_SANDBOX_SPEC.md` | PPH-PKT-EXT-005, EXT-009 | execution modes, resource limits, trust enforcement, failure isolation defined |

## 6. Residual Implementation Validation

The remaining items are implementation validation work that must produce
evidence against the required specifications:

- connector implementations must prove conformance to `PLATFORM_CONNECTOR_SYNC_SPEC.md`
- plugin sandbox implementations must prove conformance to `PLATFORM_PLUGIN_SANDBOX_SPEC.md`
- dashboard UI must render the view-model and state fixtures in `PLATFORM_DASHBOARD_WIREFRAME_SPEC.md`
- benchmark implementation must generate measured baselines from `PLATFORM_BENCHMARK_FIXTURE_SPEC.md`
