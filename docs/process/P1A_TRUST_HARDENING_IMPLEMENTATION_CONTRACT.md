---
intent_id: INT-HATE-P1A-TRUST-HARDENING-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# P1a Trust Hardening Implementation Contract

## 1. 目的

P1a は、HATE が生成する自動テスト証跡の信頼性を説明可能・再現可能にする層である。
AETE score、adapter capability、profile、canonical identity、retry aggregation、
path normalization、replay / compare / explain / recommend / doctor を実装対象とする。

P1a は release Gate ではない。AETE score は QEG や人間レビューの入力であり、
未校正 score を release approval として扱わない。

## 2. Scope

### In

- AETE 8 dimensions with 0 / 1 / 3 / 5 scale
- profile and calibration metadata
- adapter capability manifest
- canonical test identity and aliases
- matrix / shard / retry aggregation
- path normalization and artifact resolver map
- replay / compare / explain / recommend / doctor command contracts
- risk debt and manual-bb bridge trigger conditions

### Out

- QEG Gate verdict
- waiver / approval / retention / immutability
- manual test execution
- Shipyard acceptance / publish transition

## 3. AETE Score Contract

```yaml
schema_version: HATE/v1
record_type: aete_score
run_id: string
run_attempt: number
commit_sha: string
rubric_version: string
profile_version: string
calibration_status: uncalibrated | provisional | calibrated
score_confidence: low | medium | high
subject:
  subject_type: evidence_item | test_case | suite | change | run
  subject_id: string
dimensions:
  provenance_integrity: 0 | 1 | 3 | 5
  determinism_flakiness: 0 | 1 | 3 | 5
  traceability_lineage: 0 | 1 | 3 | 5
  oracle_strength: 0 | 1 | 3 | 5
  change_relevance: 0 | 1 | 3 | 5
  coverage_adequacy: 0 | 1 | 3 | 5
  cross_signal_corroboration: 0 | 1 | 3 | 5
  freshness_profile_conformance: 0 | 1 | 3 | 5
weighted_score: number
reason_refs: array
source_refs: array
```

Dimension score must include reason refs. A score without reason refs is invalid.

## 4. Scoring Rules

| Dimension | Score 0 | Score 1 | Score 3 | Score 5 |
|---|---|---|---|---|
| provenance_integrity | missing commit/run/hash | partial provenance | run + commit + hash | tamper-resistant provenance |
| determinism_flakiness | unresolved flaky | retry unknown | deterministic single run | stable across retry/matrix |
| traceability_lineage | no sourceRefs | weak refs | requirement/risk/test linked | source-backed full lineage |
| oracle_strength | no assertion | smoke only | specified oracle | mutation/contract backed |
| change_relevance | unrelated | module-level | changed file linked | changed line/risk linked |
| coverage_adequacy | none | file coverage | line coverage | branch/context coverage |
| cross_signal_corroboration | single weak signal | execution only | execution + coverage | execution + coverage + static/artifact |
| freshness_profile_conformance | stale/profile mismatch | unknown | fresh enough | fresh and profile conformant |

Weighted score follows `SPECIFICATION.md#12`. Profile can change thresholds, but cannot change
dimension vocabulary.

## 5. Adapter Capability Manifest

```yaml
adapter_id: string
adapter_version: string
kind: test_result | coverage | static | contract | mutation | artifact | upstream
input_formats: array
output_record_types: array
capability:
  execution_result: boolean
  retry: boolean
  matrix: boolean
  flaky_history: boolean
  coverage_context: boolean
  artifact_hash: boolean
  source_refs: boolean
  redaction: boolean
known_limits: array
conformance_fixtures: array
profile_support:
  default: supported | partial | unsupported
  strict: supported | partial | unsupported
  release: supported | partial | unsupported
```

Any unsupported capability that affects AETE must become a soft gap, risk debt, or doctor finding.

## 6. Canonical Test Identity

```yaml
canonical_test_id: string
identity_components:
  framework: string
  package: string
  file: string
  classname: string
  name: string
  parameters: object
  matrix: object
aliases:
  - previous_id: string
    reason: rename | parameter_change | framework_migration | path_normalization
    valid_from: string
```

