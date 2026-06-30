---
intent_id: INT-HATE-WORKFLOW-COOKBOOK-OPERATION-CONTRACT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Workflow Cookbook Operation Contract

This contract imports workflow-cookbook operating rules into HATE product
requirements. It covers HATE-GAP-021 through HATE-GAP-026.

HATE-local Birdseye remains a repository navigation artifact. Workflow-cookbook
remains the upstream operational pattern for Task Seed, Acceptance, Evidence,
freshness, plugin sync, and completion governance.

## 1. Task Seed Loop

Every implementation packet must produce a workflow-cookbook style task seed
before work starts.

Required fields:

| Field | Requirement |
|---|---|
| `task_id` | Stable ID matching `PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md` |
| `objective` | Concrete outcome, not broad roadmap language |
| `scope.in` | Files/modules/schemas/fixtures allowed to change |
| `scope.out` | Explicit non-goals and upstream authority boundaries |
| `requirements.behavior` | Observable product behavior |
| `requirements.constraints` | Compatibility, safety, no-overwrite, privacy, or performance constraints |
| `commands` | Verification commands expected before handoff |
| `dependencies` | Other task IDs, contracts, schemas, or fixtures |

Task slicing:

- Target size is at most 0.5d per task seed.
- Large packets must split into schema, runtime, fixture, and UAT seeds.
- A task seed that changes generated artifacts must say when Birdseye/codemap is updated.

No-Go:

- task seed without scope
- task seed that hides missing implementation behind `future`, `optional`, or `advisory`
- task seed marked done without acceptance or documented exception

## 2. Acceptance Linkage

Done work must link to an acceptance record.

Acceptance record path:

```text
docs/acceptance/AC-YYYYMMDD-xx.md
```

Required headings:

- Scope
- Requirements
- Verification
- Evidence
- Open Risks
- Decision

HATE may store generated UAT artifacts under fixtures or reports, but the
acceptance record is the human-readable bridge that says whether the work is
accepted, conditionally accepted, or held.

No-Go:

- `done` task without acceptance record or exception reason
- acceptance record whose scope is broader than the tested behavior
- acceptance record that cites a report without verifying it covers the requirement

## 3. Evidence Protocol

HATE artifacts must be mappable to agent-protocols Evidence records.

Required Evidence classes:

| Evidence class | HATE source |
|---|---|
| `command_execution` | test, compile, codemap, CI, CLI run |
| `artifact_generation` | JSON/NDJSON/report/dashboard/export output |
| `decision_record` | precheck, product readiness, manual review, risk debt |
| `review_record` | UAT, code review, security review, release review |
| `runtime_event` | hosted job, queue retry, connector export, incident |

Minimum fields:

- evidence_id
- source_tool
- command_or_action
- artifact_refs
- hashes
- decision_or_status
- timestamp
- sourceRefs

No-Go:

- evidence record without artifact hash when an artifact is cited
- review decision without scope
- command evidence that omits exit status

## 4. Birdseye Freshness

HATE Birdseye/codemap must be treated as a freshness-gated navigation index.

Required invariants:

- `docs/birdseye/index.json` node count matches generated caps references.
- Every node with a caps path points to an existing caps file.
- Related source/doc/schema/fixture changes update affected caps.
- README generated metadata matches index metadata.
- Stale Birdseye is a hold for product-ready claims.

Freshness thresholds:

| Context | Threshold |
|---|---|
| Local implementation handoff | affected caps updated in same commit |
| Release candidate | full index and caps regenerated |
| Real-repo trial | trial log and HATE-local Birdseye updated |
| Emergency patch | stale allowed only with explicit exception record |

No-Go:

- generated_at mismatch between README and index
- missing caps file
- product-ready claim with stale docs/schema/fixture map

## 5. Workflow Plugin Integration

HATE workflow integration must produce and validate plugin-compatible artifacts.

Required plugin surfaces:

