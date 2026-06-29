# Real Repository Trial Log

This document records HATE self-application runs against real local repositories.
It is intentionally separate from golden fixtures: these runs prove adapter and
precheck behavior against living repositories whose suites, sizes, and runtime
profiles are outside HATE's own test harness.

## Trial 2026-06-30-01

Trial root: `C:\tmp\hate-real-repo-trials-20260630-01`

Scope:

| Repository | Evidence command | Evidence artifact | HATE P0a decision | Test records |
| --- | --- | --- | --- | ---: |
| `agent-gatefield` | `uv run pytest --junitxml ...\agent-gatefield\input\junit.xml` | `junit.xml` | `eligible` | 378 |
| `agent-taskstate` | `uv run pytest --junitxml ...\agent-taskstate\input\junit.xml` | `junit.xml` | `eligible` | 412 |
| `code-to-gate` | `npx vitest run src/__tests__/smoke --maxWorkers=1 --reporter=json --outputFile ...\code-to-gate\input\vitest-report.json` | `vitest-report.json` | `eligible` | 54 |
| `shipyard-cp` | `npx vitest run --reporter=json --outputFile ...\shipyard-cp\input\vitest-report.json` | `vitest-report.json` | `eligible` | 2281 |
| `manual-bb-test-harness` | `uv run pytest --junitxml ...\manual-bb-test-harness\input\junit.xml` | `junit.xml` | `eligible` | 654 |

HATE command shape for each repository:

```powershell
uv run python -m hate p0a `
  --input C:\tmp\hate-real-repo-trials-20260630-01\<repo>\input `
  --out C:\tmp\hate-real-repo-trials-20260630-01\<repo>\hate-p0a `
  --source-version real-repo-<repo>
```

Generated HATE outputs for each repository:

- `HATE-run.json`
- `HATE-test-results.ndjson`
- `HATE-coverage.ndjson`
- `artifact-manifest.json`
- `precheck-decision.json`
- `profile-report.json`
- `quarantine-report.json`
- `record.json`
- `summary.md`

Notes:

- `agent-taskstate` completed with `412 passed in 34.62s`.
- `manual-bb-test-harness` completed with `654 passed in 78.03s`.
- `shipyard-cp` completed successfully and emitted a Vitest JSON report. Console
  output included non-fatal opencode path warnings and GLM initialization logs.
- `agent-gatefield` exceeded the external command timeout during the first run,
  but produced a complete JUnit artifact that HATE ingested as 378 test records.
- `code-to-gate` full Vitest runs exceeded 184s and 424s limits. The smoke suite
  was used for this P0a trial, producing 54 passing test records. Future full
  `code-to-gate` runs should use the long real-repo timeout policy below.

Operational timeout policy:

- Default short checks: keep the existing command-specific timeout.
- Real repository test/evidence generation: use `timeout_ms=900000` (15 minutes).
- Full suites that exceed 15 minutes should either be split by suite or recorded
  as a timed-out input attempt, with a clearly named subset used only when the
  subset is sufficient for the targeted HATE stage.

Acceptance result:

- P0a adapter ingestion succeeded for all five target repositories.
- All five repositories produced HATE P0a `eligible` decisions.
- This trial covers real JUnit and Vitest JSON evidence ingestion. It does not
  claim full external-repository P0b/P1/P2 readiness.
