---
intent_id: INT-HATE-PRODUCT-REQUIREMENTS-EXPANSION-PACKETS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-08
---

# Product Requirements Expansion Packets

This packet ledger turns HATE-GAP-027 through HATE-GAP-060 into implementable
worker units. It is separate from `PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md`
so the implemented HATE-GAP-001..026 baseline remains stable.

Detailed input vocabulary, finding codes, fixture alias policy, schema registry
rules, and UAT hardening rules are defined in
`PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md`. A packet is not implementable
until both this ledger and the detail spec contain its contract.

## 1. Common Expansion Packet Contract

| Field | Required value |
|---|---|
| `gap_id` | One `HATE-GAP-027` through `HATE-GAP-060` |
| `packet_id` | Stable handoff ID |
| `contract_ref` | Spec or future contract section |
| `positive_fixture` | Planned fixture path for pass behavior |
| `negative_fixture` | Planned fixture path for hold/deny behavior |
| `uat_evidence` | Planned generated report |
| `owner` | Role accountable for acceptance |
| `done_gate` | Test or generated evidence required before implementation can be called done |

## 2. Expansion Packet Ledger

| Gap | Packet ID | Contract ref | Positive fixture | Negative fixture | UAT evidence | Owner | Done gate |
|---|---|---|---|---|---|---|---|
| HATE-GAP-027 | HATE-PKT-EXP-001-onboarding | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#guided-onboarding-and-sample-projects` | `fixtures/expansion/onboarding/golden-walkthrough/fixture.json` | `fixtures/expansion/onboarding/parser-failure-tutorial/fixture.json` | `onboarding-uat-report.json` | Developer Platform | sample repo, expected output, failed-run tutorial tests |
| HATE-GAP-028 | HATE-PKT-EXP-002-policy-simulation | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#policy-simulation-and-change-preview` | `fixtures/expansion/policy-simulation/safe-dry-run/fixture.json` | `fixtures/expansion/policy-simulation/blast-radius-unbounded/fixture.json` | `policy-simulation-uat-report.json` | Platform Admin | dry-run diff, affected repo list, rollback evidence tests |
| HATE-GAP-029 | HATE-PKT-EXP-003-bulk-portability | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#bulk-import-export-and-data-portability` | `fixtures/expansion/bulk-portability/resumable-export/fixture.json` | `fixtures/expansion/bulk-portability/cross-tenant-import-denied/fixture.json` | `bulk-portability-uat-report.json` | Platform Admin | chunk manifest, resume token, integrity, tenant denial tests |
| HATE-GAP-030 | HATE-PKT-EXP-004-notifications | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#notifications-webhooks-and-external-delivery` | `fixtures/expansion/notifications/signed-delivery/fixture.json` | `fixtures/expansion/notifications/unsigned-webhook-denied/fixture.json` | `notification-uat-report.json` | SRE | signing, retry, dedupe, dead-letter tests |
| HATE-GAP-031 | HATE-PKT-EXP-005-self-hosted | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#self-hosted-installation-and-upgrade` | `fixtures/expansion/self-hosted/upgrade-compatible/fixture.json` | `fixtures/expansion/self-hosted/rollback-required/fixture.json` | `self-hosted-uat-report.json` | SRE | install, upgrade, downgrade, offline verification tests |
| HATE-GAP-032 | HATE-PKT-EXP-006-data-classification | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#data-classification-taxonomy` | `fixtures/expansion/data-classification/public-summary-safe/fixture.json` | `fixtures/expansion/data-classification/prohibited-telemetry-denied/fixture.json` | `data-classification-uat-report.json` | Security Engineer | field class, sink allowlist, redaction, telemetry denial tests |
| HATE-GAP-033 | HATE-PKT-EXP-007-docs-lifecycle | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#customer-documentation-lifecycle` | `fixtures/expansion/docs-lifecycle/version-bound-docs/fixture.json` | `fixtures/expansion/docs-lifecycle/stale-claim-denied/fixture.json` | `docs-lifecycle-uat-report.json` | Customer Success | required docs, version binding, broken ref, stale claim tests |
| HATE-GAP-034 | HATE-PKT-EXP-008-dependency-compliance | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#dependency-sbom-and-license-compliance` | `fixtures/expansion/dependency-compliance/sbom-clean/fixture.json` | `fixtures/expansion/dependency-compliance/denied-license/fixture.json` | `dependency-compliance-uat-report.json` | Security Engineer | SBOM, license policy, vulnerability exception expiry tests |
| HATE-GAP-035 | HATE-PKT-EXP-009-adapter-marketplace | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#adapterplugin-marketplace-lifecycle` | `fixtures/expansion/adapter-marketplace/signed-compatible-plugin/fixture.json` | `fixtures/expansion/adapter-marketplace/revoked-plugin-denied/fixture.json` | `adapter-marketplace-uat-report.json` | Developer Platform | signature, compatibility, deprecation, revocation tests |
| HATE-GAP-036 | HATE-PKT-EXP-010-product-analytics | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#product-analytics-and-adoption-measurement` | `fixtures/expansion/product-analytics/aggregate-opt-in/fixture.json` | `fixtures/expansion/product-analytics/raw-path-event-denied/fixture.json` | `product-analytics-uat-report.json` | Product Manager | event allowlist, opt-in, suppression, adoption KPI tests |
| HATE-GAP-037 | HATE-PKT-EXP-011-disaster-recovery | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#disaster-recovery-and-restore-drills` | `fixtures/expansion/disaster-recovery/restore-drill-pass/fixture.json` | `fixtures/expansion/disaster-recovery/corrupt-backup-denied/fixture.json` | `disaster-recovery-uat-report.json` | SRE | RPO/RTO, restore verification, corrupt backup tests |
| HATE-GAP-038 | HATE-PKT-EXP-012-a11y-l10n | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#accessibility-and-localization-execution` | `fixtures/expansion/a11y-l10n/locale-fallback-safe/fixture.json` | `fixtures/expansion/a11y-l10n/color-only-severity-denied/fixture.json` | `a11y-l10n-uat-report.json` | QA Lead | stable message IDs, keyboard, color, locale fallback tests |
| HATE-GAP-039 | HATE-PKT-EXP-013-cost-governance | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#cost-storage-and-usage-forecasting` | `fixtures/expansion/cost-governance/forecast-within-budget/fixture.json` | `fixtures/expansion/cost-governance/egress-risk-hold/fixture.json` | `cost-governance-uat-report.json` | Platform Admin | forecast, storage class, egress warning, non-gating tests |
| HATE-GAP-040 | HATE-PKT-EXP-014-beta-acceptance | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#customer-beta-and-acceptance-program` | `fixtures/expansion/beta-acceptance/cohort-exit-pass/fixture.json` | `fixtures/expansion/beta-acceptance/blocker-feedback-hold/fixture.json` | `beta-acceptance-uat-report.json` | Product Manager | cohort, feedback classification, blocker triage, exit criteria tests |
| HATE-GAP-041 | HATE-PKT-EXP-015-rollout-adoption | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#company-rollout-and-adoption-operations` | `fixtures/expansion/rollout-adoption/staged-wave-pass/fixture.json` | `fixtures/expansion/rollout-adoption/expired-exception-blocks/fixture.json` | `rollout-adoption-uat-report.json` | Platform Admin | rollout wave, repo status, exception expiry, rollback tests |
| HATE-GAP-042 | HATE-PKT-EXP-016-provider-matrix | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#ciscm-provider-matrix` | `fixtures/expansion/provider-matrix/gitlab-identity-pass/fixture.json` | `fixtures/expansion/provider-matrix/overbroad-permission-denied/fixture.json` | `provider-integration-uat-report.json` | Developer Platform | provider identity, permissions, artifact lifetime, rerun tests |
| HATE-GAP-043 | HATE-PKT-EXP-017-runner-dialects | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#language-and-runner-coverage` | `fixtures/expansion/runner-dialects/dotnet-xunit-pass/fixture.json` | `fixtures/expansion/runner-dialects/unsupported-runner-capability-gap/fixture.json` | `runner-dialect-coverage-uat-report.json` | Developer Platform | runner support states, conformance, capability gap tests |
| HATE-GAP-044 | HATE-PKT-EXP-018-recurring-real-repo-eval | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#recurring-real-repository-evaluation` | `fixtures/expansion/recurring-real-repo-eval/baseline-trend-pass/fixture.json` | `fixtures/expansion/recurring-real-repo-eval/regression-timeout-hold/fixture.json` | `recurring-real-repo-eval-uat-report.json` | QA Lead | roster, baseline, regression, timeout, privacy trend tests |
| HATE-GAP-045 | HATE-PKT-EXP-019-governance-workflow | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#organizational-governance-workflow` | `fixtures/expansion/governance-workflow/policy-approved-pass/fixture.json` | `fixtures/expansion/governance-workflow/self-approval-denied/fixture.json` | `governance-review-uat-report.json` | Governance Reviewer | policy approval, exception lifecycle, delegation denial tests |
| HATE-GAP-046 | HATE-PKT-EXP-020-security-procurement | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#security-procurement-and-trust-package` | `fixtures/expansion/security-procurement/trust-packet-safe/fixture.json` | `fixtures/expansion/security-procurement/unsupported-certification-claim/fixture.json` | `security-procurement-uat-report.json` | Security Engineer | data flow, control claim, vuln SLA, safe export tests |
| HATE-GAP-047 | HATE-PKT-EXP-021-value-measurement | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#value-measurement-and-roi` | `fixtures/expansion/value-measurement/aggregate-roi-pass/fixture.json` | `fixtures/expansion/value-measurement/individual-leaderboard-denied/fixture.json` | `value-measurement-uat-report.json` | Product Manager | aggregate metrics, confidence, noisy signal, privacy tests |
| HATE-GAP-048 | HATE-PKT-EXP-022-developer-experience | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#daily-developer-experience` | `fixtures/expansion/developer-experience/actionable-pr-feedback/fixture.json` | `fixtures/expansion/developer-experience/broad-suppression-denied/fixture.json` | `developer-experience-uat-report.json` | Developer Platform | PR feedback, local explain, suppression, recommendation quality tests |
| HATE-GAP-049 | HATE-PKT-EXP-023-impact-analysis | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#impact-analysis` | `fixtures/expansion/impact-analysis/dependency-impact-pass/fixture.json` | `fixtures/expansion/impact-analysis/missing-dependency-source-hold/fixture.json` | `impact-analysis-uat-report.json` | QA Lead | dependency, ownership, history, confidence sourceRefs tests |
| HATE-GAP-050 | HATE-PKT-EXP-024-test-recommendation | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#test-recommendation-engine` | `fixtures/expansion/test-recommendation/missing-oracle-actionable/fixture.json` | `fixtures/expansion/test-recommendation/generic-advice-denied/fixture.json` | `test-recommendation-uat-report.json` | Developer Platform | action taxonomy, oracle, command, verification tests |
| HATE-GAP-051 | HATE-PKT-EXP-025-flaky-classification | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#flaky-classification` | `fixtures/expansion/flaky-classification/environment-flake-classified/fixture.json` | `fixtures/expansion/flaky-classification/unknown-flake-hold/fixture.json` | `flaky-classification-uat-report.json` | QA Lead | class taxonomy, attempt history, environment deltas tests |
| HATE-GAP-052 | HATE-PKT-EXP-026-oracle-classification | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#oracle-classification` | `fixtures/expansion/oracle-classification/property-oracle-pass/fixture.json` | `fixtures/expansion/oracle-classification/snapshot-only-critical-hold/fixture.json` | `oracle-classification-uat-report.json` | QA Lead | oracle taxonomy, semantic guard, no-oracle readiness tests |
| HATE-GAP-053 | HATE-PKT-EXP-027-evidence-synthesis | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#evidence-synthesis` | `fixtures/expansion/evidence-synthesis/contract-mutation-confidence-pass/fixture.json` | `fixtures/expansion/evidence-synthesis/weak-evidence-inflation-denied/fixture.json` | `evidence-synthesis-uat-report.json` | Release Manager | weighted evidence, confidence bounds, contradiction tests |
| HATE-GAP-054 | HATE-PKT-EXP-028-test-quality | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#test-code-quality-analysis` | `fixtures/expansion/test-quality/deterministic-tests-pass/fixture.json` | `fixtures/expansion/test-quality/sleep-based-test-hold/fixture.json` | `test-quality-uat-report.json` | QA Lead | duplicate, snapshot, fixture dependency, nondeterminism tests |
| HATE-GAP-055 | HATE-PKT-EXP-029-environment-diff | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#execution-environment-diff` | `fixtures/expansion/environment-diff/runtime-version-drift-explained/fixture.json` | `fixtures/expansion/environment-diff/unexplained-env-drift-hold/fixture.json` | `environment-diff-uat-report.json` | Developer Platform | OS, runtime, image, dependency, cache, shard diff tests |
| HATE-GAP-056 | HATE-PKT-EXP-030-contradiction-detection | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#cross-evidence-contradiction-detection` | `fixtures/expansion/contradiction-detection/consistent-evidence-pass/fixture.json` | `fixtures/expansion/contradiction-detection/pass-with-critical-finding-blocked/fixture.json` | `contradiction-uat-report.json` | Release Manager | contradiction taxonomy, blocking, release claim impact tests |
| HATE-GAP-057 | HATE-PKT-EXP-031-historical-regression | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#historical-regression-analysis` | `fixtures/expansion/historical-regression/stable-trend-pass/fixture.json` | `fixtures/expansion/historical-regression/recurring-failure-blocked/fixture.json` | `historical-regression-uat-report.json` | QA Lead | baseline window, recurrence, trend degradation tests |
| HATE-GAP-058 | HATE-PKT-EXP-032-audience-report-pack | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#multi-audience-report-generation` | `fixtures/expansion/audience-report-pack/shared-sourcerefs-pass/fixture.json` | `fixtures/expansion/audience-report-pack/verdict-recomputed-denied/fixture.json` | `audience-report-pack-uat-report.json` | Release Manager | developer, QA, release, QEG, machine views tests |
| HATE-GAP-059 | HATE-PKT-EXP-033-fixture-quality | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#fixture-and-corpus-quality-detection` | `fixtures/expansion/fixture-quality/corpus-quality-pass/fixture.json` | `fixtures/expansion/fixture-quality/fixture-name-coupled-hold/fixture.json` | `fixture-quality-uat-report.json` | QA Lead | stale, duplicate, expected leakage, schema drift tests |
| HATE-GAP-060 | HATE-PKT-EXP-034-adapter-capability-diff | `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md#adapter-capability-diff` | `fixtures/expansion/adapter-capability-diff/lossless-normalization-pass/fixture.json` | `fixtures/expansion/adapter-capability-diff/lossy-field-drop-hold/fixture.json` | `adapter-capability-diff-uat-report.json` | Developer Platform | raw field map, normalized field map, lossy transform tests |

