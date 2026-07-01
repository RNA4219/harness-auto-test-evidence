---
intent_id: INT-HATE-QEG-HARDENING-CYCLES-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-02
next_review_due: 2026-07-09
---

# QEG Hardening Cycles Requirements

この仕様は、足りない可能性を10回の検証サイクルへ落とし、各サイクルを
RanD -> Code-to-gate -> HATE -> manual-bb -> QEG の順に閉じるための
machine-checkable contract である。

## Cycle Contract

各 cycle は次を満たすときだけ `go` になる。

- `missing_possibility` が明示されている
- requirement/spec/implementation/test/sourceRef がある
- RanD、Code-to-gate、HATE、manual-bb、QEG がすべて `ran`
- manual-bb brief と P0 case があり、open blocker がない
- QEG package の validate/import が `pass`
- QEG gate が `go`
- release candidate pack が `ready` で blocker がない
- HATE は QEG final approval を主張しない

## Ten Required Cycles

| Cycle | Requirement | Missing possibility | Go evidence |
|---|---|---|---|
| Cycle 1 | FR-CYCLE-001 | real repository false positive resistance | QEG package go plus no manual blocker |
| Cycle 2 | FR-CYCLE-002 | external artifact availability and path portability | QEG package go plus portable sourceRefs |
| Cycle 3 | FR-CYCLE-003 | manual oracle gap closure | manual-bb P0 cases and QEG record |
| Cycle 4 | FR-CYCLE-004 | flaky and environment drift separation | HATE evidence and QEG go |
| Cycle 5 | FR-CYCLE-005 | adapter raw-to-normalized loss regression | adapter diff evidence and QEG go |
| Cycle 6 | FR-CYCLE-006 | privacy and artifact quarantine leak resistance | safe evidence room and QEG go |
| Cycle 7 | FR-CYCLE-007 | schema registry and version migration drift | schema validation and QEG go |
| Cycle 8 | FR-CYCLE-008 | performance timeout and large corpus stability | timeout-safe run evidence and QEG go |
| Cycle 9 | FR-CYCLE-009 | report explainability and audience consistency | shared sourceRefs and QEG go |
| Cycle 10 | FR-CYCLE-010 | end-to-end release-pack reproducibility | deterministic release pack and QEG go |

## Implementation Contract

- Runtime: `src/hate/validation_cycles.py`
- Schema: `schemas/HATE/v1/validation-cycle-report.schema.json`
- Fixture: `fixtures/validation-cycles/ten-cycle-go/fixture.json`
- Tests: `tests/test_validation_cycles.py`
- CLI: `hate validation cycles --fixture ... --out ...`

## No-Go

- QEG が `go` でない cycle を `go` にしない
- external QEG approval を HATE が claimed にしない
- manual-bb open blocker を waiver 扱いしない
- 10 cycle 未満を完了扱いしない
