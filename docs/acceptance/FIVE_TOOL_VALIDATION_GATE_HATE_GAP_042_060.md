---
intent_id: INT-HATE-FIVE-TOOL-VALIDATION-GAP-042-060-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-02
next_review_due: 2026-07-09
---

# Five-Tool Validation Gate For HATE-GAP-042, HATE-GAP-043, And HATE-GAP-049..060

この記録は、`five-tool-validation-gate` の順序に従って、thin requirement
として再確認された provider matrix、runner coverage、core analysis
expansion の実装証跡を固定する。HATE は QEG の最終判定を置き換えず、
QEG に渡せる自動テスト証跡、fixture、schema、sourceRef を揃える。

対象範囲:

- HATE-GAP-042: CI/SCM provider matrix
- HATE-GAP-043: runner coverage
- HATE-GAP-049: impact analysis
- HATE-GAP-050: recommendation
- HATE-GAP-051: flake classification
- HATE-GAP-052: oracle classification
- HATE-GAP-053: evidence synthesis
- HATE-GAP-056: contradiction detection
- HATE-GAP-058: audience report
- HATE-GAP-059: fixture quality
- HATE-GAP-060: adapter capability diff

## Chain Status

| Chain stage | Status | Authoritative evidence | Notes |
|---|---|---|---|
| RanD | degraded-input | `docs/process/PRODUCT_REQUIREMENTS_DEFINITION.md` | PRD rows `FR-CI-*`, `FR-LANG-*`, and `FR-ANALYSIS-001..012` are present; no external RanD packet is stored in this repo for this slice. |
| Code-to-gate | degraded-input | `docs/process/PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md`, `docs/tasks/HATE_REQUIREMENTS_EXPANSION_TASK_SEEDS.md` | Packet and task seed rows identify scope, positive/negative fixtures, No-Go limits, and acceptance IDs; no external code-to-gate risk file is stored for this slice. |
| HATE | pass | runtime modules, schemas, fixtures, tests, expansion runner | The repo contains report builders, schema registry entries, canonical fixtures, focused tests, and expansion runner UAT report generation. |
| manual-bb | ready-for-human-plan | this document, fixture negative cases, report findings | Manual BB is not replaced. The manual plan below defines human black-box checks derived from HATE findings. |
| QEG | ready-for-import-package | `schemas/HATE/v1/qeg-bundle.schema.json`, release candidate pack path, shared `sourceRefs` | QEG remains the final gate. HATE evidence is advisory and importable, not a QEG verdict. |

## Artifact Map

