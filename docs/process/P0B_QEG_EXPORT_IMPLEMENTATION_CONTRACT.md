---
intent_id: INT-HATE-P0B-QEG-EXPORT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# P0b QEG Export Implementation Contract

## 1. 目的

P0b は、HATE が QEG optional evidence producer として成立するための最小 export 層である。
P0a の run / test / coverage / artifact / precheck / record を入力にし、
`qeg-bundle.json`, `evidence-map.json`, `diff-risk-test.json` を生成する。

HATE は QEG の Gate policy、waiver、approval、retention、immutability、schema migration、
source-backed Gate reason を実装しない。P0b の目的は、QEG が検証できる source-backed
optional evidence を出すことであり、release verdict を出すことではない。

## 2. 入力

| Input | Required | Source | Purpose |
|---|---:|---|---|
| `HATE-run.json` | yes | P0a | run provenance |
| `HATE-test-results.ndjson` | yes | P0a | canonical test nodes |
| `HATE-coverage.ndjson` | yes | P0a | coverage evidence nodes |
| `artifact-manifest.json` | yes | P0a | sourceArtifactIds / safety |
| `precheck-decision.json` | yes | P0a | evidence eligibility |
| `record.json` | yes | P0a | own-output validation |
| `diff-risk-test.json` | yes | code-to-gate / fixture | changed risk -> required test obligations |
| `HATE-static.sarif` | optional | SARIF adapter | finding / risk nodes |
| Playwright trace/screenshot/video/log refs | optional | Playwright adapter | artifact-backed execution evidence |

P0a `precheck-decision.payload.decision` が `hard_dq` の場合、正式な QEG import 用
`qeg-bundle.json` は生成しない。診断用に生成する場合は `metadata.debugOnly=true` とし、
summary に release input 不可を明記する。

## 3. 出力

| Output | Required | Role |
|---|---:|---|
| `qeg-bundle.json` | yes | QEG import bundle |
| `evidence-map.json` | yes | risk / requirement / test / evidence の中間graph |
| `diff-risk-test.json` | yes | code-to-gate risk と HATE evidence obligation の接続 |
| `qeg-export-report.json` | yes | export validation / unsupported claims / completeness |
| `qeg-export-summary.md` | yes | public-safe summary |

## 4. `qeg-bundle.json` Contract

```yaml
metadata:
  qegVersion: string
  runId: string
  runAttempt: number
  createdAt: ISO-8601
  profile: lean | standard | strict | ipo_controlled
  inputArtifacts: array[artifact_ref]
  debugOnly: boolean
nodes: array[node]
edges: array[edge]
completeness:
  score: number
  partial: boolean
  parserFailures: array
  unsupportedClaims: array
  excludedArtifacts: array
```

### 4.1 Node ID Rules

| Node kind | ID format | Source |
|---|---|---|
| requirement | `requirement:<stable-id>` | RanD / manual-bb / fixture |
| acceptance_criterion | `acceptance:<stable-id>` | RanD / workflow acceptance |
| changed_code | `changed_code:<path>#L<start>-L<end>` | diff-risk-test |
| risk | `risk:<risk-id>` | code-to-gate / SARIF |
| test | `test:<canonical_test_id_hash>` | HATE-test-results |
| execution_evidence | `execution:<run_id>:<canonical_test_id_hash>` | HATE-test-results |
| coverage | `coverage:<path_hash>` | HATE-coverage |
| evidence_artifact | `artifact:<artifact_id>` | artifact-manifest |
| gate_verdict | `hate_precheck:<run_id>:<run_attempt>` | precheck-decision |

### 4.2 Edge Rules

| Edge kind | Required | Meaning |
|---|---:|---|
| `derives_from` | conditional | requirement -> acceptance |
| `touches` | yes when diff exists | changed_code -> risk |
| `requires_test` | yes when risk has obligation | risk -> test or test_placement |
| `evidenced_by` | yes | test -> execution_evidence |
| `supports` | yes when evidence supports risk/requirement | evidence -> risk / acceptance |
| `contradicts` | conditional | SARIF / failure -> claim |
| `decides` | yes | hate_precheck -> qeg export eligibility |

Every edge must have:

