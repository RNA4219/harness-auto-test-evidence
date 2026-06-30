---
intent_id: INT-HATE-PRODUCT-REQUIREMENTS-GAP-BACKLOG-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Product Requirements Gap Backlog

This document is the canonical backlog for requirement gaps that remain after
`PRODUCT_REQUIREMENTS_DEFINITION.md`, `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md`,
and the product/enterprise contract documents.

It exists to prevent "full implementation spec exists" from being confused with
"every implementable product requirement is fully decomposed." A gap remains open
until it has all of the following:

- product requirement ID
- acceptance ID
- implementation packet ID
- schema or interface contract
- positive fixture
- negative fixture
- UAT evidence
- owner and target milestone

Implementation packet closure is defined in
`PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md`. A gap can move from
`gap_identified` to `specified` when the packet ledger names the contract,
positive fixture, negative fixture, UAT evidence, owner, and done gate. It cannot
move to `implemented` or `accepted` until code, schemas, fixtures, tests, and
acceptance records exist.

## 1. Gap Classes

| Class | Meaning | Completion requirement |
|---|---|---|
| `missing_requirement` | The capability is not described as a product requirement | Add PRD section, persona/journey impact, acceptance refs |
| `thin_requirement` | The capability is mentioned but not implementable | Add API/CLI/schema/state/error details and fixtures |
| `packet_gap` | Requirement exists but implementation work is not sliced | Add worker packet with files, tests, acceptance, UAT |
| `fixture_gap` | Acceptance names behavior but no executable fixture exists | Add positive and negative fixtures with expected outputs |
| `runtime_gap` | Local artifact exists but hosted/runtime behavior is unspecified | Add lifecycle, storage, concurrency, failure, rollback behavior |
| `operational_gap` | Product use is specified but operation/support is weak | Add observability, diagnostics, incident, migration, support flow |

## 2. Requirement Gaps Under Closure

Current closure status:

- HATE-GAP-001 through HATE-GAP-026 have implementation evidence.
- Each gap has a packet ID, task seed ID, acceptance ID, positive fixture, negative fixture, UAT report path, schema or report contract, tests, and generated gap-closure evidence.
- The current generated report is `fixtures/gap-closure/expected/gap-closure-report.json`.
- Current machine status is `implemented`, not `accepted`; acceptance remains pending until UAT evidence is reviewed and approved.

The table below is retained as the product-requirement gap catalogue. Its
"Current state" column describes the original requirement weakness that created
the gap, not the latest implementation state.

