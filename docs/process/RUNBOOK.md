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
2. `TASK.codex.md` の順番で Task を実装
3. 各 Task ごとに `record.json` 互換の検証メモを残す
4. `EVALUATION.md` の受入項目を満たして完了判定

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
  - `fixtures/golden/p0a-minimal/dq-08-coverage-only`
  - `fixtures/golden/p0a-minimal/dq-15-record-missing`
- compile check:
  - `uv run python -m compileall src tests`

P0a CLI は次を生成する。

- `HATE-run.json`
- `HATE-test-results.ndjson`
- `HATE-coverage.ndjson`
- `artifact-manifest.json`
- `precheck-decision.json`
- `record.json`
- `summary.md`

`gate-decision.json` は互換 alias であり、新規 P0a 実装では生成しない。

## 4. ローカル実行（P0b QEG Export）

P0b は P0a 出力から QEG optional evidence bundle を生成する local-first CLI。

- テスト:
  - `uv run pytest tests/test_p0b.py`
- P0b export golden path:
  - `uv run python -m hate export qeg --fixture fixtures/golden/p0b-qeg-minimal/input --out fixtures/golden/p0b-qeg-minimal/expected`
- P0b 生成物:
  - `qeg-bundle.json` - nodes/edges/completeness を含む QEG graph bundle
  - `evidence-map.json` - requirements/risks/tests/evidence/links/gaps の内部表現
  - `diff-risk-test.json` - changed_entities/risks/test_obligations の mapping (コピー)
  - `qeg-export-report.json` - completeness/unsupportedClaims/missing_execution/excludedArtifacts
  - `qeg-export-summary.md` - public-safe summary (publish_gate_override=false)

P0b contract constraints:

- `publish_gate_override` must always be `false` (HATE does not approve release)
- `decision` states: `eligible`, `conditional`, `ineligible`, `hard_dq`
- Node ID formats:
  - `test:<canonical_test_id_hash>` - deterministic test node
  - `execution:<run_id>:<hash>` - execution evidence node
  - `coverage:<path_hash>` - coverage evidence node
  - `changed_code:<path>#L<start>-L<end>` - changed code region
  - `risk:<risk-id>` - risk node
  - `hate_precheck:<run_id>:<attempt>` - gate verdict node
- Edge kinds: `touches`, `requires_test`, `evidenced_by`, `supports`, `decides`
- Completeness calculation:
  - base=1.0
  - -0.20 per missing artifact
  - -0.15 per parser failure
  - -0.10 per unsupported high-risk claim
  - floor at 0.0
- `hard_dq` precheck decision prevents QEG export

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

## 5. ロールバック方針（文書中心）

- 誤判定や schema 破綻が見つかった場合
  - その Task を未完了に戻し、受入条件を更新
  - 影響を受ける証跡出力を削除ではなく再生成で置換

## 6. 最新メモ

- 直近: 2026-06-27 `workflow-cookbook` の書式で実装準備文書を追加
- 次点: Task ベース実装へ移行
