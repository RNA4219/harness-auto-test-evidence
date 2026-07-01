---
intent_id: INT-HATE-PLATFORM-PLUGIN-SANDBOX-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Platform Plugin Sandbox Specification

本書は detector plugin の実行境界、resource limit、trust enforcement、
failure isolation を定義する。

## 1. Execution Modes

| Mode | Purpose | Allowed In Release |
|---|---|---:|
| `in_process_builtin` | built-in trusted detectors | yes |
| `subprocess_local` | workspace plugin | conditional |
| `containerized` | hosted/enterprise plugin | yes |
| `disabled` | denied plugin | no |

Release/regulated profile は unsigned workspace plugin を実行しない。

## 2. Sandbox Inputs

Plugin receives:

- redacted canonical input bundle
- effective policy subset
- detector-specific config
- temp working directory
- read-only artifact metadata

Plugin does not receive:

- raw unsafe artifact body
- secrets
- unrestricted filesystem path
- network access by default

## 3. Resource Limits

Required controls:

- timeout_ms
- max_output_bytes
- max_input_bytes
- max_memory_mb where platform supports it
- filesystem allowlist
- network mode: `none`, `allowlisted`, `unrestricted-denied-in-release`

## 4. Output Contract

Plugin output must be:

- JSON
- schema versioned
- detector_id scoped
- sourceRefs preserving
- deterministic for identical input/policy

Malformed output creates `plugin_output_invalid` finding.

## 5. Failure Isolation

| Failure | Finding |
|---|---|
| timeout | `plugin_timeout` |
| over output budget | `plugin_output_budget_exceeded` |
| forbidden filesystem access | `plugin_forbidden_filesystem_access` |
| forbidden network access | `plugin_forbidden_network_access` |
| crash | `plugin_execution_failed` |
| trust denied | `plugin_trust_denied` |

Plugin failure cannot crash the platform run unless profile explicitly marks the
detector as required-blocking.

## 6. Required Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/platform/plugin-sandbox/builtin-pass/fixture.json` | built-in detector passes |
| `fixtures/platform/plugin-sandbox/workspace-unsigned-release-denied/fixture.json` | release trust denied |
| `fixtures/platform/plugin-sandbox/output-budget-exceeded/fixture.json` | budget finding |
| `fixtures/platform/plugin-sandbox/network-denied/fixture.json` | network denied finding |
| `fixtures/platform/plugin-sandbox/crash-isolated/fixture.json` | run continues with finding |
