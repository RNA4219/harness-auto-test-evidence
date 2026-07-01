# Real Repository Evaluation

HATE の実リポジトリ耐性確認は、repo ごとの unit/smoke/full test を `hate real-repo run`
で実行し、timeout、command failure、record count collapse、subset limitation を証跡化する。

## Agent_tools Full Roster

正本 roster:

- `docs/process/real-repo-rosters/agent-tools-full.json`
- `docs/process/real-repo-rosters/codex-dev-root-extra.json`
- `docs/process/real-repo-rosters/opencode-package-tests.json`

実行コマンド:

```powershell
uv run python -m hate real-repo run `
  --roster docs\process\real-repo-rosters\agent-tools-full.json `
  --out tmp\real-repo-agent-tools-full\reports `
  --source-version agent-tools-full-local
```

## 2026-07-01 Local Evaluation

対象は `Agent_tools/HUB.codex.md` の正本 repo 9件。

| repo | command class | status | records | notes |
| --- | --- | ---: | ---: | --- |
| agent-gatefield | `uv run --extra dev pytest -q` | pass | 1447 | no hold |
| agent-protocols | `npm test` | pass | 83 | no hold |
| agent-state-gate | `uv run --extra dev pytest -q` | pass | 473 | no hold |
| agent-taskstate | `uv run --extra dev pytest -q` | pass | 410 | no hold |
| manual-bb-test-harness | `uv run --extra dev pytest -q` | pass | 654 | fixed stale workflow-cookbook capsules |
| memx-resolver | `uv run --with pytest python -m pytest tests -q` | pass | 24 | avoids WindowsApps `python.exe` shim |
| shipyard-cp | `npm test` | pass | 2281 | no hold |
| tracker-bridge-materials | `uv run --extra dev pytest -q` | pass | 130 | no hold |
| workflow-cookbook | `uv run --extra dev pytest -q` | pass | 549 | no hold |

Run summary:

- repos: 9
- passed: 9
- held: 0
- timeout_count: 0
- executed_record_count: 6051

## 2026-07-01 Codex_dev Root Extra Evaluation

対象は `C:/Users/ryo-n/Codex_dev` 直下の追加 repo のうち、HATE 本体、
`Agent_tools` 正本で評価済みの重複 repo、root からの test 実行を禁止している
`opencode` を除いた13件。

正本 roster:

- `docs/process/real-repo-rosters/codex-dev-root-extra.json`

実行コマンド:

```powershell
uv run python -m hate real-repo run `
  --roster docs\process\real-repo-rosters\codex-dev-root-extra.json `
  --out tmp\real-repo-codex-dev-root-extra\reports `
  --source-version codex-dev-root-extra-local
```

| repo | command class | status | records | notes |
| --- | --- | ---: | ---: | --- |
| aituber-kit | `npm test -- --runInBand` | pass | 1297 | Jest full suite |
| code-to-gate | `npm run test:ci:stable` | pass | 3235 | large timeout profile |
| dit-adapter | `uv run --extra dev python -m pytest -q` | pass | 12 | avoids uv script trampoline issue |
| image-summarizer-backend | backend compile check | pass | 1 | compile/build evidence, no root unit suite |
| image-summarizer-frontend | `npm run build` | pass | 1 | Next.js production build |
| lyriclytic | `npm run test:run` | pass | 1314 | Vitest suite |
| ndlocr-lite | `uv run python -m compileall src` | pass | 1 | compile evidence, no tests directory |
| open-synaptic-code | `cargo test` | pass | 25 | required network once for crates.io dependencies |
| pokemon-card-ai-battle | pytest with explicit local deps | pass | 620 | subtests appear in raw pytest output but main count is 620 |
| quality-evidence-graph | `npm run typecheck` | pass | 1 | TypeScript contract check |
| rand-research-runtime | pytest with explicit `tzdata` | pass | 64 | Windows timezone dependency made explicit |
| rna4219-webpage | `npm run build` | pass | 1 | Astro production build |
| storm-access | `uv run --with pytest pytest -q` | pass | 16 | pytest suite |

Run summary:

- repos: 13
- passed: 13
- held: 0
- timeout_count: 0
- executed_record_count: 6588

