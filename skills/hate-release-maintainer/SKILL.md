---
name: hate-release-maintainer
description: Maintain and release the harness-auto-test-evidence HATE repository. Use when Codex is asked to update HATE release docs, README files, product readiness claims, platform CLI evidence, major OSS validation records, codemap freshness, release candidate packs, or pre-release validation before commit/push.
---

# HATE Release Maintainer

Use this skill for release-oriented work in the HATE repository. Keep claims
evidence-backed, keep README files human-readable, and preserve the boundary
that HATE prepares evidence but does not own final QEG release approval.

## Start Here

1. Work from the repository root: `harness-auto-test-evidence`.
2. Read `README.md` first. It is the agent-facing entrypoint.
3. Read `docs/README_JA.md` or `docs/README_EN.md` when changing
   human-facing product wording.
4. Read `docs/process/RUNBOOK.md` and `docs/process/EVALUATION.md` before
   changing release, acceptance, or validation behavior.
5. For release-specific work, read
   `references/release-checklist.md`.

## Claim Discipline

- Do not describe HATE as production-ready, enterprise-ready, regulated-ready,
  or a final release gate unless a current QEG release approval artifact proves
  it.
- Use `PoC complete` only when the PoC acceptance records and tests still pass.
- Keep `product_ready=false` unless product-grade evidence and external release
  approval support changing it.
- If README wording changes a status number, rerun the matching verification or
  phrase it as historical acceptance evidence.

## Standard Release Loop

1. Inspect `git status --short --branch`.
2. Review changed claims in README, acceptance records, release notes, and
   product-grade reports.
3. Run targeted tests for touched surfaces.
4. Run full release checks when the change is release-visible:

```powershell
uv run pytest -q
uv run python -m compileall src tests
uv run python tools/codemap/update.py --check
git diff --check
```

5. If codemap is stale, run:

```powershell
uv run python tools/codemap/update.py
```

6. Re-run the failing check instead of editing around it.
7. Commit only relevant files. Push only when requested or when the release task
   explicitly includes publication.

## README Rules

- Keep root `README.md` agent-facing and concise.
- Keep `docs/README_JA.md` and `docs/README_EN.md` human-facing and more
  explanatory.
- Link to acceptance evidence instead of duplicating long historical detail.
- Keep CLI examples executable from the repository root.
- Avoid stale exact counts unless they are tied to a dated acceptance record.

## Platform Evidence Rules

- Use `hate platform verdict` for expected-verdict corpus precision/recall.
- Use `hate platform triage` to expose stable holds and subset gaps as operator
  work items.
- Treat pytest compile-smoke as a self-hosted runner `soft_gap`, not full-suite
  proof.
- Treat major OSS holds as evidence requiring triage, not as hidden pass
  conditions.

## Completion Criteria

A release-maintenance task is complete only when:

- Documentation links resolve to committed files.
- README claims match current evidence or cite dated acceptance records.
- Tests and compile checks pass for the touched scope.
- Codemap is fresh or regenerated.
- `git diff --check` is clean.
- The final response reports remaining release caveats instead of overstating
  readiness.

