---
intent_id: INT-HATE-POST-POC-IMPLEMENTATION-GAP-CHECKLIST-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-03
next_review_due: 2026-07-17
---

# Post-PoC Implementation Gap Checklist

This is the workflow-cookbook style implementation checklist for the 16
post-PoC productization gaps.

Inputs:

- `POST_POC_REQUIREMENTS_GAP_AUDIT.md`
- `POST_POC_PRODUCTIZATION_DETAIL_SPEC.md`
- `POST_POC_SPEC_TRACEABILITY_CHECKLIST.md`
- `PRODUCT_PLATFORM_PHASE_IMPLEMENTATION_PACKETS.md#72-post-poc-productization-packets`
- `WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md`

## 1. Workflow-Cookbook Rules Applied

This checklist follows the imported workflow-cookbook contract:

- Every implementation item has a stable `task_id`.
- Every task has `objective`, `scope.in`, `scope.out`,
  `requirements.behavior`, `requirements.constraints`, `commands`, and
  `dependencies`.
- Every task carries `priority_score` and rationale.
- No task is marked `done` without an acceptance record.
- Birdseye/codemap freshness is required after implementation.
- HATE must not claim product-ready from this checklist alone.

Status vocabulary:

- `specified`: requirement, detail spec, and implementation packet exist.
- `previously-open`: runtime/schema/fixtures/tests/acceptance were missing before closure.
- `in_progress`: implementation exists but acceptance is not proven.
- `accepted`: implementation and acceptance record exist.

## 2. Spec-to-Implementation Gap Matrix

Task status is generated from the canonical registry. Accepted local slices must not be interpreted as closed production gaps.

<!-- BEGIN GENERATED:POST_POC_IMPLEMENTATION -->
| Task ID | Gap ID | Local Slice | Product Status | Acceptance | Blocking Product Work |
|---|---|---|---|---|---|
| TASK-POSTPOC-001 | HATE-POSTPOC-GAP-001 | accepted | open | docs/acceptance/AC-20260703-postpoc-001.md | Hosted queue/daemon wiring, durable leases, and production crash recovery remain unproven. |
| TASK-POSTPOC-002 | HATE-POSTPOC-GAP-002 | accepted | open | docs/acceptance/AC-20260703-postpoc-002.md | A full interactive frontend, browser UAT, and a real authentication provider remain unproven. |
| TASK-POSTPOC-003 | HATE-POSTPOC-GAP-003 | accepted | open | docs/acceptance/AC-20260703-postpoc-003.md | Live provider writes, provider authentication, and production delivery operations remain unproven. |
| TASK-POSTPOC-004 | HATE-POSTPOC-GAP-004 | accepted | open | docs/acceptance/AC-20260703-postpoc-004.md | A browser workflow and hosted approval service remain unproven. |
| TASK-POSTPOC-005 | HATE-POSTPOC-GAP-005 | accepted | open | docs/acceptance/AC-20260703-postpoc-005.md | Real dependency bootstrap execution and 100+ repository operating evidence remain unproven. |
| TASK-POSTPOC-006 | HATE-POSTPOC-GAP-006 | accepted | open | docs/acceptance/AC-20260703-postpoc-006.md | Cryptographic signing, marketplace hosting, and container isolation remain unproven. |
| TASK-POSTPOC-007 | HATE-POSTPOC-GAP-007 | accepted | open | docs/acceptance/AC-20260703-postpoc-007.md | Real provider credentials and third-party writeback acceptance remain unproven. |
| TASK-POSTPOC-008 | HATE-POSTPOC-GAP-008 | accepted | open | docs/acceptance/AC-20260703-postpoc-008.md | Hosted query APIs, retention services, and warehouse-scale operation remain unproven. |
| TASK-POSTPOC-009 | HATE-POSTPOC-GAP-009 | accepted | open | docs/acceptance/AC-20260703-postpoc-009.md | Semantic cross-document drift beyond the canonical registry remains ongoing hardening. |
| TASK-POSTPOC-010 | HATE-POSTPOC-GAP-010 | accepted | open | docs/acceptance/AC-20260703-postpoc-010.md | Live external approval engines and publication authority remain outside HATE. |
| TASK-POSTPOC-011 | HATE-POSTPOC-GAP-011 | accepted | open | docs/acceptance/AC-20260703-postpoc-011.md | A production server, OIDC provider, API gateway, and session store remain unproven. |
| TASK-POSTPOC-012 | HATE-POSTPOC-GAP-012 | accepted | open | docs/acceptance/AC-20260703-postpoc-012.md | Managed backup services and live recovery drills remain unproven. |
| TASK-POSTPOC-013 | HATE-POSTPOC-GAP-013 | accepted | open | docs/acceptance/AC-20260703-postpoc-013.md | Long-running stress infrastructure and independently reproduced scale baselines remain unproven. |
| TASK-POSTPOC-014 | HATE-POSTPOC-GAP-014 | accepted | open | docs/acceptance/AC-20260703-postpoc-014.md | External assessor signoff and customer-specific legal guarantees remain outside HATE. |
| TASK-POSTPOC-015 | HATE-POSTPOC-GAP-015 | accepted | open | docs/acceptance/AC-20260703-postpoc-015.md | Hosted telemetry vendors, live alert routing, and incident drills remain unproven. |
| TASK-POSTPOC-016 | HATE-POSTPOC-GAP-016 | accepted | open | docs/acceptance/AC-20260703-postpoc-016.md | An interactive UI, notification path, and hosted approval service remain unproven. |
<!-- END GENERATED:POST_POC_IMPLEMENTATION -->

