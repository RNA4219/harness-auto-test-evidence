---
intent_id: INT-HATE-GAP-CLOSURE-ACCEPTANCE-INDEX-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Acceptance Index

This index links workflow-cookbook style acceptance records to the HATE gap
closure ledger. It is intentionally small and machine-checkable.

| Acceptance record | Scope | Gap acceptance IDs |
|---|---|---|
| [AC-20260630-01.md](AC-20260630-01.md) | HATE gap closure UAT readiness and implemented evidence for HATE-GAP-001 through HATE-GAP-026 | AC-HATE-GAP-001, AC-HATE-GAP-002, AC-HATE-GAP-003, AC-HATE-GAP-004, AC-HATE-GAP-005, AC-HATE-GAP-006, AC-HATE-GAP-007, AC-HATE-GAP-008, AC-HATE-GAP-009, AC-HATE-GAP-010, AC-HATE-GAP-011, AC-HATE-GAP-012, AC-HATE-GAP-013, AC-HATE-GAP-014, AC-HATE-GAP-015, AC-HATE-GAP-016, AC-HATE-GAP-017, AC-HATE-GAP-018, AC-HATE-GAP-019, AC-HATE-GAP-020, AC-HATE-GAP-021, AC-HATE-GAP-022, AC-HATE-GAP-023, AC-HATE-GAP-024, AC-HATE-GAP-025, AC-HATE-GAP-026 |
| [HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md](HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md) | Implemented expansion evidence for HATE-GAP-027 through HATE-GAP-060, pending human acceptance | AC-HATE-GAP-027, AC-HATE-GAP-028, AC-HATE-GAP-029, AC-HATE-GAP-030, AC-HATE-GAP-031, AC-HATE-GAP-032, AC-HATE-GAP-033, AC-HATE-GAP-034, AC-HATE-GAP-035, AC-HATE-GAP-036, AC-HATE-GAP-037, AC-HATE-GAP-038, AC-HATE-GAP-039, AC-HATE-GAP-040, AC-HATE-GAP-041, AC-HATE-GAP-042, AC-HATE-GAP-043, AC-HATE-GAP-044, AC-HATE-GAP-045, AC-HATE-GAP-046, AC-HATE-GAP-047, AC-HATE-GAP-048, AC-HATE-GAP-049, AC-HATE-GAP-050, AC-HATE-GAP-051, AC-HATE-GAP-052, AC-HATE-GAP-053, AC-HATE-GAP-054, AC-HATE-GAP-055, AC-HATE-GAP-056, AC-HATE-GAP-057, AC-HATE-GAP-058, AC-HATE-GAP-059, AC-HATE-GAP-060 |
| [FIVE_TOOL_VALIDATION_GATE_HATE_GAP_042_060.md](FIVE_TOOL_VALIDATION_GATE_HATE_GAP_042_060.md) | five-tool-validation-gate evidence for provider matrix, runner coverage, and core analysis expansion | AC-HATE-GAP-042, AC-HATE-GAP-043, AC-HATE-GAP-049, AC-HATE-GAP-050, AC-HATE-GAP-051, AC-HATE-GAP-052, AC-HATE-GAP-053, AC-HATE-GAP-056, AC-HATE-GAP-058, AC-HATE-GAP-059, AC-HATE-GAP-060 |
| [QEG_HARDENING_CYCLE_ACCEPTANCE.md](QEG_HARDENING_CYCLE_ACCEPTANCE.md) | Ten repeated QEG hardening cycles for remaining product-readiness risks | HATE-QEG-CYCLE-001, HATE-QEG-CYCLE-002, HATE-QEG-CYCLE-003, HATE-QEG-CYCLE-004, HATE-QEG-CYCLE-005, HATE-QEG-CYCLE-006, HATE-QEG-CYCLE-007, HATE-QEG-CYCLE-008, HATE-QEG-CYCLE-009, HATE-QEG-CYCLE-010 |

## Generation Policy

- Regenerate this index when an `AC-YYYYMMDD-xx.md` record is added or split.
- A gap cannot be called accepted unless its `AC-HATE-GAP-*` ID is reachable
  from this index and the linked record states the accepted scope.
- This index does not replace `HATE_GAP_CLOSURE_ACCEPTANCE.md`; it bridges
  workflow-cookbook human-readable acceptance records to HATE gap IDs.