| Gap ID | Class | Area | Current state | Required specification work | Target milestone |
|---|---|---|---|---|---|
| HATE-GAP-001 | `runtime_gap` | Hosted job/worker model | Hosted API/read model is specified, but background ingestion, queueing, retries, cancellation, and worker ownership are not fully decomposed | Add `HOSTED_WORKER_RUNTIME_CONTRACT.md` with job states, retry policy, idempotency, queue leases, poison messages, and worker UAT fixtures | Enterprise |
| HATE-GAP-002 | `runtime_gap` | Tenant isolation | Enterprise domain model names org/workspace/project, but physical isolation and cross-tenant denial tests are thin | Add tenant boundary matrix for store, artifact, cache, audit, export, support bundle, and telemetry paths | Enterprise |
| HATE-GAP-003 | `thin_requirement` | Rate limit and abuse prevention | API requirements mention authz/idempotency but not quota, abuse, or noisy CI behavior | Add endpoint/job/export quotas, retry-after semantics, burst handling, and abuse audit events | Team GA |
| HATE-GAP-004 | `missing_requirement` | Billing and entitlement | Packaging/entitlement exists as a contract, but plan gates and usage counters are not a product requirement matrix | Add plan/feature matrix, metering events, entitlement denial fixtures, and non-gating local-first behavior | Enterprise |
| HATE-GAP-005 | `thin_requirement` | GitHub App vs GitHub Action | CI/PR loop is specified, but GitHub App permissions, Action artifact ownership, annotations, and rerun behavior are not split enough | Add `GITHUB_INTEGRATION_CONTRACT.md` with scopes, event triggers, app/action responsibilities, check-run annotations, and security boundaries | Team GA |
| HATE-GAP-006 | `runtime_gap` | Store migration and index rebuild | Store/replay requirements exist, but long-lived DB/index migration, rebuild, compaction, and corruption recovery are thin | Add migration lifecycle, version skew handling, rebuild checkpoints, rollback, and replay verification fixtures | Enterprise |
| HATE-GAP-007 | `fixture_gap` | Large conformance corpus | Adapter/acceptance docs name fixture families, but corpus size, generation strategy, and maintenance rules are insufficient for product scale | Add corpus manifest, minimum dialect counts, synthetic-vs-real labeling, mutation rules, and stale fixture audit | Internal Alpha |
| HATE-GAP-008 | `thin_requirement` | Dashboard detailed UX states | UI workflows exist, but page-level loading/empty/error/partial/stale/RBAC-denied states are not fully enumerated | Add per-view state matrix, view-model schemas, keyboard/accessibility UAT, and snapshot/E2E fixtures | Team GA |
| HATE-GAP-009 | `thin_requirement` | API contract depth | API requirements list endpoints, but full request/response/error/pagination schemas are not complete for every endpoint | Expand OpenAPI and add contract tests for filters, sorting, pagination, staleness, authz leak denial, and partial data | Team GA |
| HATE-GAP-010 | `operational_gap` | Observability and incident response | SLO/incident contract exists, but runtime metrics, logs, traces, alert thresholds, and escalation runbooks are thin | Add observability contract with metric names, log fields, trace spans, alert rules, and incident fixture pack | Enterprise |
| HATE-GAP-011 | `operational_gap` | Customer diagnostics | Support bundle concepts exist, but customer environment diagnostics and safe remote triage flows are under-specified | Add diagnostic collection contract, redaction guarantees, environment matrix, and support escalation workflow | Enterprise |
| HATE-GAP-012 | `thin_requirement` | Real repository continuous evaluation | Real repo trials are logged manually, but recurring evaluation, baselines, regressions, and trend reports are not specified | Add real-repo evaluation scheduler, repo roster, timeouts, baseline comparison, and regression gate policy | Internal Alpha |
| HATE-GAP-013 | `missing_requirement` | Model/agent implementation quality comparison | Test integrity detects some AI avoidance, but model/agent comparative quality evaluation is not a product requirement | Add evaluation model for agent outputs, scoring dimensions, reviewer workflow, and evidence retention | Regulated |
| HATE-GAP-014 | `packet_gap` | Adapter implementation packets | Adapter SDK and dialect specs exist, but each adapter family is not decomposed into uniform worker packets | Add per-adapter packets for JUnit, pytest, Jest, Vitest, Playwright, LCOV, Cobertura, JaCoCo, coverage.py, SARIF, Pact, Stryker | Internal Alpha |
| HATE-GAP-015 | `packet_gap` | Enterprise control packets | RBAC/audit/retention specs exist, but implementation packets are not complete enough for parallel workers | Add worker packets for role matrix, permission evaluator, audit hash chain, legal hold, retention jobs, SCIM/SSO stubs | Enterprise |
| HATE-GAP-016 | `runtime_gap` | Artifact storage lifecycle | Artifact safety exists, but retention, quarantine release, raw access approval, archive scanning, and storage lifecycle are thin | Add artifact lifecycle state machine and fixtures for safe, unsafe, expired, legal hold, support export, and deletion denied | Team GA |
| HATE-GAP-017 | `thin_requirement` | Deployment topology | Data residency/deployment exists, but single-node/local/hosted/air-gapped deployment matrices are thin | Add topology matrix, secret management, backup/restore, region pinning, and offline mode acceptance | Enterprise |
| HATE-GAP-018 | `operational_gap` | Performance benchmark population | Scale requirements include budgets, but measured repo classes, dataset sizes, and benchmark ownership are not enough | Add benchmark catalog with small/medium/large/monorepo fixtures, performance baselines, and drift thresholds | Team GA |
| HATE-GAP-019 | `thin_requirement` | Release channel and migration policy | Release/migration exists, but release channels, deprecation windows, customer communication, and rollback evidence are thin | Add release channel matrix and migration acceptance for schema/API/adapter/profile changes | Enterprise |
| HATE-GAP-020 | `fixture_gap` | End-to-end product UAT | Acceptance matrix exists, but full user journeys do not all have executable E2E fixtures | Add E2E journey fixtures for developer PR, QA risk review, release review, admin governance, security quarantine, support triage | Team GA |
| HATE-GAP-021 | `operational_gap` | Workflow-cookbook Task Seed loop | HATE has implementation roadmaps and GLM packets, but not every gap/task is projected into workflow-cookbook style Task Seed fields | Add Task Seed projection rules with objective, scope, requirements, commands, dependencies, and <=0.5d slicing guidance | Internal Alpha |
| HATE-GAP-022 | `operational_gap` | Acceptance record linkage | HATE has UAT notes and evidence reports, but done work is not uniformly linked to `docs/acceptance/AC-YYYYMMDD-xx.md` style records | Add acceptance record contract, done-task acceptance requirement, exception policy, and acceptance index generation | Internal Alpha |
| HATE-GAP-023 | `operational_gap` | Evidence protocol linkage | HATE generates local artifacts, but agent/action evidence is not uniformly mapped to agent-protocols Evidence records | Add evidence mapping contract for agent run, command, artifact, decision, review, and CI result records | Team GA |
| HATE-GAP-024 | `operational_gap` | Birdseye freshness gate | HATE has local Birdseye/codemap, but freshness, generation consistency, and stale failure policy are not specified as workflow gates | Add freshness thresholds, index/caps generation invariants, stale failure conditions, and local recovery steps | Internal Alpha |
| HATE-GAP-025 | `packet_gap` | Workflow plugin integration | HATE mentions workflow artifacts, but cross-repo plugin config, task/acceptance sync, docs stale checks, and generated indexes are not decomposed | Add workflow plugin worker packets and fixtures for task sync, acceptance sync, docs stale, and cross-repo config validation | Team GA |
| HATE-GAP-026 | `operational_gap` | Completion expression governance | HATE has completion reports, but scope-safe wording is not uniformly enforced against task, acceptance, release, and changelog evidence | Add completion governance checker for overclaiming, missing acceptance, missing release evidence, and stale completion records | Internal Alpha |

