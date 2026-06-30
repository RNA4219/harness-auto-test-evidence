---
intent_id: INT-HATE-STORE-MIGRATION-INDEX-REBUILD-CONTRACT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Store Migration And Index Rebuild Contract

This contract closes HATE-GAP-006 for long-lived store and index operation.

## 1. Scope

This contract covers migrations for HATE's local and hosted derived stores:

- canonical evidence bundle metadata
- read-model indexes
- replay/compare derived reports
- migration journal records
- rollback and rebuild evidence

Out of scope:

- vendor-specific hosted database provisioning
- QEG schema migration authority
- irreversible customer data deletion

Canonical bundles are immutable. Migration may write derived stores, migrated
views, indexes, journals, and reports, but it must not rewrite source evidence
without an explicit repair artifact.

## 2. Migration Lifecycle

```text
planned -> dry_run -> backup_created -> migrating -> verifying -> complete
planned -> dry_run -> blocked
migrating -> rollback -> restored
verifying -> failed -> rollback
```

Allowed terminal states:

| State | Meaning | Product-ready effect |
|---|---|---|
| `complete` | migration, replay, rebuild, and verification passed | none |
| `blocked` | dry-run found unsupported version or unsafe plan | hold |
| `restored` | rollback completed and pre-migration hashes match | soft gap until reviewed |
| `failed` | failure detected but rollback is absent or unverified | hold |

Required artifacts:

- migration-plan.json
- migration-dry-run-report.json
- backup-manifest.json
- index-rebuild-checkpoints.jsonl
- replay-verification-report.json
- rollback-report.json

## 3. Record Contract

`store-migration-report.json` must contain:

| Field | Required behavior |
|---|---|
| `record_type` | `store-migration-report` |
| `migration_id` | stable id, not derived from fixture filename only |
| `from_schema` / `to_schema` | semantic schema names or HATE schema ids |
| `compatibility_class` | `compatible`, `migration_required`, `unsupported`, `blocked` |
| `lifecycle_state` | one lifecycle state from this contract |
| `source_bundle_hash_before` | hash of source canonical bundle before migration |
| `source_bundle_hash_after` | same value unless an explicit repair artifact exists |
| `derived_store_hash_before` | optional when no derived store exists |
| `derived_store_hash_after` | required after migration or rollback |
| `backup_manifest_ref` | required before mutating derived store |
| `rollback_report_ref` | required when lifecycle_state is `failed` or `restored` |
| `replay_verification_ref` | required before `complete` |
| `index_rebuild_checkpoints` | ordered checkpoint refs with sequence and hash |
| `findings` | structured findings with code, severity, sourceRef |
| `sourceRefs` | input fixture, plan, backup, replay, and rollback refs |

No field may be inferred from directory names alone. The checker must use
payload fields and explicit refs.

## 4. Version Skew

| Producer | Consumer | Behavior |
|---|---|---|
| old schema | new reader | compatible or migration required error |
| new schema | old reader | explicit unsupported version error |
| partial index | hosted API | stale/partial metadata, never silent success |
| corrupt index | replay | rebuild required, no product-ready claim |
| unknown schema | any reader | blocked until migration policy names it |

Compatibility rules:

- Minor compatible migrations may pass only when replay output hashes match the
  expected report set.
- Major or unknown versions are hold/block unless a migration guide and rollback
  plan are present.
- A migration that changes readiness verdict, risk debt, manual review status,
  or QEG export eligibility must emit `verdict_effect`.
- Old bundles must remain readable or be rejected with a structured
  `store_schema_version_unsupported` finding.

## 5. Index Rebuild And Corruption Recovery

Indexes are derived artifacts. Rebuild must satisfy:

- input source is the canonical bundle or an accepted migrated bundle
- checkpoints are monotonic by `sequence`
- each checkpoint has `input_hash`, `output_hash`, `record_count`, and
  `sourceRef`
- rebuild does not change canonical bundle hash
- corrupt index state is never silently repaired
- hosted API may return `rebuilding` or `stale`, but not `fresh`, while rebuild
  is incomplete

Corruption handling:

| Condition | Required finding | Effect |
|---|---|---|
| corrupt index and no checkpoint | `store_index_corrupt_rebuild_required` | hold |
| checkpoint hash mismatch | `store_index_rebuild_hash_mismatch` | hold |
| partial rebuild exposed as fresh | `store_index_partial_marked_fresh` | hold |
| canonical bundle hash changed during rebuild | `store_canonical_hash_changed` | hard hold |

## 6. Rollback

Rollback is required when migration fails after backup creation or when
verification detects hash drift.

Rollback report must prove:

- backup manifest exists and is referenced
- derived store hash after rollback equals hash before migration
- canonical bundle hash is unchanged
- index state is `restored`, `stale`, or `rebuilding`, never `fresh` without
  replay verification
- audit event records owner, timestamp, reason, and sourceRefs

No-Go:

- `failed` migration without rollback report
- rollback restores derived store but loses legal hold or retention metadata
- rollback report lacks before/after hashes
- rollback selects backup by newest filename rather than manifest id

## 7. Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/store/migration/forward-compatible/fixture.json` | dry run and replay pass |
| `fixtures/store/migration/rollback-required/fixture.json` | rollback report emitted |
| `fixtures/store/migration/corrupt-index/fixture.json` | rebuild required and hold |
| `fixtures/store/migration/version-skew-denied/fixture.json` | structured version error |
| `fixtures/store/migration/rebuild-checkpoint-hash-mismatch/fixture.json` | checkpoint hash mismatch hold |
| `fixtures/store/migration/canonical-hash-changed/fixture.json` | canonical mutation hard hold |

## 8. Implementation Packet Minimum

Implementation for HATE-GAP-006 must provide:

- `src/hate/store/migration_rebuild.py`
- `schemas/HATE/v1/store-migration-report.schema.json`
- `tests/test_store_migration_rebuild.py`
- all fixtures listed in this contract
- gap closure implementation evidence update
- Birdseye update

Minimum tests:

- forward compatible dry-run and replay pass
- rollback required on verification failure
- unsupported future schema is structured hold
- corrupt index requires rebuild checkpoint
- checkpoint hash mismatch is hold
- canonical hash mutation is hard hold
- rollback cannot lose legal hold metadata
- migration report includes sourceRefs and before/after hashes

## 9. Acceptance

Store migration is accepted when replay, rollback, rebuild checkpoint, version
skew, hash mismatch, canonical immutability, and legal hold preservation fixtures
pass.
