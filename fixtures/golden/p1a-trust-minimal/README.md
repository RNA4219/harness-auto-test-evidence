# P1a Trust Minimal Fixture

Purpose: verify that a frozen P0b QEG bundle can produce P1a trust-hardening
artifacts without claiming release or publish authority.

Oracle:

- `aete-score.json` contains the 8 AETE dimensions, reason refs, profile metadata,
  `calibration_status=uncalibrated`, and `score_confidence=medium`.
- `doctor-report.json` reports the visible P0b missing execution as a
  `qeg_fixture` finding.
- `canonical-identity-index.json` records deterministic canonical test identity.
- `retry-aggregation.json` aggregates the single execution as `stable_passed`.
- `replay-expected/replay-report.json` contains a deterministic recalculation
  hash for the frozen bundle.
- `compare-expected/compare-report.json` reports zero trust delta for identical
  trust artifact directories.
- `explain-expected/explain-report.json` provides a source-backed reason tree for
  the visible missing execution soft gap.
- `recommend-expected/recommendation-report.json` recommends automation,
  manual-bb bridge review, and risk debt tracking for the gap.
- `doctor-expected/adapter-conformance-report.json` covers adapter, qeg_fixture,
  path, artifact_safety, schema, and profile conformance categories.
- `artifact-resolver-map.json` normalizes source refs without local absolute path
  leakage.
- `trust-summary.md` keeps `publish_gate_override=false` and
  `release_gate_override=false`.

Source refs:

- `docs/process/P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md`
- `docs/process/SPECIFICATION.md`
- `fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json`
- `fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json`