## 3. Required New Specification Documents

| Document | Covers | Blocks |
|---|---|---|
| `HOSTED_WORKER_RUNTIME_CONTRACT.md` | background jobs, queues, retries, cancellation, worker leases | HATE-GAP-001 |
| `TENANT_ISOLATION_CONTRACT.md` | physical/logical tenant boundaries and denial tests | HATE-GAP-002 |
| `GITHUB_INTEGRATION_CONTRACT.md` | GitHub App, Action, checks, annotations, permissions | HATE-GAP-005 |
| `STORE_MIGRATION_INDEX_REBUILD_CONTRACT.md` | schema migration, index rebuild, compaction, corruption recovery | HATE-GAP-006 |
| `REAL_REPO_EVALUATION_CONTRACT.md` | recurring real repo trials, baselines, trend reports | HATE-GAP-012 |
| `ADAPTER_CORPUS_MANIFEST.md` | corpus size, fixture generation, dialect coverage, stale checks | HATE-GAP-007, HATE-GAP-014 |
| `PRODUCT_E2E_UAT_CONTRACT.md` | end-to-end journeys and product UAT evidence | HATE-GAP-020 |
| `WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md` | Task Seed, acceptance, Evidence, Birdseye freshness, workflow plugin, completion governance | HATE-GAP-021..026 |

## 3.1 Specification Closure Status

| Gap range | Requirement/specification status | Implementation status |
|---|---|---|
| HATE-GAP-001..020 | `specified` by this backlog plus `PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md` and referenced contracts | `implemented`; awaiting acceptance |
| HATE-GAP-021..026 | `specified` by `WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md` and packet ledger | `implemented`; awaiting acceptance |

This status means ambiguity is closed enough for worker dispatch. It does not
mean the product capability is accepted or product-ready.

## 4. No-Go Rules

The product must not be claimed as 50万〜100万行級 implementation-ready while any
of the following are true:

- any `missing_requirement` remains open
- any P0/P1 adapter family lacks a positive and negative fixture
- hosted/runtime behavior is represented only by local JSON reports
- API or dashboard completion is claimed without contract and RBAC negative tests
- enterprise readiness is claimed without tenant isolation and audit fixtures
- scale readiness is claimed without real repo baselines and performance thresholds
- support readiness is claimed without safe diagnostic bundle fixtures
- workflow operation readiness is claimed without Task Seed, acceptance, Evidence,
  Birdseye freshness, and completion governance linkage

## 5. Current Assessment

Current state:

- Core local-first evidence and precheck requirements are comparatively strong.
- Product/enterprise contract documents now have packet-level implementation
  evidence for HATE-GAP-001 through HATE-GAP-026.
- Requirement-to-packet decomposition for runtime, hosted, enterprise, corpus,
  and operational behavior is represented by fixtures, schemas, tests, and
  generated UAT reports.
- Workflow-cookbook alignment now has a Task Seed -> Acceptance -> Evidence ->
  Birdseye freshness -> completion governance loop in the gap-closure report.

Assessment:

`PRODUCT_REQUIREMENTS_DEFINITION.md` remains the top-level PRD. This backlog is
now the controlling evidence ledger for the first 26 requirement gaps: the gaps
are implemented, but not accepted. Remaining growth toward a 50万〜100万行級
product should continue through new gap IDs or versioned expansion packets rather
than reusing these 26 gaps as if they were still unspecified.

## 6. Expansion Backlog

The next requirement-gap wave starts at HATE-GAP-027 and is tracked in:

- `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md`
- `PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md`
- `docs/tasks/HATE_REQUIREMENTS_EXPANSION_TASK_SEEDS.md`
- `docs/acceptance/HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md`

Expansion gaps are `specified` until their runtime code, schemas, fixtures,
tests, generated UAT reports, Birdseye updates, and acceptance records exist.
They must not be counted as implemented by the HATE-GAP-001..026 gap-closure
report.
