# HATE: harness-auto-test-evidence

HATE is a local-first CLI for collecting automated test and real-repository
validation signals, normalizing them into HATE/v1 JSON evidence, and preparing
those records for QEG and adjacent workflow tools.

HATE is not the final release gate. It does not own release approval, waivers,
immutability, retention, or the final Go/No-Go decision. Its job is to produce
structured, inspectable evidence that downstream governance tools can evaluate.

## What HATE Does

- Converts automated test and coverage artifacts into HATE/v1 records
- Exports optional evidence bundles for QEG
- Produces trust, AETE, DQ, replay, compare, explain, recommend, and doctor reports
- Maps evidence into RanD, Shipyard, and workflow-cookbook advisory artifacts
- Generates product-readiness and release-candidate advisory artifacts
- Runs real repositories from roster files and records timeouts, counts, holds, and regressions
- Provides a platform CLI for findings, risk debt, manual review, assignment, score, verdict, and triage workflows
- Measures precision and recall against a frozen expected-verdict corpus for 10 major OSS repositories

## Current Status

- PoC complete.
- `product_ready` remains false.
- HATE alone is not a production release authority.
- The final two-cycle major OSS validation stabilized at 5 pass / 5 hold with 22,171 records per cycle.
- `hate platform verdict` reports 10/10 matched verdicts with precision, recall, and accuracy at 1.0 against the frozen corpus.
- `hate platform triage` produces 6 operator items: 5 stable holds and 1 pytest compile-smoke subset soft gap.

## Install And Run

Use Python 3.11 or newer with uv. For source development:

    git clone https://github.com/RNA4219/harness-auto-test-evidence.git
    cd harness-auto-test-evidence
    uv sync --dev --frozen
    uv run python -m hate --help

To install the built wheel as a tool:

    uv build
    uv tool install dist/harness_auto_test_evidence-0.2.0-py3-none-any.whl
    hate --help

v0.2.0 packages the HATE/v1 schemas. The main v0.1 migration changes are
strict JSON Schema enforcement and default denial of local subprocess plugins.
Plugin execution requires --allow-local-exec, still executes arbitrary code,
and does not provide filesystem or network isolation. Release and regulated
profiles deny local subprocess mode. See ../CHANGELOG.md and ../SECURITY.md.

Run the minimal P0a golden path:

    uv run python -m hate p0a --input fixtures/golden/p0a-minimal/input --out tmp/p0a-smoke --source-version local-smoke

## Platform CLI

`hate platform` is the operator-facing surface over canonical HATE reports.

Common commands:

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

When updating release or customer-facing claims, verify that README files,
acceptance records, Birdseye, the schema registry, and product-grade status do
not contradict each other.

## License

MIT License. See [LICENSE](../LICENSE).

## v0.3.0 Responsibility Freeze and Bridge-Only Migration

New HATE development is frozen to P0a/P0b/P1a plus schemas, adapters/plugins, and local evidence history/replay. Existing post-P1a commands are thin bridges. The default compat-v0.2 provider preserves the v0.2 command, option, output-file, required-field, and exit-code contracts.

Pass --bridge-provider handoff on a leaf command to create bridge-request.json without starting an external process or network call. HATE_BRIDGE_PROVIDER is also supported, with the CLI option taking precedence. Use hate bridge materialize for external results; schema, bridge ID, owner, SHA-256, or sourceRefs mismatches fail closed with exit 2 and no partial legacy output.

HATE/v1 remains available through v1. Post-P1a compatibility surfaces are deprecated since 0.3.0 and have a removal window after 1.0.0. HATE remains an advisory evidence producer: product_ready is false and verdict, Go/No-Go, waiver, approval, and publish authority remain external.
