# Major OSS Re-Attack - 2026-07-04

## Scope

Re-ran the 10-repository major OSS corpus after the deep operational hardening commit.

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

Baseline roster:

- `C:\tmp\hate-major-oss-roster-20260704.json`

Baseline roster status:

- Kept only as a historical control sample.
- It intentionally lacks bootstrap and split/resume configuration.
- Do not use it as the current operational OSS validation roster.
- Use `docs\process\real-repo-rosters\major-oss-improved-20260704.json` for repeat validation.

Re-attack output:

- `C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening`

## Same-Roster Result

- Overall status: hold
- Repo count: 10
- Passed: 2
- Held: 8
- Timeout count: 1
- Executed records: 6,490

Held repos:

- requests: timeout
- fastapi: test_failure
- pydantic: missing_test_dependency
- pytest: runner_config_mismatch
- starlette: test_failure
- express: missing_test_dependency
- axios: missing_test_dependency
- lodash: missing_test_dependency

Confirmed improvements:

- requests timeout now records `runner_parser.parser_status=partial`.
- requests timeout now records `partial_progress_percent=45`.
- requests timeout emits `real_repo_runner_partial_progress_observed`.
- platform score remains stable at average score 67.4 with no external-hold regression penalty.
- platform HTML correctly returns hold with 26 critical/high operator queue items.
- platform directory input does not re-ingest prior platform self outputs.

## Bootstrap Re-Attack

Ran explicit dependency bootstrap against the three Node repos that previously stopped at missing dependency:

- express
- axios
- lodash

Bootstrap command:

- `npm install --ignore-scripts`

First bootstrap result:

- express: pass, but parser was unparsed and record_count fell back to 1.
- axios: hold, test_failure, 947 records.
- lodash: pass, but parser was unparsed and record_count fell back to 1.

New HATE issue found:

- Mocha and lodash custom test summaries were not parsed.

Implemented correction:

- Added `mocha` runner summary parsing.
- Added `lodash-test` runner summary parsing.

Post-parser bootstrap result:

- express: pass, mocha parsed, 1,258 records.
- axios: hold, vitest parsed, 947 records, 2 failed / 945 passed.
- lodash: pass, lodash-test parsed, 7,158 records.
- Node bootstrap attack total records improved from 949 to 9,363.

## Remaining Product/Operational Findings

- Same-roster full corpus still has 8 external holds because the baseline roster intentionally has no dependency bootstrap or split plans.
- requests still times out at 180 seconds; it now preserves partial progress, but a split/resume roster should be authored for full proof.
- pydantic still needs an explicit dependency bootstrap recipe for `tzdata` or an equivalent test environment.
- pytest still needs a runner isolation/configuration recipe because the local command hits a pytest minversion mismatch.
- axios has real test failures after bootstrap, not a HATE implementation failure.
- express/lodash bootstrap installed dependencies into the external corpus; storage should be cleaned later if the user wants to reclaim space.

## Improved Roster Re-Attack

Added a reproducible improved roster:

- `docs\process\real-repo-rosters\major-oss-improved-20260704.json`

Re-attack output:

- `C:\tmp\hate-major-oss-eval-20260704-improved-roster`

Result:

- Overall status: hold
- Repo count: 10
- Passed: 5
- Held: 5
- Timeout count: 1
- Executed records: 22,159
- Platform average score: 75.8
- Platform blocked count: 0
- HTML report finding count: 16

Improved from the same-roster run:

- Holds reduced from 8 to 5.
- Executed records increased from 6,490 to 22,159.
- Node dependency bootstrap is now explicit in the roster.
- Node parser coverage remains healthy:
  - express: pass, mocha parsed, 1,258 records
  - lodash: pass, lodash-test parsed, 7,158 records
  - axios: hold, vitest parsed, 947 records, real test failure
- pydantic now runs after explicit `tzdata` bootstrap:
  - bootstrap: pass
  - pytest: hold, 5,712 records, real test failure
- pytest runner self-hosting mismatch is isolated with an explicit compile smoke subset:
  - status: pass
  - subset limitation visible
  - `proves_full_suite=false`
