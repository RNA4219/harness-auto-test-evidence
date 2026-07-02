---
intent_id: INT-HATE-PLATFORM-CLI-PRODUCT-GRADE-20260703
owner: RNA4219
status: active
last_reviewed_at: 2026-07-03
next_review_due: 2026-07-17
---

# Platform CLI and Product-Grade Gate Evidence 2026-07-03

This record captures the validation chain for the platform CLI closure and
product-grade recalculation work.

## Scope

- Requirements and detail specs were updated before implementation.
- `hate platform run/history/compare/findings/debt/review/policy/report/serve`
  was connected to the existing real-repo, history, policy, read model, and
  HTML projection capabilities.
- Product-grade evidence now recalculates from requirement docs,
  implementation refs, test refs, real-repo validation evidence, and QEG smoke
  evidence instead of returning a hard-coded `no_go`.
- README status was refreshed from the current implementation state.

## Five-Tool Validation Chain

| Tool | Status | Evidence |
|---|---|---|
| RanD | `ready` | Requirements were expanded in `PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md` before code changes. |
| Code-to-gate | `ready` | Platform CLI routes compare/report/policy/projection behavior through executable unit tests. |
| HATE | `ran` | `uv run pytest -q` passed with 1495 tests. |
| manual-bb-test-harness | `ready` | CLI operator flows are represented as black-box commands: compare, findings, debt, review, policy explain, HTML report. |
| QEG | `ran` | QEG `build`, `validate`, `gate`, and `record` passed on `fixtures/positive-release-go`; QEG worktree stayed clean after the run. |

## HATE Evidence

```powershell
uv run pytest tests/test_platform_cli.py tests/test_product_grade.py -q
uv run python -m compileall src tests
uv run pytest -q
uv run python tools/codemap/update.py
uv run hate product grade-reports --docs-root docs\process --out tmp\product-grade-platform-closure --source-version platform-cli-product-grade-20260703
npm run build
node dist\cli.js validate fixtures\positive-release-go
node dist\cli.js gate fixtures\positive-release-go
node dist\cli.js record fixtures\positive-release-go
```

Observed results:

- Targeted tests: 6 passed
- Full regression: 1495 passed
- compileall: success
- Birdseye/codemap: 1325 nodes, 459 edges
- Product-grade status: `conditional_go`
- Product ready: `false`
- QEG validate/gate/record: pass, verdict `go`
- QEG worktree: clean after smoke run

## Product-Grade Residual Blockers

`tmp/product-grade-platform-closure/product-grade-evidence-summary.json`
reported all 13 product-grade areas as `implemented_with_evidence`, but retained
these blockers from real-repo validation:

- `memx-resolver` dependency setup remains unstable.
- `uv` cache permission friction remains in combined/sandboxed runs.
- Build/typecheck records must stay out of executable test-oracle scoring.

## Acceptance

This change is accepted as a platform-closure implementation when:

- Platform CLI subcommands are available and covered by tests.
- Product-grade no longer returns a hard-coded implementation `no_go`.
- Product-grade remains conservative: residual operational blockers prevent
  `product_ready=true`.
- README status reflects the current test count and gate semantics.
- QEG smoke is rerun and recorded before claiming final release readiness.
