---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Runbook

## 0. 準備

- 対象リポジトリ: `harness-auto-test-evidence`
- 実行環境: local / CI を想定
- 前提: `manual-bb-test-harness` / `code-to-gate` / `quality-evidence-graph` 参照可

## 1. 実装フロー（最短）

1. `BLUEPRINT.md` で In/Out と I/O を固定
2. `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md` で仕様不足が閉じていることを確認
3. `IMPLEMENTATION_TASK_BREAKDOWN.md` の順番で Task を実装
4. `IMPLEMENTATION_ROADMAP_CHECKLIST.md` で現在の milestone / next sprint を確認
5. 各 Task ごとに `record.json` 互換の検証メモを残す
6. `EVALUATION.md` の受入項目を満たして完了判定

`TASK.codex.md` は初期 seed として参照する。現在の実装粒度、affected paths、
acceptance、Done 条件は `IMPLEMENTATION_TASK_BREAKDOWN.md` を優先する。

## 2. ローカル実行（準備）

- リポジトリの状態確認（文書整合含む）
- CI 連携の dry run 設定（GitHub metadata mock）
- テスト素材（JUnit/LCOV/SARIF/trace）1セットを用意
- RanD 接続を確認する場合は `requirements_audit_packet.json` の fixture を用意
- shipyard-cp 接続を確認する場合は `WorkerResult` / `RunSystemPacket` の fixture を用意
- workflow-cookbook 接続を確認する場合は Task Seed / Acceptance / Evidence /
  docs stale / Birdseye map の fixture を用意
- Enterprise product readiness を確認する場合は `ENTERPRISE_PRODUCT_REQUIREMENTS.md` と
  PRG-0..PRG-6 の product-readiness fixture を用意
- Enterprise domain model を確認する場合は `ENTERPRISE_DOMAIN_MODEL.md` の
  scope / role / retention / audit event 契約を確認する
- user-facing failure を確認する場合は `PRODUCT_ERROR_TAXONOMY.md` の
  error code / remediation / diagnostic bundle 契約を確認する
- schema 互換性を確認する場合は `SCHEMA_REGISTRY_CONTRACT.md` の
  field policy / fixture matrix / version policy を確認する
- adapter 追加を確認する場合は `ADAPTER_SDK_CONTRACT.md` の manifest /
  required interface / conformance report を確認する
- risk debt を確認する場合は `RISK_DEBT_REGISTER.md` の status / aging /
  owner / sourceRefs / recommended_actions を確認する
- privacy / quarantine を確認する場合は `PRIVACY_QUARANTINE_CONTRACT.md` の
  classification / safety check / output policy を確認する
- hosted read model / API を確認する場合は `HOSTED_READ_MODEL_API.md` の
  source artifact / RBAC / consistency rule を確認する
- release / migration を確認する場合は `RELEASE_MIGRATION_POLICY.md` の
  release gates / migration artifacts / rollback policy を確認する
- packaging / entitlement を確認する場合は `PACKAGING_ENTITLEMENT_CONTRACT.md` の
  edition / entitlement / usage meter / over-limit policy を確認する
- customer-facing docs を確認する場合は `CUSTOMER_DOCUMENTATION_CONTRACT.md` の
  required docs / source_contracts / freshness / verification を確認する
- SLO / incident response を確認する場合は `SLO_INCIDENT_RESPONSE_CONTRACT.md` の
  severity / incident class / status communication / postmortem 契約を確認する
- customer success / adoption を確認する場合は `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` の
  adoption stage / success plan / adoption health / renewal readiness を確認する
- security review / trust を確認する場合は `SECURITY_REVIEW_TRUST_CONTRACT.md` の
  trust packet / control mapping / vulnerability handling / freshness を確認する
- product telemetry / analytics を確認する場合は `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` の
  telemetry mode / allowed signal / prohibited signal / retention を確認する
- data residency / deployment を確認する場合は `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` の
  deployment mode / residency profile / data class routing / recovery を確認する
- product governance / roadmap を確認する場合は `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` の
  roadmap item / decision record / customer request / deprecation decision を確認する
- accessibility / localization を確認する場合は `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` の
  accessibility target / message catalog / locale fallback / stable identifier を確認する
- legal / commercial contracting を確認する場合は `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` の
  commitment register / procurement response / contract exception / commercial risk を確認する
- audit fixture / assurance を確認する場合は `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` の
  audit fixture / assurance pack / evidence room / audit finding を確認する
- requirements portfolio を確認する場合は `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` の
  tier / stage / WIP / dependency / portfolio health を確認する
- P0a を確認する場合は `P0A_GOLDEN_PATH.md` と
  `fixtures/golden/p0a-minimal` の input / expected 契約を用意

## 2.1 実リポジトリ評価 roster

実リポジトリ耐性確認は `hate real-repo run` で roster 化して実行する。timeout は
証跡であり、無言の失敗として扱わない。

Roster 例:

```json
{
  "source_version": "real-repo-local",
  "repositories": [
    {
      "repo_id": "agent-gatefield",
      "repo_class": "small",
      "path": "C:/Users/ryo-n/Codex_dev/agent-gatefield",
      "command": ["uv", "run", "pytest", "-q"],
      "subset": false
    }
  ]
}
```

`timeout_ms` を省略した場合は `repo_class` から既定値を決める。

| repo_class | default timeout |
| --- | ---: |
| small | 900000 ms |
| medium | 1800000 ms |
| large | 2700000 ms |
| xlarge | 3600000 ms |

`timeout_ms` を明示した場合は `repo_class` より優先する。`code-to-gate` のように
serial full-suite が 15 分を超える repo は `repo_class=large` 以上、または明示
timeout を roster に残す。

`hate real-repo run` は親 HATE プロセスの Python 仮想環境を評価対象 repo に漏らさない。
そのため、roster の command は対象 repo 単体で成立する依存同期を含める。例えば
optional dev dependencies が必要な Python repo は `["uv", "run", "--extra", "dev",
"pytest", "-q"]` のように書く。

実行例:

```powershell
uv run python -m hate real-repo run `
  --roster C:\tmp\hate-real-repo-roster.json `
  --out C:\tmp\hate-real-repo-eval `
  --source-version real-repo-local
```

生成物:

- `real-repo-evaluation-run-report.json`
- `real-repo-<repo_id>.json`
- `real-repo-run-history.jsonl`

履歴 store へ保存:

```powershell
uv run python -m hate real-repo history-ingest `
  --history C:\tmp\hate-real-repo-eval\real-repo-run-history.jsonl `
  --store C:\tmp\hate-real-repo-store
```

履歴 query:

```powershell
uv run python -m hate real-repo history-query `
  --store C:\tmp\hate-real-repo-store `
  --repo-id agent-gatefield `
  --suite-id unit `
  --status hold `
  --since 2026-07-01T00:00:00Z
```

`history-ingest` は append-only の `run_history.jsonl` と軽量 projection の
`history-index.json` を更新する。`history-query` は repo、suite、source version、
status、started_at の期間で絞り込み、`real-repo-history-query-report` を返す。

Roster v2:

- `record_type: real-repo-roster-v2` は `repositories[].suites[]` を使い、
  repo と suite を分離して管理する
- repository は `ownership_scope` (`owned`, `external`, `third_party_sample`) と
  `repo_class` (`small`, `medium`, `large`, `xlarge`, `monorepo`) を必須にする
- suite は `suite_id`, `suite_kind`, `command`, `timeout_profile`, `subset` を必須にする
- v2 run は `run_id`, `roster_hash`, `policy_hash`,
  `environment_fingerprint`, `started_at`, `finished_at` を report と history に残す
- 同一 repo に複数 suite がある場合、report は
  `real-repo-<repo_id>-<suite_id>.json` として衝突を避ける
- `ownership_scope=external` の hold は `external_hold` と
  `real_repo_external_hold_detected` に分離し、HATE 実装失敗として扱わない

Agent_tools 正本 repo の一括評価は `REAL_REPO_EVALUATION.md` と
`real-repo-rosters/agent-tools-full.json` を参照する。

判定:

- command exit code が非0なら `real_repo_command_failed` として hold
- timeout は `real_repo_timeout_recorded` として hold
  - report の `current.timeout_cleanup` に `timeout_reason`,
    `cleanup_attempted`, `cleanup_method`, `cleanup_completed` を残す
