# Platform Long-Term Operations UX - 2026-07-05

## Scope

This acceptance record closes the remaining thin platform operations UX around
long-term operation, history comparison, owner/SLA assignment, notification, and
baseline promotion review.

## Implemented CLI Surface

- `hate platform history-analytics --input <json> [--out <json>]`
- `hate platform history-materialize --input <json> [--previous-manifest <json>] [--manifest-out <json>] [--out <json>]`
- `hate platform notify route --input <json> [--out <json>]`
- `hate platform notify deliver --input <json> [--out <json>]`
- `hate platform baseline review --input <json> [--out <json>]`

These commands sit beside the existing platform commands:

- `history`
- `compare`
- `schedule`
- `assign`
- `score`
- `verdict`
- `triage`
- `baseline promote`

## Requirement Coverage

| Requirement | Evidence |
|---|---|
| Long-term operation | `history-analytics-report` exposes flake rate, freshness, debt age, repo health, baseline drift, regression clusters, and manual review latency. |
| Incremental history | `history-materialization-plan` and `history-materialization-manifest` support reuse/recompute/drop decisions from sample fingerprints. |
| History comparison | Existing `hate platform compare` remains the base/head report comparison path. |
| Owner assignment and SLA | Existing `hate platform assign` builds owner, due-date, and SLA queue evidence. |
| Notification UX | `notify route` builds owner/team/escalation routing; `notify deliver` records delivery, retry, duplicate suppression, and dead-letter evidence. |
| Baseline promotion UX | `baseline promote` records promotion state transitions; `baseline review` emits human review packets with required review items and comparison deltas. |
| Major OSS verdict corpus | Existing `hate platform verdict` reports precision/recall against the frozen major OSS corpus. |
| OSS Hold triage | Existing `hate platform triage` turns requests, fastapi, pydantic, starlette, axios, and pytest subset gap into operator work items. |

## Verification

```powershell
uv run pytest tests/test_platform_cli.py tests/test_post_poc_history_analytics.py tests/test_post_poc_notifications.py tests/test_post_poc_baseline.py tests/test_post_poc_baseline_cli.py -q
```

Result:

- `58 passed`

The full release validation for this change also includes:

```powershell
uv run pytest -q
uv run python -m compileall src tests
uv run python tools/codemap/update.py --check
git diff --check
```

## Caveat

This is still a local-first operations UX. It does not claim hosted scheduler,
external notification provider delivery, or QEG release approval authority.
