# HATE: harness-auto-test-evidence

HATE converts local test and repository validation results into HATE/v1 JSON
evidence for QEG and related workflow tools. Release approval, waivers,
immutability, retention, final Go/No-Go, and publication decisions belong to QEG.

## What HATE Does

- Converts automated test and coverage artifacts into HATE/v1 records
- Exports optional evidence bundles for QEG
- Produces trust, AETE, DQ, replay, compare, explain, recommend, and doctor reports
- Generates workflow, product-readiness, and release-candidate advisory artifacts
- Provides platform commands for repository validation, history, findings, risk debt, and manual review

## Current Status

- PoC complete; `product_ready=false`.
- The final two-cycle major OSS validation stabilized at 5 pass / 5 hold with 22,171 records per cycle.
- `hate platform verdict` reports 10/10 matched verdicts with precision, recall, and accuracy at 1.0 against the frozen corpus.
- `hate platform triage` produces 6 operator items: 5 stable holds and 1 pytest compile-smoke subset soft gap.

## Maintenance Fixes — 2026-09-11

Fixes cover Bridge, LocalStore persistence and recovery, P0a/P0b input validation,
and P1a trust scoring. Collection-only or skipped records do not satisfy execution
requirements; gaps remain visible as risk debt and follow-up requests.
See [FIX-001–104](process/MAINTENANCE_FINDINGS.md) for details and remaining investigations.

The maintenance snapshot passed **4,029 local tests** and all 14 CI checks before merge.
The [validation record](acceptance/MAINTENANCE_VALIDATION_20260911.md) links the commits and CI results.

## Install And Run

Use Python 3.11 or newer with uv. The fixes are on `main`; existing v0.3.0 release
assets were not republished. To install the fixed source:

    git clone https://github.com/RNA4219/harness-auto-test-evidence.git
    cd harness-auto-test-evidence
    uv sync --dev --frozen
    uv run python -m hate --help

For the published v0.3.0 package, download the
[GitHub Release wheel](https://github.com/RNA4219/harness-auto-test-evidence/releases/tag/v0.3.0)
and install it locally (packages are not published to PyPI):

    uv tool install ./harness_auto_test_evidence-0.3.0-py3-none-any.whl
    hate --help

Use `uv build` to build a wheel from source. HATE/v1 and HATE-bridge/v1 schemas are included.
Local subprocess plugins are denied by default and require `--allow-local-exec`.
They execute arbitrary code without filesystem or network isolation; release and regulated
profiles deny this mode. See [CHANGELOG](../CHANGELOG.md) and [SECURITY](../SECURITY.md) for migration and execution boundaries.

Run the minimal P0a golden path:

    uv run python -m hate p0a --input fixtures/golden/p0a-minimal/input --out tmp/p0a-smoke --source-version local-smoke

## Platform CLI

`hate platform` is the operator-facing surface over canonical HATE reports.

- `run`: run a real-repo roster
- `history`: query run history
- `compare`: compare base/head reports
- `schedule`: create cache, retry, and resume-aware run plans
- `findings`: list findings
- `debt`: list risk debt
- `review`: list manual review requests
- `assign`: build owner, due-date, and SLA queues
- `score`: compute explainable readiness scores
- `verdict`: evaluate observed reports against an expected-verdict corpus
- `triage`: convert holds and subset gaps into operator work items
- `history-analytics`: aggregate long-term flake rate, debt age, baseline drift, and manual review latency
- `history-materialize`: incrementally materialize history windows and emit reusable manifests
- `notify route`: route owner, team, and SLA-breach records to notification targets and escalation subscribers
- `notify deliver`: record notification attempts, retry, dead-letter, and payload-safety evidence
- `baseline review`: convert baseline promotion candidates into human review packets
- plugin run: default-denied execution for explicitly authorized trusted local plugins, with enforced and unenforced controls reported
- `policy explain`: explain effective platform policy
- `report html`: generate an offline HTML report

Major OSS corpus example:

```powershell
uv run python -m hate platform verdict `
  --input tmp/major-oss-two-cycle/cycle-2 `
  --corpus docs/process/real-repo-verdict-corpus/major-oss-expected-verdicts-20260704.json `
  --out tmp/platform-verdict.json

uv run python -m hate platform triage `
  --input tmp/major-oss-two-cycle/cycle-2 `
  --out tmp/platform-triage.json
```

## Documentation

- [Agent README](../README.md): repository entrypoint for coding agents
- [Blueprint](process/BLUEPRINT.md): scope and responsibility boundaries
- [Specification](process/SPECIFICATION.md): HATE/v1 implementation contract
- [Product requirements](process/PRODUCT_REQUIREMENTS_DEFINITION.md): requirements definition
- [Product-grade implementation spec](process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md): product-grade completion criteria
- [Runbook](process/RUNBOOK.md): operating procedures
- [Evaluation](process/EVALUATION.md): acceptance rules
- [PoC completion](acceptance/POC_COMPLETION_20260703.md): PoC completion evidence
- [Major OSS two-cycle validation](acceptance/MAJOR_OSS_TWO_CYCLE_20260704.md): real-data validation evidence

## Release Checks

```powershell
uv run pytest -q
uv run python -m compileall src tests
uv run python tools/codemap/update.py --check
git diff --check
```

Keep claims consistent with related documentation, acceptance records, schemas, and product-grade status.

## v0.3.0 Responsibility Freeze and Bridge-Only Migration

New development covers P0a/P0b/P1a, schemas, adapters/plugins, and local evidence history/replay.
Post-P1a commands are thin bridges; the default compat-v0.2 provider preserves
v0.2 commands, options, output files, required fields, and exit codes.

Use `--bridge-provider handoff` on a leaf command or `HATE_BRIDGE_PROVIDER` (CLI takes precedence) to
generate bridge-request.json without external processes or network calls.
`hate bridge materialize` rejects schema, ID, owner, SHA-256, or sourceRefs mismatches
with exit 2 and no legacy output.

HATE/v1 remains available through v1. Post-P1a compatibility surfaces are deprecated
since 0.3.0, with removal after 1.0.0.

## License

MIT License. See [LICENSE](../LICENSE).