| Gap | Requirement | Spec | Runtime | Schema | Fixtures | Tests |
|---|---|---|---|---|---|---|
| HATE-GAP-042 | `FR-CI-001` | `PRODUCT_REQUIREMENTS_PORTFOLIO_READINESS_DETAIL_SPEC.md` | `src/hate/expansion/portfolio_readiness.py::build_provider_integration_report` | `schemas/HATE/v1/provider-integration-report.schema.json` | `fixtures/expansion/provider-matrix/*/fixture.json` | `tests/test_expansion_portfolio_readiness.py` |
| HATE-GAP-043 | `FR-LANG-001` | `PRODUCT_REQUIREMENTS_PORTFOLIO_READINESS_DETAIL_SPEC.md` | `src/hate/expansion/portfolio_readiness.py::build_runner_dialect_coverage_report` | `schemas/HATE/v1/runner-dialect-coverage-report.schema.json` | `fixtures/expansion/runner-dialects/*/fixture.json` | `tests/test_expansion_portfolio_readiness.py` |
| HATE-GAP-049 | `FR-ANALYSIS-001` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/impact_analysis.py` | `schemas/HATE/v1/impact-analysis-report.schema.json` | `fixtures/expansion/impact-analysis/*/fixture.json` | `tests/test_analysis_impact_analysis.py` |
| HATE-GAP-050 | `FR-ANALYSIS-002` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/test_recommendation.py` | `schemas/HATE/v1/test-recommendation-report.schema.json` | `fixtures/expansion/test-recommendation/*/fixture.json` | `tests/test_analysis_test_recommendation.py` |
| HATE-GAP-051 | `FR-ANALYSIS-003` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/flaky_classification.py` | `schemas/HATE/v1/flaky-classification-report.schema.json` | `fixtures/expansion/flaky-classification/*/fixture.json` | `tests/test_analysis_flaky_classification.py` |
| HATE-GAP-052 | `FR-ANALYSIS-004` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/oracle_classification.py` | `schemas/HATE/v1/oracle-classification-report.schema.json` | `fixtures/expansion/oracle-classification/*/fixture.json` | `tests/test_analysis_oracle_classification.py` |
| HATE-GAP-053 | `FR-ANALYSIS-005` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/evidence_synthesis.py` | `schemas/HATE/v1/evidence-synthesis-report.schema.json` | `fixtures/expansion/evidence-synthesis/*/fixture.json` | `tests/test_analysis_evidence_synthesis.py` |
| HATE-GAP-056 | `FR-ANALYSIS-008` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/contradiction_detection.py` | `schemas/HATE/v1/contradiction-report.schema.json` | `fixtures/expansion/contradiction-detection/*/fixture.json` | `tests/test_analysis_contradiction_detection.py` |
| HATE-GAP-058 | `FR-ANALYSIS-010` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/audience_report_pack.py` | `schemas/HATE/v1/audience-report-pack.schema.json` | `fixtures/expansion/audience-report-pack/*/fixture.json` | `tests/test_analysis_audience_report_pack.py` |
| HATE-GAP-059 | `FR-ANALYSIS-011` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/fixture_quality.py` | `schemas/HATE/v1/fixture-quality-report.schema.json` | `fixtures/expansion/fixture-quality/*/fixture.json` | `tests/test_analysis_fixture_quality.py` |
| HATE-GAP-060 | `FR-ANALYSIS-012` | `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md` | `src/hate/analysis/adapter_capability_diff.py` | `schemas/HATE/v1/adapter-capability-diff-report.schema.json` | `fixtures/expansion/adapter-capability-diff/*/fixture.json` | `tests/test_analysis_adapter_capability_diff.py` |

## Findings And Risks

- HATE implementation evidence is present for the target slice.
- External RanD and Code-to-gate artifacts are not stored in this repo, so the chain
  is recorded as degraded-input rather than fully external-verified.
- QEG final judgment is not claimed. HATE only prepares evidence and sourceRefs.
- The expansion backlog table preserves the original discovery class; the current
  implementation state is controlled by acceptance, packet, runner, and tests.

## Manual BB Plan

| Priority | Scenario | Expected result |
|---|---|---|
| P0 | Overbroad provider permission in GitLab/Azure/Bitbucket-style provider input | Provider report holds or blocks with least-privilege finding and sourceRef. |
| P0 | Unsupported runner capability for .NET/Rust/Cypress-style runner | Runner report emits capability gap and does not overclaim support. |
| P0 | Changed dependency with ownership and history signals | Impact report produces affected tests, requirements, confidence, and sourceRefs. |
| P0 | Generic recommendation without oracle or command | Recommendation report denies generic advice and requires actionable verification. |
| P0 | Unknown retry instability | Flaky report holds unknown flake and does not mark it pass. |
| P0 | Snapshot-only oracle on critical risk | Oracle report holds because semantic guard is insufficient. |
| P0 | Weak coverage-only evidence inflates readiness | Evidence synthesis blocks readiness inflation. |
| P0 | Passing tests conflict with critical static finding | Contradiction report blocks or holds the release claim. |
| P1 | Audience report tries to recompute QEG verdict | Audience report denies recomputation and preserves shared sourceRefs. |
| P1 | Fixture name determines behavior | Fixture quality report emits coupling finding. |
| P1 | Adapter drops raw fields while claiming capability | Adapter capability diff emits lossy transform or claim drift finding. |

## QEG Gate Package

QEG import should receive:

- generated expansion reports from `hate expansion run`
- generated `*-uat-report.json` reports for the target areas
- release candidate pack containing all `EXPANSION_REPORT_TYPES`
- `sourceRefs` from fixtures and report builders
- any manual-bb output created from the plan above

QEG must decide final `go`, `conditional_go`, or `no_go`. HATE must not convert
its own `pass` into QEG approval.

## Verdict

Conditional Go for the HATE-side implementation slice.

理由:

- 要件、仕様、runtime、schema、fixture、tests、expansion runner 接続は揃っている。
- five-tool chain は repo 内証跡として固定された。
- 外部 RanD/Code-to-gate/QEG 実行 artifact はこの repo にないため、最終 gate は
  QEG 側で再評価する。

## Next Commands

```powershell
uv run pytest tests\test_expansion_portfolio_readiness.py tests\test_expansion_runner.py tests\test_analysis_impact_analysis.py tests\test_analysis_test_recommendation.py tests\test_analysis_flaky_classification.py tests\test_analysis_oracle_classification.py tests\test_analysis_evidence_synthesis.py tests\test_analysis_contradiction_detection.py tests\test_analysis_audience_report_pack.py tests\test_analysis_fixture_quality.py tests\test_analysis_adapter_capability_diff.py tests\test_requirements_expansion_docs.py -q
uv run pytest -q
uv run python -m compileall src tests
uv run python tools/codemap/update.py
git diff --check
```
