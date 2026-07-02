---
intent_id: INT-HATE-PLATFORM-OPS-RUNTIME-20260703
owner: RNA4219
status: active
last_reviewed_at: 2026-07-03
next_review_due: 2026-07-17
---

# Platform Operations Runtime 2026-07-03

This record captures the implementation closure for operational friction that
remained after the initial platform CLI and product-grade gate.

## Scope

- `hate platform schedule`: recurring run planning with cache TTL, bounded retry,
  and resume token visibility.
- `hate platform assign`: owner, due-date, and SLA projection from findings.
- `hate platform report html`: daily operator report sections for queue, risk
  debt, and manual review.
- `hate platform plugin run`: manifest-driven plugin execution routed through
  sandbox trust/resource/output/isolation checks.
- `hate platform score`: explainable score projection from real-repo reports,
  including freshness, regression, manual debt, timeout, unsafe artifact, and
  oracle confidence.

## Acceptance Evidence

```powershell
uv run pytest tests/test_platform_ops.py tests/test_platform_cli.py -q
uv run python -m compileall src tests
```

Observed targeted result:

- Platform operations and platform CLI tests: 9 passed
- compileall: success

## Residual Boundaries

- The scheduler is a deterministic local planner; hosted cron/daemon operation
  remains outside this repository.
- Plugin execution supports local subprocess manifests and sandbox validation;
  container orchestration and remote plugin marketplace distribution remain
  future hardening.
- Score output is explainable and bounded, but release approval remains QEG's
  responsibility.
