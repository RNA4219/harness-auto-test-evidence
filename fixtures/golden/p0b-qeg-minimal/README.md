---
intent_id: INT-HATE-P0B-FIXTURE-001
owner: RNA4219
status: active
---

# P0b QEG Export Minimal Fixture

## Input

- `p0a/HATE-run.json` - P0a run provenance
- `p0a/HATE-test-results.ndjson` - P0a canonical test nodes
- `p0a/HATE-coverage.ndjson` - P0a coverage evidence
- `p0a/artifact-manifest.json` - P0a artifact safety manifest
- `p0a/precheck-decision.json` - P0a evidence eligibility
- `p0a/record.json` - P0a audit record
- `diff-risk-test.json` - Code-to-gate risk obligation

## Scenario

- High-risk changed path: `src/auth.py` (authentication module)
- Required test: `test_login` (present in P0a output)
- Evidence: execution present, coverage present
- Evidence: DB connection execution evidence is present for `src/db.py`
- Gap: none in the default release/UAT fixture. Missing-execution behavior is covered by dedicated negative tests.

## Expected Output

- `qeg-bundle.json` - QEG import bundle with nodes, edges, completeness
- `evidence-map.json` - Risk/requirement/test/evidence graph
- `qeg-export-report.json` - Export validation report
- `qeg-export-summary.md` - Public-safe summary
