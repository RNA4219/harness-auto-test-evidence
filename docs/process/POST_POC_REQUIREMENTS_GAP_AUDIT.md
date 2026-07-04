---
intent_id: INT-HATE-POST-POC-REQUIREMENTS-GAP-AUDIT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-03
next_review_due: 2026-07-17
---

# Post-PoC Requirements Gap Audit

This document is the canonical gap register for requirements that remain after
`POC_COMPLETION_20260703.md`.

PoC completion means the local evidence loop, platform CLI path, product-grade
calculation, and black-box PoC flow are executable. It does not mean product,
enterprise, regulated, or hosted-operation requirements are complete.

## 1. Boundary Rule

| Claim | Meaning | Required Next Evidence |
|---|---|---|
| `poc_ready=true` | Local-first evidence loop closes with mitigated known PoC friction. | Keep non-overclaim guardrails and real-repo evidence visible. |
| `product_ready=false` | HATE must not claim production release authority. | QEG release approval and post-PoC gap closure evidence. |
| `enterprise_ready=false` | Enterprise runtime, hosted operations, connectors, and support paths are not complete. | Implementation, UAT, and acceptance records for the gaps below. |

No-Go:

- Do not treat this document as optional roadmap prose when claiming
  product-ready, enterprise-ready, or regulated-ready.
- Do not close a gap with docs-only evidence.
- Do not mark a gap implemented unless it has requirements, detail spec,
  implementation refs, tests, fixtures or real-data evidence, and an acceptance
  record.

## 2. Gap Register