ID generation:

```text
canonical_test_id = <framework>:<normalized_file>::<classname>::<name>[::<stable_parameter_hash>]
```

Matrix values that do not change the logical test must be stored in `matrix`, not in `name`.

## 7. Retry / Matrix Aggregation

| Raw results | Aggregate status | Rule |
|---|---|---|
| all passed | stable_passed | deterministic success |
| pass after fail | flaky_passed | soft gap unless profile makes it hard |
| fail after pass | flaky_failed | hard or conditional depending profile |
| all failed | failed | evidence exists but contradicts claim |
| missing shard | inconclusive | soft gap or hard DQ for release profile |
| parser failure | adapter_failed | exit 1 or DQ based requiredness |

Aggregation key:

```text
canonical_test_id + normalized matrix group + run_attempt
```

The same input must produce the same aggregate status.

## 8. Path Normalization and Resolver

```yaml
artifact_resolver_map:
  schema_version: HATE/v1
  run_id: string
  entries:
    - original: string
      normalized: string
      root_kind: workspace | package | container | windows | url
      resolution_status: resolved | unresolved | unsafe
      source_refs: array
```

Rules:

- Windows separators become `/`
- absolute workspace paths become workspace-relative paths
- container paths must resolve to workspace or package root
- `..` traversal, symlink escape, and unsafe URL become `unsafe`
- unresolved path is a doctor finding and may become soft gap

## 9. Command Contracts

```text
HATE replay --bundle <bundle> --profile <profile>
HATE compare --base <bundle> --head <bundle>
HATE explain --bundle <bundle> --why-excluded|--why-soft-gap|--why-score-changed
HATE recommend --bundle <bundle> --gap <gap_id>
HATE doctor --fixture <path> --profile <profile>
```

Outputs:

| Command | Output |
|---|---|
| replay | `replay-report.json`, deterministic recalculation hash |
| compare | `compare-report.json`, trust delta / DQ delta / risk coverage delta |
| explain | `explain-report.json`, source-backed reason tree |
| recommend | `recommendation-report.json`, next evidence / test layer / manual bridge |
| doctor | `doctor-report.json`, adapter / schema / path / provenance / QEG findings |

## 10. Doctor Finding Taxonomy

| Category | Examples | Default severity |
|---|---|---|
| adapter | unknown dialect, partial parse | medium |
| schema | missing required, invalid enum | high |
| path | unresolved path, unsafe traversal | high |
| provenance | missing commit/run/hash | high |
| qeg_fixture | unsupported claim, missing sourceRefs | high |
| artifact_safety | unsafe URL, secret scan fail | critical |
| profile | unsupported capability for profile | medium |

## 11. Fixture Contract

```text
fixtures/trust/
  aete-score-minimal/
  aete-score-low-confidence/
  retry-matrix-flaky/
  retry-matrix-stable/
  canonical-identity-rename/
  path-normalization-windows/
  path-normalization-container/
  replay-deterministic/
  compare-trust-delta/
  explain-soft-gap/
  recommend-manual-bridge/
  doctor-path-unsafe/
```

Each fixture must include:

- `input/`
- `expected/`
- `README.md` with purpose and oracle
- source refs to this contract and `SPECIFICATION.md`

## 12. Shipyard Acceptance

| Stage | Required evidence |
|---|---|
| plan | P1a task packet references this contract |
| dev | AETE, identity, resolver, command modules changed |
| acceptance | fixture results for aete, retry, identity, path, replay, doctor |
| integrate | QEG export and risk debt references remain consistent |
| publish | no release approval emitted by HATE |

## 13. Go Criteria

RanD KanoMode can treat P1a trust hardening specification as `go` when:

- AETE schema, dimension score table, and metadata are specified
- adapter capability and profile support are specified
- canonical identity and aggregation rules are specified
- replay / compare / explain / recommend / doctor command contracts are specified
- fixture tree and failure taxonomy are specified
- implementation completion remains gated by executable fixture results
