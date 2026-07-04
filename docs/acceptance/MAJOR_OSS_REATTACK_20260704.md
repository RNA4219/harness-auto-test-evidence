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

## Verification

- `uv run python -m hate platform run --roster C:\tmp\hate-major-oss-roster-20260704.json --out C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening --source-version major-oss-reattack-after-hardening-20260704`
  - 10 repos, 2 passed, 8 held, 6,490 records
- `uv run python -m hate platform score --input C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening --out C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening\platform-score.json`
  - average score 67.4, blocked count 1
- `uv run python -m hate platform report html --input C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening --out C:\tmp\hate-major-oss-eval-20260704-reattack-after-hardening\platform-report.html`
  - overall status hold, report count 11, finding count 26
- `uv run pytest tests/test_real_repo_operational_oss.py tests/test_real_repo_platform_packets.py -q`
  - 29 passed
- `uv run pytest -q`
  - 1890 passed
- `uv run python tools\codemap\update.py`
  - 1601 Birdseye nodes and 552 edges
- `git diff --check`
  - passed
