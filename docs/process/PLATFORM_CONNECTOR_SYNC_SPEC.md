---
intent_id: INT-HATE-PLATFORM-CONNECTOR-SYNC-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Platform Connector Sync Specification

本書は operating record を GitHub、Slack、issue tracker へ同期するための
payload、state、failure handling を定義する。

## 1. Source of Truth

HATE の `operating_event` と `operating_projection` が正本である。
外部 connector は mirror であり、外部状態は canonical event なしに
finding、risk debt、manual review を変更できない。

## 2. Connector Types

| Connector | Direction | Purpose |
|---|---|---|
| GitHub Check | outbound | run/finding summary and annotations |
| GitHub Issue | outbound/inbound-ack | owner work item mirror |
| Slack | outbound | escalation and review notification |
| Generic Tracker | outbound/inbound-ack | issue state mirror |
| Webhook | outbound | automation integration |

## 3. Sync Payload

Required fields:

- `sync_id`
- `operating_record_id`
- `connector_id`
- `external_system`
- `direction`
- `operation`: `create`, `update`, `comment`, `close`, `ack`
- `idempotency_key`
- `payload_hash`
- `redaction_status`
- `sourceRefs`

Payload must include safe summary only. Raw artifact body, secret, PII, and
restricted local paths are never sent.

## 4. State Machine

States:

- `queued`
- `prepared`
- `sent`
- `acknowledged`
- `failed_retryable`
- `failed_terminal`
- `cancelled`

Retry rules:

- retry transport failures with backoff
- do not retry authorization denial blindly
- do not close canonical finding when external close fails
- write `notification_failed` or `tracker_sync_failed` operating event

## 5. Inbound Ack

Inbound ack may attach:

- external url
- external status
- external actor
- external timestamp

Inbound ack cannot:

- resolve risk debt
- decide manual review
- change owner
- change expiry
- hide finding

## 6. Required Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/platform/connectors/github-check-safe-summary/fixture.json` | safe check payload |
| `fixtures/platform/connectors/slack-notification-failed/fixture.json` | retryable failure event |
| `fixtures/platform/connectors/inbound-close-denied/fixture.json` | external close cannot resolve canonical state |
| `fixtures/platform/connectors/idempotent-retry/fixture.json` | duplicate send avoided |
| `fixtures/platform/connectors/redaction-before-send/fixture.json` | unsafe fields removed |
