---
intent_id: INT-HATE-GITHUB-INTEGRATION-CONTRACT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# GitHub Integration Contract

This contract closes HATE-GAP-005 by separating GitHub Action, GitHub App, and
local CLI responsibilities.

## 1. Responsibility Split

| Surface | Owns | Must not own |
|---|---|---|
| GitHub Action | collecting CI artifacts, running HATE CLI, uploading safe outputs | org policy mutation, release approval |
| GitHub App | check-run annotations, PR comments, permission-scoped reads | raw artifact parsing without HATE safety |
| HATE CLI | normalization, decisions, local summaries | GitHub token storage |
| Hosted API | durable read model and admin policy | QEG verdict override |

## 2. Permissions

| Permission | Required for |
|---|---|
| `checks:write` | check-run summary and annotations |
| `pull-requests:read` | changed files and PR metadata |
| `actions:read` | workflow run metadata |
| `contents:read` | sourceRefs and config |
| `issues:write` | optional PR comment, if enabled |

No-Go:

- broad repository administration permission for normal PR loop
- posting unsafe artifact paths in annotations
- rerun behavior that changes canonical evidence without a new run ID

## 3. Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/github/pr-check-success/fixture.json` | annotations point to safe sourceRefs |
| `fixtures/github/permission-denied/fixture.json` | structured authz error |
| `fixtures/github/rerun-preserves-run-id-link/fixture.json` | rerun links previous evidence |
| `fixtures/github/unsafe-artifact-redacted/fixture.json` | PR surface redacts unsafe data |

## 4. Acceptance

GitHub integration is accepted when Action, App, and CLI responsibilities are
separately tested and no GitHub surface can bypass HATE artifact safety.