```yaml
traceability:
  sourceRefs: non-empty array
  confidence: low | medium | high
  assumptions: array
```

## 5. `evidence-map.json` Contract

`evidence-map.json` は QEG bundle より実装寄りの中間表現である。

```yaml
schema_version: HATE/v1
run_id: string
run_attempt: number
requirements: array
risks: array
tests: array
evidence: array
links:
  requires_test: array
  evidenced_by: array
  supports: array
  contradicts: array
gaps:
  unsupported_claims: array
  missing_execution: array
  missing_coverage: array
  unsafe_artifacts: array
```

No hidden gap is allowed. If a changed high-risk path has no execution evidence, it must appear in
`gaps.missing_execution` and either `risk-debt-register.json` or `manual-bb-bridge-requests.jsonl`.

## 6. `diff-risk-test.json` Contract

```yaml
schema_version: HATE/v1
source_tool: code-to-gate | fixture | manual
commit_sha: string
changed_entities:
  - entity_id: string
    path: string
    ranges: array
    risk_refs: array
risks:
  - risk_id: string
    severity: low | medium | high | critical
    title: string
    required_test_layers: array
    source_refs: array
test_obligations:
  - obligation_id: string
    risk_id: string
    expected_test_refs: array
    required_evidence_kinds: array
```

P0b fixture では、少なくとも high-risk changed path 1 件、required test 1 件、
evidence present 1 件、evidence missing 1 件を含める。

## 7. Completeness Calculation

P0b completeness score は QEG verdict ではない。HATE export の充足度である。

```text
base = 1.0
- 0.20 if required artifact missing
- 0.15 per parser failure affecting required evidence
- 0.10 per unsupported high-risk claim
- 0.10 if path normalization incomplete
- 0.10 if artifact safety excludes required evidence
floor at 0
```

`partial=false` にできる条件:

- required P0a artifact がすべて存在
- precheck decision が `eligible` または `conditional`
- required sourceRefs が non-empty
- high-risk changed path の missing execution が 0、または manual bridge / risk debt に接続済み
- unsafe artifact が export から除外済み

## 8. Fixture Contract

```text
fixtures/golden/p0b-qeg-minimal/
  input/
    p0a/
      HATE-run.json
      HATE-test-results.ndjson
      HATE-coverage.ndjson
      artifact-manifest.json
      precheck-decision.json
      record.json
    diff-risk-test.json
    HATE-static.sarif
    artifacts/
  expected/
    qeg-bundle.json
    evidence-map.json
    qeg-export-report.json
    qeg-export-summary.md
```

Negative fixtures:

| Fixture | Expected |
|---|---|
| `missing-source-ref` | export report unsupported claim |
| `missing-required-artifact` | `hard_dq` or export failure |
| `unsafe-artifact-required` | quarantine + partial export |
| `high-risk-no-execution` | risk debt + manual-bb bridge |

## 9. CLI Contract

```text
HATE export qeg --fixture fixtures/golden/p0b-qeg-minimal/input --out .hate/out/p0b
HATE qeg validate --bundle .hate/out/p0b/qeg-bundle.json
HATE qeg explain --bundle .hate/out/p0b/qeg-bundle.json --unsupported
```

Exit codes:

| Exit | Meaning |
|---:|---|
| 0 | valid export |
| 1 | CLI / parser / schema failure |
| 2 | HATE hard DQ or required evidence not exportable |

## 10. Shipyard Acceptance

| Stage | Required evidence |
|---|---|
| plan | task packet references this contract and `SPECIFICATION.md#13` |
| dev | changed paths include qeg exporter, schemas, fixtures |
| acceptance | qeg export command, validation result, manual-bb gap review |
| integrate | QEG compatibility report and no reimplementation assertion |
| publish | release candidate may reference qeg export, but HATE does not approve release |

## 11. Go Criteria

RanD KanoMode can treat P0b QEG export specification as `go` when:

- this contract exists and is referenced by `SPECIFICATION.md`
- fixture tree, output schema, failure behavior, and CLI contract are specified
- No-Go triggers are explicit
- HATE/QEG responsibility boundary is explicit
- implementation completion remains gated by actual generated artifacts
