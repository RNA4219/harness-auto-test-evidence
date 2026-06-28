---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# P0a Golden Path Contract

## 1. 目的

P0a golden path は、HATE が enterprise-ready なプロダクト水準へ進むための最小実行契約である。
この契約は「最小入力から、同一の正規化 artifact、precheck decision、record を
再現可能に生成できる」ことを証明する。

P0a は hosted service、QEG runtime、Playwright artifact、SARIF、SSO、RBAC、
dashboard、外部 SaaS に依存してはならない。

## 2. Golden Fixture Tree

実装時は次の fixture tree を正本にする。

```text
fixtures/golden/p0a-minimal/
  input/
    github-context.json
    junit.xml
    lcov.info
    artifacts/
      README.txt
  expected/
    HATE-run.json
    HATE-test-results.ndjson
    HATE-coverage.ndjson
    artifact-manifest.json
    precheck-decision.json
    record.json
    summary.md
```

`input/` と `expected/` は docs、schema、unit tests、integration tests、
Quickstart が同じものを参照する。サンプル用とテスト用で別々の golden input を
作らない。

## 3. Required Inputs

| Input | 必須 | 役割 |
|---|---|---|
| `github-context.json` | yes | run_id、run_attempt、commit_sha、workflow、job、started_at、finished_at |
| `junit.xml` | yes | canonical test result の最小入力 |
| `lcov.info` | yes | canonical coverage slice の最小入力 |
| `artifacts/README.txt` | optional | artifact manifest の no-op fixture |

### 3.1 GitHub Context Minimum

```json
{
  "repository": "RNA4219/sample",
  "workflow": "ci.yml",
  "job": "test",
  "run_id": "1001",
  "run_attempt": 1,
  "commit_sha": "0123456789abcdef0123456789abcdef01234567",
  "base_sha": "abcdefabcdefabcdefabcdefabcdefabcdefabcd",
  "started_at": "2026-06-28T00:00:00Z",
  "finished_at": "2026-06-28T00:01:00Z",
  "event_name": "pull_request"
}
```

## 4. Required Outputs

| Output | 必須 | 判定 |
|---|---|---|
| `HATE-run.json` | yes | common envelope と CI provenance を持つ |
| `HATE-test-results.ndjson` | yes | 1 行以上の `test_result` record を持つ |
| `HATE-coverage.ndjson` | yes | 1 行以上の `coverage_slice` record を持つ |
| `artifact-manifest.json` | yes | artifact がない場合でも empty manifest を出す |
| `precheck-decision.json` | yes | `eligible` / `conditional` / `ineligible` / `hard_dq` の decision を持つ |
| `record.json` | yes | own-output validation record を持つ |
| `summary.md` | yes | public-safe summary を持つ |
| `gate-decision.json` | optional | 互換 alias。新規実装では不要 |

## 5. Decision Contract

`precheck-decision.json` は HATE precheck の出力であり、release Gate 正本ではない。

| decision | 意味 | exit code |
|---|---|---:|
| `eligible` | QEG optional evidence として export 可能 | 0 |
| `conditional` | export は可能だが soft gap がある | 0 |
| `ineligible` | hard DQ ではないが evidence として採用不可 | 2 |
| `hard_dq` | HATE-DQ により run / artifact / evidence が失格 | 2 |

CLI / schema / adapter failure は decision ではなく実行失敗として exit code 1 にする。

## 6. Common Envelope Contract

P0a の全 JSON / NDJSON record は、次の field を必須にする。

```yaml
schema_version: HATE/v1
record_type: string
record_id: string
run_id: string
run_attempt: number
commit_sha: string
created_at: ISO-8601 timestamp
source_tool: string
source_version: string
sha256: string
redaction_status: not_required | redacted | pending | failed
payload: object
```

Unknown field は P0a では許容するが、summary には出さない。schema registry 実装後は
`additionalProperties` policy を record_type ごとに固定する。

## 7. P0a DQ Coverage

Golden path では最低限、次の DQ fixture を持つ。

| Fixture | Trigger | Expected |
|---|---|---|
| `dq-01-sha-missing` | commit_sha 欠落 | `hard_dq`, exit 2 |
| `dq-02-junit-malformed` | JUnit parse failure | adapter failure または `hard_dq` |
| `dq-03-artifact-missing` | manifest ref の実体欠落 | `hard_dq`, exit 2 |
| `dq-08-coverage-only` | coverage はあるが test result なし | `hard_dq`, exit 2 |
| `dq-15-record-missing` | record 生成不能 | `hard_dq`, exit 2 |

P0a では HATE-DQ-05 / 07 / 10 は入力不足により完全検証しなくてよいが、
未対応であることを `doctor-report.json` または summary に hidden gap として出さない。

## 8. Artifact Manifest Contract

artifact が存在しない場合でも `artifact-manifest.json` は生成する。

```json
{
  "schema_version": "HATE/v1",
  "run_id": "1001",
  "run_attempt": 1,
  "commit_sha": "0123456789abcdef0123456789abcdef01234567",
  "artifacts": []
}
```

artifact が存在する場合は最低限、次を持つ。

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
security_checks: object
```

`security_checks` は secret scan、MIME / 拡張子整合、archive 展開制限、
symlink / path traversal、外部 URL 参照の結果を持つ。

## 9. Summary Contract

`summary.md` は public-safe でなければならない。

含めるもの:

- run_id、run_attempt、commit_sha の短縮表示
- test result count
- coverage file count
- decision
- DQ summary
- generated artifact names

含めないもの:

- `safe_for_summary=false` の artifact path
- secret / token / PII / restricted path
- redaction pending / failed の artifact detail
- local absolute path の詳細

## 10. Quickstart Acceptance

P0a Quickstart は次の条件を満たす。

- 新規ユーザーが 5 分以内に golden fixture を実行できる
- 生成結果と `expected/` の差分を説明できる
- 失敗時に stable error code と remediation が出る
- 外部 SaaS、ネットワーク、QEG runtime、SSO、dashboard が不要
- Windows / Linux の path 差を summary に漏らさない

## 11. Product Readiness Link

P0a golden path は `ENTERPRISE_PRODUCT_REQUIREMENTS.md` の PRG-0 に対応する。

PRG-0 を満たすには、次の evidence が必要である。

- golden fixture input / expected が存在する
- schema validation が通る
- precheck decision が再現可能
- public-safe summary が生成される
- `record.json` が生成される
- `git diff --check` 相当で文書と fixture に空白エラーがない