## 3. Workflow Task Seeds

The following task seeds are ready for implementation dispatch. Each task is
bounded as a first implementation slice; larger features must split further
into schema, runtime, fixtures, and UAT subtasks before coding starts.

| task_id | objective | scope.in | scope.out | requirements.behavior | requirements.constraints | commands | dependencies | priority_score |
|---|---|---|---|---|---|---|---|---|
| TASK-POSTPOC-001 | Implement hosted scheduler lifecycle evidence and dispatch manifest. | `src/hate/post_poc/scheduler.py`, schemas, fixtures/post-poc/scheduler, tests | hosted SaaS deployment, external queue service | stale leases, retries, cancellation, resume tokens, deterministic shards, and dispatch entries produce canonical records | no silent pass on expired lease; preserve sourceRefs; invalid concurrency/duplicates/missing resume tokens hold | targeted pytest, compileall, codemap check | POSTPOC-PKT-001 | 96: scheduler unlocks unattended large-roster operation |
| TASK-POSTPOC-002 | Implement dashboard route-state, action-intent model, and read-only static artifact. | `src/hate/post_poc/dashboard.py`, dashboard schemas, fixtures/post-poc/dashboard, tests | full SPA frontend styling polish, real auth provider | route states and action intents are canonical, RBAC-safe, and renderable as local HTML evidence | dashboard does not recompute verdicts or show unsafe bodies/raw payloads | targeted pytest, compileall, codemap check | POSTPOC-PKT-002 | 82: human operation needs usable view layer |
| TASK-POSTPOC-003 | Implement notification delivery runtime evidence and routing/escalation manifest. | `src/hate/post_poc/notifications.py`, schemas, fixtures/post-poc/notifications, tests | real Slack/email writes without explicit live config | retry, dedupe, signing, dead-letter events, owner/team routing, and SLA escalation are recorded | no raw secret/PII payload; delivery failure cannot close findings; SLA breach needs escalation route | targeted pytest, compileall, codemap check | POSTPOC-PKT-003 | 88: owner/SLA loop needs delivery evidence |
| TASK-POSTPOC-004 | Implement baseline promotion workflow evidence and review packet. | `src/hate/post_poc/baseline.py`, schemas, fixtures/post-poc/baseline, tests | QEG release approval/full browser UI | approve/freeze/revoke/expire baseline transitions are replayable and reviewable with required checklist and comparison deltas | no self approval; unapproved baseline cannot hide regression; review packet blocks missing comparison or new regressions | targeted pytest, compileall, codemap check | POSTPOC-PKT-004 | 91: regression trust depends on governed baselines |
| TASK-POSTPOC-005 | Implement real-repo roster maintenance evidence and execution manifest. | `src/hate/post_poc/roster.py`, schemas, fixtures/post-poc/roster, tests | modifying external repos | stale repo, dependency bootstrap, quarantine, external boundaries, and scheduler-facing execution entries are explicit | external repo repair denied unless explicitly owned/requested; quarantined/external-held repos do not become runnable jobs | targeted pytest, compileall, codemap check | POSTPOC-PKT-005 | 90: real-repo scaling depends on roster hygiene |
| TASK-POSTPOC-006 | Implement plugin distribution trust evidence and install manifest. | `src/hate/post_poc/plugin_distribution.py`, schemas, fixtures/post-poc/plugin-distribution, tests | public marketplace hosting/package hosting | package hash, signature, allowlist, revocation, API compatibility, sandbox evidence, and installable entries are enforced | release/regulated profile denies untrusted plugins; blocked plugins cannot become installable | targeted pytest, compileall, codemap check | POSTPOC-PKT-006 | 87: plugin ecosystem requires trust gate |
| TASK-POSTPOC-007 | Implement live connector runtime evidence and safe execution manifest. | `src/hate/post_poc/connectors.py`, schemas, fixtures/post-poc/connectors, tests | real third-party side effects by default | dry-run/live/idempotency/rollback visibility, approval gates, side-effect steps, and rollback previews are represented | fake endpoints for tests; no token exposure; dry-run skips execute and live requires approval plus rollback visibility | targeted pytest, compileall, codemap check | POSTPOC-PKT-007 | 84: operating model needs external sync path |
| TASK-POSTPOC-008 | Implement long-term history analytics evidence and incremental materialization plan. | `src/hate/post_poc/history_analytics.py`, schemas, fixtures/post-poc/history, tests | data warehouse backend/retention service | flake, freshness, debt aging, drift, and regression clusters are queryable and cacheable by sample fingerprint | query budget failures explicit; no empty-result pass; changed samples recompute and removed samples drop | targeted pytest, compileall, codemap check | POSTPOC-PKT-008 | 79: trend insight raises product usefulness |
| TASK-POSTPOC-009 | Implement docs and acceptance freshness CI evidence. | `src/hate/post_poc/docs_freshness.py`, schemas, fixtures/post-poc/docs-freshness, tests, CI if needed | replacing codemap generator | stale README/acceptance/codemap/schema/product-grade claims produce holds | emergency exception requires owner, reason, expiry | targeted pytest, compileall, codemap check | POSTPOC-PKT-009 | 94: prevents overclaim and stale-state regression |
| TASK-POSTPOC-010 | Implement QEG/Shipyard handoff evidence. | `src/hate/post_poc/release_handoff.py`, schemas, fixtures/post-poc/handoff, tests | implementing QEG or Shipyard approval | external verdict refs are recorded and denial is preserved | HATE final approval claim is hard denial | targeted pytest, compileall, codemap check | POSTPOC-PKT-010 | 92: release authority boundary must remain crisp |
| TASK-POSTPOC-011 | Implement hosted multi-tenant API evidence and route contract artifact. | `src/hate/post_poc/hosted_api.py`, schemas, fixtures/post-poc/hosted-api, tests | production web server deployment/OIDC provider/API gateway | tenant authz, token expiry, service scope, rate limit records, audit policy, and platform route contracts are emitted | cross-tenant denial cannot leak restricted data; every route is tenant-scoped, scoped, audited, and rate-limited | targeted pytest, compileall, codemap check | POSTPOC-PKT-011 | 86: enterprise hosted use requires tenant boundary |
| TASK-POSTPOC-012 | Implement store backup/restore DR evidence and restore runbook. | `src/hate/post_poc/store_dr.py`, schemas, fixtures/post-poc/dr, tests | managed cloud backup service/live restore environment | backup, restore, corruption, legal hold, RTO/RPO, rebuild, and required runbook steps are verified | corrupt backup denied; legal hold must survive restore; blocked runbook steps prevent restore readiness | targeted pytest, compileall, codemap check | POSTPOC-PKT-012 | 89: auditability depends on recoverable store |
| TASK-POSTPOC-013 | Implement measured capacity benchmark evidence and regression packet. | `src/hate/post_poc/capacity.py`, schemas, fixtures/post-poc/capacity, tests | indefinite stress tests/hardware lab scheduler | measured baselines include dataset hash, runtime, memory, degradation mode, and current-vs-previous scenario deltas | degradation cannot be silent pass; runtime/memory/cache regressions block capacity promotion | targeted pytest, compileall, codemap check | POSTPOC-PKT-013 | 80: scale claims need measured baseline |
| TASK-POSTPOC-014 | Implement compliance/procurement evidence pack. | `src/hate/post_poc/compliance.py`, schemas, fixtures/post-poc/compliance, tests | legal advice or customer-specific guarantees | procurement/control claims link to evidence and reviewer decision | unsupported or stale claims hold; safe export only | targeted pytest, compileall, codemap check | POSTPOC-PKT-014 | 74: company procurement needs evidence pack |
| TASK-POSTPOC-015 | Implement observability, incident evidence, and response packet. | `src/hate/post_poc/observability.py`, schemas, fixtures/post-poc/observability, tests | hosted observability vendor integration | telemetry, alert route, SLO burn, incident lifecycle, post-incident pack, and response actions are recorded | raw secret logs denied; incidents need owner/review; blocked response actions prevent readiness | targeted pytest, compileall, codemap check | POSTPOC-PKT-015 | 83: operations require failure visibility |
| TASK-POSTPOC-016 | Implement human review workflow evidence and queue packet. | `src/hate/post_poc/human_review.py`, schemas, fixtures/post-poc/human-review, tests | replacing QEG waiver/approval/hosted UI | reviewer assignment, evidence, approve/deny/revoke/expire/supersede/replay, SLA handoff, and allowed queue actions are modeled | human review cannot become waiver bypass; queue packet cannot be ready with workflow findings or missing SLA | targeted pytest, compileall, codemap check | POSTPOC-PKT-016 | 93: risk debt and manual decisions need governed workflow |

## 4. Dispatch Order

Recommended implementation order:

1. All POSTPOC implementation tasks are accepted for the first local evidence slice.

## 5. Acceptance Placeholders

Each task must create an acceptance record only after implementation evidence
exists:

```text
docs/acceptance/AC-20260703-postpoc-001.md
docs/acceptance/AC-20260703-postpoc-002.md
...
docs/acceptance/AC-20260703-postpoc-016.md
```

Required headings:

- Scope
- Requirements
- Verification
- Evidence
- Open Risks
- Decision

No acceptance placeholder may be marked accepted until the implementation,
fixtures, tests, compileall, codemap freshness, and product-grade exposure are
verified.