- subset 実行は `subset_label` が必須で、full-suite readiness の証明には使わない
- baseline より current decision が弱い場合は `real_repo_regression_detected`
- baseline は `real-repo-baseline-event` の append-only event から
  `real-repo-baseline-governance-report` にreduceして使う。`proposed`,
  `expired`, `revoked`, `superseded` の baseline は regression comparison に使えない。
  `external` baseline は外部repo証跡であり、HATE実装readinessの証明にしない。
- score は `real-repo-score-report` に分離し、`score_breakdown` と
  `decision_basis` なしでは出さない。score は release approval ではない。
- command excerpt は `current.output_safety` の redaction metadata と一緒に保存する。
  read model 用 excerpt に secret、PII、private absolute path、ANSI/control
  character を残さない。raw output が必要な場合は quarantine 前提にする。
- runner summary は `runner_dialects` parser を通し、pytest/vitest/bun の
  aggregate count と dialect を `current.runner_dialect` /
  `current.runner_parser` に残す。非summaryの error/noise 行は
  `ignored_noise` として扱い、record count に混ぜない。

## 2.2 Operations operating model

Phase B の finding / risk debt / manual review は `operating-event-record`
を append-only 正本とし、`operating-projection-report` へreduceする。

- `risk_debt_accepted` は owner、expiry、decision basis を必要とする
- `risk_debt_resolved` は resolving evidence を必要とする
- `record_superseded` は superseding record id を必要とする
- `manual_review_decided` は required decision と evidence refs を必要とする
- inbound tracker close は canonical record を解決できず、mirror event として保持する
- `notification_failed` は finding を閉じず、operating finding として残す
- retention / legal hold / projection rebuild event は current projection に保持する
- `verify_event_stream=true` の projection rebuild は sequence 順に sort し、
  event gap と previous/event hash continuity を hold finding にする
- sourceRefs と evidence_refs は lifecycle event をまたいで保持する

最小確認:

```powershell
uv run pytest tests/test_operating_model.py -q
```

## 2.3 Platform connector sync

Connector sync は operating record の mirror payload であり、外部 tracker /
Slack / GitHub の状態を正本にしない。

- outbound payload は safe summary と `payload_hash`、`idempotency_key` を持つ
- raw artifact、secret、PII、private path は connector payload に出さない
- retry duplicate は同一 idempotency key + payload hash なら再送せず skip する
- inbound ack は external status を添付できるが、owner、expiry、status、manual
  review decision を変更できない
- transport failure は `notification_failed` または `tracker_sync_failed`
  operating event として残す

最小確認:

```powershell
uv run pytest tests/test_platform_connector_sync.py -q
```

## 2.4 Platform dashboard/read model projection

Dashboard は canonical read model consumer であり、readiness を再計算しない。

- Findings Queue は `operating-projection-report.records` から owner、due_date、
  severity、sourceRefs を表示する
- Risk Debt Board は risk debt lifecycle、expiry、evidence refs、decision basis を表示する
- Manual Review Queue は operating manual review の required decision と blocking を表示する
- Connector Sync view は safe summary と hash/idempotency だけを表示し、raw payload body を描画しない
- API read model は `operating_records` と `connector_sync_payloads` を投影し、
  operating/connector findings を doctor findings に混ぜる

最小確認:

```powershell
uv run pytest tests/test_platform_dashboard_views.py tests/test_api_read_model.py -q
```

## 2.5 Platform policy config

正本: `PLATFORM_POLICY_CONFIG_SPEC.md`。確認: `uv run pytest tests/test_platform_policy_config.py -q`

## 2.6 Platform plugin sandbox

正本: `PLATFORM_PLUGIN_SANDBOX_SPEC.md`。確認: `uv run pytest tests/test_platform_plugin_sandbox.py -q`

## 2.7 Platform RBAC matrix

正本: `PLATFORM_RBAC_MATRIX_SPEC.md`。確認: `uv run pytest tests/test_platform_rbac.py -q`

## 2.8 Platform store schema

正本: `PLATFORM_STORE_SCHEMA_SPEC.md`。確認: `uv run pytest tests/test_platform_store_schema.py -q`

## 2.9 Platform dashboard wireframe

正本: `PLATFORM_DASHBOARD_WIREFRAME_SPEC.md`。確認: `uv run pytest tests/test_platform_dashboard_wireframe.py -q`

## 2.10 Platform benchmark fixture

正本: `PLATFORM_BENCHMARK_FIXTURE_SPEC.md`。確認: `uv run pytest tests/test_platform_benchmark.py -q`

## 2.11 Release candidate pack validator

正本: `RELEASE_CANDIDATE_PACK_VALIDATOR_SPEC.md`。確認: `uv run pytest tests/test_release_candidate_pack_validator_spec.py -q`

## 3. ローカル実行（P0a 実装）

P0a は Python 標準ライブラリのみで動く local-first CLI として実装する。

- テスト:
  - `uv run pytest`
- P0a golden path:
  - `uv run python -m hate p0a --input fixtures/golden/p0a-minimal/input --out C:\tmp\hate-p0a-check --source-version dev --fixture-path-prefix fixtures/golden/p0a-minimal/input`
- P0a DQ fixtures:
  - `fixtures/golden/p0a-minimal/dq-01-sha-missing`
  - `fixtures/golden/p0a-minimal/dq-02-junit-malformed`
  - `fixtures/golden/p0a-minimal/dq-03-artifact-missing`
  - `dq-control.json` による HATE-DQ-005 / HATE-DQ-007 / HATE-DQ-010 の fixture control
  - `fixtures/golden/p0a-minimal/dq-08-coverage-only`
  - `fixtures/golden/p0a-minimal/dq-15-record-missing`
- P0a generic CI context adapter:
  - `github-context.json` がない入力でも `ci-context.json` または `generic-ci-context.json` を run context として使える
  - provider は `generic-ci` に正規化し、`HATE-run.json.payload.ci.provider` に残す
  - `uv run python -m hate p0a --input fixtures/adapters/ci/generic/input --out C:\tmp\hate-generic-ci-check --source-version generic-ci-test`
  - `generic-ci-context.json` alias: `fixtures/adapters/ci/generic/generic-file-name`
  - required field 欠落は input error: `fixtures/adapters/ci/generic/missing-required`
  - `record.json.payload.source_refs` は実際に読んだ context file を参照し、GitHub context を捏造しない
- P0a pytest adapter (no junit.xml):
  - pytest-report.json alone is eligible if it produces test results
  - `uv run python -m hate p0a --input fixtures/adapters/test-results/pytest/no-junit --out C:\tmp\hate-pytest-check --source-version pytest-test`
  - flaky / retry_index attributes preserved in HATE-test-results.ndjson
- P0a vitest adapter (no junit.xml):
  - vitest-report.json alone is eligible if it produces test results
  - `uv run python -m hate p0a --input fixtures/adapters/test-results/vitest/no-junit --out C:\tmp\hate-vitest-check --source-version vitest-test`
  - flaky attribute preserved in HATE-test-results.ndjson
- P0a jest adapter (no junit.xml):
  - jest-report.json alone is eligible if it produces test results
  - `uv run python -m hate p0a --input fixtures/adapters/test-results/jest/no-junit --out C:\tmp\hate-jest-check --source-version jest-test`
  - failure_type: snapshot_mismatch preserved in HATE-test-results.ndjson
- P0a coverage.py adapter:
  - coverage.json with show_contexts=true is eligible
  - contexts must be array of objects with test_id field
  - `uv run python -m hate p0a --input fixtures/adapters/coveragepy/input --out C:\tmp\hate-coveragepy-check --source-version coveragepy-test`
  - show_contexts=false is hard DQ (HATE-DQ-002): `fixtures/adapters/coveragepy/missing-context`
  - partial contexts (show_contexts=true, some lines missing context) is eligible: `fixtures/adapters/coveragepy/partial`
- P0a Cobertura adapter:
  - `uv run python -m hate p0a --input fixtures/adapters/coverage/cobertura/input --out C:\tmp\hate-cobertura-check --source-version cobertura-test`
  - `filename` がない class は package/name から stable POSIX path に補完する
  - partial coverage は parseable な line が残っていれば eligible: `fixtures/adapters/coverage/cobertura/partial`
  - malformed XML は hard DQ (HATE-DQ-002): `fixtures/adapters/coverage/cobertura/malformed`
  - Windows absolute path は public output で workspace-relative POSIX path に正規化する: `fixtures/adapters/coverage/cobertura/windows-path`
