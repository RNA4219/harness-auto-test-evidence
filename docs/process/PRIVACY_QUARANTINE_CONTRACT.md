---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Privacy and Quarantine Contract

## 1. 目的

HATE が扱う trace、screenshot、video、log、coverage、SARIF、report には、
secret、PII、customer data、local path、token、private URL が混入しうる。
この文書は artifact safety、privacy report、quarantine、summary/export 制御の
契約を定義する。

## 2. 原則

- unsafe artifact は public summary / QEG export / external export に出さない
- quarantine は削除ではなく隔離と説明である
- secret / PII / restricted path は diagnostic bundle にも含めない
- redaction が未完了なら `safe_for_summary=false` とする
- artifact safety failure は hidden gap にしない
- HATE は retention / legal hold の最終統制を再実装せず、metadata と refs を出す

## 3. Classification

| Classification | 例 | summary | export | diagnostic |
|---|---|---|---|---|
| public | aggregate count, generic decision | allow | allow | allow |
| internal | repo-relative path, test name | allow with masking | allow | allow with masking |
| confidential | screenshot, trace, customer-like data | deny | conditional | deny raw |
| restricted | secret, token, PII, credential URL | deny | deny | deny |

## 4. Safety Checks

| Check | Required | Failure |
|---|---|---|
| secret scan | yes | quarantine |
| PII heuristic | yes for text / logs | quarantine or redact |
| MIME / extension match | yes | quarantine |
| archive size / entry count limit | yes | quarantine |
| zip bomb / compression ratio | yes | quarantine |
| symlink detection | yes | quarantine |
| path traversal | yes | quarantine |
| external URL allowlist | yes for URL refs | block |
| metadata IP / localhost block | yes for URL refs | block |
| max artifact size | yes | budget warning or quarantine |
| redaction rule version | yes | pending if missing |

## 5. Artifact Manifest Fields

```yaml
artifact_id: string
kind: trace | screenshot | video | log | coverage | static | report | other
path: string
sha256: string
size_bytes: number
classification: public | internal | confidential | restricted
redaction_status: not_required | redacted | pending | failed
redaction_rule_version: string
safe_for_summary: boolean
public_exposure: none | summary | artifact_url | external
retention: object
security_checks:
  secret_scan: pass | fail | skipped
  pii_scan: pass | fail | skipped
  mime_match: pass | fail | skipped
  archive_safety: pass | fail | skipped
  symlink_check: pass | fail | skipped
  path_traversal: pass | fail | skipped
  external_url_policy: pass | fail | skipped
quarantine:
  status: none | quarantined | released
  reason: string
  released_by: string
  released_at: string
```

## 6. Privacy Report

`privacy-report.json` は最低限次を持つ。

```json
{
  "schema_version": "HATE/v1",
  "run_id": "1001",
  "commit_sha": "0123456789abcdef0123456789abcdef01234567",
  "summary": {
    "checked": 0,
    "quarantined": 0,
    "redacted": 0,
    "blocked_from_summary": 0
  },
  "items": []
}
```

## 7. Quarantine Semantics

| Status | 意味 |
|---|---|
| none | quarantine 不要 |
| quarantined | artifact は存在するが summary/export/diagnostic から除外 |
| released | review により安全な参照のみ解放 |

`released` は HATE が compliance approval を出したという意味ではない。
sourceRefs と actor を記録し、上位統制へ委譲する。

## 8. Output Policy

| Output | unsafe artifact の扱い |
|---|---|
| `summary.md` | path / URL / raw detail を出さない |
| `qeg-bundle.json` | unsafe artifact 本体参照を出さず blocked metadata のみ |
| `diagnostic bundle` | raw artifact を含めない |
| external export | connector に送らない |
| `artifact-manifest.json` | quarantine metadata を残す |
| `risk-debt-register.json` | artifact_unsafe debt として追跡可能 |

## 9. Acceptance

- unsafe artifact が public summary / QEG export / diagnostic bundle に漏れない
- quarantine reason と sourceRefs が残る
- redaction rule version が記録される
- skipped safety check は hidden gap にならない
- released artifact は actor / timestamp / reason を持つ
- retention / legal hold の最終統制を HATE が再実装しない
