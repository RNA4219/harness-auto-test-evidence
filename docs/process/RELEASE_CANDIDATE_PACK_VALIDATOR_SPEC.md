---
intent_id: INT-HATE-RELEASE-CANDIDATE-PACK-VALIDATOR-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-08
---

# Release Candidate Pack Validator Spec

This document closes the requirements-to-spec gap between release readiness
requirements and an executable validator. `RELEASE_MIGRATION_POLICY.md` defines
release policy; this document fixes validator inputs, blockers, output, and UAT.

## 1. Required Inputs

| Input | Required fields |
|---|---|
| `required_reports[]` | report id, path, hash, required_for_stage |
| `product_readiness_report` | status, unsupported claims, blockers |
| `test_integrity_report` | unresolved holds/hard DQ |
| `security_quarantine_report` | unsafe export attempts, redaction failures |
| `enterprise_control_report` | RBAC/audit/retention/legal hold findings |
| `migration_compatibility_report` | compatibility decision, rollback evidence |
| `commercial_truthfulness_report` | unsupported commitments |
| `qeg_refs` | validate/import/gate/record refs, approval claim flag |
| `manual_review_state` | open/expired/unresolved reviews |
| `evidence_room_manifest` | included/excluded artifacts and safety reasons |

## 2. Validator Output

```yaml
release_candidate_pack:
  schema_version: HATE/v1
  record_type: release-candidate-pack
  release_candidate_id: string
  release_ready: boolean
  stage: prototype | internal_alpha | private_beta | team_ga | enterprise_ready | regulated_ready
  required_reports: array
  missing_required_reports: array
  blockers: array
  qeg_refs: object
  qeg_approval_claimed: false
  evidence_room_manifest: object
  pack_hash: string
  sourceRefs: array
```

## 3. Blocking Rules

The validator must set `release_ready=false` for:

- missing required report
- open hard DQ
- unresolved manual review required for release/product profile
- unsupported commercial or customer-facing claim
- unsafe artifact included in evidence room
- quarantined artifact export attempt
- QEG validate/import failure
- `qeg_approval_claimed=true`
- migration compatibility hard DQ
- legal hold lost or protected metadata mutation
- stale required report hash

## 4. Deterministic Hash

`pack_hash` is computed from sorted report ids, report hashes, blocker codes,
QEG refs, evidence room included/excluded refs, and release candidate id. It must
not include timestamps except as sourceRef payload fields.

## 5. Required Fixtures

- `fixtures/release-candidate-pack/all-required-reports-pass/fixture.json`
- `fixtures/release-candidate-pack/missing-required-report/fixture.json`
- `fixtures/release-candidate-pack/qeg-approval-claimed/fixture.json`
- `fixtures/release-candidate-pack/unsafe-artifact-included/fixture.json`
- `fixtures/release-candidate-pack/open-manual-review/fixture.json`

## 6. Acceptance

Implementation is acceptable only when:

- all blocker classes have negative tests
- successful pack has deterministic `pack_hash`
- missing report lists exact report id and expected path
- QEG approval is never claimed by HATE
- evidence room excludes unsafe/quarantined artifacts with reasons
- validator output is covered by `release-candidate-pack.schema.json`