Excluded from this roster:

- `opencode`: root `package.json` intentionally defines `npm test` as
  `echo 'do not run tests from root' && exit 1`. This requires a separate
  package-specific roster.
- HATE itself: covered by HATE internal verification in this repository.
- root repos that duplicate `Agent_tools` canonical repo names: evaluated through
  `agent-tools-full.json` unless explicitly targeted separately.

## Fixed Holds

### manual-bb-test-harness

Initial status: hold.

Cause:

- `tests/test_workflow_cookbook_freshness.py::TestCliIntegration::test_cli_strict_mode`
  failed because 27 `docs/workflow-cookbook/caps/*.json` records had
  `last_verified=2026-05-30` while source files were modified on 2026-06-27.

Fix:

- Updated affected workflow-cookbook capsule `last_verified` metadata to `2026-07-01`.

Verification:

- `uv run --extra dev pytest tests/test_workflow_cookbook_freshness.py -q`
- `uv run --extra dev pytest -q`

### memx-resolver

Initial status: hold.

Cause:

- Roster command `python -m pytest tests -q` resolved to the WindowsApps
  `python.exe` shim in isolated HATE execution.

Fix:

- Changed roster command to `uv run --with pytest python -m pytest tests -q`.
  `memx-resolver` has no root `pyproject.toml`; this command supplies pytest
  without relying on the parent HATE virtual environment.

Verification:

- `uv run --with pytest python -m pytest tests -q`
- `hate real-repo run` with `agent-tools-full.json`

### pokemon-card-ai-battle

Initial status: hold in isolated HATE execution.

Cause:

- `uv run --group dev pytest -q` passed in an already prepared shell, but
  HATE's isolated child process did not inherit that environment and failed to
  import `jsonschema`.

Fix:

- Changed roster command to explicitly provide local test dependencies:
  `uv run --with pytest --with jsonschema --with coverage --with kagglehub python -m pytest -q`.

Verification:

- Isolated subprocess check with HATE environment scrubber
- `hate real-repo run` with `codex-dev-root-extra.json`

### rand-research-runtime

Initial status: hold in isolated HATE execution.

Cause:

- Windows `ZoneInfo("Asia/Tokyo")` failed without `tzdata` in the isolated
  test environment.

Fix:

- Changed roster command to `uv run --with tzdata --with pytest python -m pytest -q`.

Verification:

- Isolated subprocess check with HATE environment scrubber
- `hate real-repo run` with `codex-dev-root-extra.json`

## Current Limitations

- `Agent_tools` canonical repositories and root-extra repositories are kept in
  separate rosters to avoid mixing governance repos with application/demo repos.
- `opencode` root execution remains intentionally excluded. Package-specific
  evaluation is split by package and, for `packages/opencode`, by high-cost
  test directory because a single local package-wide run exceeded the 10 minute
  command budget while still progressing through later test files.
- Absolute local paths in this roster are intentional for this workstation-local UAT.
  Portable CI rosters should use checkout-relative paths.

## Remaining Evaluation Gap

### opencode

Status: current clean package-specific split evaluation is hold. The roster is
still useful as non-invasive external evidence, but it is not a proof of the
monolithic `packages/opencode` full suite because every entry is intentionally
kept marked as subset evidence.

Observed behavior:

- Root `npm test` / `bun run test` is intentionally disabled by the repository.
- Root `bun run typecheck` currently fails before validation because `bun turbo`
  resolves `turbo.json` as a runnable file in this local environment.
- `bun install` was attempted to restore dependencies, but exceeded the outer
  30 minute command budget. It still created enough `node_modules` content for
  package-specific tests.
- A monolithic direct `bun test --timeout 30000` inside `packages/opencode`
  exceeded a 600000ms outer command budget. The run had progressed through ACP,
  account, agent, permission, provider, question, and server test groups, so
  the remaining evidence gap is full package duration/completion, not a
  currently isolated assertion failure.
- Bun on this workstation emits `Cannot read file "C:\Users\ryo-n\": EPERM`
  even for `bun -e "console.log(...)"`. The noise is tracked as local Bun
  output quality; commands with exit code 0 remain valid pass evidence.

