---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Product Error Taxonomy

## 1. 目的

この文書は HATE の user-facing error code、remediation、support diagnostic
bundle の契約を定義する。Enterprise-ready な製品では、失敗を単なる stack trace
やログ断片として出すのではなく、利用者が直せる単位、support が再現できる単位、
監査で説明できる単位へ分類する必要がある。

## 2. 原則

- すべての user-facing failure は stable error code を持つ
- error code は breaking change なしに意味を変えない
- remediation は人間向け summary と machine-readable JSON の両方に出す
- secret / PII / unsafe artifact path を error detail に含めない
- CLI / schema / adapter failure と HATE precheck decision を混同しない
- QEG の Gate policy / waiver / approval を HATE error code で上書きしない

## 3. Error Code Format

```text
HATE-<CATEGORY>-<NNN>
```

| Segment | 例 | 意味 |
|---|---|---|
| CATEGORY | CLI, CFG, SCH, ADP, ART, DQ, AET, QEG, PRV, SEC, EXP, SYS | 分類 |
| NNN | 001 | 分類内の連番 |

例: `HATE-ART-003`, `HATE-SCH-001`, `HATE-DQ-007`

## 4. Categories

| Category | 説明 | 既定 exit code |
|---|---|---:|
| CLI | CLI 引数、command、入出力指定の問題 | 1 |
| CFG | config / profile / env の問題 | 1 |
| SCH | schema validation / version compatibility の問題 | 1 |
| ADP | adapter parse / normalize / capability の問題 | 1 |
| ART | artifact manifest / hash / resolver / safety の問題 | 1 または 2 |
| DQ | evidence eligibility に関わる DQ | 2 |
| AET | AETE scoring / calibration / profile の問題 | 1 または 2 |
| QEG | QEG bundle compatibility / export の問題 | 1 |
| PRV | provenance / SHA / run window / clock skew の問題 | 2 |
| SEC | secret / unsafe artifact / policy violation の問題 | 2 |
| EXP | external export / optional connector の問題 | 0 または 1 |
| SYS | internal failure / resource / IO / timeout の問題 | 1 |

## 5. Core Error Codes

| Code | Severity | 説明 | Remediation |
|---|---|---|---|
| HATE-CLI-001 | error | unknown command | `HATE --help` と command list を確認する |
| HATE-CLI-002 | error | required input path missing | input path と working directory を確認する |
| HATE-CFG-001 | error | profile not found | profile path / name / inheritance を確認する |
| HATE-CFG-002 | error | profile drift detected | `profile simulate` または profile diff を確認する |
| HATE-SCH-001 | error | schema invalid | record_type と required field を確認する |
| HATE-SCH-002 | error | unsupported schema version | migration guide または schema registry を確認する |
| HATE-ADP-001 | error | adapter parse failed | source artifact の形式、encoding、tool version を確認する |
| HATE-ADP-002 | warning | adapter capability missing | capability manifest の unsupported field を確認する |
| HATE-ADP-003 | error | duplicate test identity | canonical_test_id / aliases を確認する |
| HATE-ART-001 | error | artifact referenced but missing | artifact path / resolver / upload step を確認する |
| HATE-ART-002 | error | artifact hash mismatch | artifact の改変、再生成、path 解決を確認する |
| HATE-ART-003 | error | unsafe artifact blocked | privacy report と quarantine reason を確認する |
| HATE-ART-004 | warning | artifact exceeds budget | artifact budget report と retention policy を確認する |
| HATE-DQ-001 | hard_dq | commit SHA missing or mismatched | CI context と input bundle の SHA を揃える |
| HATE-DQ-002 | hard_dq | schema invalid / parse failed | schema validation result を確認する |
| HATE-DQ-003 | hard_dq | artifact hash missing or file missing | manifest と artifact resolver を確認する |
| HATE-DQ-005 | hard_dq | unresolved flakiness over threshold | retry history / baseline / flaky owner を確認する |
| HATE-DQ-007 | hard_dq | high-risk changed path has no execution evidence | test layer または manual 補完要求を追加する |
| HATE-DQ-010 | hard_dq | unresolved high / critical SARIF on changed path | SARIF finding を修正または sourceRefs 付きで説明する |
| HATE-DQ-015 | hard_dq | own-output validation record missing | record generation と output directory を確認する |
| HATE-AET-001 | warning | score is uncalibrated | calibration_status と rubric_version を確認する |
| HATE-AET-002 | error | AETE dimension missing for required profile | profile threshold と adapter capability を確認する |
| HATE-QEG-001 | error | qeg-bundle minimal fixture invalid | QEG mapping と sourceRefs を確認する |
| HATE-QEG-002 | error | QEG export version incompatible | version matrix と migration guide を確認する |
| HATE-PRV-001 | hard_dq | run window mismatch | started_at / finished_at / artifact timestamp を確認する |
| HATE-SEC-001 | hard_dq | secret detected in artifact or summary candidate | artifact を quarantine し redaction rule を更新する |
| HATE-SEC-002 | hard_dq | path traversal or unsafe archive entry | archive extraction policy を確認する |
| HATE-SEC-003 | hard_dq | external URL blocked by safety policy | allowlist / URL classification を確認する |
| HATE-EXP-001 | warning | optional external export failed | local artifact と QEG export は維持し connector 設定を確認する |
| HATE-SYS-001 | error | unexpected internal error | diagnostic bundle を生成して support に渡す |

## 6. Error Record Shape

```json
{
  "schema_version": "HATE/v1",
  "error_code": "HATE-ART-003",
  "severity": "warning|error|hard_dq",
  "category": "ART",
  "message": "unsafe artifact blocked",
  "remediation": "privacy report と quarantine reason を確認する",
  "source_refs": [],
  "safe_for_summary": true,
  "related_dq": ["HATE-DQ-03"],
  "exit_code": 2
}
```

## 7. Summary Policy

人間向け summary には次のみ出す。

- error_code
- severity
- short message
- remediation
- safe source_refs

出してはいけないもの:

- secret / token / PII
- local absolute path の詳細
- unsafe artifact path
- redaction pending / failed の raw detail
- external connector token / URL credential

## 8. Diagnostic Bundle

`HATE doctor --bundle` 相当の diagnostic bundle は、support が再現と初動 triage を
行うための最小情報を持つ。

含めるもの:

- HATE version
- schema registry version
- command and sanitized args
- profile name / profile hash
- adapter registry summary
- capability manifest summary
- DQ summary
- error records
- safe artifact manifest summary
- QEG compatibility summary

含めないもの:

- raw source code
- raw trace / screenshot / video
- secret / PII / unsafe artifact path
- customer private URLs
- full environment variables

## 9. Acceptance

- user-facing failure の 100% が stable error code を持つ
- error code の 100% が remediation を持つ
- public summary に unsafe detail が出ない
- diagnostic bundle が secret / PII / unsafe artifact を含まない
- optional external export failure は local-first precheck と QEG export を壊さない
- error taxonomy の変更は migration guide または release note に記録される
