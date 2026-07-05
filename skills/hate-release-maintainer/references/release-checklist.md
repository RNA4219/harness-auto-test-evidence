# HATE Release Checklist

Use this checklist for release-facing HATE work.

## Evidence Sources

- Agent entrypoint: `README.md`
- Human Japanese README: `docs/README_JA.md`
- Human English README: `docs/README_EN.md`
- Runbook: `docs/process/RUNBOOK.md`
- Evaluation contract: `docs/process/EVALUATION.md`
- Product requirements: `docs/process/PRODUCT_REQUIREMENTS_DEFINITION.md`
- Product-grade spec: `docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md`
- PoC acceptance: `docs/acceptance/POC_COMPLETION_20260703.md`
- Major OSS acceptance: `docs/acceptance/MAJOR_OSS_TWO_CYCLE_20260704.md`

## Required Checks

Run these before release-facing commit:

```powershell
uv run pytest -q
uv run python -m compileall src tests
uv run python tools/codemap/update.py --check
git diff --check
```

If codemap check fails, regenerate and commit the resulting `docs/birdseye`
changes:

```powershell
uv run python tools/codemap/update.py
```

## Product Claim Guardrails

Allowed without external QEG release approval:

- PoC complete
- local-first evidence normalizer
- advisory artifact generator
- platform CLI operator workflow
- expected-verdict corpus for measured OSS validation

Disallowed without external QEG release approval:

- production-ready
- enterprise-ready
- regulated-ready
- final release gate
- release approval authority

## Major OSS Release Evidence

The frozen major OSS corpus is:

- `docs/process/real-repo-verdict-corpus/major-oss-expected-verdicts-20260704.json`

The accepted two-cycle record is:

- `docs/acceptance/MAJOR_OSS_TWO_CYCLE_20260704.md`

The expected current summary for that frozen corpus is:

- 10 expected repo/suite verdicts
- 5 true positives for held suites
- 5 true negatives for passing suites
- precision: 1.0
- recall: 1.0
- accuracy: 1.0
- triage items: 6, including pytest compile-smoke self-hosted soft gap

