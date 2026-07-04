# Major OSS Operational Validation - 2026-07-04

## Scope

Validated HATE platform behavior against 10 shallow-cloned external OSS repositories under
`C:\Users\ryo-n\Codex_dev\external\hate-oss-corpus`.

Repository cap: 10.

Corpus:
- click
- requests
- flask
- express
- pytest
- fastapi
- pydantic
- starlette
- axios
- lodash

Roster artifact:
- `C:\tmp\hate-major-oss-roster-20260704.json`

Final evaluation artifact:
- `C:\tmp\hate-major-oss-eval-20260704-external-baseline-fixed`

## Initial Finding

The initial platform run correctly executed real external repositories, but exposed product friction:

- External first-run holds were treated like owned-code regressions.
- Missing Node/Python test dependencies were not classified specifically.
- Runner configuration mismatch was not separated from generic command failure.
- Real test failures were not separated from launch/dependency failures.
- Platform HTML reports always returned `pass`, even with high-severity operator queue items.
- Re-running platform output generation in the same directory caused prior platform artifacts to be re-ingested.

## Implemented Corrections

- Added real-repo failure kinds and findings:
  - `missing_test_dependency`
  - `runner_config_mismatch`
  - `test_failure`
- External repositories without an explicit baseline no longer default to a synthetic `pass` baseline.
- Unbaselined external holds emit external hold evidence without noisy regression findings.
- Platform score ignores `external_hold_detected` for stability and regression penalty calculations.
- Platform HTML reports return `hold` when input reports hold or high/critical findings enter the operator queue.
- Directory input for platform reports ignores prior self-generated platform projection artifacts.
- Pytest timeout output with progress bars is preserved as partial progress evidence instead of being silently unparsed.

## Final OSS Result

Final platform run:

- Overall status: `hold`
- Repositories: 10
- Passing repos: 2 (`click`, `flask`)
- Held repos: 8
- Timeout count: 1 (`requests`)
- Executed records: 6,490

Classified held repos:

- `requests`: `timeout`
- `fastapi`: `test_failure`
- `starlette`: `test_failure`
- `pydantic`: `missing_test_dependency`
- `pytest`: `runner_config_mismatch`
- `express`: `missing_test_dependency`
- `axios`: `missing_test_dependency`
- `lodash`: `missing_test_dependency`

Post-fix score projection:

- Score count: 10
- Average score: 67.4
- Blocked count: 1
- `external_hold_detected` no longer applies regression penalty.

Post-fix HTML projection:

- Overall status: `hold`
- Report count: 11
- Finding count: 25
- Critical queue count: 25
- Prior platform outputs in the same directory are excluded from re-ingestion.

Partial timeout evidence:

- Pytest progress-only output such as `[ 45%]` is stored as `parser_status=partial`.
- Partial progress does not inflate `record_count`; it records `partial_progress_percent` and emits `real_repo_runner_partial_progress_observed`.

## Verification

- `uv run pytest tests/test_platform_ops.py tests/test_platform_cli.py tests/test_real_repo_evaluation.py tests/test_real_repo_platform_packets.py -q`
  - 73 passed
- `uv run pytest -q`
  - 1880 passed
- `uv run python -m compileall src\hate\platform_ops.py src\hate\platform_cli.py src\hate\evaluation\real_repo.py src\hate\evaluation\regression_engine.py tests\test_platform_ops.py tests\test_platform_cli.py tests\test_real_repo_evaluation.py`
  - passed
- `git diff --check`
  - passed

## Remaining Operational Gaps

- Some OSS suites require dependency bootstrap before HATE can classify deeper test evidence.
- Timeout output may contain partial progress that is not yet converted into partial record evidence.
- External hold score semantics are now cleaner, but release-approval behavior still needs policy-level treatment for external corpora.