- P0a JaCoCo adapter:
  - `uv run python -m hate p0a --input fixtures/adapters/coverage/jacoco/input --out C:\tmp\hate-jacoco-check --source-version jacoco-test`
  - package/sourcefile から workspace-relative POSIX path を生成する
  - partial coverage は parseable な sourcefile が残っていれば eligible: `fixtures/adapters/coverage/jacoco/partial`
  - malformed XML は hard DQ (HATE-DQ-002): `fixtures/adapters/coverage/jacoco/malformed`
  - Windows absolute path は public output で workspace-relative POSIX path に正規化する: `fixtures/adapters/coverage/jacoco/windows-path`
- P0a artifact safety engine:
  - safe artifact: `uv run python -m hate p0a --input fixtures/adapters/artifacts/safe --out C:\tmp\hate-artifact-safe --source-version artifact-test`
  - secret artifact: `uv run python -m hate p0a --input fixtures/adapters/artifacts/secret --out C:\tmp\hate-artifact-secret --source-version artifact-test`
  - external URL ref: `uv run python -m hate p0a --input fixtures/adapters/artifacts/external-url --out C:\tmp\hate-artifact-url --source-version artifact-test`
  - path traversal ref: `uv run python -m hate p0a --input fixtures/adapters/artifacts/path-traversal --out C:\tmp\hate-artifact-traversal --source-version artifact-test`
  - symlink ref: `uv run python -m hate p0a --input fixtures/adapters/artifacts/symlink --out C:\tmp\hate-artifact-symlink --source-version artifact-test`
  - archive artifact: `uv run python -m hate p0a --input fixtures/adapters/artifacts/archive --out C:\tmp\hate-artifact-archive --source-version artifact-test`
  - `artifact-manifest.json` は `security_checks` を安定出力する
  - unsafe artifact は `safe_for_summary=false`, `public_exposure=none`
  - `quarantine-report.json` は P0a で生成し、理由を `secret`, `external_url`, `path_traversal`, `symlink`, `unsafe_archive` などで分類する
  - summary は secret value、external URL、path traversal raw path を出さない
  - P0b は unsafe required artifact を `excludedArtifacts` と `evidence-map.gaps.unsafe_artifacts` に残す
  - HATE-PG-005A artifact safety/secret quarantine detector:
    - 6 detectors: secret_detected, pii_detected, unsafe_path_detected, external_url_detected, archive_or_binary_risk, quarantine_required
    - secret_detected: token/API key/private key/password detection with confidence scoring
    - pii_detected: email/phone/address/user id/name detection with redaction hints
    - unsafe_path_detected: absolute path, home dir (~), Windows drive (C:\), traversal (../), temp/private paths
    - external_url_detected: external URL, webhook, signed URL, cloud storage (s3://, gs://)
    - archive_or_binary_risk: archive without manifest (>50MB or nested), binary blob, base64 opaque payload (>4KB decoded)
    - quarantine_required: unsafe artifact quarantine decision with status/reason/redaction_hint/sourceRef
    - allowlist_ref context: test_fixture, synthetic_pii, example_value, placeholder, documentation markers exempt fake/test secrets
    - Profile effects: default soft_gap, strict hold, release hard_dq for secret/PII/path/URL risks
    - Classification: public, internal, confidential, restricted levels
    - No-Go criteria: secret/PII/path/URL warning-only pass, quarantine_required with readiness pass, allowlist_ref-less fake secret exemption, missing redaction_hint/sourceRef, 004C workspace contamination
    - fixture path: `fixtures/security/artifact-safety/` contains 12 canonical fixtures
    - test: `uv run pytest tests/test_artifact_safety.py`
  - HATE-PG-005B redaction and summary/export safety filter:
    - 3 modules: redaction.py, export_filter.py, summary_filter.py
    - redaction filter: Remove secrets/PII/restricted paths/private URLs with [REDACTED_*] markers, preserve sourceRef/traceability, non-reversible proof hash
    - export filter: Exclude quarantined artifacts from external/support export, keep safe metadata, failed redaction = hold/hard_dq
    - summary filter: Display-only safety, NEVER change readiness verdicts, control per export surface (dashboard/support/public/internal)
    - Classification: public (allow all), internal (mask), confidential (conditional), restricted (deny external)
    - Quarantine semantics: none, quarantined, released (not deletion)
    - Export surfaces: summary, dashboard, support_bundle, qeg_export, diagnostic_bundle, external_export, public
    - Profile effects: default soft_gap, strict hold, release/product hard_dq for redaction failures
    - fixture path: `fixtures/security/redaction/` contains 10 canonical fixtures (5 positive, 5 negative)
    - schema: `schemas/HATE/v1/safe-diagnostic-bundle.schema.json`
    - test: `uv run pytest tests/test_artifact_redaction.py`
- P0a schema validation:
  - P0a は生成直後に `schemas/HATE/v1` の producer schema で自己検証する
  - 対象は `HATE-run.json`, `HATE-test-results.ndjson`, `HATE-coverage.ndjson`, `artifact-manifest.json`, `precheck-decision.json`, `record.json`
  - schema invalid は `HATE-DQ-015` として `precheck-decision.json` に残る
  - invalid decision enum と required envelope field 欠損は regression test で固定する
  - unknown field は `SCHEMA_REGISTRY_CONTRACT.md` の P0a policy に従い preserve し、summary 成功根拠にはしない
- P0a profile-aware precheck:
  - default profile: `uv run python -m hate p0a --profile default --input fixtures/golden/p0a-minimal/input --out C:\tmp\hate-profile-default --source-version profile-test`
  - strict profile: `uv run python -m hate p0a --profile strict --input fixtures/golden/p0a-minimal/input --out C:\tmp\hate-profile-strict --source-version profile-test`
  - release profile: `uv run python -m hate p0a --profile release --input fixtures/golden/p0a-minimal/input --out C:\tmp\hate-profile-release --source-version profile-test`
  - experimental profile: `uv run python -m hate p0a --profile experimental --input fixtures/golden/p0a-minimal/input --out C:\tmp\hate-profile-experimental --source-version profile-test`
  - `profile-report.json` は profile、継承chain、rules、checks、decision_impact を出す
  - strict は unsafe artifact を soft gap として `conditional` にできる
  - release は unsafe artifact を `HATE-DQ-018` として hard DQ にできる
  - profile判定は HATE evidence eligibility であり、QEG release Gate policy ではない
- compile check:
  - `uv run python -m compileall src tests`
- HATE 自身の自動検収:
  - `uv run pytest tests/test_acceptance_pipeline.py`
  - P0a -> P0b -> P1a -> P1b -> P2/P3 を CLI で一気通貫し、advisory 境界、readiness 降格、絶対パス漏れなし、golden fixture 非汚染を確認する
- CI:
  - `.github/workflows/ci.yml` が `uv run python -m compileall src tests` と `uv run pytest` を実行する

P0a CLI は次を生成する。

- `HATE-run.json`
- `HATE-test-results.ndjson`
- `HATE-coverage.ndjson`
- `artifact-manifest.json`
- `precheck-decision.json`
- `record.json`
- `summary.md`

`gate-decision.json` は互換 alias であり、新規 P0a 実装では生成しない。

P0a schema / source ref constraints:

- 共通 envelope record は生成直後に最小 schema validation を行う
- `record.json` の `source_refs` は `fixture:/` または `workspace:/` 形式へ正規化し、
  ローカル絶対パスを public-safe output に出さない
- DQ 005 / 007 / 010 は現時点では `dq-control.json` による local fixture control として再現する。
  実 CI 由来の flaky baseline / diff-risk / SARIF ingest は後続 adapter 拡張で扱う

## 4. ローカル実行（P0b QEG Export）

P0b は P0a 出力から QEG optional evidence bundle を生成する local-first CLI。
現行 minimal fixture は high-risk path の execution evidence を含むため、期待される
export status は `success`、exit code は 0 とする。missing execution が再発した場合は
hidden gap にせず `partial` へ降格し、risk debt / manual-bb bridge へ接続する。

- テスト:
  - `uv run pytest tests/test_p0b.py`
- P0b export golden path:
  - `uv run python -m hate export qeg --fixture fixtures/golden/p0b-qeg-minimal/input --out fixtures/golden/p0b-qeg-minimal/expected`
- P0b SARIF full finding mapping:
  - SARIF fixture: `fixtures/adapters/sarif/full-mapping/HATE-static.sarif`
  - `HATE-static.sarif` がある場合、QEG bundle に `finding` node を生成する
  - finding data は rule id/name/description/help URI、level/severity、location range、fingerprints、message を保持する
  - changed code range と finding location が重なる場合だけ `touches` edge を作る
  - `evidence-map.json` は `findings` と `links.touches` に同じ対応を出す
- P0b Playwright artifact evidence:
  - Playwright fixture: `fixtures/adapters/playwright/evidence`
  - test result の `artifacts` が trace / screenshot / video / log を参照する場合、QEG bundle の `evidence_artifact` node に `adapter=playwright` と `artifact_role` を残す
  - `test -> artifact` と `execution -> artifact` の `evidenced_by` edge を生成する
  - `evidence-map.json` の `evidence` と `links.evidenced_by` に Playwright artifact role を残す
  - unsafe artifact は既存 safety engine に従い `excludedArtifacts` / `gaps.unsafe_artifacts` へ送る
- P0b Pact contract evidence:
  - Pact fixture: `fixtures/adapters/pact/contract-evidence/HATE-contract.ndjson`
  - optional input `p0a/HATE-contract.ndjson` がある場合、QEG bundle に `contract_evidence` node を生成する
  - `required_contract_refs` が passed contract を指す場合は `supports` edge、failed contract を指す場合は `contradicts` edge を生成する
  - failed required contract は `unsupportedClaims` / `contract_failures` に残し、export status を `partial` にする
  - `evidence-map.json` は `contracts` と `links.contradicts` に同じ対応を出す
- P0b Stryker mutation evidence:
  - Stryker fixture: `fixtures/adapters/stryker/mutation-evidence/HATE-mutation.ndjson`
  - optional input `p0a/HATE-mutation.ndjson` がある場合、QEG bundle に `mutation_evidence` node を生成する
  - `required_mutation_refs` が killed / timeout mutant を指す場合は `supports` edge を生成する
  - survived / no_coverage mutant は `contradicts` edge、`unsupportedClaims`、`mutation_gaps` に残し、export status を `partial` にする
  - `evidence-map.json` は `mutations` と `links.contradicts` に同じ対応を出す
- P0b QEG schema compatibility:
  - local schema: `schemas/HATE/v1/qeg-bundle.schema.json`
  - P0b export は生成した `qeg-bundle.json` を schema validation し、`qeg-export-report.json.qeg_schema_compatibility` に結果を残す
  - valid bundle は `valid=true`, `errors=[]`
  - required metadata / node / edge / completeness 欠損は compatibility error として検出する
- P0b risk debt lifecycle:
  - lifecycle fixture: `fixtures/adapters/risk-debt/lifecycle/risk-debt-lifecycle.json`
  - optional input `risk-debt-lifecycle.json` がある場合、生成する `risk-debt-register.json` に status / owner / age / evidence refs を引き継ぐ
  - current missing execution は lifecycle item と risk_id/debt_type または debt_id で照合する
  - historical mitigated / stale items は `items` / `debts` に残し、`summary.by_status` に集計する
  - HATE は acknowledged / mitigated / stale を waiver や release approval として扱わない
- P0b manual-bb bridge contract:
  - contract fixture: `fixtures/manual-bb/missing-high-risk/expected/manual-supplement-request.shape.json`
  - high-risk missing execution は `manual-bb-bridge-requests.jsonl` に `contract_type=manual_supplement_request` として出力する
  - request は `gap_type=no_execution`, `recommended_manual_layer=manual-scripted`, `source_refs`, `required_oracle_refs`, `manual_case_seed` を持つ
  - `handoff_policy.does_not_override_qeg_verdict=true` を維持し、manual request を waiver や release approval として扱わない
- P0b 生成物:
  - `qeg-bundle.json` - nodes/edges/completeness を含む QEG graph bundle
  - `evidence-map.json` - requirements/risks/tests/evidence/findings/links/gaps の内部表現
  - `diff-risk-test.json` - changed_entities/risks/test_obligations の mapping (コピー)
  - `qeg-export-report.json` - completeness/qeg_schema_compatibility/unsupportedClaims/missing_execution/excludedArtifacts
  - `qeg-export-summary.md` - public-safe summary (publish_gate_override=false)
  - `risk-debt-register.json` - missing_execution の継続追跡
  - `manual-bb-bridge-requests.jsonl` - manual-bb 補完要求

P0b contract constraints:

- `publish_gate_override` must always be `false` (HATE does not approve release)
- `decision` states: `eligible`, `conditional`, `ineligible`, `hard_dq`
- Node ID formats:
  - `test:<canonical_test_id_hash>` - deterministic test node
  - `execution:<run_id>:<hash>` - execution evidence node
  - `coverage:<path_hash>` - coverage evidence node
  - `changed_code:<path>#L<start>-L<end>` - changed code region
  - `risk:<risk-id>` - risk node
  - `finding:<finding-id>` - SARIF finding node
  - `contract:<contract-id>` - Pact contract evidence node
  - `mutation:<mutation-id>` - Stryker mutation evidence node
  - `hate_precheck:<run_id>:<attempt>` - gate verdict node
- Edge kinds: `touches`, `requires_test`, `evidenced_by`, `supports`, `decides`
- Completeness calculation:
  - base=1.0
  - -0.20 per missing artifact
  - -0.15 per parser failure
  - -0.10 per unsupported high-risk claim
  - -0.10 when required sourceRefs are missing
  - -0.10 when artifact safety excludes required evidence
  - floor at 0.0
- `hard_dq` precheck decision prevents QEG export
- minimal fixture の `missing_execution=0` は期待値。`completeness.score=1.0`,
  `completeness.partial=false`, `export_status=success` であることを確認する。
- P0b edge hardening:
  - missing sourceRefs は `unsupportedClaims` に出す
  - missing required P0a artifact は export failure として exit 2
  - unsafe required artifact は quarantine し、`excludedArtifacts` / `gaps.unsafe_artifacts` に出す
  - Playwright trace/screenshot/video/log は test / execution / artifact 間の `evidenced_by` edge で追跡する
  - failed required Pact contract は `contract_failures` と `links.contradicts` で追跡する
  - survived / no_coverage Stryker mutant は `mutation_gaps` と `links.contradicts` で追跡する
  - QEG bundle schema compatibility は `qeg_schema_compatibility.valid` で確認する
  - high-risk missing execution は lifecycle付き `risk-debt-register.json` と `manual-bb-bridge-requests.jsonl` に接続する
  - manual-bb bridge request は `source_refs` / `required_oracle_refs` / `manual_case_seed.oracle` で traceability を持つ

## 4.1 ローカル実行（P1a Trust Minimal）

P1a trust minimal は frozen P0b bundle から AETE score、artifact resolver map、
doctor report、public-safe summary を生成する。AETE は release Gate ではなく、
`release_gate_override=false` と `publish_gate_override=false` を常に維持する。

- テスト:
  - `uv run pytest tests/test_p1a.py`
- P1a trust golden path:
  - `uv run python -m hate trust evaluate --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --out fixtures/golden/p1a-trust-minimal/expected`
- P1a 生成物:
  - `aete-score.json` - 8 dimensions / reason_refs / profile / calibration metadata
  - `artifact-resolver-map.json` - sourceRefs の正規化結果
  - `doctor-report.json` - qeg_fixture / artifact_safety / path などの findings
  - `adapter-registry.json` - implemented adapter manifests / capability / fixtures / profile support
  - `adapter-capability-manifest.json` - P1a upstream QEG bundle adapter compatibility manifest
  - `adapter-conformance-report.json` - registry coverage and adapter conformance checks
  - `canonical-identity-index.json` - canonical test identity と alias 入口
  - `retry-aggregation.json` - matrix / retry 集約の最小結果
  - `trust-summary.md` - public-safe trust summary
- P1a adapter registry:
  - fixture: `fixtures/registry/adapter-registry/expected/adapter-registry.shape.json`
  - `context`, `test-result`, `coverage`, `static`, `artifact`, `contract`, `mutation`, `export` adapters を一覧化する
  - each manifest includes adapter_id / name / version / adapter_type / input_formats / output_record_types / capabilities / fixtures / profile_support
  - conformance report includes `adapter_registry.adapter_ids` and `summary.adapter_count`
- P1a adapter conformance runner:
  - fixture: `fixtures/registry/conformance-runner/expected/adapter-conformance.shape.json`
  - `adapter-conformance-report.json.adapter_results[]` は adapter ごとの結果を持つ
  - each adapter result includes `fixture_results[]` for `manifest-required-fields`, `capability-fields`, and `profile-support`
  - `summary.adapter_result_count` must match `adapter_registry.adapter_count`
  - `summary.fixture_result_count` must be at least three times the adapter count
- P1a profile inheritance:
  - fixture: `fixtures/profile/inheritance/expected/profile-report.shape.json`
  - `profile-report.json` is emitted by P0a precheck, P1a trust evaluate, and P1a doctor
  - `inherits` / `effective_chain` expose deterministic chains such as `default -> strict -> release`
  - `rule_sources` and `rule_diffs` show which profile introduced or overrode each effective rule
  - `drift_checks` must pass and `qeg_gate_policy=false`, `release_gate_override=false`, `publish_gate_override=false`
  - `aete-score.json.profile_version` must match `profile-report.json.profile_version`
- P1a signal-based AETE scoring:
  - fixture: `fixtures/aete/signal-based/expected/aete-signal-report.shape.json`
  - `aete-signal-report.json` contains one signal per AETE dimension
  - `aete-score.json.dimension_signals` mirrors the signal report
  - each `reason_refs[]` entry points to a `signal:<dimension>:<score>` id
  - score values remain discrete: `0`, `1`, `3`, or `5`
  - missing execution / unsupported claims must lower the relevant dimensions through explicit observed signals
- P1a canonical identity hardening:
  - fixture: `fixtures/identity/canonical/expected/canonical-identity-index.shape.json`
  - `canonical-identity-index.json` includes `identity_id`, `normalized_canonical_test_id`, `identity_components`, aliases, and duplicate summary
  - identity components split framework / package / file / classname / name / parameters / matrix
  - parameters may affect the normalized logical id through a stable hash
  - matrix values stay in `identity_components.matrix` and must not change the logical test name
  - path normalization aliases use `reason=path_normalization`
- P1a retry / matrix / shard aggregation:
  - fixture: `fixtures/aggregation/retry-matrix-shard/expected/retry-aggregation.shape.json`
  - aggregation key uses normalized canonical identity, matrix group, and run attempt
  - retry attempts are ordered by `retry_index`
  - pass-after-fail becomes `flaky_passed`; fail-after-pass becomes `flaky_failed`
  - missing shard evidence sets `aggregate_status=inconclusive`
  - summary includes `matrix_group_count` and `missing_shard_count`
- P1a artifact resolver:
  - fixture: `fixtures/resolver/artifact-paths/expected/artifact-resolver-map.shape.json`
  - `artifact-resolver-map.json.entries[]` includes both `source_ref` and `artifact_path` entries
  - artifact path entries preserve artifact id, kind, role, sha256, normalized path, root kind, and resolution status
  - URLs and traversal paths are `unsafe` and become doctor `path` findings
  - summary includes entry, unsafe, unresolved, artifact path, and source ref counts
- P1a replay / compare / explain / recommend hardening:
  - fixture: `fixtures/replay/hardening/expected/replay-compare-explain-recommend.shape.json`
  - `replay-report.json.deterministic_inputs` hashes AETE, signal, profile, resolver, doctor, conformance, identity, and retry artifacts
  - `compare-report.json` includes `signal_delta`, `resolver_unsafe_delta`, `identity_duplicate_delta`, and `profile_hash_changed`
  - `explain-report.json.summary.traceability_complete` must be true for generated reason trees
  - `recommendation-report.json.summary` includes recommendation count, traceability status, and manual bridge recommendation count
- P1a doctor finding taxonomy:
  - fixture: `fixtures/doctor/taxonomy/expected/doctor-report.shape.json`
  - every doctor finding includes `finding_code`, `taxonomy_version`, `blocking`, `remediation`, and source refs
  - known taxonomy codes include `HATE-DOC-QEG-001`, `HATE-DOC-ART-001`, and `HATE-DOC-PATH-001`
  - summary includes `by_category`, `by_severity`, and `taxonomy_version`
- P1a replay:
  - `uv run python -m hate replay --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --out fixtures/golden/p1a-trust-minimal/replay-expected`
- P1a compare:
  - `uv run python -m hate compare --base fixtures/golden/p1a-trust-minimal/replay-expected --head fixtures/golden/p1a-trust-minimal/replay-expected --out fixtures/golden/p1a-trust-minimal/compare-expected`
- P1a explain:
  - `uv run python -m hate explain --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --out fixtures/golden/p1a-trust-minimal/explain-expected --mode why-soft-gap`
- P1a recommend:
  - `uv run python -m hate recommend --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --out fixtures/golden/p1a-trust-minimal/recommend-expected --gap missing_execution`

P1a minimal constraints:

- AETE dimension は 0 / 1 / 3 / 5 の離散値だけを使う
- `calibration_status=uncalibrated` を release approval と誤認させない
- sourceRefs にローカル絶対パスを漏らさない
- P1a minimal は advisory evidence であり、release approval として扱わない

## 4.2 ローカル実行（P1b Workflow Mapping）

P1b workflow mapping は frozen P0b bundle と P1a trust artifacts を、
RanD / Shipyard-cp / workflow-cookbook へ渡せる advisory artifact に変換する。
HATE は RanD Requirement Definition Gate、Shipyard runtime dispatch、
Shipyard publish approval、workflow-cookbook checker を再実装しない。

- テスト:
  - `uv run pytest tests/test_p1b.py`
- P1b workflow golden path:
  - `uv run python -m hate workflow map --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --trust fixtures/golden/p1a-trust-minimal/expected --out fixtures/golden/p1b-workflow-minimal/expected`
- P1b RanD requirements packet ingest:
  - `uv run python -m hate workflow map --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --trust fixtures/golden/p1a-trust-minimal/expected --rand-requirements fixtures/rand/requirements-packet/input/requirements_packet.json --out .uat-p1b001/out`
  - `requirement-evidence-alignment.json` の `rand.requirements_packet_ingested=true`、
    `rand.packet_id=rand-packet-hate-p1b-001`、`summary.rand_requirement_count=2` を確認する
  - RanD packet の `gate_verdict`, `kpis`, `acceptance_criteria`, `risk_refs`,
    `source_refs` は requirement 単位で保持され、`upstream_gate_verdict` としても残る
  - `requirements[*].trace_links` は QEG bundle の `touches` / `requires_test` /
    `evidenced_by` / `supports` edge から、requirement -> risk -> changed code ->
    test -> execution -> coverage を辿れる形で保持する
  - `summary.trace_link_count` と `summary.fully_linked_requirement_count` により、
    requirement-risk-test-evidence link の生成数を確認する
  - RanD packet に `conditional_go` が含まれる場合、HATE は `workflow_status=conditional`
    とし、`go` に丸めない
- P1b RanD audit no-overwrite:
  - `uv run python -m hate workflow map --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --trust fixtures/golden/p1a-trust-minimal/expected --rand-audit fixtures/rand/audit-no-overwrite/input/audit_packet.json --out .uat-p1b002/out`
  - `requirement-evidence-alignment.json` の `rand_audit.audit_packet_ingested=true`、
    `rand_audit.overall_assessment=no_go`、`summary.gate_verdict=no_go` を確認する
  - `rand_audit.requirement_verdicts[*].upstream_gate_verdict` は audit packet の
    `gate_verdict` と同一でなければならない
  - `boundary.rand_verdict_override=false`、`boundary.rand_audit_overwrite=false`、
    `shipyard-run-evidence.json.publish_gate_override=false` を維持する
- P1b Shipyard WorkerResult / RunSystemPacket ingest:
  - `uv run python -m hate workflow map --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --trust fixtures/golden/p1a-trust-minimal/expected --shipyard-worker-result fixtures/shipyard/worker-result/input/worker_result.json --shipyard-run-system-packet fixtures/shipyard/worker-result/input/run_system_packet.json --out .uat-p1b004/out`
  - `shipyard-run-evidence.json.shipyard_inputs.worker_result_ingested=true` と
    `shipyard_inputs.run_system_packet_ingested=true` を確認する
  - `shipyard_refs.worker_result.typed_ref`、`shipyard_refs.run_system_packet.run_ref`、
    `job_ref`、`contract_refs.evidence_ref`、`audit_refs` を保持する
  - HATE は Shipyard の state machine owner ではないため、
    `shipyard_state_override=false`、`publish_gate_override=false`、`shipyard_inputs.advisory_only=true`
    を維持する
- P1b Shipyard no-overwrite negative fixture:
  - `uv run python -m hate workflow map --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --report fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json --trust fixtures/golden/p1a-trust-minimal/expected --shipyard-worker-result fixtures/shipyard/no-overwrite/input/worker_result.json --shipyard-run-system-packet fixtures/shipyard/no-overwrite/input/run_system_packet.json --out .uat-p1b005/out`
  - 入力に `mode=enforce`、`stage=publish`、publish requested / approved 風の refs があっても、
    HATE 出力の `publish_gate_override=false`、`release_gate_override=false`、
    `shipyard_state_override=false` を維持する
  - `shipyard_refs` には入力refsを保持するが、HATEは Shipyard publish approval を発行しない
- P1b 生成物:
  - `requirement-evidence-alignment.json` - requirement / acceptance / risk / gate_verdict と HATE evidence の結線
  - `workflow-task-seed.json` - HATE-MVP-* と acceptance refs の Task Seed 互換素材
  - `workflow-acceptance-record.json` - acceptance record 互換の checks / verdict
  - `workflow-evidence.jsonl` - QEG / AETE / alignment / Shipyard advisory evidence
  - `workflow-docs-stale.json` - docs / schema / fixture freshness checker へ渡す素材
  - `workflow-birdseye-map.json` - docs / artifacts / workflow 依存候補
  - `workflow-cookbook-evidence-map.json` - Task Seed / Acceptance / Evidence /
    Birdseye / Docs Stale を workflow-cookbook surface へ結線する索引
  - `shipyard-run-evidence.json` - Shipyard run / audit に添付可能な advisory packet

P1b minimal constraints:

- `publish_gate_override=false`, `release_gate_override=false`,
  `shipyard_state_override=false` を維持する
- RanD `no_go` / `conditional_go` を HATE 側で `go` に変換しない
- workflow-cookbook の checker / plugin host / Birdseye generator を再実装しない
- `workflow-cookbook-evidence-map.json.workflow_cookbook.*_reimplemented=false` を維持し、
  workflow-cookbook へ渡す入力索引だけを生成する
- `risk-db-high` の execution evidence は現行 minimal fixture で充足済み。
  missing execution が再発した場合は `unverified_acceptance` と manual-bb bridge として残す

## 4.3 ローカル実行（P2/P3 Product Readiness）

P2/P3 product readiness は P0b/P1a/P1b の canonical artifacts から、
product readiness と enterprise readiness の advisory artifact を生成する。
これは hosted SaaS runtime、dashboard frontend、REST server、enterprise connector
の起動証跡ではない。

- テスト:
  - `uv run pytest tests/test_p2p3.py`

### File size guard

Before adding major product-grade behavior, run:

```powershell
uv run python tools/check_file_size.py
```

The guard follows `docs/process/REFACTORING_PLAN.md`: hand-written source and test modules above
900 lines fail, markdown above 1000 lines fails unless it is an approved root index pending split,
and oversized generated fixtures are allowed only in golden expected-output paths.
- P2/P3 readiness golden path:
  - `uv run python -m hate product readiness --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --trust fixtures/golden/p1a-trust-minimal/expected --workflow fixtures/golden/p1b-workflow-minimal/expected --out fixtures/golden/p2p3-product-readiness-minimal/expected`
- P2 local store / history index:
  - `uv run python -m hate store ingest --store .hate --bundle fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json --readiness fixtures/golden/p2p3-product-readiness-minimal/expected`
  - `uv run python -m hate store history --store .hate`
  - `uv run python -m hate store query --store .hate --resource bundle --run-id 1001`
  - `uv run python -m hate store query --store .hate --resource risk-debt`
  - store は `.hate/history-index.json` と `.hate/runs/<run_id>/store-manifest.json` を生成し、
    run / bundle / product readiness / risk debt を再読込できる
  - store query は `canonical_source_preserved=true`、`stale_cache=false`、
    `publish_gate_override=false`、`release_gate_override=false` を維持する
- P2/P3 生成物:
  - `product-readiness-report.json` - PRG-0..PRG-6 coverage、advisory `evaluation` score、境界field
  - `dashboard-report.html` - canonical artifacts から派生する静的 dashboard surface
  - `dashboard-view-model.json` - overview / risk matrix / evidence map /
    artifact budget / readiness trend の必須view model
  - `pr-annotation-export.json` - changed high-risk path 単位の GitHub PR annotation 互換 export
  - `artifact-budget-report.json` - artifact 容量 / retention / storage class /
    public exposure / limit policy / over-limit action
  - `attestation-report.json` - optional signed evidence / attestation 素材
    subject digest / provenance / signing state / release refs を含む
  - `external-export-report.json` - Allure / ReportPortal / Codecov /
    SonarQube の optional exporter payload と non-gating failure policy
  - `product-error-catalog.json` - stable user-facing error code と remediation
  - `enterprise-risk-debt-register.json` - owner / age / sourceRefs 付き risk debt
  - `privacy-quarantine-report.json` - unsafe artifact quarantine と output policy
  - `hosted-read-model-index.json` - canonical bundle から再構築できるread model index
  - `domain-model-report.json` - org / workspace / project / repo / run /
    attempt / bundle / profile の enterprise domain model
  - `rbac-matrix-report.json` - role / resource / action の allow/deny matrix と
    hosted read model resource mapping
  - `identity-connector-report.json` - SSO / SCIM optional connector dry-run contract
  - `enterprise-connector-report.json` - SIEM / warehouse / ticketing optional connector dry-run contract
  - `audit-event-log.json` - required audit events の append-only synthetic log
  - `retention-governance-report.json` - classification-linked retention /
    legal hold / customer export / delete request policy
  - `release-migration-report.json` - release gate / migration / rollback / compatibility
  - `entitlement-usage-report.json` - edition / usage / over-limit と非上書き保証
  - `enterprise-metrics-report.json` - product metrics とprivacy boundary
  - `customer-docs-index.json` - required docs / freshness / verification index
  - `incident-slo-report.json` - severity / class / timeline / evidence refs
  - `adoption-health-report.json` - adoption stage / milestone / renewal readiness
  - `security-trust-packet.json` - controls / SBOM / vulnerability / subprocessor
  - `residency-deployment-report.json` - deployment mode / data class routing / recovery
  - `roadmap-decision-record.json` - roadmap status / customer-facing claim guard
  - `accessibility-localization-report.json` - accessibility / localization stable id
  - `commercial-contract-report.json` - commitment / contract exception / unsupported claim
  - `audit-assurance-pack.json` - assurance expected output / evidence room index
  - `support-diagnostic-bundle.json` - support向けsafe-to-share diagnostic bundle
  - `privacy-telemetry-report.json` - allowed/prohibited telemetry signal
  - `governance-portfolio-report.json` - portfolio tier / owner / P0 dependency leak
  - `release-candidate-pack.json` - P3 required reports / RG-1..RG-8 /
    compatibility / rollback evidence
  - `shipyard-run-evidence.json` - P2/P3 advisory Shipyard evidence
- Hosted read model query:
  - `uv run python -m hate product query --readiness fixtures/golden/p2p3-product-readiness-minimal/expected --resource product-readiness --request-id req_local`
  - filter / stale / pagination: `uv run python -m hate product query --readiness fixtures/golden/p2p3-product-readiness-minimal/expected --resource risk-debt --role auditor --filter status=open --stale-cache --cursor cursor_001`
  - RBAC error: `uv run python -m hate product query --readiness fixtures/golden/p2p3-product-readiness-minimal/expected --resource artifacts --role viewer`
  - API envelope は `schema_version`, `request_id`, `data`, `errors`, `pagination.next_cursor`,
    `source.bundle_id`, `source.record_id`, `source.generated_at` を保持する
  - forbidden resource は stable error `HATE-E-PRODUCT-QUERY-403`、unknown resource は
    `HATE-E-PRODUCT-QUERY-404` を返し、`remediation` を含む
- Hosted read model REST server:
  - `uv run python -m hate product serve --readiness fixtures/golden/p2p3-product-readiness-minimal/expected --host 127.0.0.1 --port 8765`
  - `GET /v1/product-readiness` は `HOSTED_READ_MODEL_API.md` の response envelope を返す
  - `GET /v1/risk-debt?role=auditor&filter.status=open&stale_cache=true&cursor=next_1` は
    filter と stale marker と pagination cursor を envelope に残す
  - `GET /v1/artifacts?role=viewer` は HTTP 403 と `HATE-E-PRODUCT-QUERY-403` を返す

P2/P3 minimal constraints:

- `publish_gate_override=false`, `release_gate_override=false` を維持する
- `product-readiness-report.json` は `hosted_saas_claim=false` を明示する
- `dashboard-view-model.json.required_views` は `overview`, `risk_matrix`,
  `evidence_map`, `artifact_budget`, `readiness_trend` を含み、canonical artifact から再構築できる
- `pr-annotation-export.json.annotations[]` は `annotation_level`, `path`,
  `start_line`, `end_line`, `message`, `raw_details.required_test_refs`,
  `raw_details.execution_evidence_refs`, `raw_details.coverage_refs` を持つ
- PR annotation は advisory export であり、`publish_gate_override=false` と
  `release_gate_override=false` を維持する
- `artifact-budget-report.json` は `budget_policy`, `summary.by_kind`,
  `summary.by_public_exposure`, `retention_days`, `over_limit_reasons`,
  `budget_action` を出す。over-limit は evidence を隠さず
  `warn_only_do_not_drop_evidence` として扱う
- artifact budget は canonical decision を変更せず、
  `canonical_decision_unchanged=true`, `evidence_dropped_for_budget=false` を維持する
- `attestation-report.json` は `subjects[*].digest`, `provenance`, `signing`,
  `release_refs`, `immutability` を持つ。署名未設定でも `attestation_status=unsigned_optional`
  とし、local-first precheck や canonical decision を変えない
- `external-export-report.json` は `allure`, `reportportal`, `codecov`, `sonarqube`
  の provider id を持ち、各 provider は `failure_policy=non_gating_warning` を維持する
- external export failure fixture は `stable_error_code=HATE-EXP-001`,
  `non_gating=true`, `canonical_decision_unchanged=true` を持ち、precheck / QEG /
  product status / publish / release gate を上書きしない
- product readiness は固定 `go` ではない。入力 artifact 欠損がある場合は `hold`、
  doctor finding または unverified acceptance が残る場合は `conditional` に降格する
- `product-readiness-report.json.summary.evaluation_score` は 0..100 の advisory score とし、
  `evaluation.additions[]` で AETE、PRG coverage、artifact completeness、workflow acceptance、
  doctor hygiene を説明用に集計し、`evaluation.penalties[]` で入力欠損、doctor finding、
  unverified acceptance、未校正 AETE、低 confidence を減点した `raw_score` を出す。
  最終 score は `evaluation.caps[]` の gate cap を適用した値であり、入力 artifact 欠損、
  doctor finding、unverified acceptance、workflow gap、未校正/低 confidence が残る場合は
  高得点に逃がさない
- `go_label_is_advisory=true` を常に保持し、`evaluation.release_approval=false` を明示する。
  release approval / waiver / gate 正本は HATE が持たず、score は説明責任と優先順位付けに使う
- 現行 golden fixture は high-risk execution evidence と doctor finding 0 を保持するため、
  `product_status=go`, `prg_coverage=7/7` を期待値とする
- `hate product query` と `hate product serve` は `HOSTED_READ_MODEL_API.md` の response envelope を返す
- `domain-model-report.json` は P0/P1 local bundle が org / workspace / hosted
  service なしで成立すること、hosted read model が canonical bundle から再構築できること、
  auditor read-only、service account が human approval を代替しないこと、
  artifact classification が summary / export / diagnostic 可否に効くことを示す
- `rbac-matrix-report.json` は admin / maintainer / developer / auditor / viewer /
  service_account / security_reviewer の role を持ち、viewer raw artifact deny、
  developer audit log deny、auditor read-only、service account approval非代替を
  invariant として検証できる
- `hate product query` / `serve` の forbidden response は `rbac-matrix-report.json`
  と同じ read model resource mapping に従う
- `identity-connector-report.json` は SSO / SCIM を optional enterprise connector
  として dry-runし、未設定でも `non_gating=true`、`credentials_present_in_fixture=false`、
  `contains_connector_token=false`、`external_network_required=false` を維持する
- `enterprise-connector-report.json` は SIEM / warehouse / ticketing を optional
  connector として dry-runし、failure fixture は `HATE-EXP-001`,
  `non_gating=true`, `local_artifacts_preserved=true`, `qeg_export_preserved=true`
  を維持する。payload は raw artifact、customer code、connector token、PII、
  unsafe artifact を含まない
- `security-trust-packet.json` は security review record、trust packet refs、
  data flow、control mapping、privacy summary、SBOM、vulnerability report、
  subprocessor、freshness、attestation summary を含み、critical/high vulnerability
  owner/due/mitigation、customer source code/secret/PII/unsafe artifact 非混入、
  QEG Gate policy / waiver / approval 非上書きを検証できる
- `residency-deployment-report.json` は local_only / ci_attached /
  hosted_read_model / private_tenant / customer_managed / air_gapped_export の
  data plane / control plane / owner、residency profile、data class routing、
  connectivity controls、backup / recovery を持ち、region / deployment mode が
  evidence eligibility や local-first precheck を変えないことを示す
- `commercial-contract-report.json` は commercial commitment register、
  procurement response、contract exception、commercial risk、safety boundary を持つ。
  planned / unsupported capability は available と表現せず、例外は owner / expiry /
  risk / workaround / linked roadmap item を持ち、precheck / QEG verdict を変えない
- `audit-assurance-pack.json` は audit fixture manifest、auditor walkthrough、
  expected output index、verification log、evidence room index、audit finding register、
  assurance summary を持つ。open finding と limitation を隠さず、customer code /
  secret / PII / unsafe artifact を含まず、precheck / QEG verdict を変えない
- `release-candidate-pack.json` は P3 required reports をすべて含み、
  `missing_required_reports=[]`、RG-1..RG-8 all pass、compatibility matrix、
  release notes、rollback instructions、unsupported future schema safe reject を持つ。
  release approval を代替せず、precheck / QEG verdict / publish gate を変えない
- `audit-event-log.json` は `bundle.created`, `bundle.exported`, `profile.changed`,
  `adapter.changed`, `artifact.accessed`, `artifact.quarantined`, `riskdebt.created`,
  `diagnostic.generated` を含み、各eventのrequired fields、sequence monotonic、
  append-only、safe-to-share、QEG/precheck非上書きを検証できる
- `retention-governance-report.json` は classification ごとの retention、
  legal hold 時の delete block、customer export の metadata-only 方針、
  customer delete の system-of-record 委譲、QEG retention 非再実装を検証できる
- `support-diagnostic-bundle.json` は `hate_version`, `schema_registry_version`,
  sanitized command, profile, adapter registry summary, capability summary, DQ summary,
  doctor summary, error records, QEG compatibility summary を持つ
- support diagnostic bundle は `safety_checks` と `environment_policy` で customer code、
  raw artifact、secret、PII、unsafe artifact、customer private URL、full environment、
  external connector token を含まないことを明示する
- telemetry / diagnostic bundle は customer code、raw artifact、secret、PII を含まない
- P2/P3 productization は P0a/P0b local-first loop の必須依存にならない

## 5. 受理前確認

- DQ 条件（HATE-DQ-01〜15）が未解消のまま判定に進んでいないか
- Diff-risk-test で `changed high-risk path` と `execution` の接続欠損がないか
- P1a 以降では AETE スコアが計算不能なら `hard_dq` または明示的な
  `soft_gap` になるか。P0a では AETE 未実装を失敗条件にしない
- P0a では `P0A_GOLDEN_PATH.md` の required inputs / outputs /
  decision enum / DQ fixture / summary safety と実装結果が一致しているか
- P1a 以降では AETE score に `rubric_version`, `profile_version`,
  `score_confidence`, `calibration_status` が残り、未校正 score を release Gate
  正本のように表示していないか
- P1a 以降では test result の `canonical_test_id`, `identity_components`,
  `aliases` により rename / parameterized test / matrix の履歴差分を説明できるか
- HATE が QEG の Gate policy / waiver / approval / retention / immutability /
  schema migration を重複実装していないか
- P1b 以降では RanD の Requirement Definition Gate verdict を HATE が上書きしていないか
- `requirement-evidence-alignment.json` が requirement / acceptance / risk ごとの
  自動テスト証跡と不足理由を説明できるか
- P1b 以降では `shipyard-run-evidence.json` が Shipyard の run / audit refs と HATE artifact refs を
  結線し、Shipyard の state machine を変更していないか
- P1b 以降では `workflow-task-seed.json` から HATE-MVP-* と acceptance refs を辿れるか
- P1b 以降では `workflow-acceptance-record.json` が acceptance record 必須 field を満たすか
- P1b 以降では `workflow-evidence.jsonl` が HATE artifact refs、AETE summary、DQ summary を保持するか
- P1b 以降では `workflow-docs-stale.json` と `workflow-birdseye-map.json` が docs freshness /
  依存候補を説明できるか
- P1b 以降では HATE が workflow-cookbook の checker / plugin host / Birdseye 生成器を
  重複実装していないか
- matrix / shard / retry aggregation が同一入力で同一結果になるか
- coverage / SARIF / JUnit / Playwright artifact の path が QEG の sourceRefs /
  artifact metadata に渡せる形へ正規化されているか
- HATE optional evidence を QEG minimal fixture に接続しても `validate / gate / record`
  の前提を壊さないか
- P1a 以降では `HATE replay` が frozen bundle から同一 AETE / DQ / QEG export を
  再計算できるか
- P1a 以降では `HATE compare` が trust delta / DQ 増減 / risk coverage 低下を
  差分として説明できるか
- P1a 以降では `HATE explain` / `HATE recommend` が不足証跡の理由と次アクションを
  sourceRefs 付きで説明できるか
- P1a 以降では `HATE doctor` が adapter / schema / path / provenance /
  QEG fixture の診断を summary と JSON に出せるか
- P1a 以降では artifact resolver が summary / manifest / QEG sourceRefs の
  artifact 参照を同じ規則で解決しているか
- artifact safety が secret scan、MIME / 拡張子整合、archive 展開制限、
  symlink / path traversal、外部 URL 参照の検査を通し、失敗 artifact を
  public summary / QEG export / external export へ漏らしていないか
- privacy / quarantine が `PRIVACY_QUARANTINE_CONTRACT.md` の classification /
  security_checks / quarantine / output policy と一致しているか
- P1a 以降では schema registry と adapter conformance fixtures により、
  schema drift と adapter 最低準拠を検証できるか
- P1a 以降では `SCHEMA_REGISTRY_CONTRACT.md` の unknown / deprecated /
  required / optional field policy と実装結果が一致しているか
- P1a 以降では `ADAPTER_SDK_CONTRACT.md` の adapter manifest、required interface、
  failure contract、conformance report と実装結果が一致しているか
- P1a 以降では `RISK_DEBT_REGISTER.md` の risk debt item、status、aging、
  recommendation link と実装結果が一致しているか
- P1b 以降では manual-bb bridge が high-risk gap を手動補完要求へ変換し、
  手動テスト実施そのものを HATE が代替していないか
- P2 以降では PR annotation / artifact budget / attestation が optional 拡張として扱われ、
  未設定でも local-first precheck を妨げないか
- P2/P3 以降では hosted dashboard / REST API / enterprise connector が
  canonical bundle から派生し、HATE 独自の release approval 正本を持っていないか
- hosted read model / API が `HOSTED_READ_MODEL_API.md` の source artifact /
  response envelope / RBAC / stale cache policy と一致しているか
- release / migration が `RELEASE_MIGRATION_POLICY.md` の RG-1..RG-8 /
  compatibility matrix / rollback policy と一致しているか
- packaging / entitlement が `PACKAGING_ENTITLEMENT_CONTRACT.md` の edition /
  entitlement / usage meter / over-limit policy と一致し、precheck / QEG verdict を
  変更していないか
- customer-facing docs が `CUSTOMER_DOCUMENTATION_CONTRACT.md` の required docs /
  source_contracts / freshness / verification と一致し、実装状態を超えて表現していないか
- SLO / incident response が `SLO_INCIDENT_RESPONSE_CONTRACT.md` の severity /
  incident class / containment / communication / postmortem と一致し、canonical evidence を
  改変していないか
- customer success / adoption が `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` の adoption stage /
  success plan / adoption gap / renewal readiness と一致し、precheck / QEG verdict を
  変更していないか
- security review / trust が `SECURITY_REVIEW_TRUST_CONTRACT.md` の trust packet /
  control mapping / vulnerability handling / freshness と一致し、customer source code、
  secret、PII、unsafe artifact を含んでいないか
- product telemetry / analytics が `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` の telemetry mode /
  allowed signal / prohibited signal / retention と一致し、telemetry off でも local-first
  precheck と QEG export が動くか
- data residency / deployment が `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` の deployment mode /
  residency profile / data class routing / backup recovery と一致し、region / deployment mode で
  precheck / QEG verdict を変更していないか
- product governance / roadmap が `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` の roadmap item /
  decision record / customer request / deprecation decision と一致し、candidate を released と
  表現していないか
- accessibility / localization が `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` の accessibility target /
  localization report / locale fallback と一致し、stable code / schema field / record_id を
  翻訳で変更していないか
- legal / commercial contracting が `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` の
  commitment register / procurement response / contract exception と一致し、unsupported / planned
  capability を available と表現していないか
- audit fixture / assurance が `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` の fixture manifest /
  assurance pack / evidence room と一致し、open finding や limitation を隠していないか
- requirements portfolio が `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` の tier / stage /
  WIP / dependency と一致し、P0a/P0b が P2/P3 productization に依存していないか
- P2/P3 以降では product error code、risk debt register、privacy report、
  support diagnostic bundle が QEG の Gate policy / waiver / approval を上書きしていないか
- product error code が `PRODUCT_ERROR_TAXONOMY.md` の category / severity /
  remediation / summary policy と一致しているか
- enterprise domain model が `ENTERPRISE_DOMAIN_MODEL.md` の Organization /
  Workspace / Project / Repository / Run / EvidenceBundle / AuditEvent 境界と一致しているか
- P3 以降では RBAC、audit log、retention、SSO / SCIM、SIEM connector、
  compliance pack、support SLA が `ENTERPRISE_PRODUCT_REQUIREMENTS.md` の PRG-4..PRG-6 と
  対応しているか
- support diagnostic bundle が secret / PII / unsafe artifact を含まず、
  version、schema、profile、adapter、DQ、doctor 結果を説明できるか
- tests は golden fixture を直接 test-output で汚さず、`tmp_path` にコピー / 出力して実行する。
  golden `expected` を更新する場合だけ Runbook の golden path command を明示的に実行する
- HATE 自身の検収は `tests/test_acceptance_pipeline.py` を正本とし、CLI pipeline が壊れる、
  product readiness が欠損時に `hold` へ降格しない、または source refs にローカル絶対パスが漏れる場合は失敗させる

## 6. ロールバック方針（文書中心）

- 誤判定や schema 破綻が見つかった場合
  - その Task を未完了に戻し、受入条件を更新
  - 影響を受ける証跡出力を削除ではなく再生成で置換

## 7. 最新メモ

- 直近: 2026-06-28 P0a/P0b/P1a/P1b/P2/P3 の local/advisory artifact 実装を現行化
- 直近: 2026-06-28 DQ 005/007/010 の fixture control、最小 schema validation、
  stable source refs、P2/P3 readiness 降格、pytest tmp output 分離を追加
- 直近: 2026-06-28 HATE 自身の E2E 自動検収 `tests/test_acceptance_pipeline.py` と
  GitHub Actions CI `.github/workflows/ci.yml` を追加
- 次点: 実 CI 由来の flaky baseline / SARIF / diff-risk adapter と hosted runtime は別ゲートで扱う
