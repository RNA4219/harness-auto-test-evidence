# HATE: harness-auto-test-evidence

HATE is a CLI that converts JUnit XML, coverage, and repository validation results
into HATE/v1 JSON. A CI or E2E platform can use that JSON to store or display test
results. QEG is the external system responsible for release approval, waivers,
immutability, retention, final Go/No-Go, and publication decisions.

## Display one failed E2E test

Configure your test runner in CI to write its results to JUnit XML. HATE reads
the XML and a `ci-context.json` file containing the run ID and commit SHA. This
example uses the bundled login test results and CI metadata. PowerShell prints
the values you can pass to a UI.

1. Download `hate.exe` and `harness-auto-test-evidence-rust.zip` from the
   [Rust GitHub release](https://github.com/RNA4219/harness-auto-test-evidence/releases/tag/v0.3.0%2Brust.1).
   Extract the ZIP and place `hate.exe` in the directory containing `Cargo.toml`
   and `fixtures`. You can also place the executable in an existing checkout.
   The executable runs without Python, uv, or a change to PATH.
2. Open PowerShell in that directory and import the sample files.

   ```powershell
   $hate = '.\hate.exe'
   $demo = Join-Path ([IO.Path]::GetTempPath()) ("hate-demo-" + [guid]::NewGuid())
   $inputDir = New-Item -ItemType Directory -Path (Join-Path $demo input) -Force
   Copy-Item fixtures/adapters/ci/generic/input/ci-context.json -Destination $inputDir.FullName
   Copy-Item fixtures/adapters/junit/surefire/junit.xml -Destination $inputDir.FullName

   & $hate p0a --input $inputDir.FullName --out "$demo/out" --source-version readme-demo
   if ($LASTEXITCODE -ne 0) { throw "HATE exit code: $LASTEXITCODE" }
   ```

   In this example, HATE exits with code `0` because it imported the files and
   wrote the results successfully. `HATE-test-results.ndjson` contains one test
   result per line, and the result for `loginFails` has `payload.status` set to
   `failed`.

3. Read the NDJSON as UTF-8 and print the failed test's name, duration, and run ID.

   ```powershell
   Get-Content -Encoding UTF8 "$demo/out/HATE-test-results.ndjson" |
     ForEach-Object { ConvertFrom-Json -InputObject $_ } |
     Where-Object { $_.payload.status -eq 'failed' } |
     ForEach-Object {
       "{0} | Failed | {1} ms | run_id={2}" -f $_.payload.identity_components.name,
         $_.payload.duration_ms, $_.run_id
     }
   ```

   ```text
   loginFails | Failed | 4 ms | run_id=generic-2001
   ```

For your own pipeline, replace the sample XML and run metadata with your CI
outputs. In the UI, use `payload.status` to choose a label, `payload.duration_ms`
to show how long the test took, and `run_id` to identify the run.

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

Install from the directory containing the Rust source. The installed binary
runs without Python or uv.

    cargo install --path . --locked
    hate --help

For a local release binary, run `cargo build --release --locked`. The Windows
binary is `target/release/hate.exe`. Compatibility tests use the Python package
in this checkout as a reference.
To evaluate this project with `product grade-reports` or `gap closure`, supply
the project checkout with its documentation and fixtures.

For the Python CLI, download the
[v0.3.0 release wheel](https://github.com/RNA4219/harness-auto-test-evidence/releases/tag/v0.3.0)
and install it locally. The wheel is distributed through GitHub Releases.

    uv tool install ./harness_auto_test_evidence-0.3.0-py3-none-any.whl
    hate --help

Use `uv build` to build a wheel from source. HATE/v1 and HATE-bridge/v1 schemas are included.
Local subprocess plugins are denied by default and require `--allow-local-exec`.
They execute arbitrary code without filesystem or network isolation; release and regulated
profiles deny this mode. See [CHANGELOG](../CHANGELOG.md) and [SECURITY](../SECURITY.md) for migration and execution boundaries.

Run the minimal P0a golden path:

    hate p0a --input fixtures/golden/p0a-minimal/input --out tmp/p0a-smoke --source-version local-smoke

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
hate platform verdict `
  --input tmp/major-oss-two-cycle/cycle-2 `
  --corpus docs/process/real-repo-verdict-corpus/major-oss-expected-verdicts-20260704.json `
  --out tmp/platform-verdict.json

hate platform triage `
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
cargo test --locked
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