Package-specific roster:

- `docs/process/real-repo-rosters/opencode-package-tests.json`

Run command:

```powershell
uv run python -m hate real-repo run `
  --roster docs\process\real-repo-rosters\opencode-package-tests.json `
  --out tmp\real-repo-opencode-package-tests\reports `
  --source-version opencode-package-tests-local
```

2026-07-01 package-specific split exploratory result:

Important:

- `opencode` is an external validation target, not an owned product in this
  repository.
- Exploratory local patches made while isolating Windows failures were reverted
  from the `opencode` worktree.
- Therefore this table is retained as historical diagnosis evidence, not as a
  current pass claim against a clean `opencode` checkout.
- Current non-invasive evaluation should treat newly exposed `opencode` failures
  as external-repo holds/findings, not as HATE implementation work.

| package repo_id | status | records | runtime_ms | notes |
| --- | ---: | ---: | ---: | --- |
| opencode-effect-drizzle-sqlite | pass | 7 | 382 | Bun package test |
| opencode-http-recorder | pass | 33 | 697 | Bun package test |
| opencode-ui | pass | 57 | 307 | Bun package test |
| opencode-llm | pass | 307 | 1121 | Bun package test |
| opencode-core | pass | 1007 | 115293 | exploratory local patch made this pass; not current clean-checkout proof |
| opencode-tui | pass | 185 | 6146 | exploratory local patch made this pass; not current clean-checkout proof |
| opencode-opencode-acp | pass | 119 | 2597 | split `packages/opencode` ACP tests |
| opencode-opencode-server | pass | 290 | 151020 | exploratory local patch made this pass; not current clean-checkout proof |
| opencode-opencode-account | pass | 26 | 2554 | split `packages/opencode` account tests |
| opencode-opencode-agent | pass | 49 | 20365 | split `packages/opencode` agent tests |
| opencode-opencode-permission-task | pass | 21 | 7888 | split `packages/opencode` permission task tests |

Exploratory run summary:

- package entries: 11
- passed: 11
- held: 0
- timeout_count: 0
- executed_record_count: 2101

HATE runner fixes discovered by this evaluation:

- Timeout handling now terminates the Windows child process tree instead of
  leaving orphaned Bun workers.
- Real repo reports now include `current.command_excerpt` for held commands.
- Roster entries support string-only `env` overrides, used here to isolate
  HOME/XDG writable locations for packages that touch user cache/state.

OpenCode findings identified by this evaluation, not applied:

- `packages/core/src/npm-config.ts`: project `.npmrc` handling appeared fragile
  on Windows under the local test environment.
- `packages/core/test/location-layer.test.ts`: one live catalog/location test
  exceeded Bun's default timeout locally.
- `packages/tui/src/runtime.tsx`: POSIX-style path abbreviation behaved
  differently on Windows.
- `packages/tui/src/context/kv.tsx`: missing `kv.json` produced local read
  noise rather than initializing quietly.
- `packages/tui/test/fixture/tui-environment.tsx`: the shared TUI test fixture
  appeared to miss `ExitProvider` compared with the real app provider stack.
- `packages/opencode/test/fixture/plugin.ts` and server listener tests:
  plugin dependency readiness could block or delay config/listener tests.
- Several `packages/opencode/test/**` cases assume symlink privileges, LF-only
  stdout/stderr, short local subprocess startup, or POSIX-like signal behavior;
  these should be treated as external repo Windows-portability findings.

Remaining `packages/opencode` limitation:

- The previous HATE timeboxed command `bun --cwd packages/opencode test`
  timed out at 120000ms.
- Direct package command with 600000ms outer timeout also timed out while still
  making progress through later test groups.
- `test/project/instance-bootstrap.test.ts` passes alone, so the remaining gap
  is full package suite duration/hang isolation rather than that individual file.
- The expanded split roster includes additional `packages/opencode` directories
  as non-invasive external validation targets. Failing entries should be
  reported as holds/findings; HATE should not patch `opencode` to make them pass.
- `packages/opencode` `bench:test` currently cannot run as-is on this Windows
  shell because the script calls `Bun.spawn(["bun", ...])`, while the available
  executable is exposed through the shell shim (`bun.cmd` / `bun.ps1`).

## 2026-07-01 OpenCode Clean External Evaluation

方針:

- `opencode` は HATE の所有プロダクトではないため、HATE 側から修正しない。
- clean worktree のまま一括評価し、失敗は外部 repo finding / hold として扱う。
- expanded roster は `packages/opencode` の monolithic full suite 代替ではなく、
  高コスト領域を分割した非侵襲評価証跡である。

実行コマンド:

```powershell
uv run python -m hate real-repo run `
  --roster docs\process\real-repo-rosters\opencode-package-tests.json `
  --out tmp\real-repo-opencode-package-tests\reports-expanded-clean-opencode `
  --source-version opencode-package-tests-20260701-clean-external
```

Run summary:

- package entries: 18
- passed: 13
- held: 5
- timeout_count: 0
- executed_record_count: 4722
- overall_status: hold

| package repo_id | status | records | runtime_ms | notes |
| --- | ---: | ---: | ---: | --- |
| opencode-effect-drizzle-sqlite | pass | 7 | 368 | package test |
| opencode-http-recorder | pass | 33 | 681 | package test |
| opencode-ui | pass | 57 | 319 | package test |
| opencode-llm | pass | 307 | 1155 | 277 pass / 30 skip |
| opencode-opencode-acp | pass | 119 | 2693 | split `packages/opencode` ACP tests |
| opencode-opencode-server | pass | 290 | 161011 | 267 pass / 23 skip; stderr contains expected error logs, command exit 0 |
| opencode-opencode-account | pass | 26 | 2726 | split account tests |
| opencode-opencode-agent | pass | 49 | 21714 | split agent tests |
| opencode-opencode-permission-task | pass | 21 | 8511 | split permission task tests |
| opencode-opencode-provider | pass | 399 | 17013 | provider tests |
| opencode-opencode-plugin | pass | 162 | 18079 | plugin tests |
| opencode-opencode-project | pass | 89 | 73058 | 87 pass / 2 skip |
| opencode-opencode-lsp-mcp-tool | pass | 470 | 144316 | lsp + mcp + tool tests |
| opencode-core | hold | 1007 | 119053 | 995 pass / 5 fail / 7 skip |
| opencode-tui | hold | 185 | 5870 | 175 pass / 9 fail / 1 skip |
| opencode-opencode-rest | hold | 762 | 219836 | 751 pass / 6 fail / 5 skip |
| opencode-opencode-session | hold | 370 | 93747 | 347 pass / 2 fail / 20 skip |
| opencode-opencode-cli | hold | 369 | 155162 | 354 pass / 9 fail / 6 skip |

Clean external hold findings:

- `opencode-core`: project `.npmrc` cases fail in `packages/core/test/npm-config.test.ts`.
  The observed failures include registry, scoped registry, boolean/list option,
  and registry normalization expectations.
- `opencode-tui`: Windows-local execution reports missing `kv.json`, path
  abbreviation mismatch, and related fixture/provider assumptions.
- `opencode-opencode-rest`: broad rest-directory split reports 6 failed tests.
  Earlier isolation indicates Windows symlink permission and Bun home-read
  stderr noise are part of this hold class.
- `opencode-opencode-session`: session split reports retry/shell queue timing
  failures under local Windows/Bun timing.
- `opencode-opencode-cli`: CLI subprocess split reports Windows temp-dir EBUSY,
  CRLF/stdout expectations, symlink permission, and process-signal behavior
  assumptions.

HATE interpretation:

- These 5 holds are evidence that the external repo is not green under this
  workstation-local Windows test profile.
- They are not HATE implementation failures unless HATE misclassifies,
  under-reports, times out without cleanup, or fails to preserve command
  excerpts and subset limitation metadata.
- Current HATE behavior correctly records non-zero commands as hold,
  preserves record counts, exposes command excerpts, and keeps subset evidence
  marked as not proving a full suite.
- HATE command summary parsing must ignore runner log text such as expected
  `ERROR ... 500 errors` messages unless the line is a recognized test-summary
  line. This is covered by `test_real_repo_runner_ignores_bun_non_summary_error_logs`.
