---
intent_id: INT-HATE-SCALE-PERFORMANCE-REQUIREMENTS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Scale and Performance Requirements

## 1. Purpose

This document defines scale, performance, memory, pagination, sharding, and large-fixture
requirements. It prevents toy implementations from satisfying product-grade claims.

## 2. Scale Targets

| Target ID | Dimension | Product target |
|---|---|---:|
| SCALE-001 | test cases per run | 100,000 |
| SCALE-002 | coverage line/branch records per run | 10,000,000 |
| SCALE-003 | artifact metadata entries per run | 100,000 |
| SCALE-004 | risk/evidence graph nodes | 500,000 |
| SCALE-005 | risk/evidence graph edges | 2,000,000 |
| SCALE-006 | parser failure records | 100,000 |
| SCALE-007 | retained run index | 1,000,000 run attempts |

These are design and fixture targets. Production limits may be lower per edition, but the architecture
must show where limits are enforced and how partial/stale states are represented.

## 3. Performance Budgets

| Operation | Budget |
|---|---:|
| P0a standard PR precheck | P95 <= 5 minutes |
| P0a minimal golden path | <= 30 seconds |
| large JUnit/JSON parse | streaming or bounded memory |
| coverage ingestion 10M records | chunked, bounded memory, progress visible |
| run list API | P95 <= 500 ms for indexed query |
| run detail API | P95 <= 1.5 s excluding cold rebuild |
| evidence graph first render | <= 3 s with aggregation |
| release pack generation | incremental; no full recompute if source hash unchanged |

## 4. Large Fixture Requirements

| Fixture | Purpose | Required checks |
|---|---|---|
| scale-100k-tests | parser, identity, aggregation | deterministic count, bounded memory |
| scale-10m-coverage | coverage chunking | coverage-only not execution evidence |
| scale-100k-artifacts | artifact metadata pagination | no raw restricted paths |
| scale-500k-graph | graph aggregation | no full render requirement |
| scale-sharded-matrix | shard/matrix aggregation | deterministic aggregate identity |
| scale-cache-stale | cache invalidation | stale source hash detected |
| scale-archive-limit | archive safety | expansion stopped deterministically |

## 5. Architecture Requirements

- parsers must stream or chunk large inputs
- store indexes must be append-friendly and queryable by run/risk/evidence/artifact
- dashboard must aggregate or virtualize large lists/graphs
- API must require pagination for large resources
- release pack generation must be incremental and hash-aware
- artifact safety scan must have size/count/time limits
- shard/matrix aggregation must be deterministic
- partial results must be explicit and source-backed

## 6. No-Go

- loading unbounded test/coverage/artifact files into memory
- rendering all graph nodes in dashboard
- returning unpaginated evidence lists
- sorting large result sets only in application memory without index strategy
- using fixture filename ordering as baseline logic
- hiding stale cache behind fresh status
- continuing archive expansion after policy limit

## 7. Evidence Report

`scale-performance-report.json` must include:

```yaml
scale_targets:
  tests: number
  coverage_records: number
  artifact_metadata: number
  graph_nodes: number
  graph_edges: number
budgets:
  operation: string
  target_ms: number
  observed_ms: number | null
  status: pass | fail | not_run
resource_limits:
  max_memory_mb: number
  max_input_bytes: number
  max_archive_entries: number
pagination:
  required: boolean
  tested: boolean
staleness:
  cache_invalidation_tested: boolean
findings: array
```

Product-ready is blocked when the report is missing or any required scale No-Go is present.

