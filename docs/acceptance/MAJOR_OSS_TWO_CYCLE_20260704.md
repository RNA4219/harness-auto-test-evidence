# Major OSS Two-Cycle Stability Validation - 2026-07-04

## Scope

Ran the same 10 major OSS repositories for two consecutive HATE platform
cycles to check result stability, repeated-run friction, and remaining false
hold sources.

Corpus:

- click
- requests
- flask
- fastapi
- pydantic
- pytest
- starlette
- express
- axios
- lodash

Tracked operational roster:

- `docs\process\real-repo-rosters\major-oss-improved-20260704.json`

Runtime roster:

- `tmp\major-oss-two-cycle\major-oss-two-cycle-prebootstrapped-20260704.json`

The runtime roster preserves the same 10 repos and suites, but omits Node
`bootstrap_command` entries after dependency bootstrap has already been
completed. This prevents each repeated cycle from re-running expensive
`npm install` operations while still keeping the tracked bootstrap recipe in
the source roster.

## Hardening Found During The Run

Node dependency bootstrap:

- axios and lodash completed dependency restore in the sandbox.
- express dependency restore stalled in the sandbox, but completed with network
  escalation in 16 seconds.
- The tracked roster now uses Node bootstrap flags:
  - `--ignore-scripts`
  - `--no-audit`
  - `--no-fund`
  - `--package-lock=false`
- Node `node_modules` directories for express, axios, and lodash were removed
  after evidence capture to restore external corpus storage.

Pytest cache isolation:

- Initial two-cycle attempt produced stable but inaccurate `record_count=0`
  holds for click, flask, pydantic, and starlette.
- Cause: external corpus `.pytest_cache` write permission failures after test
  execution.
- Fix: all Python pytest commands in the tracked roster now pass
  `-p no:cacheprovider`.
- After this fix, the repeated-cycle records recovered to expected counts.

UV cache isolation:

- `UV_CACHE_DIR` was fixed to
  `tmp\uv-cache-two-cycle` to avoid the user-level uv cache permission issue.

## Final Two-Cycle Result

Both final cycles produced identical aggregate results:

| Cycle | Passed | Held | Records | Timeouts | Average score | Blocked |
|---|---:|---:|---:|---:|---:|---:|
| cycle-1 | 5 | 5 | 22,171 | 0 | 77.8 | 0 |
| cycle-2 | 5 | 5 | 22,171 | 0 | 77.8 | 0 |

Per-repo stability:

| Repo | Cycle 1 | Cycle 2 | Failure kind | Records | Stable |
|---|---|---|---|---:|---|
| axios | hold | hold | test_failure | 947 | yes |
| click | pass | pass |  | 1,707 | yes |
| express | pass | pass |  | 1,258 | yes |
| fastapi | hold | hold | test_failure | 3,311 | yes |
| flask | pass | pass |  | 491 | yes |
| lodash | pass | pass |  | 7,158 | yes |
| pydantic | hold | hold | test_failure | 5,712 | yes |
| pytest | pass | pass |  | 1 | yes |
| requests | hold | hold | test_failure | 605 | yes |
| starlette | hold | hold | test_failure | 981 | yes |

Requests split detail after cache isolation:

- 9 split shards executed.
- 7 split shards passed.
- 2 split shards held with test failures.
- Timeout count is now 0.
- `real_repo_resume_token_missing` remains absent.

Remaining holds:

- requests: split execution test failures remain.
- fastapi: real upstream/local test failure.
- pydantic: real upstream/local test failure.
- starlette: real upstream/local test failure.
- axios: real upstream/local test failure, including missing Playwright browser
  executable in the local environment and two unit failures.

## Product Conclusion

The two-cycle run improved confidence in HATE's operational precision:

- Repeated-cycle aggregate results are stable.
- Record collapse from pytest cache write failures was found and removed.
- Requests no longer times out under the split/cache-isolated roster.
- Remaining holds are stable test-failure holds, not bootstrap/parser/cache
  artifacts.
- Node repeated-cycle operation still benefits from a prebootstrap phase; the
  tracked bootstrap recipe remains necessary for cold-start reproducibility.

## Verification Commands

- `npm install --ignore-scripts --no-audit --no-fund --package-lock=false`
  - express required escalation; completed in 16 seconds.
- `uv run python -m hate platform run --roster tmp\major-oss-two-cycle\major-oss-two-cycle-prebootstrapped-20260704.json --out tmp\major-oss-two-cycle\cycle-1 --source-version major-oss-two-cycle-20260704-cycle-1-cache-isolated`
  - 10 repos, 5 passed, 5 held, 22,171 records.
- `uv run python -m hate platform score --input tmp\major-oss-two-cycle\cycle-1 --out tmp\major-oss-two-cycle\cycle-1\platform-score.json`
  - average score 77.8, blocked count 0.
- `uv run python -m hate platform report html --input tmp\major-oss-two-cycle\cycle-1 --out tmp\major-oss-two-cycle\cycle-1\platform-report.html`
  - overall status hold, report count 11, finding count 16.
- `uv run python -m hate platform run --roster tmp\major-oss-two-cycle\major-oss-two-cycle-prebootstrapped-20260704.json --out tmp\major-oss-two-cycle\cycle-2 --source-version major-oss-two-cycle-20260704-cycle-2-cache-isolated`
  - 10 repos, 5 passed, 5 held, 22,171 records.
- `uv run python -m hate platform score --input tmp\major-oss-two-cycle\cycle-2 --out tmp\major-oss-two-cycle\cycle-2\platform-score.json`
  - average score 77.8, blocked count 0.
- `uv run python -m hate platform report html --input tmp\major-oss-two-cycle\cycle-2 --out tmp\major-oss-two-cycle\cycle-2\platform-report.html`
  - overall status hold, report count 11, finding count 16.
