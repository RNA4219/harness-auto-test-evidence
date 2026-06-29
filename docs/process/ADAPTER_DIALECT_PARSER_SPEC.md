---
intent_id: INT-HATE-ADAPTER-DIALECT-PARSER-SPEC-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# Adapter Dialect Parser Specification

## 1. Purpose

This document defines parser dialect requirements for HATE adapters. A supported adapter must
include parser logic, dialect fixtures, malformed/partial cases, capability manifest, and
conformance results.

## 2. Dialect Matrix

| Adapter family | Dialects | Required cases |
|---|---|---|
| JUnit | Surefire, Gradle, pytest, Jest, Vitest, Playwright, Go junit | pass, fail, error, skipped, parameterized, malformed |
| pytest JSON | pytest-json-report, rerunfailures, xfail/xpass markers | json-only, junit+json merge, conflict, missing path |
| Jest JSON | nested suite, snapshot failure, todo, focused tests | snapshot-only, todo, malformed |
| Vitest JSON | browser/node env, retry, flaky, focused tests | node/browser matrix, malformed |
| Playwright | JSON, JUnit, trace attachments, screenshot/video/log | safe, secret, pii, missing, large |
| Coverage | LCOV, Cobertura, JaCoCo, coverage.py JSON/XML contexts | branch, context, windows path, partial, malformed |
| SARIF | SARIF 2.1.0, CodeQL-like, Sonar-like import | high/critical changed path, suppression, malformed |
| Pact | verification JSON, can-i-deploy summary | pass, failed required contract, version mismatch |
| Stryker | mutation report | killed, survived, timeout, no coverage, malformed |

## 3. Parser Output Requirements

Each parser emits:

- normalized records
- sourceRefs
- parser diagnostics
- capability report
- unsupported dialect warnings
- profile-aware failure impact

## 4. Failure Classes

| Class | Meaning | Required behavior |
|---|---|---|
| required_missing | required input absent | DQ or CLI failure |
| malformed_required | required input parse failure | DQ or CLI failure |
| malformed_optional | optional input parse failure | parserFailures visible |
| unsupported_dialect | dialect detected but not supported | doctor finding |
| partial | parse succeeded with missing optional fields | soft gap/warning |
| unsafe_artifact | artifact unsafe | quarantine/exclusion |

## 5. Conformance Requirement

Adapter conformance passes only when:

- all required dialect fixtures run
- malformed fixtures produce expected failure class
- capability manifest matches actual parser behavior
- sourceRefs are present
- profile impact is deterministic
- no fixture-name branch exists in production code

