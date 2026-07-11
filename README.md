---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-05
next_review_due: 2026-07-19
---

# HATE Agent README

This root README is for coding agents working inside this repository. For
human-facing product documentation, read:

- [日本語 README](docs/README_JA.md)
- [English README](docs/README_EN.md)

HATE, short for `harness-auto-test-evidence`, is a local-first evidence
normalizer for automated test and repository validation artifacts. It prepares
structured HATE/v1 records that can be consumed by QEG and related workflow
tools. It is not the final release gate, approval authority, or hosted SaaS
control plane.

## Current State

- Package version: 0.3.0
- CLI entrypoint: `hate`
- Runtime posture: local-first CLI and JSON/HTML artifact generator
- PoC posture: PoC complete with explicit non-overclaim guardrails
- Product-ready posture: `product_ready=false` until external release/QEG
  approval and remaining production-readiness gaps are closed
- Latest local full regression observed during release prep: `1910 passed`
- Major OSS validation corpus: 10 repositories, 22,171 records per final
  two-cycle run, 5 pass / 5 hold, expected-verdict precision and recall at 1.0
  for the frozen corpus

Important acceptance records:

- [PoC completion](docs/acceptance/POC_COMPLETION_20260703.md)
- [Major OSS two-cycle validation](docs/acceptance/MAJOR_OSS_TWO_CYCLE_20260704.md)
- [Platform CLI and product-grade gate](docs/acceptance/PLATFORM_CLI_PRODUCT_GRADE_GATE_20260703.md)
- [Docs freshness review](docs/acceptance/DOCS_FRESHNESS_REVIEW_20260705.md)
- [v0.3.0 responsibility freeze acceptance](docs/acceptance/RELEASE_V0_3_0_20260711.md)
- [v0.2.0 local release acceptance](docs/acceptance/RELEASE_V0_2_0_20260711.md)
- [v0.1.0 PoC preview release](docs/acceptance/RELEASE_V0_1_0_20260705.md)

## Agent Operating Rules

1. Do not claim HATE is production-ready, enterprise-ready, regulated-ready, or
   a final release authority unless a current QEG release approval artifact says
   so.
2. Treat `docs/process/PRODUCT_REQUIREMENTS_DEFINITION.md` as the high-level
   requirement source and `docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md`
   as the product-grade implementation contract.
3. Treat `docs/process/RUNBOOK.md` and `docs/process/EVALUATION.md` as the
   default execution and acceptance references.
4. Update `docs/birdseye` with `uv run python tools/codemap/update.py` after
   changing source, tests, schemas, fixtures, or important docs.
5. Keep generated runtime artifacts under `tmp/` or another ignored output
   directory unless an acceptance record explicitly belongs in `docs/acceptance`.
6. When changing customer-facing claims, check
   `docs/process/LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` and avoid unsupported
   product claims.

## Read First

For ordinary implementation work:

1. [Blueprint](docs/process/BLUEPRINT.md)
2. [Specification](docs/process/SPECIFICATION.md)
3. [Product requirements](docs/process/PRODUCT_REQUIREMENTS_DEFINITION.md)
4. [Product-grade implementation spec](docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md)
5. [Requirements expansion detail spec](docs/process/PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md)
6. [Test integrity implementation spec](docs/process/TEST_INTEGRITY_IMPLEMENTATION_SPEC.md)
7. [Enterprise control state transition spec](docs/process/ENTERPRISE_CONTROL_STATE_TRANSITION_SPEC.md)
8. [Release candidate pack validator spec](docs/process/RELEASE_CANDIDATE_PACK_VALIDATOR_SPEC.md)
9. [Implementation task breakdown](docs/process/IMPLEMENTATION_TASK_BREAKDOWN.md)
10. [Runbook](docs/process/RUNBOOK.md)
11. [Evaluation](docs/process/EVALUATION.md)

For platform and release work:

1. [Product platform requirements](docs/process/PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md)
2. [Product platform detail spec](docs/process/PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md)
3. [Release migration policy](docs/process/RELEASE_MIGRATION_POLICY.md)
4. [Post-PoC requirements gap audit](docs/process/POST_POC_REQUIREMENTS_GAP_AUDIT.md)
5. [Canonical Post-PoC gap registry](docs/process/post-poc-gap-registry.json)
6. [Post-PoC productization detail spec](docs/process/POST_POC_PRODUCTIZATION_DETAIL_SPEC.md)
7. [Post-PoC spec traceability checklist](docs/process/POST_POC_SPEC_TRACEABILITY_CHECKLIST.md)
8. [Post-PoC implementation gap checklist](docs/process/POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md)

PoC 100% は product / enterprise / regulated 要件完了を意味しない。Post-PoC
の残課題は上記3文書と `POST_POC_REQUIREMENTS_GAP_AUDIT.md` を正本として扱う。

For navigation:

- [HATE file-reference codemap](docs/birdseye/README.md)
- [Agent skill: hate-release-maintainer](skills/hate-release-maintainer/SKILL.md)

## Common Commands

Install/test from the repository root:

```powershell
uv run pytest -q
uv run python -m compileall src tests
uv run python tools/codemap/update.py --check
```

Run the P0a golden path:

```powershell
uv run python -m hate p0a `
  --input fixtures/golden/p0a-minimal/input `
  --out tmp/readme-p0a `
  --source-version readme-smoke
