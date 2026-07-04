# Major OSS Deep Operational Hardening - 2026-07-04

## Scope

This record closes the remaining operational gaps found after the first major OSS corpus run:

- Dependency bootstrap before deep real-repo validation.
- Long-running timeout mitigation through split/resume execution.
- External OSS baseline promotion policy.

## Implemented Behavior

### Dependency Bootstrap

Real-repo roster entries may now declare an explicit bootstrap command:

- `bootstrap.command`
- `bootstrap_command`
- `dependency_bootstrap_command`

HATE executes only declared bootstrap commands. It does not infer or mutate external repositories by default.

Bootstrap evidence is stored under `current.bootstrap` with:

- status
- command
- exit code
- runtime
- timeout evidence
- safe command excerpt
- output safety metadata

If bootstrap fails, the suite is held with `real_repo_bootstrap_failed` and the main suite command is not run.

### Split And Resume Execution

Real-repo roster entries may declare split execution:

- `split_commands`
- `split_execution.commands`
- `timeout_strategy.commands`

Each split command is executed as an isolated shard and aggregated into the real-repo report. Completed split IDs can be skipped by declaring:

- `split_execution.completed_splits`
- `completed_splits`

When completed shards are skipped or a split times out, `resume_required` becomes true. If no `resume_token` is present, HATE holds with `real_repo_resume_token_missing`.

Split evidence is stored under `current.split_execution` with:

- mode
- split count
- completed count
- skipped count
- resume token
- per-split status
- original command

### External OSS Baseline Policy

External OSS baseline approval now requires:

- `external_run_ref`
- `external_decision_ref`
- at least two successful observations via `observation_count >= 2`

Missing external references produce `baseline_external_reference_missing`.
Insufficient repeated observations produce `baseline_external_observation_floor_missing`.

The policy prevents a single local external run from silently becoming a trusted comparison baseline.

## Verification

- Real OSS bootstrap smoke:
  - Repository: `click`
  - Roster: explicit `bootstrap_command` followed by `uv run --group tests pytest -q`
  - Result: pass
  - Executed records: 1,707
  - Bootstrap status: pass
- `uv run pytest tests/test_real_repo_operational_oss.py tests/test_post_poc_baseline.py tests/test_real_repo_evaluation.py -q`
  - 62 passed
- `uv run pytest -q`
  - 1888 passed
- `uv run python tools\codemap\update.py`
  - 1600 Birdseye nodes and 551 edges
- `git diff --check`
  - passed
- `uv run python -m compileall src\hate\evaluation\real_repo.py src\hate\post_poc\baseline.py tests\test_real_repo_operational_oss.py tests\test_post_poc_baseline.py`
  - passed

## Remaining Notes

The implementation supports explicit bootstrap and split plans. Live dependency installation for external OSS still depends on user-provided roster commands and the available machine/network policy.