| Gap ID | Area | Current Evidence | Missing Requirement | Acceptance Evidence |
|---|---|---|---|---|
| HATE-POSTPOC-GAP-001 | Hosted scheduler runtime | `hate platform schedule` creates deterministic local plans. | A daemon or hosted worker model with leases, heartbeats, retry queues, cancellation, and crash recovery. | Worker lifecycle fixtures, stale lease recovery tests, and an acceptance run with interrupted/resumed jobs. |
| HATE-POSTPOC-GAP-002 | Interactive dashboard frontend | HTML reports and dashboard view models exist. | Human-operable authenticated dashboard with portfolio, finding, debt, manual review, policy, and audit views. | Browser/UAT evidence for loading, empty, stale, denied, unsafe-hidden, and drill-down states. |
| HATE-POSTPOC-GAP-003 | Notification delivery runtime | Assignment and SLA queue reports exist. | Delivery connectors for Slack/email/webhook/GitHub with retry, dedupe, escalation, and failure events. | Fixture-backed delivery attempts, duplicate suppression, failed delivery hold, and redacted payload evidence. |
| HATE-POSTPOC-GAP-004 | Baseline promotion workflow | Baseline selection and invalid filename-sort detection exist. | Explicit propose/approve/freeze/expire/revoke CLI or UI with actor, reason, expiry, and immutable audit event. | Approval-path tests, denial-path tests, and replay proving regressions are not hidden by unapproved baselines. |
| HATE-POSTPOC-GAP-005 | Real-repo roster operations | Bulk validation covered 22 repo/suites. | Roster maintenance for discovery, dependency bootstrap, environment recipes, quarantine, retry isolation, and external repo ownership boundaries. | 100+ repo dry-run roster evidence, held dependency remediation records, and stale/quarantined repo tests. |
| HATE-POSTPOC-GAP-006 | Plugin distribution and trust | Local subprocess plugin PoC exists. | Signed package format, allowlist, revocation, compatibility matrix, resource isolation, and migration policy. | Signed/unsigned/revoked/mismatched plugin conformance fixtures and release-profile denial tests. |
| HATE-POSTPOC-GAP-007 | Live connector runtime | Connector reports and dry-run sync projections exist. | Live writeback modes for tracker/SIEM/warehouse/SCIM/SSO with dry-run/live separation, idempotency, and rollback visibility. | Contract tests against fake endpoints, idempotency tests, denied secret/token exposure tests, and operator acceptance. |
| HATE-POSTPOC-GAP-008 | Long-term history analytics | Local history and compare exist. | Trend analytics for flake rate, evidence freshness, debt aging, repo health, baseline drift, and regression clusters. | Multi-run synthetic and real-history tests with stable query contracts and performance budgets. |
| HATE-POSTPOC-GAP-009 | Docs and acceptance freshness CI | Codemap freshness commands exist. | CI gate that fails stale README, acceptance ledger, codemap, schema registry, and product-grade status claims. | CI fixture or script tests that intentionally stale a referenced artifact and produce hold/no-go. |
| HATE-POSTPOC-GAP-010 | QEG and Shipyard release handoff | HATE exports and smoke-validates QEG-compatible artifacts. | Explicit handoff protocol to QEG/Shipyard release or publish approval without claiming final authority. | Mocked external approval references, denial cases, and acceptance record proving HATE never overwrites verdict. |
| HATE-POSTPOC-GAP-011 | Hosted multi-tenant API | RBAC and read-model contracts exist. | Hosted API/session/auth/OIDC/token enforcement with tenant-scoped request handling and negative tests. | API tests for cross-tenant denial, expired token, service account limits, audit events, and rate limits. |
| HATE-POSTPOC-GAP-012 | Store backup, restore, and DR operations | Migration/rebuild reports exist. | Operator commands and drills for backup, restore, corruption detection, legal hold preservation, and projection rebuild. | Corrupt backup denial, successful restore, legal-hold preservation, and recovery-time evidence. |
| HATE-POSTPOC-GAP-013 | Capacity benchmark with measured baselines | Scale fixtures and capacity models exist. | Measured benchmark runs for large repos, 1000 repo roster, 1M findings, memory, runtime, and degradation mode. | Baseline benchmark artifacts, regression thresholds, and failure-mode reports under bounded resource budgets. |
| HATE-POSTPOC-GAP-014 | Compliance and procurement evidence | Security/trust contracts exist as docs and reports. | SOC2/ISO-style evidence pack, DPA/data residency mapping, procurement questionnaire outputs, and review workflow. | Generated compliance pack, reviewer signoff records, redaction checks, and stale-control detection. |
| HATE-POSTPOC-GAP-015 | Observability and incident operations | Support/ops observability reports exist. | Runtime metrics, logs, traces, alert routing, incident lifecycle, SLO burn-rate, and post-incident evidence. | Incident simulation fixtures, alert delivery failure tests, SLO breach reports, and support bundle acceptance. |
| HATE-POSTPOC-GAP-016 | Human review operating UI/CLI | Manual review requests and risk debt records exist. | Decision workflow for reviewer assignment, evidence attachment, expiry, revoke, supersede, and audit replay. | CLI/UI path tests for approve/deny/revoke/expire, missing evidence no-go, and replay-stable audit trail. |

## 3. Implementation Order

The gaps must be closed in requirement-first order:

1. Expand the requirement in `PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md` or a
   linked domain requirement document.
2. Add or thicken the detail spec in `PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md` or
   the appropriate split spec.
3. Add implementation packet(s) with scope, non-goals, commands, and acceptance.
4. Implement runtime/schema/fixtures/tests.
5. Add an acceptance record under `docs/acceptance/`.
6. Run product-grade and codemap freshness checks.

## 4. Product-Grade Integration Rule

`product-grade-evidence-summary.json` must expose this audit as known
post-PoC productization debt. A green PoC cannot hide these gaps. The presence
of open post-PoC gaps must keep `product_ready=false` unless an external
release authority and gap closure records prove otherwise.

## 5. Spec Traceability Checklist

After requirements are added here, specification lowering must be checked in
`POST_POC_SPEC_TRACEABILITY_CHECKLIST.md`. That checklist is the canonical
cross-check for whether a gap has requirement text, detail spec, implementation
packet, runtime path, schema, fixtures, tests, acceptance, and product-grade
exposure.

The detail specification for all 16 gaps is
`POST_POC_PRODUCTIZATION_DETAIL_SPEC.md`. Implementation packet references are
listed in `PRODUCT_PLATFORM_PHASE_IMPLEMENTATION_PACKETS.md#72-post-poc-productization-packets`.
The spec-to-implementation gap checklist is
`POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md`.