- requests now uses split execution:
  - 7 of 9 split shards passed
  - 593 records captured before hold
  - resume token is visible: `requests-pytest-split-20260704`
  - remaining hold is a timeout/test-failure split result, not parser loss
  - `real_repo_resume_token_missing` is no longer emitted

Remaining findings after the improved roster:

- requests: split execution hold, 1 timeout shard and 1 failing shard remain.
- fastapi: external real test failure.
- pydantic: external real test failure after dependency bootstrap.
- starlette: external real test failure.
- axios: external real test failure after dependency bootstrap.

External corpus storage after Node bootstrap:

- express `node_modules`: 44.4 MB
- axios `node_modules`: 152.6 MB
- lodash `node_modules`: 101.1 MB
- Total reclaimable dependency cache in the external corpus: about 298.1 MB
- Cleanup completed after evidence capture:
  - `express\node_modules`: removed
  - `axios\node_modules`: removed
  - `lodash\node_modules`: removed
  - Re-running the improved roster will restore these dependencies through explicit `bootstrap_command` entries.

Product conclusion:

- The previous bootstrap/parser/configuration gaps are materially improved.
- The remaining holds are now mostly real upstream test outcomes or intentionally visible subset limitations.
- The next HATE-side improvement is not another parser fix; it is better operator UX for follow-up triage and retrying only failed split shards.

Residual requirement status:

- Same 10 baseline roster without bootstrap/split:
  - Resolved operationally by adding the improved tracked roster and demoting the original temporary roster to historical control only.
- requests 180 second timeout:
  - Improved with split execution and partial proof.
  - Not fully eliminated because `TestTimeout` still exceeds 180 seconds and one TLS-related shard fails in the local corpus.
  - Remaining action is failed-shard retry/resume UX, not a parser/bootstrap fix.
- pydantic explicit bootstrap:
  - Resolved with `tzdata` bootstrap recipe.
  - Remaining status is real pytest failure after 5,712 records.
- pytest runner isolation/config mismatch:
  - Resolved for this validation cycle with explicit compile smoke isolation and visible subset limitation.
  - Full pytest self-hosted suite proof still needs a dedicated upstream-compatible environment recipe.
- axios after bootstrap:
  - Confirmed as real test failure after successful bootstrap and vitest parsing.
- Node bootstrap storage:
  - Cleaned after evidence capture.

## Verification

- `uv run python -m hate platform run --roster C:\tmp\hate-major-oss-roster-20260704.json --out C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening --source-version major-oss-reattack-after-hardening-20260704`
  - 10 repos, 2 passed, 8 held, 6,490 records
- `uv run python -m hate platform score --input C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening --out C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening\platform-score.json`
  - average score 67.4, blocked count 1
- `uv run python -m hate platform report html --input C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening --out C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening\platform-report.html`
  - overall status hold, report count 11, finding count 26
- `uv run python -m hate platform run --roster docs\process\real-repo-rosters\major-oss-improved-20260704.json --out C:\tmp\hate-major-oss-eval-20260704-improved-roster --source-version major-oss-improved-roster-20260704`
  - 10 repos, 5 passed, 5 held, 22,159 records
- `uv run python -m hate platform run --roster docs\process\real-repo-rosters\major-oss-improved-20260704.json --out C:\tmp\hate-major-oss-eval-20260704-improved-roster --source-version major-oss-improved-roster-20260704-resume-token`
  - 10 repos, 5 passed, 5 held, 22,159 records
  - requests split resume token retained; `real_repo_resume_token_missing` removed
- `uv run python -m hate platform score --input C:\tmp\hate-major-oss-eval-20260704-improved-roster --out C:\tmp\hate-major-oss-eval-20260704-improved-roster\platform-score.json`
  - average score 75.8, blocked count 0
- `uv run python -m hate platform report html --input C:\tmp\hate-major-oss-eval-20260704-improved-roster --out C:\tmp\hate-major-oss-eval-20260704-improved-roster\platform-report.html`
  - overall status hold, report count 11, finding count 16
- `uv run pytest tests/test_real_repo_operational_oss.py tests/test_real_repo_platform_packets.py -q`
  - 29 passed
- `uv run pytest -q`
  - 1890 passed
- `uv run python tools\codemap\update.py`
  - 1601 Birdseye nodes and 552 edges
- `git diff --check`
  - passed
