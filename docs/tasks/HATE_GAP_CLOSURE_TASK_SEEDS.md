---
intent_id: INT-HATE-GAP-CLOSURE-TASK-SEEDS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# HATE Gap Closure Task Seeds

This document projects HATE-GAP-001 through HATE-GAP-026 into workflow-cookbook
style Task Seeds. It is the dispatch ledger for turning requirement gaps into
small implementation work.

Each task seed is intentionally scoped to a <=0.5d slice when implemented by a
single worker. If a packet is larger, it must split into child seeds while
preserving the parent `packet_id`.

## Common Requirements

- Update source, schema, fixture, tests, docs, and Birdseye when applicable.
- Add positive and negative fixtures named in `PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md`.
- Add or update acceptance evidence in `docs/acceptance/HATE_GAP_CLOSURE_ACCEPTANCE.md`.
- Do not mark a task `done` without acceptance evidence or an explicit exception.
- Do not claim hosted, enterprise, product-ready, or accepted status from docs-only work.

## Task Seed Ledger

| Task seed | Gap | Packet | Objective | Scope in | Scope out | Acceptance |
|---|---|---|---|---|---|---|
| TASK-HATE-GAP-001 | HATE-GAP-001 | HATE-PKT-RUNTIME-001-worker-runtime | Implement hosted worker job lifecycle contract and fixtures | runtime worker schema, queue state tests, worker fixtures | local P0/P1 CLI dependency | AC-HATE-GAP-001 |
| TASK-HATE-GAP-002 | HATE-GAP-002 | HATE-PKT-ENT-001-tenant-isolation | Implement tenant isolation matrix and denial fixtures | enterprise authz, store/artifact/audit/export fixtures | global admin UX | AC-HATE-GAP-002 |
| TASK-HATE-GAP-003 | HATE-GAP-003 | HATE-PKT-API-001-rate-limit | Implement API rate limit and abuse prevention contract | API envelope, quota fixtures, audit events | billing charge calculation | AC-HATE-GAP-003 |
| TASK-HATE-GAP-004 | HATE-GAP-004 | HATE-PKT-COM-001-entitlement | Implement plan entitlement and local-first non-gating behavior | entitlement schema, plan fixtures, denial tests | payment processor integration | AC-HATE-GAP-004 |
| TASK-HATE-GAP-005 | HATE-GAP-005 | HATE-PKT-GH-001-github-integration | Implement GitHub App/Action responsibility split fixtures | GitHub contract fixtures, annotation export tests | QEG approval or GitHub admin policy mutation | AC-HATE-GAP-005 |
| TASK-HATE-GAP-006 | HATE-GAP-006 | HATE-PKT-STORE-001-migration-rebuild | Implement store migration, rollback, and index rebuild evidence | store migration schema, replay verification, rollback report, version-skew denial, rebuild checkpoint hash, canonical immutability fixtures | hosted DB vendor provisioning | AC-HATE-GAP-006 |
| TASK-HATE-GAP-007 | HATE-GAP-007 | HATE-PKT-CORPUS-001-adapter-corpus | Implement adapter corpus manifest and stale fixture audit | corpus manifest, dialect matrix, stale audit tests | every future third-party adapter | AC-HATE-GAP-007 |
| TASK-HATE-GAP-008 | HATE-GAP-008 | HATE-PKT-UI-001-dashboard-states | Implement dashboard state matrix fixtures | view-model schemas, ready/error/empty/stale/RBAC fixtures | full visual frontend app | AC-HATE-GAP-008 |
| TASK-HATE-GAP-009 | HATE-GAP-009 | HATE-PKT-API-002-contract-depth | Expand API request/response/error contract tests | OpenAPI, filter/sort/pagination fixtures, authz denial | hosted deployment runtime | AC-HATE-GAP-009 |
| TASK-HATE-GAP-010 | HATE-GAP-010 | HATE-PKT-OPS-001-observability | Implement observability contract and incident fixtures | metrics/log/span schemas, alert fixtures, incident report tests | external monitoring SaaS setup | AC-HATE-GAP-010 |
| TASK-HATE-GAP-011 | HATE-GAP-011 | HATE-PKT-SUP-001-diagnostics | Implement safe customer diagnostics bundle contract | support bundle schema, redaction fixtures, environment matrix | remote customer code collection | AC-HATE-GAP-011 |
| TASK-HATE-GAP-012 | HATE-GAP-012 | HATE-PKT-EVAL-001-real-repo-scheduler | Implement real-repo evaluation baseline and regression contract | evaluation roster, timeout records, baseline comparison fixtures | always-on hosted scheduler | AC-HATE-GAP-012 |
| TASK-HATE-GAP-013 | HATE-GAP-013 | HATE-PKT-EVAL-002-agent-quality | Implement agent/model quality evaluation requirement | scoring schema, reviewer workflow fixtures, retention contract | model training or ranking service | AC-HATE-GAP-013 |
| TASK-HATE-GAP-014 | HATE-GAP-014 | HATE-PKT-ADAPTER-001-family-packets | Decompose adapter families into uniform implementation packets | adapter family packets, manifest tests, malformed fixtures | vendor-specific support SLAs | AC-HATE-GAP-014 |
| TASK-HATE-GAP-015 | HATE-GAP-015 | HATE-PKT-ENT-002-control-packets | Decompose enterprise controls into implementation packets | RBAC, audit, legal hold, retention, connector packet fixtures | production IdP rollout | AC-HATE-GAP-015 |
| TASK-HATE-GAP-016 | HATE-GAP-016 | HATE-PKT-ART-001-artifact-lifecycle | Implement artifact lifecycle state machine and fixtures | quarantine/release/delete/hold fixtures, lifecycle schema | blob storage vendor provisioning | AC-HATE-GAP-016 |
| TASK-HATE-GAP-017 | HATE-GAP-017 | HATE-PKT-DEPLOY-001-topology | Implement deployment topology matrix and acceptance fixtures | topology report schema, backup/restore/offline fixtures | infra automation for every cloud | AC-HATE-GAP-017 |
| TASK-HATE-GAP-018 | HATE-GAP-018 | HATE-PKT-PERF-001-benchmark-catalog | Implement benchmark catalog and drift thresholds | performance fixtures, baseline reports, budget tests | exhaustive public benchmark suite | AC-HATE-GAP-018 |
| TASK-HATE-GAP-019 | HATE-GAP-019 | HATE-PKT-REL-001-release-channel | Implement release channel and migration evidence policy | channel matrix, rollback fixtures, deprecation tests | marketing release calendar | AC-HATE-GAP-019 |
| TASK-HATE-GAP-020 | HATE-GAP-020 | HATE-PKT-UAT-001-product-e2e | Implement six product E2E journey UAT fixtures | E2E fixtures, journey reports, open-risk register | complete hosted UI | AC-HATE-GAP-020 |
| TASK-HATE-GAP-021 | HATE-GAP-021 | HATE-PKT-WF-001-task-seed-loop | Implement Task Seed projection and validation | task seed schema/checker, valid/missing-scope fixtures | external issue tracker sync | AC-HATE-GAP-021 |
| TASK-HATE-GAP-022 | HATE-GAP-022 | HATE-PKT-WF-002-acceptance-linkage | Implement done-task acceptance linkage check | acceptance ledger, done-without-record fixture, index generation | GitHub PR automation | AC-HATE-GAP-022 |
| TASK-HATE-GAP-023 | HATE-GAP-023 | HATE-PKT-WF-003-evidence-protocol | Implement agent-protocols Evidence mapping | evidence schema, command/artifact/decision fixtures | remote evidence service | AC-HATE-GAP-023 |
| TASK-HATE-GAP-024 | HATE-GAP-024 | HATE-PKT-WF-004-birdseye-freshness | Implement Birdseye freshness gate | index/caps invariant checker, stale capsule fixture | workflow-cookbook upstream replacement | AC-HATE-GAP-024 |
| TASK-HATE-GAP-025 | HATE-GAP-025 | HATE-PKT-WF-005-plugin-integration | Implement workflow plugin integration contract | plugin config schema, task/acceptance/docs stale fixtures | all Agent_tools repo runtime integration | AC-HATE-GAP-025 |
| TASK-HATE-GAP-026 | HATE-GAP-026 | HATE-PKT-WF-006-completion-governance | Implement scope-safe completion governance checker | completion checker, overclaim fixtures, release evidence checks | human review replacement | AC-HATE-GAP-026 |

## Verification Commands

Every completed task seed must run the relevant subset plus:

```powershell
uv run python -m compileall src tests tools
uv run pytest -q
uv run pytest --cov=src/hate --cov-report=term-missing --cov-fail-under=80
uv run python tools/codemap/update.py
git diff --check
```

Large real-repo or product-scale checks should use `timeout_ms=900000`.
