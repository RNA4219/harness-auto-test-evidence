---
intent_id: INT-HATE-HOSTED-WORKER-RUNTIME-CONTRACT-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-30
next_review_due: 2026-07-07
---

# Hosted Worker Runtime Contract

This contract closes HATE-GAP-001 for hosted job and worker behavior. It does
not make hosted runtime mandatory for local-first P0/P1 usage.

## 1. Job Model

| Entity | Required fields |
|---|---|
| `job` | job_id, tenant_id, kind, status, idempotency_key, created_at, updated_at |
| `attempt` | attempt_id, job_id, worker_id, lease_token, started_at, heartbeat_at |
| `lease` | lease_token, expires_at, renewal_count, owner_worker_id |
| `retry_policy` | max_attempts, backoff_strategy, retryable_errors, poison_threshold |
| `job_artifact` | artifact_id, job_id, hash, safety_status, retention_class |

Statuses:

```text
queued -> leased -> running -> succeeded
queued -> leased -> running -> retry_wait -> queued
queued -> leased -> running -> failed
queued -> leased -> running -> poison
queued|leased|running -> cancelling -> cancelled
```

## 2. Idempotency

- Mutating job creation requires idempotency key.
- Duplicate idempotency key returns the existing job envelope.
- A worker may not create duplicate canonical bundles for the same job attempt.

## 3. Retry And Poison Rules

| Error class | Retry | Terminal state |
|---|---|---|
| transient_io | yes | failed after max attempts |
| rate_limited | yes, respect retry_after | failed after max attempts |
| schema_invalid_input | no | failed |
| unsafe_artifact | no | succeeded_with_quarantine or failed by profile |
| invariant_violation | no | poison |

Poison messages require audit evidence and cannot be hidden from product
readiness reports.

## 4. Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/runtime/worker/successful-ingest/fixture.json` | job reaches succeeded with bundle hash |
| `fixtures/runtime/worker/retry-then-success/fixture.json` | retry_wait occurs before succeeded |
| `fixtures/runtime/worker/cancel-running/fixture.json` | cancellation preserves partial evidence |
| `fixtures/runtime/worker/poison-message/fixture.json` | poison state and audit event emitted |

## 5. Acceptance

Hosted worker runtime is accepted only when queue lease, retry, cancellation,
poison, idempotency, artifact safety, and audit fixtures pass.
