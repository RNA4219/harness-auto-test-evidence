---
intent_id: INT-HATE-REAL-REPO-BULK-VALIDATION-20260702
owner: RNA4219
status: active
last_reviewed_at: 2026-07-02
next_review_due: 2026-07-16
---

# Real Repo Bulk Validation 2026-07-02

This record captures a real local repository validation pass for false-positive
resistance, adapter coverage, long-history ingestion, operational friction, and
external-tool handoff readiness.

## Scope

| Roster | Repo/suite count | Passed | Held | Executed records | Evidence path |
|---|---:|---:|---:|---:|---|
| Agent_tools full | 9 | 8 | 1 | 6052 | `tmp/real-repo-bulk/agent-tools-full/` |
| Codex_dev root extra split | 13 | 13 | 0 | 6719 | `tmp/real-repo-bulk/split-results/` |
| Parser-fix confirmation | 7 | 7 | 0 | 31 | `tmp/real-repo-bulk/post-parser-fix/` |

Primary run coverage: 22 repo/suites and 12,771 executed records.

## Findings

| Area | Result | Evidence |
|---|---|---|
| False-positive resistance | `cargo test` was originally misclassified as `pytest` because the output contained `25 passed`; fixed by parsing `cargo-test` before pytest-like summaries. | `fixtures/platform/evaluation/noisy-runner-log/fixture.json`, `tests/test_real_repo_platform_packets.py` |
| Adapter/dialect coverage | Added visible classifications for `cargo-test`, `nextjs-build`, `astro-build`, `typescript-typecheck`, and `python-compileall`. These are not counted as test cases unless they expose real test totals. | `src/hate/evaluation/runner_dialects.py` |
| Long-history ingestion | 22 history entries were ingested and queried from `tmp/real-repo-bulk/history-store/run_history.jsonl`. | `real-repo history-ingest`, `real-repo history-query` |
| Operational friction | Sandbox execution intermittently blocked `uv` cache access under `AppData/Local/uv/cache`; reruns required explicit escalation. This is an environment friction, not a HATE implementation failure. | shell output: `Failed to initialize cache ... os error 5` |
| External-tool friction | `quality-evidence-graph` typecheck runs as a real-repo suite and is now classified as `typescript-typecheck`. Final QEG gate must remain the release aggregation authority. | `tmp/real-repo-bulk/post-parser-fix/09-quality-evidence-graph/` |
| QEG final gate smoke | QEG `build`, `validate`, `gate`, and `record` passed on `fixtures/positive-release-go`; QEG worktree stayed clean after the run. | `C:/Users/ryo-n/Codex_dev/quality-evidence-graph` |
| Owned repo hold | `memx-resolver` held due missing `yaml` during test collection. HATE redacted the local path and retained the hold as command failure/regression evidence. | `tmp/real-repo-bulk/agent-tools-full/real-repo-memx-resolver.json` |

## Commands

```powershell
uv run hate real-repo run --roster docs\process\real-repo-rosters\agent-tools-full.json --out tmp\real-repo-bulk\agent-tools-full --source-version bulk-agent-tools-20260702
uv run hate real-repo run --roster tmp\real-repo-bulk\split-rosters\<repo>.json --out tmp\real-repo-bulk\split-results\<repo> --source-version bulk-<repo>-20260702
uv run hate real-repo history-ingest --history tmp\real-repo-bulk\agent-tools-full\real-repo-run-history.jsonl --store tmp\real-repo-bulk\history-store
uv run hate real-repo history-query --store tmp\real-repo-bulk\history-store
uv run pytest tests\test_real_repo_platform_packets.py tests\test_real_repo_evaluation.py -q
npm run build                         # in quality-evidence-graph
node dist\cli.js validate fixtures\positive-release-go
node dist\cli.js gate fixtures\positive-release-go
node dist\cli.js record fixtures\positive-release-go
```

## Residual Gaps

- `memx-resolver` dependency setup should be corrected in its own repository or roster command before treating that suite as a stable baseline.
- The combined `codex-dev-root-extra.json` run hit the same `uv` cache access problem before it emitted a manifest; split execution provides usable repo-level evidence but the combined-run UX should report this outer environment failure more clearly.
- Build/typecheck classifications intentionally use `total_checks`, not `total_tests`; downstream scoring must avoid treating these as executable test oracles.
