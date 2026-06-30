---
intent_id: INT-HATE-REAL-REPO-EVALUATION-CONTRACT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Real Repository Evaluation Contract

This contract closes HATE-GAP-012. Real repository trials are recurring product
evidence, not one-off anecdotes.

## 1. Repository Roster

Each repo entry must include:

- repo_id
- path or remote
- language/runtime
- default evidence command
- timeout_ms
- subset command, if full suite is too slow
- baseline artifact
- owner
- last_successful_evaluation

## 2. Baseline Rules

- Baselines store record counts, decision status, runtime, warnings, and known limitations.
- A subset baseline must be labeled as subset and cannot prove full-suite readiness.
- Timeout is evidence, not silence.
- Regression is detected by decision downgrade, parser failure, record count collapse,
  runtime budget breach, or new unsafe artifact finding.

## 3. Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/evaluation/real-repo/baseline-pass/fixture.json` | baseline comparison passes |
| `fixtures/evaluation/real-repo/regression-detected/fixture.json` | hold with reason |
| `fixtures/evaluation/real-repo/timeout-recorded/fixture.json` | timeout evidence retained |
| `fixtures/evaluation/real-repo/subset-labeled/fixture.json` | subset limitation visible |

## 4. Acceptance

Real repo evaluation is accepted when scheduled trials can compare baselines and
produce trend reports without overstating subset evidence.