## 3. Status

All expansion packets are `specified`. A packet remains `planned` until code,
schemas, fixtures, tests, generated UAT reports, Birdseye updates, and
acceptance records exist.

HATE-GAP-034 through HATE-GAP-040 are `specified-ready` at the documentation
contract level after `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` section 11
through section 18. They remain unimplemented until runtime modules, schemas,
fixtures, tests, generated UAT reports, Birdseye updates, and acceptance records
exist.

HATE-GAP-041 through HATE-GAP-048 are `implemented-ready` as third-wave
portfolio readiness reports. Their runtime module is
`src/hate/expansion/portfolio_readiness.py`; their schemas are registered under
`schemas/HATE/v1/*-report.schema.json`; their positive and negative canonical
fixtures live under `fixtures/expansion/{rollout-adoption,provider-matrix,
runner-dialects,recurring-real-repo-eval,governance-workflow,
security-procurement,value-measurement,developer-experience}/`; and they are
specified in `PRODUCT_REQUIREMENTS_PORTFOLIO_READINESS_DETAIL_SPEC.md` and
connected to the expansion runner, release candidate pack, acceptance matrix,
and tests.

HATE-GAP-049 through HATE-GAP-060 are `specified-ready` at the documentation
contract level after `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` section 23
through section 26. They remain unimplemented until runtime modules, schemas,
fixtures, tests, generated UAT reports, Birdseye updates, and acceptance records
exist.
