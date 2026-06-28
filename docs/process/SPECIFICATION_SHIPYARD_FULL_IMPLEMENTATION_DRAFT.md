---
intent_id: INT-HATE-SPEC-SHIPYARD-FULL-IMPL-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# HATE 仕様書: Shipyard-cp フル実装ドラフト

## 1. 目的

このドラフトは、Shipyard-cp の `plan -> dev -> acceptance -> integrate -> publish`
段階で HATE を P0a から P3 まで実装するための worker-facing 仕様である。

`SPECIFICATION.md` を正本とし、本書は Shipyard worker へ渡す実装分解、成果物、
acceptance gate、監査証跡を一枚にまとめる。draft worker の出力は直接正本にせず、
HATE maintainer が `SPECIFICATION.md` と `SPECIFICATION_SHIPYARD_AUDIT.md` に統合してから
正本扱いにする。

## 2. フル実装の定義

HATE のフル実装は、次をすべて満たす状態である。

| Phase | 完了定義 | 必須成果物 |
|---|---|---|
| P0a | local-first precheck が外部依存なしで再現可能 | `HATE-run.json`, `HATE-test-results.ndjson`, `HATE-coverage.ndjson`, `artifact-manifest.json`, `precheck-decision.json`, `record.json`, `summary.md`, DQ fixtures |
| P0b | QEG optional evidence として import 可能 | `qeg-bundle.json`, `evidence-map.json`, `diff-risk-test.json`, SARIF / Playwright artifact refs |
| P1a | trust hardening が再現可能 | `aete-score.json`, `adapter-capability.json`, `profile.json`, `artifact-resolver-map.json`, `doctor-report.json`, replay / compare / explain / recommend outputs |
| P1b | external workflow 接続が artifact として生成可能 | `requirement-evidence-alignment.json`, `shipyard-run-evidence.json`, `workflow-task-seed.json`, `workflow-acceptance-record.json`, `workflow-evidence.jsonl`, `workflow-docs-stale.json`, `workflow-birdseye-map.json`, `manual-bb-bridge-requests.jsonl` |
| P2 | productization が canonical bundle から派生可能 | PR annotation report, artifact budget report, attestation report, hosted read model export, product error report |
| P3 | enterprise readiness が artifact / metric で検証可能 | `product-readiness-report.json`, trust packet, SLO / incident report, residency profile, legal commitment register, assurance pack, portfolio health report |

## 3. Shipyard Task Packet

Shipyard へ渡す task は phase ごとに分割する。各 task は `plan`, `dev`, `acceptance`,
`integrate`, `publish` を通るが、HATE は Shipyard の state machine、worker dispatch、
publish approval を再実装しない。

| task_id | phase | objective | affected paths | acceptance |
|---|---|---|---|---|
| HATE-MVP-001 | P0a | common envelope / provenance / schema registry を実装 | `schemas/HATE/v1`, `src/schema`, `fixtures/golden/p0a-minimal` | JSON schema validation, common envelope present |
| HATE-MVP-002 | P0a | JUnit / LCOV adapter と canonical output を実装 | `src/adapters`, `fixtures/adapters`, `fixtures/golden/p0a-minimal` | generated output equals expected |
| HATE-MVP-003 | P0a | artifact manifest / precheck / record / summary を実装 | `src/precheck`, `src/manifest`, `src/summary` | decision enum, summary safety, record generation |
| HATE-MVP-004 | P0a | DQ negative fixtures と exit code を固定 | `fixtures/golden/p0a-minimal/dq-*`, `tests` | DQ-001/002/003/008/015 pass |
| HATE-MVP-005 | P0b | QEG minimal bundle / evidence-map / diff-risk-test を実装 | `src/qeg`, `fixtures/golden/p0b-qeg-minimal` | QEG minimal valid |
| HATE-MVP-006 | P0b | SARIF / Playwright artifact refs と safety を実装 | `src/adapters/sarif`, `src/adapters/playwright`, `src/security` | unsafe artifact quarantined |
| HATE-MVP-007 | P1a | AETE 8次元 / profile / calibration を実装 | `src/aete`, `fixtures/aete` | 0/1/3/5 score and metadata |
| HATE-MVP-008 | P1a | canonical identity / retry aggregation / path normalization を実装 | `src/identity`, `src/aggregate`, `src/path` | deterministic aggregation |
| HATE-MVP-009 | P1a | replay / compare / explain / recommend / doctor を実装 | `src/commands`, `fixtures/replay` | frozen bundle deterministic |
| HATE-MVP-010 | P1b | RanD alignment / manual-bb bridge を実装 | `src/integrations/rand`, `src/integrations/manual-bb` | no upstream verdict overwrite |
| HATE-MVP-011 | P1b | Shipyard run evidence mapping を実装 | `src/integrations/shipyard`, `fixtures/shipyard` | `publish_gate_override=false` |
| HATE-MVP-012 | P1b | workflow-cookbook artifacts を実装 | `src/integrations/workflow`, `fixtures/workflow` | task -> acceptance -> evidence trace |
| HATE-MVP-013 | P2 | optional export / PR annotation / artifact budget / attestation を実装 | `src/exporters`, `src/reports` | local precheck unchanged |
| HATE-MVP-014 | P2 | hosted read model / product operation reports を実装 | `src/read-model`, `src/product` | derived from canonical bundle |
| HATE-MVP-015 | P3 | enterprise readiness / trust / assurance / portfolio reports を実装 | `src/enterprise`, `src/assurance` | PRG-0..PRG-6 artifact metrics |

詳細契約:

- P0b QEG export: `P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md`
- P1a trust hardening: `P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md`
- full implementation specification readiness: `FULL_IMPLEMENTATION_SPEC_READINESS_CONTRACT.md`

## 4. Stage Gate Contract

| Shipyard stage | HATE worker action | Required evidence | Gate rule |
|---|---|---|---|
| plan | task scope, source docs, acceptance refs を固定 | task packet, source_refs, assumptions | source_refs がない task は hold |
| dev | code / schema / fixture / docs を生成 | changed files, generated artifacts | unrelated docs churn を禁止 |
| acceptance | local commands と manual-bb cases を実行 | test logs, generated artifacts, gate decision | P0/P1 fail は revise |
| integrate | QEG / workflow / Shipyard refs の整合確認 | cross-ref report, schema validation | downstream gate の再実装は block |
| publish | release candidate evidence を提示 | release brief, open risks, rollback note | HATE は publish approval を出さない |

## 5. Phase Acceptance Matrix

| Phase | Acceptance ID | Must pass before next phase | No-Go trigger |
|---|---|---|---|
| P0a | AC-HATE-P0A-GOLDEN | golden input から P0a required outputs を生成 | converter / CLI がない |
| P0a | AC-HATE-P0A-DQ | DQ-001/002/003/008/015 が expected decision / exit code と一致 | hard_dq が再現不能 |
| P0a | AC-HATE-P0A-SUMMARY-SAFETY | unsafe / restricted artifact が summary へ出ない | secret / PII / unsafe path leak |
| P0b | AC-HATE-P0B-QEG-BUNDLE | QEG minimal schema 互換 | `qeg-bundle.json` missing |
| P0b | AC-HATE-P0B-DIFF-RISK | risk -> test -> evidence edge が辿れる | high-risk path が unsupported claim |
| P1a | AC-HATE-P1A-AETE | 8次元 score と calibration metadata | uncalibrated score がGate正本扱い |
| P1a | AC-HATE-P1A-REPLAY | frozen bundle 再計算が deterministic | replay drift |
| P1a | AC-HATE-P1A-DOCTOR | adapter / schema / path / provenance finding を分類 | hidden gap |
| P1b | AC-HATE-P1B-RAND | RanD verdict を上書きせず alignment 生成 | upstream `no_go` overwrite |
| P1b | AC-HATE-P1B-SHIPYARD | Shipyard refs と HATE artifact refs を結線 | publish gate override |
| P1b | AC-HATE-P1B-WORKFLOW | task -> acceptance -> evidence が辿れる | workflow checker再実装 |
| P2 | AC-HATE-P2-OPTIONAL-EXPORT | optional export が canonical decision を変えない | external adapter が gating化 |
| P3 | AC-HATE-P3-ENTERPRISE | PRG-0..PRG-6 が artifact / metric を持つ | sales claim と実装状態の乖離 |

## 6. 実装証跡の最小コマンド契約

実装後は、少なくとも次のコマンド相当を固定する。

```text
HATE collect --fixture fixtures/golden/p0a-minimal/input --out .hate/out/p0a
HATE precheck --input .hate/out/p0a --profile default
HATE export qeg --fixture fixtures/golden/p0b-qeg-minimal/input --out .hate/out/p0b
HATE replay --bundle .hate/out/p0b/qeg-bundle.json
HATE compare --base fixtures/baseline --head .hate/out/p0b
HATE explain --bundle .hate/out/p0b/qeg-bundle.json --why-soft-gap
HATE recommend --bundle .hate/out/p0b/qeg-bundle.json
HATE doctor --fixture fixtures/golden/p0a-minimal/input
HATE workflow evidence --run <run_id>
HATE shipyard evidence --run-system-packet fixtures/shipyard/run-system-packet.sample.json
```

実 CLI 名は実装時に変更してよいが、`RUNBOOK.md`、`EVALUATION.md`、fixture、
Shipyard task packet の参照は同時に更新する。

## 7. フル実装で許容しないショートカット

- P0a expected fixture を手書きで更新して実装成功扱いにする
- DQ negative fixture を P1 以降へ先送りして P0a complete とする
- QEG `gate`, `waiver`, `approval`, `retention`, `immutability`, `schema migration` を HATE 側で実装する
- Shipyard `publish approval` または `acceptance verdict` を HATE artifact で代替する
- workflow-cookbook の checker / plugin host / Birdseye generator を HATE 側で再実装する
- P2/P3 contract document だけで enterprise readiness complete とする

## 8. Shipyard WorkerResult 要件

各 worker は次を返す。

```yaml
worker_result:
  task_id: string
  phase: P0a | P0b | P1a | P1b | P2 | P3
  status: success | failed | needs_manual_review
  changed_paths: array
  generated_artifacts: array
  validation_commands: array
  validation_results: array
  open_risks: array
  source_refs: array
  publish_gate_override: false
```

`publish_gate_override` は常に `false`。`needs_manual_review` は manual-bb へ接続するが、
manual-bb の結果を HATE が release approval として扱わない。

## 9. Completion Definition

フル実装仕様としての完成は、次を満たす。

- P0a〜P3 の phaseごとに task, artifact, acceptance, no-go trigger が定義されている
- Shipyard stage rules が `plan -> dev -> acceptance -> integrate -> publish` に対応している
- manual-bb full implementation gate の No-Go 条件が仕様内で説明されている
- P0b / P1a の No-Go 要件に対して詳細実装契約が存在する
- QEG / Shipyard / workflow-cookbook / manual-bb の再実装禁止が明示されている
- `SPECIFICATION.md` から本書と監査記録へ辿れる