| Surface | HATE artifact |
|---|---|
| task sync | task seed index |
| acceptance sync | acceptance index |
| docs stale | docs freshness report |
| evidence bridge | agent-protocols Evidence JSONL |
| cross-repo config | workflow plugin config validation report |

No-Go:

- plugin config references a missing repository, task, acceptance, or schema
- task marked done while acceptance sync reports missing acceptance
- docs stale report ignored for product-ready claims

## 6. Priority, Metrics, And Feature Detection

HATE must preserve workflow-cookbook's operational scoring and KPI contracts
when turning implementation work into product readiness claims.

Priority Score:

- Every PR, worker handoff, or implementation packet that claims progress must
  carry a `priority_score` value and a short rationale.
- The score is advisory for sequencing, but the rationale must name the risk,
  user impact, and acceptance evidence that justify the work.
- Missing Priority Score is a workflow hold for release or product-ready claims,
  not a runtime DQ for local evidence ingestion.

Metrics and KPI evidence:

- `.ga/qa-metrics.json` is the machine-readable KPI artifact when metrics are
  available.
- Required KPI names are `spec_completeness`,
  `birdseye_refresh_delay_minutes`, and `review_latency`.
- `check_metrics_thresholds.py --check --metrics-json .ga/qa-metrics.json`
  is the verification command for KPI threshold evidence.
- Missing KPI evidence may be accepted during local implementation only with an
  explicit acceptance exception; product-ready claims must not ignore it.

Feature detection:

- Feature detection must use `.ga/qa-metrics.json` and
  `governance/predictor.yaml` compatible fields when such artifacts exist.
- Feature detection must not infer support from docs wording alone.
- A missing or stale feature detection artifact is a hold for claims about
  operational maturity, rollout readiness, or adaptive evaluation.

No-Go:

- PR or handoff claims progress without Priority Score rationale.
- KPI threshold failures are hidden behind green unit tests.
- Feature detection contradicts metrics or predictor evidence.

## 7. Security And Release Evidence

Security and release evidence are workflow gates. HATE may produce advisory
evidence, but it must not replace release approval.

Required command evidence:

- `check_security_posture.py --check --github-repo <owner/name>` for security
  posture evidence when GitHub repository context is available.
- `check_release_evidence.py --check --github-repo <owner/name>` for release
  evidence when release readiness is claimed.
- Branch protection state must be cited or explicitly marked unavailable before
  a product-ready or release-ready statement is made.

Required linkage:

- Security posture evidence links to security review or trust contract docs.
- Release evidence links to changelog, release record, migration or rollback
  evidence, and open-risk acceptance notes.
- Branch protection exceptions require an owner, expiry, and acceptance record.

No-Go:

- security posture is claimed without evidence.
- release evidence is claimed without changelog/release/migration linkage.
- branch protection gaps are ignored in product-ready wording.

## 8. Completion Governance

Completion statements must be scope-safe.

Allowed completion wording:

| Claim | Requirement |
|---|---|
| `specified` | requirement, contract, packet, fixture paths, UAT path named |
| `implemented` | code/schema/fixtures/tests/docs exist and pass |
| `accepted` | acceptance record approves scope |
| `product-ready` | all relevant product gates pass and no blocking gap remains |

Overclaim examples:

- "full implementation complete" when only specs exist
- "hosted-ready" when only local JSON artifacts exist
- "enterprise-ready" without tenant isolation or audit fixtures
- "accepted" without UAT evidence and acceptance record

Completion governance checks must detect:

- missing acceptance for done task
- stale completion record
- release evidence mismatch
- scope broader than verification
- generated artifact changed without Birdseye refresh

## 9. Acceptance

This contract is accepted when:

- HATE-GAP-021 through HATE-GAP-026 have packet IDs.
- Each packet names positive and negative fixture paths.
- Done status requires acceptance linkage.
- Evidence mapping covers command, artifact, decision, review, and runtime events.
- Birdseye freshness has explicit No-Go conditions.
- Priority Score, KPI, feature detection, security posture, release evidence,
  and branch protection policies are represented as workflow holds.
- Completion claims have a taxonomy and overclaim checks.