```

Run the platform surface:

```powershell
uv run python -m hate platform --help
uv run python -m hate platform score --input tmp/major-oss-two-cycle/cycle-2 --out tmp/platform-score.json
uv run python -m hate platform verdict `
  --input tmp/major-oss-two-cycle/cycle-2 `
  --corpus docs/process/real-repo-verdict-corpus/major-oss-expected-verdicts-20260704.json `
  --out tmp/platform-verdict.json
uv run python -m hate platform triage `
  --input tmp/major-oss-two-cycle/cycle-2 `
  --out tmp/platform-triage.json
```

Generate a release candidate pack from product readiness artifacts:

```powershell
uv run python -m hate release candidate `
  --readiness tmp/product-readiness `
  --out tmp/release-candidate `
  --dry-run
```

## CLI Map

Primary commands:

- `hate p0a`: ingest local test/coverage inputs and generate P0a evidence
- `hate export qeg`: export optional QEG evidence
- `hate trust`: build AETE and trust-hardening reports
- `hate workflow`: map evidence to RanD, Shipyard, and workflow-cookbook
- `hate product`: generate or query product readiness artifacts
- `hate platform`: operate run/history/compare/schedule/findings/debt/review/
  assign/score/verdict/triage/history-analytics/history-materialize/
  notify/baseline/plugin/policy/report/serve flows
- `hate real-repo`: run recurring real repository validation rosters
- `hate release`: assemble release candidate evidence packs

## v0.3.0 Responsibility Freeze and Bridge Migration

HATEの新規開発責務はP0a/P0b/P1a、schema/adapter/plugin、local evidence history/replayへ固定されています。workflow、product、release、gap、expansion、real-repo、platform、validationの公開CLIはthin bridgeです。

- 既定providerはcompat-v0.2で、v0.2のcommand/options/output files/required fields/exit codeを維持します。CLI JSON stdoutにはcompatibility_provider、canonical_owner、deprecated_since、remove_afterを追加し、stderrへprocess単位で1回warningを出します。
- 外部handoffはleaf commandへ --bridge-provider handoff を付けます。HATE_BRIDGE_PROVIDERでも指定でき、CLI optionが優先します。handoffはprocess/networkを起動せずbridge-request.jsonだけを生成します。
- 外部owner resultは hate bridge materialize --request REQUEST --result RESULT --out OUT で検証・materializeします。ID、owner、hash、sourceRefs、schemaが不一致ならexit 2で、legacy artifactは生成しません。
- HATE/v1はv1まで維持します。P1b+ removal windowはdeprecated_since=0.3.0、remove_after=1.0.0です。
- 責務の正本はgovernance/responsibility-registry.jsonです。product_ready=falseと外部release authorityは変更ありません。

v0.2利用者は通常の互換動作ではcommandを変更する必要はありません。新しい外部owner連携を試す場合だけhandoffを明示してください。

## v0.3.0 Distribution, Safety, and Migration

- Official v0.3.0 packages are the wheel and source distribution attached to
  the GitHub Release. PyPI is intentionally not a distribution channel.
- Download the wheel from the GitHub Release, then install it with
  `uv tool install` and the local wheel path. The package includes HATE/v1 JSON
  schemas.
- Local subprocess plugins are denied by default. The operator must pass
  --allow-local-exec, and the manifest must carry signed and trusted external
  evidence. Release and regulated profiles always deny local subprocess mode.
- signature_valid is advisory external evidence, not cryptographic verification.
- Local subprocess mode does not provide filesystem or network isolation.
- See CHANGELOG.md for v0.1 migration notes and SECURITY.md for the execution
  boundary.
- Contributor guidance is in CONTRIBUTING.md and community expectations are in
  CODE_OF_CONDUCT.md.

## Release Checklist For Agents

Before calling a release task complete:

- README links work and route humans to both Japanese and English docs.
- Current test count and readiness claims are refreshed or explicitly marked as
  historical.
- `uv run pytest -q` passes.
- `uv run python -m compileall src tests` passes.
- `uv run python tools/codemap/update.py --check` passes, or codemap was
  regenerated and committed.
- `git diff --check` is clean.
- Any generated acceptance evidence is committed only if it is durable,
  human-readable release evidence.
- HATE still states that QEG/release approval is external to HATE.

Long-term operation checks:

- `hate platform history-analytics --input <history-window.json>`
- `hate platform history-materialize --input <history-window.json> --manifest-out <manifest.json>`
- `hate platform notify route --input <operating-record.json>`
- `hate platform notify deliver --input <delivery-attempts.json>`
- `hate platform baseline review --input <baseline-review.json>`

<!-- responsibility-freeze:start -->
## Responsibility Freeze (generated)

| 境界 | 現在値 |
|---|---:|
| core CLI leaf | 12 |
| bridge CLI leaf | 33 |
| core HATE/v1 record type | 29 |
| compat HATE/v1 record type | 311 |

- canonical owner: agent-gatefield, agent-state-gate, manual-bb-test-harness, product-ops-evidence, quality-evidence-graph, shipyard-cp, workflow-cookbook
- P1b以降は compat-v0.2 または明示的な handoff のみ。
- product_ready=false。QEG verdict、Go/No-Go、waiver、approval、publish authorityは外部責務。
- deprecated since: 0.3.0; remove after: 1.0.0（v0.xでは物理削除しない）。
- machine-readable source: governance/responsibility-registry.json
<!-- responsibility-freeze:end -->
