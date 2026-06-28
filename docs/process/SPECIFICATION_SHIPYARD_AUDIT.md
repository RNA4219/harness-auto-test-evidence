---
intent_id: INT-HATE-SPEC-SHIPYARD-AUDIT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Shipyard-cp 仕様書監査記録

## 1. 目的

この文書は、Shipyard-cp の `plan -> dev -> acceptance -> integrate -> publish`
運用に沿って作られた HATE 仕様書ドラフトを、HATE maintainer 観点で監査し、
`SPECIFICATION.md` を正本として完成へ導くための監査証跡である。

Shipyard-cp は worker draft と run / audit refs を作る補助 control plane として扱う。
HATE は Shipyard の state machine、acceptance verdict、publish approval を再実装しない。

## 2. 監査対象

| 対象 | 役割 | 判定 |
|---|---|---|
| `docs/process/SPECIFICATION.md` | 仕様書正本 | pass with follow-up |
| `docs/process/SPECIFICATION_COMPLETION_AUDIT.md` | Shipyard specification completion audit | pass |
| `docs/process/SPECIFICATION_SHIPYARD_DRAFT.md` | Shipyard worker draft | integrated |
| `docs/process/SPECIFICATION_SHIPYARD_FULL_IMPLEMENTATION_DRAFT.md` | Shipyard full implementation worker draft | integrated |
| `docs/process/MANUAL_BB_GATE_SPECIFICATION.md` | manual-bb gate 証跡 | referenced |
| `docs/process/MANUAL_BB_GATE_FULL_IMPLEMENTATION.md` | manual-bb full implementation gate | referenced |
| `docs/process/RAND_KANO_MODE_FULL_IMPLEMENTATION_AUDIT.md` | RanD KanoMode full implementation audit | referenced |
| `docs/process/rand-kano-mode-full-implementation-audit.json` | RanD requirements audit packet | pass with no_go |
| `docs/process/rand-kano-mode-full-implementation-kano.json` | RanD kano audit artifact | pass |
| `docs/process/RAND_KANO_MODE_FULL_IMPLEMENTATION_READINESS_GO.md` | RanD KanoMode readiness Go summary | pass |
| `docs/process/rand-kano-mode-full-implementation-readiness-audit.json` | RanD readiness requirements audit packet | pass with go |
| `docs/process/rand-kano-mode-full-implementation-readiness-kano.json` | RanD readiness kano artifact | pass |
| `docs/process/RAND_KANO_MODE_REQUIREMENTS_QUALITY_AUDIT.md` | RanD KanoMode requirements quality audit | pass with conditional_go |
| `docs/process/rand-kano-mode-requirements-quality-audit.json` | RanD requirements quality audit packet | pass with conditional_go |
| `docs/process/rand-kano-mode-requirements-quality-kano.json` | RanD requirements quality kano artifact | pass |
| `docs/process/RAND_KANO_MODE_IDEA_QUALITY_AUDIT.md` | RanD KanoMode idea quality audit | pass with conditional_go |
| `docs/process/rand-kano-mode-idea-quality-audit.json` | RanD idea quality audit packet | pass with conditional_go |
| `docs/process/rand-kano-mode-idea-quality-kano.json` | RanD idea quality kano artifact | pass |
| `docs/process/P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md` | P0b QEG export dense contract | pass |
| `docs/process/P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md` | P1a trust hardening dense contract | pass |
| `docs/process/FULL_IMPLEMENTATION_SPEC_READINESS_CONTRACT.md` | RanD readiness audit boundary | pass |
| `docs/process/shipyard-run-evidence-p0a-schema-bootstrap.json` | Shipyard local run evidence | pass |
| `docs/process/shipyard-run-evidence-full-implementation-spec.json` | Shipyard full implementation spec evidence | pass |
| `docs/process/shipyard-run-evidence-p0a-cli-implementation.json` | Shipyard local P0a CLI implementation evidence | pass |
| `docs/process/shipyard-run-evidence-p0a-dq-fixtures.json` | Shipyard local P0a DQ fixture evidence | pass |
| `schemas/HATE/v1/*` | P0a schema bootstrap | pass with P1 follow-up |
| `fixtures/golden/p0a-minimal/*` | P0a golden fixture and DQ negative fixtures | pass |
| `src/hate/*` | P0a local-first CLI implementation | pass |
| `tests/test_p0a.py` | P0a CLI and DQ regression tests | pass |

## 3. Shipyard Stage 監査

| Stage | 期待 | 現状 | 判定 |
|---|---|---|---|
| plan | 正本文書、範囲、Task Seed 粒度が固定される | README / BLUEPRINT / SPECIFICATION / P0A / SCHEMA を参照 | pass |
| dev | worker draft が正本に直接ならず、統合候補として残る | `SPECIFICATION_SHIPYARD_DRAFT.md` を draft として保持 | pass |
| acceptance | QEG / workflow-cookbook / Shipyard / manual-bb の責務境界を検査 | SPEC 30/31/36 と manual-bb gate が存在 | pass |
| integrate | schema / fixture / run evidence が SPEC と一致する | P0a manifest field を修正、Shipyard evidence を 30.1 へ近接 | pass |
| publish | publish approval を HATE が代替しない | `publish_gate_override=false` を明示 | pass |

## 4. 監査所見と処置

