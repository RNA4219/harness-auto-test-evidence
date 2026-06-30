---
intent_id: INT-HATE-ADAPTER-CORPUS-MANIFEST-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Adapter Corpus Manifest

This contract closes HATE-GAP-007 and HATE-GAP-014.

## 1. Corpus Requirements

Each adapter family must define:

- adapter_id
- supported dialects
- minimum positive fixtures
- minimum negative fixtures
- malformed input cases
- partial input cases
- path normalization cases
- metadata preservation cases
- conformance expected output
- stale review owner

Each family entry must be explicit data in the manifest input. A checker may use
the repository fixture tree to verify paths, but it must not infer adapter
coverage from directory names alone. The manifest is the authority for claims;
fixture files are evidence for those claims.

## 2. Minimum Families

| Family | Required dialects |
|---|---|
| Test results | JUnit, pytest JSON, Jest JSON, Vitest JSON, Playwright JSON |
| Coverage | LCOV, Cobertura, JaCoCo, coverage.py JSON |
| Static findings | SARIF generic, CodeQL-like, Sonar-like |
| Contract | Pact |
| Mutation | Stryker |
| Artifacts | trace, screenshot, video, log, archive, external URL |

Minimum per-family counts:

| Family | Positive fixtures | Negative fixtures | Required checks |
|---|---:|---:|---|
| Test results | 5 | 5 | dialect parsing, retry/flaky metadata, malformed input |
| Coverage | 4 | 4 | path normalization, context preservation, malformed input |
| Static findings | 3 | 2 | severity mapping, location normalization, unsupported schema |
| Contract | 1 | 2 | provider/pass mapping, version mismatch |
| Mutation | 1 | 2 | killed/survived/timeout, unknown status |
| Artifacts | 6 | 3 | safe path, traversal denial, secret quarantine |

Synthetic fixtures must be labeled `synthetic`. Fixtures copied from real
projects must be labeled `real_anonymized` and must include redaction evidence.
Any fixture older than `stale_after_days` without `reviewed_at` and
`review_owner` is a hold.

Required manifest fields per family:

- `family`
- `adapter_id`
- `dialects`
- `fixture_paths`
- `positive_count`
- `negative_count`
- `malformed_count`
- `partial_count`
- `path_normalization_count`
- `metadata_preservation_count`
- `expected_output_ref`
- `reviewed_at`
- `review_owner`
- `stale_after_days`
- `sourceRefs`

Readiness effects:

| Condition | Finding | Effect |
|---|---|---|
| Missing required family | `adapter_corpus_family_missing` | hold |
| Missing dialect | `adapter_corpus_dialect_missing` | hold |
| Positive or negative count below minimum | `adapter_corpus_fixture_count_below_minimum` | hold |
| Stale review owner/date | `adapter_corpus_stale_fixture` | hold |
| Unsupported capability claim | `adapter_corpus_unsupported_claim` | hold |
| Expected output ref missing | `adapter_corpus_expected_output_missing` | hold |

## 3. Manifest Fixture Contract

| Fixture | Expected |
|---|---|
| `fixtures/corpus/manifest/minimum-dialects/fixture.json` | all required dialects present |
| `fixtures/corpus/manifest/stale-fixture/fixture.json` | stale review finding |
| `fixtures/adapters/family/junit-pass/fixture.json` | family packet positive case |
| `fixtures/adapters/family/malformed-input/fixture.json` | family packet negative case |

## 4. Acceptance

Adapter corpus readiness requires a conformance report that lists every adapter
family, fixture count, dialect coverage, stale status, and unsupported claim.

## 5. Implementation Packet Minimum

Implementation for HATE-GAP-007 must provide:

- `src/hate/adapters/corpus_manifest.py`
- `schemas/HATE/v1/adapter-conformance-report.schema.json`
- `tests/test_adapter_corpus_manifest.py`
- gap closure implementation evidence update
- Birdseye update

Minimum tests:

- all required families and dialects pass
- stale fixture review produces `adapter_corpus_stale_fixture`
- missing family produces `adapter_corpus_family_missing`
- missing dialect produces `adapter_corpus_dialect_missing`
- fixture count below minimum produces
  `adapter_corpus_fixture_count_below_minimum`
- unsupported capability claim produces `adapter_corpus_unsupported_claim`
- expected output ref is required
- report includes sourceRefs and family summaries
