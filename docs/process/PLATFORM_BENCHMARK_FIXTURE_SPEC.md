---
intent_id: INT-HATE-PLATFORM-BENCHMARK-FIXTURE-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Platform Benchmark Fixture Specification

本書は 1000 repo / 100万 finding 級の benchmark fixture 生成仕様である。

## 1. Dataset Classes

| Class | Repo Count | Finding Count | Artifact Metadata | Purpose |
|---|---:|---:|---:|---|
| `bench-small` | 10 | 10,000 | 10,000 | local regression |
| `bench-medium` | 100 | 100,000 | 100,000 | team scale |
| `bench-large` | 1000 | 1,000,000 | 1,000,000 | enterprise readiness |

## 2. Generator Inputs

- seed
- repo count
- suite count per repo
- run count per suite
- finding distribution
- severity distribution
- debt expiry distribution
- artifact safety distribution
- policy drift rate
- scheduler failure rate

Generator output must be deterministic for the same seed.

## 3. Distribution Requirements

Minimum distribution:

- 5% critical findings
- 15% high findings
- 30% medium findings
- 50% low findings
- 10% accepted debt
- 2% expired accepted debt
- 1% unsafe artifact metadata
- 3% external repo holds
- 5% stale cache candidates

## 4. Performance Metrics

Benchmark report records:

- generation time
- store ingest time
- projection rebuild time
- read model query P50/P95/P99
- dashboard view model generation time
- scheduler lease scan time
- artifact metadata query time
- memory high-water mark where available

Budgets must be declared before benchmark execution:

- ingest budget
- projection rebuild budget
- read model P95 budget
- dashboard view model P95 budget
- scheduler lease scan budget
- artifact metadata query budget

Measured baselines must include hardware class, OS, Python version, storage mode,
dataset class, seed, and policy hash.

## 5. Degradation Modes

When budget is exceeded, system must report:

- `degraded_query`
- `partial_projection`
- `scheduler_backpressure`
- `cache_disabled`
- `artifact_metadata_only`

Degradation must never produce pass/readiness claims without scope limitation.

## 6. Required Fixtures

| Fixture | Expected |
|---|---|
| `fixtures/platform/benchmark/small-deterministic/fixture.json` | same seed same counts |
| `fixtures/platform/benchmark/expired-debt-distribution/fixture.json` | expired debt appears |
| `fixtures/platform/benchmark/external-hold-distribution/fixture.json` | external holds separated |
| `fixtures/platform/benchmark/stale-cache-distribution/fixture.json` | stale cache candidates |
| `fixtures/platform/benchmark/degraded-query/fixture.json` | degradation reported |
| `fixtures/platform/benchmark/measured-baseline-metadata/fixture.json` | hardware/policy/seed metadata present |