| ID | 所見 | 処置 | 状態 |
|---|---|---|---|
| AUD-SHIP-001 | `artifact-manifest.json` fixture が `id` / `size` を使い、schema の `artifact_id` / `size_bytes` と不一致 | fixture を schema / P0A 契約へ修正 | closed |
| AUD-SHIP-002 | Shipyard evidence が仕様 30.1 の `run_id`, `run_attempt`, `commit_sha`, `hate.*` を欠いていた | advisory evidence に required refs を追加 | closed |
| AUD-SHIP-003 | P0a DQ negative fixtures は仕様上必須だが、未追加だった | `dq-01`, `dq-02`, `dq-03`, `dq-08`, `dq-15` fixture と `tests/test_p0a.py` の hard_dq 回帰を追加 | closed |
| AUD-SHIP-004 | `qeg-bundle.json` は P0b 仕様であり、P0a fixture には存在しない | `qeg_bundle_ref=null` とし、P0b follow-up に分離 | closed |
| AUD-SHIP-005 | Shipyard-cp runtime への実API投入は未実施 | local advisory run evidence として扱い、実runtime連携は P1b に分離 | closed |
| AUD-SHIP-006 | 以前の実装ゲートは P0a 着手可否に寄り、フル実装範囲の判定として狭かった | `MANUAL_BB_GATE_FULL_IMPLEMENTATION.md` を追加し、full implementation claim を `no_go` として分離 | closed |
| AUD-SHIP-007 | フル実装までの worker-facing task / artifact / acceptance / no-go trigger が一枚化されていなかった | `SPECIFICATION_SHIPYARD_FULL_IMPLEMENTATION_DRAFT.md` を追加し、P0a〜P3 を Shipyard task packet として整理 | closed |
| AUD-SHIP-008 | 仕様書完成と実装完成が混同される恐れがあった | full implementation spec evidence で `spec_completion_candidate=true`, `implementation_completion_claim=false` を明示 | closed |
| AUD-SHIP-009 | RanD KanoMode audit で P0b QEG export と P1a trust hardening が `no_go` になった | `RAND_KANO_MODE_FULL_IMPLEMENTATION_AUDIT.md` を追加し、RanD verdict を上書きせず implementation blocker として保持 | closed |
| AUD-SHIP-010 | RanD No-Go のうち P0b / P1a は仕様密度不足としても扱える状態だった | P0b / P1a の詳細実装契約と full spec readiness 境界契約を追加 | closed |
| AUD-SHIP-011 | RanD KanoMode readiness audit を再実行し、仕様書 readiness として `overall_assessment=go` を確認した | `RAND_KANO_MODE_FULL_IMPLEMENTATION_READINESS_GO.md` と readiness audit JSON を追加 | closed |
| AUD-SHIP-012 | RanD KanoMode で要件定義品質を監査し、`overall_assessment=conditional_go` を確認した | `RAND_KANO_MODE_REQUIREMENTS_QUALITY_AUDIT.md` を追加し、顧客証跡、KPI baseline、AC圧縮を Go 化条件として分離 | closed |
| AUD-SHIP-013 | RanD KanoMode でアイデア品質を監査し、`overall_assessment=conditional_go` を確認した | `RAND_KANO_MODE_IDEA_QUALITY_AUDIT.md` を追加し、ユーザー実証、市場比較、商用焦点、delighter分離を Go 化条件として分離 | closed |
| AUD-SHIP-014 | P0a golden path が仕様書だけで、実行できる CLI が存在しなかった | Python 標準ライブラリのみの `hate p0a` CLI、JUnit/LCOV正規化、precheck、record、summary、regression test を追加 | closed |
| AUD-SHIP-015 | 仕様書完成条件を requirement-by-requirement で証明する監査表がなかった | `SPECIFICATION_COMPLETION_AUDIT.md` を追加し、`SPECIFICATION.md#36` の全項目を証跡へ写像 | closed |

## 5. 仕様書完成判定

仕様書完成 claim は `go`。

仕様書としては、次を満たすため `SPECIFICATION.md` を正本としてフル実装計画へ進められる。

- HATE / QEG / workflow-cookbook / Shipyard-cp / manual-bb の責務境界が明示されている
- P0a から P3 までの phase contract と acceptance matrix がある
- P0a schema / fixture / run evidence の最小証跡が存在する
- P0a DQ negative fixture と実行回帰が存在する
- Shipyard-cp 接続は advisory evidence に限定され、publish gate override を禁止している
- フル実装までの Shipyard task packet、stage gate、phase acceptance、No-Go trigger が定義されている
- manual-bb full implementation gate が実装完了 claim を No-Go とし、仕様書完成 claim と分離している
- RanD KanoMode audit packet が存在し、overall `no_go` を HATE 側で上書きしていない
- RanD KanoMode の仕様 readiness 再監査に必要な P0b / P1a 詳細契約が存在する
- RanD KanoMode readiness audit が overall `go` で、Go の対象が仕様書 readiness に限定されている
- RanD KanoMode requirements quality audit が overall `conditional_go` で、Go 化条件が顧客証跡、KPI baseline、AC圧縮に限定されている
- `SPECIFICATION_COMPLETION_AUDIT.md` が `SPECIFICATION.md#36` の全 completion gate item を pass として証跡化している

残タスクは仕様書完成を阻害しない P0b 以降の implementation follow-up とする。ただし、フル実装完了 claim は
`MANUAL_BB_GATE_FULL_IMPLEMENTATION.md` の minimum_go_conditions と
`RAND_KANO_MODE_FULL_IMPLEMENTATION_AUDIT.md` の No-Go follow-up を満たすまで禁止する。

つまり、この文書の `go` は仕様書完成に限る。フル実装完了の `no_go` は別スコープであり、
仕様書完成判定を取り消すものではない。
