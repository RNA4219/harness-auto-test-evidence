---
intent_id: INT-HATE-PRODUCT-REQUIREMENTS-DEFINITION-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-29
next_review_due: 2026-07-29
---

# 製品要件定義書

## 1. 目的

本書は `harness-auto-test-evidence` を 50万〜100万行級の製品実装へ進めるための
要件定義正本である。

`SPECIFICATION.md` は実装契約、`PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` は
製品グレード実装粒度を定義する。本書はその前段として、誰のどの業務課題を、
どの利用シナリオ、機能、非機能、受入条件で満たすのかを固定する。

詳細な story、acceptance、API、UI、data/legal、scale/performance、epic 分解は
以下を補助正本とする。

- `USER_STORY_MAP.md`
- `ACCEPTANCE_CRITERIA_MATRIX.md`
- `API_REQUIREMENTS.md`
- `UI_WORKFLOW_REQUIREMENTS.md`
- `DATA_RETENTION_LEGAL_REQUIREMENTS.md`
- `SCALE_PERFORMANCE_REQUIREMENTS.md`
- `IMPLEMENTATION_EPIC_BREAKDOWN.md`
- `PRODUCT_REQUIREMENTS_GAP_BACKLOG.md`
- `PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md`
- `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md`
- `PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md`
- `PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md`
- `TEST_INTEGRITY_IMPLEMENTATION_SPEC.md`
- `ENTERPRISE_CONTROL_STATE_TRANSITION_SPEC.md`
- `RELEASE_CANDIDATE_PACK_VALIDATOR_SPEC.md`
- `WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md`

要件定義としての目的:

- 実装者が最小CLIやadvisory artifactだけで完了扱いできないようにする
- 顧客、利用者、業務フロー、データ、権限、運用、検収条件を明確にする
- MVP / Team GA / Enterprise / Regulated の段階差を固定する
- 各要件が仕様、実装タスク、fixture、UAT、product-ready evidenceへ辿れるようにする
- 未仕様、浅い仕様、実装packet不足は `PRODUCT_REQUIREMENTS_GAP_BACKLOG.md` で
  open gap として管理し、閉じるまで50万〜100万行級の実装準備完了と呼ばない
- HATE-GAP-001..026 実装後に見えた追加不足は
  `PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md` で HATE-GAP-027+ として
  管理し、既存gap closure reportへ混ぜずに versioned expansion として扱う

## 2. Product Problem Statement

現代の開発組織では、CI結果、coverage、static analysis、E2E artifact、
contract test、mutation test、manual QA、release approval、agent task evidence が
分断されている。その結果、次が起きる。

| Problem ID | 問題 | 影響 |
|---|---|---|
| PROB-001 | テストが通った理由とリスク充足が結びつかない | high-risk change が低品質証跡で通る |
| PROB-002 | coverage が証拠として過大評価される | oracle のない実行が release safety と誤認される |
| PROB-003 | AI/agent 実装がテストを回避する | skip、mock abuse、test coupling が見逃される |
| PROB-004 | artifact に secret/PII/unsafe path が混入する | summary、外部export、監査資料で漏えいする |
| PROB-005 | QEG / Shipyard / RanD / manual-bb の判定境界が混ざる | release gate や上流判定を前段ツールが上書きする |
| PROB-006 | 大規模monorepoで risk/test/evidence の対応を追えない | QA/Release が差分影響を説明できない |
| PROB-007 | 監査時に同じ判断を再計算できない | SOC2/ISO/regulated review で証跡が弱い |
| PROB-008 | adapter追加が属人的 | 新test runner/coverage形式を安全に受け入れられない |
| PROB-009 | product readiness がreport名だけで過大表現される | 顧客・経営・監査に誤った完成claimが出る |
| PROB-010 | enterprise運用の権限/保持/監査/連携が後付けになる | 本番導入時に設計を作り直す |

## 3. Goals and Non-Goals

### 3.1 Goals

| Goal ID | Goal | Success measure |
|---|---|---|
| GOAL-001 | CI証跡を canonical bundle として再現可能にする | frozen input から同一 decision/evidence が再生成できる |
| GOAL-002 | risk/test/evidence の traceability を提供する | high-risk change の required evidence が sourceRefs 付きで説明される |
| GOAL-003 | AI/automation のテスト回避を検出する | test integrity signal が product readiness を降格できる |
| GOAL-004 | QEG optional evidence として安全に export する | HATE は QEG verdict を上書きせず、schema-compatible bundle を出す |
| GOAL-005 | local-first と enterprise-ready を両立する | P0 local loop は SaaSなしで動き、enterprise control は後段で追加可能 |
| GOAL-006 | artifact safety を product default にする | unsafe artifact は summary/QEG/export/dashboard から遮断される |
| GOAL-007 | adapter ecosystem を作る | adapter SDK と conformance suite で外部adapterを検証できる |
| GOAL-008 | audit/release/support に耐える evidence room を作る | release candidate pack と support diagnostic が安全に共有できる |

### 3.2 Non-Goals

| Non-Goal ID | Non-Goal |
|---|---|
| NGOAL-001 | HATE は QEG の release Gate evaluator、waiver、approval を再実装しない |
| NGOAL-002 | HATE は Shipyard の state machine / publish approval を再実装しない |
| NGOAL-003 | HATE は RanD requirements verdict を上書きしない |
| NGOAL-004 | HATE は manual-bb-test-harness の手動テスト設計・実施を代替しない |
| NGOAL-005 | HATE は coverage だけで release readiness を主張しない |
| NGOAL-006 | HATE は hosted SaaS なしで local precheck が動かない製品にしない |
| NGOAL-007 | HATE は customer source code、artifact body、secret、PII を telemetry に収集しない |
| NGOAL-008 | HATE は docs-only / fixture-only / report-only の作業を implemented と呼ばない |

## 4. Stakeholders and Personas

| Persona ID | Persona | Primary jobs | Required outcomes | Blocking pain |
|---|---|---|---|---|
| PER-DEV | Developer | PRで不足証跡を直す | 何が足りないか、どのtestを足すかが分かる | failureが抽象的で修正に時間がかかる |
| PER-QA | QA Lead | riskごとの証跡充足を見る | risk coverage と manual補完要求を管理できる | coverageとoracleの区別ができない |
| PER-REL | Release Manager | release前のevidence eligibilityを確認する | HATE precheck、QEG export、open riskを説明できる | gate直前に証跡不足が発覚する |
| PER-SEC | Security Engineer | artifact/SARIF/secret/PIIを確認する | unsafe artifactが漏れない | trace/log/screenshotに機密が混ざる |
| PER-AUD | Auditor | 後から判断を再計算する | frozen bundle、hash、sourceRefs、audit logが揃う | 監査時にCIログが消えている |
| PER-PLAT | Platform Admin | org/repo/profile/adapter/policyを運用する | RBAC、retention、connector、profile driftを管理できる | チームごとに品質証跡がばらつく |
| PER-EXEC | Engineering Executive | 品質投資とrelease riskを見る | portfolio health、risk debt、trendを把握する | 局所的なテスト成功しか見えない |
| PER-SUP | Support Engineer | 顧客環境の問題を診断する | safe diagnostic bundle と error remediation がある | raw artifactなしでは原因が追えない |

## 5. Primary User Journeys

### 5.1 Developer PR Evidence Loop

| Step | User action | System response | Acceptance |
|---|---|---|---|
| J-DEV-001 | PRでCIを実行する | HATE GitHub Action が test/coverage/artifact を収集する | summary と artifacts が生成される |
| J-DEV-002 | summaryを見る | hard DQ、soft gap、test integrity signal、recommendation を表示する | 修正対象 file/test/risk が分かる |
| J-DEV-003 | recommendationに従ってtestを足す | retry後に risk coverage が更新される | high-risk gap が消えるか manual request へ移る |
| J-DEV-004 | unsafe artifact が出る | quarantine と remediation が出る | unsafe path/content は summary に出ない |

### 5.2 QA Risk Coverage Review

| Step | User action | System response | Acceptance |
|---|---|---|---|
| J-QA-001 | risk coverage matrix を開く | changed risk、required layer、execution、oracle、coverage を表示する | high/critical risk が上に出る |
| J-QA-002 | oracle不足を見る | `risk_without_oracle` と manual-bb request を表示する | required_oracle_refs がある |
| J-QA-003 | manual補完を要求する | manual request artifact を作る | HATE は waiver にしない |
| J-QA-004 | risk debt を更新する | owner/status/age/audit event を残す | status遷移が監査可能 |

### 5.3 Release Evidence Review

| Step | User action | System response | Acceptance |
|---|---|---|---|
| J-REL-001 | release candidate pack を生成する | required product reports と QEG result refs を束ねる | missing_required_reports が明示される |
| J-REL-002 | QEG live/dry-run を実行する | validate/import/gate/record refs を保存する | HATE は verdict を改変しない |
| J-REL-003 | open risk を確認する | hard DQ、manual unresolved、unsupported claim を表示する | unresolved があれば release-ready にならない |

### 5.4 Auditor Replay

| Step | User action | System response | Acceptance |
|---|---|---|---|
| J-AUD-001 | old bundle を読み込む | local store が frozen bundle を再読込する | hash と schema version を検証する |
| J-AUD-002 | replay を実行する | derived outputs を再計算する | deterministic対象は byte-stable |
| J-AUD-003 | decision差分を見る | compare report が decision/score/risk debt の差分を出す | sourceRefs で説明できる |

### 5.5 Platform Admin Rollout

| Step | User action | System response | Acceptance |
|---|---|---|---|
| J-ADM-001 | org/workspace/repo を登録する | RBAC、profile、retention、adapter policy を設定できる | default policy が明示される |
| J-ADM-002 | adapter を追加する | conformance suite を実行する | failed adapter は有効化できない |
| J-ADM-003 | connector を dry-run する | SSO/SCIM/SIEM/warehouse/ticket 結果を保存する | failure は canonical bundle を変えない |

### 5.6 Security Artifact Review

| Step | User action | System response | Acceptance |
|---|---|---|---|
| J-SEC-001 | quarantine queue を確認する | secret/PII/path/archive/external URL/redaction failure を分類表示する | unsafe artifact は raw link を出さない |
| J-SEC-002 | SARIF/finding を確認する | changed high/critical finding と suppression state を表示する | suppression は sourceRef と owner を持つ |
| J-SEC-003 | diagnostic/support bundle を確認する | safe-to-share 判定と除外理由を表示する | customer code/secret/PII/artifact body を含まない |

### 5.7 Support Triage

| Step | User action | System response | Acceptance |
|---|---|---|---|
| J-SUP-001 | 顧客から diagnostic bundle を受け取る | version/profile/adapter/store/QEG compatibility を表示する | raw artifactなしで一次切り分けできる |
| J-SUP-002 | error code を検索する | remediation、known issue、migration note、rollback path を表示する | user-facing error は stable code を持つ |
| J-SUP-003 | incident candidate を作る | unsafe leak/wrong eligibility/schema drift/QEG incompatibility を分類する | incident timeline と owner を持つ |

## 6. Product Scope by Edition

| Capability | OSS/Local | Team | Enterprise | Regulated |
|---|---|---|---|---|
| CLI collect/normalize/precheck | required | required | required | required |
| Canonical schema and fixture | required | required | required | required |
| GitHub Action summary | optional | required | required | required |
| QEG optional export | optional | required | required | required |
| Adapter SDK/conformance | optional | required | required | required |
| Local store/replay | required | required | required | required |
| Hosted read model API | not required | optional | required | required |
| Dashboard | not required | optional | required | required |
| RBAC/audit/retention | local minimal | team audit | required | required |
| SSO/SCIM | not required | not required | required | required |
| SIEM/warehouse/ticket | not required | optional | required | required |
| Legal hold/evidence room | not required | optional | required | required |
| Attestation/compliance pack | not required | optional | optional | required |

Edition, entitlement, over-limit, and procurement must never change evidence eligibility,
QEG bundle content, or QEG verdict.

## 7. Functional Requirements

### 7.1 Evidence Ingestion and Normalization

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-ING-001 | GitHub Actions and generic CI context must normalize into run records | P0 | missing commit/run/time window is DQ or input failure |
| FR-ING-002 | JUnit dialects must support pytest/Jest/Vitest/Playwright/Surefire/Gradle/go-junit variants | P0 | dialect fixture matrix passes conformance |
| FR-ING-003 | pytest JSON, Vitest JSON, Jest JSON must preserve retry/flaky/snapshot metadata | P0 | JSON-only and no-junit fixtures remain eligible when sufficient |
| FR-ING-004 | coverage formats must include LCOV/Cobertura/JaCoCo/coverage.py contexts | P0 | coverage-only is not eligible as release evidence |
| FR-ING-005 | SARIF/Pact/Stryker/Playwright artifact evidence must map to canonical evidence graph | P0b | finding/contract/mutation/artifact edges are traceable |
| FR-ING-006 | Adapter failures must distinguish required input failure from optional parser failure | P0 | optional failure is visible, not hidden |
| FR-ING-007 | Adapter SDK must expose parser interface, capability manifest, and conformance runner | P1 | third-party adapter can self-test |

### 7.2 Evidence Graph and Risk Traceability

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-GRAPH-001 | requirement/risk/test/execution/coverage/finding/artifact/manual nodes must be first-class | P0b | graph fixture has all node types |
| FR-GRAPH-002 | high/critical changed risk must have required test layer and oracle requirement | P0b | missing requirement creates risk debt and manual request |
| FR-GRAPH-003 | coverage must not create execution evidence edge by itself | P0 | coverage_without_evidence is soft gap or hard DQ by profile |
| FR-GRAPH-004 | unsupported customer-facing claim must be explicit | P2 | unsupportedClaims blocks product-ready |
| FR-GRAPH-005 | sourceRefs must point to safe, normalized, non-secret references | P0 | local absolute paths excluded from public summary |

### 7.3 Test Integrity and Anti-Abuse

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-TI-001 | Detect new skip/xfail/only/todo/focused tests in changed test scope | P0 | `only` is hard DQ in release/product profile |
| FR-TI-002 | Detect mock abuse and distinguish external-boundary mocks | P1 | behavior-under-test mock blocks product-ready |
| FR-TI-003 | Detect weak assertion quality | P1 | no-assertion/snapshot-only required risk creates hold |
| FR-TI-004 | Detect implementation-test coupling | P1 | production branch on fixture/test/env marker is hard DQ |
| FR-TI-005 | Detect risk without oracle | P0b | high/critical risk without oracle holds |
| FR-TI-006 | Detect coverage without evidence | P0 | coverage-only required risk holds or hard DQ |
| FR-TI-007 | Require human review for suspicious AI avoidance | P1 | unresolved manual_review_required blocks product-ready |

### 7.4 Artifact Safety and Privacy

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-SEC-001 | Secret scan must run on logs, trace metadata, summaries, diagnostic bundles | P0 | fake token fixture is quarantined |
| FR-SEC-002 | PII/path safety must detect local absolute path, Windows drive, UNC, traversal, symlink | P0 | unsafe paths do not appear in summary/export |
| FR-SEC-003 | Archive policy must bound expanded size, file count, nested archive, MIME mismatch | P1 | unsafe archive is quarantined |
| FR-SEC-004 | External URL artifact references must be allowlisted and SSRF-safe | P1 | metadata/localhost URL is blocked |
| FR-SEC-005 | Redaction pending/failed must block public/export exposure | P0 | failed redaction keeps safe_for_summary=false |

### 7.5 Store, Replay, and History

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-STO-001 | Local store must persist run/bundle/evidence/artifact/risk debt/audit indexes | P1 | store query reloads resources |
| FR-STO-002 | Canonical bundle must be immutable and hash verified | P1 | mutation changes digest and doctor reports corruption |
| FR-STO-003 | Replay must regenerate deterministic outputs from frozen inputs | P1 | replay report is byte-stable for deterministic artifacts |
| FR-STO-004 | Compare must explain decision/score/risk debt changes between runs | P1 | compare report links sourceRefs |
| FR-STO-005 | Store migration must have before/after fixtures and rollback path | P2 | migration failure does not destroy prior bundle |

### 7.6 API and Dashboard

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-API-001 | API must provide runs/evidence/risks/artifacts/doctor/risk-debt/profiles/bundles/exports resources | P2 | contract tests cover envelope, errors, authz, pagination |
| FR-API-002 | Read model must expose staleness and source bundle hash | P2 | stale response is explicit |
| FR-API-003 | Dashboard must be read-model consumer and must not compute verdicts | P2 | view model source refs are API/read model based |
| FR-API-004 | Dashboard must include overview, risk coverage, evidence graph, adapter health, artifact safety, doctor, risk debt, release pack, admin | P2 | UAT covers each view |
| FR-API-005 | Restricted artifacts must not be linked to unauthorized users | P2 | RBAC UAT denies raw artifact |

### 7.7 Enterprise Controls

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-ENT-001 | RBAC must define roles, permissions, resource scopes, deny reasons | P2 | allow/deny matrix passes |
| FR-ENT-002 | Audit log must be append-only and source-backed | P2 | hash chain fixture detects tampering |
| FR-ENT-003 | Retention/legal hold/export/delete must respect artifact classification | P2 | legal hold blocks delete |
| FR-ENT-004 | SSO/SCIM/SIEM/warehouse/ticket connectors must support dry-run and non-gating failure | P3 | connector failure leaves canonical bundle unchanged |
| FR-ENT-005 | Residency/deployment modes must define data class routing and backup/recovery | P2 | local/hosted/private/airgap fixtures pass |
| FR-ENT-006 | Assurance pack must include control mapping, evidence room, limitations, open findings | P3 | auditor walkthrough fixture passes |

### 7.8 Operations, Support, and Commercial Truthfulness

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-OPS-001 | Every user-facing failure must have stable error code and remediation | P0 | error catalog covers generated findings |
| FR-OPS-002 | Support diagnostic bundle must be safe to share | P2 | no secret/PII/customer code/artifact body |
| FR-OPS-003 | Migration and rollback guide must accompany breaking schema/store changes | P2 | release pack includes migration report |
| FR-OPS-004 | Incident classes must cover unsafe leak, wrong eligibility, schema drift, QEG incompatibility | P2 | incident fixture has timeline and postmortem state |
| FR-OPS-005 | Customer-facing docs must not claim unsupported/planned capability as available | P2 | docs freshness/overclaim check blocks product-ready |
| FR-OPS-006 | Commercial commitments must map to implemented evidence or unsupported claim | P2 | unsupported commitment appears in commercial report |

### 7.9 UI and Workflow Requirements

The product must not treat a generated HTML report as a full dashboard. UI requirements are
workflow requirements: each screen must answer a user question, expose sourceRefs, respect RBAC,
and handle empty, loading, error, stale, unauthorized, and high-volume states.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-UI-001 | Run Overview must explain decision, profile, DQ, AETE, parser failures, and previous-run diff | P2 | UAT covers pass/conditional/hold/hard_dq states |
| FR-UI-002 | Risk Coverage must let QA filter by severity, owner, layer, execution status, oracle status, and manual request | P2 | high/critical risk without oracle is visible without scrolling through low risk |
| FR-UI-003 | Evidence Graph must support node search, edge filtering, sourceRef drawer, unsafe artifact placeholders, and unsupported claim view | P2 | user can trace requirement -> risk -> test -> evidence -> artifact |
| FR-UI-004 | Adapter Health must show conformance results, parser failure trends, dialect limits, and enablement state | P2 | failed adapter cannot be marked healthy |
| FR-UI-005 | Artifact Safety must show classification, redaction, quarantine reason, export eligibility, and remediation | P2 | restricted artifact link is hidden for unauthorized users |
| FR-UI-006 | Doctor must rank findings by severity, affected persona, remediation command, and blocking release effect | P2 | P0/P1 findings appear above advisory warnings |
| FR-UI-007 | Risk Debt must support lifecycle transition, owner assignment, stale escalation, and audit trail | P2 | illegal transition is denied with reason |
| FR-UI-008 | Release Pack view must list required reports, missing evidence, QEG refs, unsupported claims, and manual review status | P2 | product-ready cannot be shown when required report is missing |
| FR-UI-009 | Admin console must manage org/workspace/repo, profile, adapter, retention, connector, and RBAC policy | P3 | policy change emits audit event and preview diff |
| FR-UI-010 | UI must support accessibility and localization without changing stable IDs, severity, error code, or schema fields | P2 | color-only severity fails UAT |

### 7.10 API Contract Requirements

API requirements must be strong enough to drive independent client, dashboard, CLI, and connector
implementations.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-APIX-001 | Every API resource must define request schema, response schema, error schema, pagination, filtering, sorting, and authorization | P2 | contract test fails for undocumented field or missing error |
| FR-APIX-002 | Bundle import API must be idempotent by bundle hash and reject schema/hash/sourceRef mismatch | P2 | duplicate import returns existing resource |
| FR-APIX-003 | Risk debt PATCH must enforce legal transitions and emit audit events | P2 | transition matrix fixture passes |
| FR-APIX-004 | Export APIs must be asynchronous, non-gating, retryable, and record canonical hash before/after | P2 | failed export leaves canonical hash unchanged |
| FR-APIX-005 | Admin APIs must support dry-run policy changes before committing | P3 | diff preview exists and no audit mutation occurs on dry-run |
| FR-APIX-006 | API versioning must distinguish compatible additions, deprecated fields, and breaking changes | P2 | compatibility matrix and migration tests exist |
| FR-APIX-007 | API must expose rate limit, request id, staleness, and partial-result metadata | P2 | stale/partial response is explicit |
| FR-APIX-008 | Unauthorized responses must not reveal restricted artifact path, secret pattern, or tenant existence | P2 | negative authz fixture passes |

### 7.11 Adapter and Format Coverage Requirements

Adapter requirements must specify concrete format families, dialect classes, and conformance gates.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-ADP-001 | Test result adapters must cover JUnit family, pytest JSON, Jest JSON, Vitest JSON, Playwright JSON/JUnit, and OTR-like event streams | P0-P1 | each family has valid, malformed, partial, retry, skip, flaky fixtures |
| FR-ADP-002 | Coverage adapters must cover LCOV, Cobertura, JaCoCo, coverage.py JSON/XML contexts, branch coverage, and path normalization variants | P0-P1 | coverage fixture matrix includes Windows/container/workspace paths |
| FR-ADP-003 | Static/quality adapters must cover SARIF 2.1.0, Sonar-like issue export, CodeQL-like severity, and suppression state | P1 | high/critical changed-path finding affects risk graph |
| FR-ADP-004 | Contract adapters must cover Pact verification, can-i-deploy style summary, provider/consumer version, and failed required contract | P1 | failed required contract creates contradiction edge |
| FR-ADP-005 | Mutation adapters must cover Stryker-style killed/survived/timeout/no-coverage status and threshold policies | P1 | survived required mutant lowers oracle strength |
| FR-ADP-006 | Artifact adapters must cover trace, screenshot, video, log, archive, external URL, symlink, and missing artifact references | P0-P1 | unsafe required artifact is quarantined and visible |
| FR-ADP-007 | Adapter conformance must separate parser failure, capability gap, unsupported dialect, unsafe artifact, and schema violation | P1 | conformance report has distinct failure classes |
| FR-ADP-008 | Adapter enablement must be profile-aware and tenant/repo scoped in enterprise mode | P3 | org policy can disable unsafe adapter without changing old bundles |

### 7.12 Large-Scale and Performance Requirements

50万行以上の implementation scope implies high-volume data handling. Requirements must prevent
toy data structures from becoming the accepted design.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-SCALE-001 | Ingest must stream or chunk large test/coverage/artifact inputs without loading unbounded files into memory | P1 | large fixture profile records memory and time budget |
| FR-SCALE-002 | Store indexes must support repo/run/evidence/risk/artifact queries at 100k tests and 100k artifacts metadata | P1 | query latency budget is measured |
| FR-SCALE-003 | Dashboard/API must paginate large result sets and avoid rendering all evidence nodes at once | P2 | graph view handles large fixture with aggregation |
| FR-SCALE-004 | CI must support shard/matrix aggregation and partial rerun without corrupting canonical identity | P1 | shard fixture produces deterministic aggregate |
| FR-SCALE-005 | Release pack generation must be incremental and cache derived read models safely | P2 | cache invalidation fixture detects stale source bundle |
| FR-SCALE-006 | Artifact safety scan must enforce bounded archive expansion and timeout policies | P1 | unsafe archive fixture is stopped deterministically |

### 7.13 Observability and Product Operations Requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-OBS-001 | Each pipeline stage must emit latency, count, error, DQ, parser failure, safety, and export metrics | P2 | metrics fixture maps to dashboard and support bundle |
| FR-OBS-002 | Logs must be structured, redacted, correlated by run_id/request_id, and safe for support sharing | P2 | log fixture contains no secret/raw path |
| FR-OBS-003 | Alerts must exist for unsafe leak, wrong eligibility, schema drift, QEG incompatibility, and connector failure spike | P3 | incident class and alert routing are documented |
| FR-OBS-004 | Support diagnostic must include version matrix, profile diff, adapter health, store integrity, and recent failures | P2 | support UAT can triage without raw customer code |
| FR-OBS-005 | Product analytics must be opt-in, aggregate, and prohibited from collecting raw code/test/artifact content | P2 | prohibited telemetry fixture is rejected |

### 7.14 Migration, Compatibility, and Lifecycle Requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-LIFE-001 | Schema, store, API, profile, adapter manifest, and dashboard view model versions must have compatibility policy | P2 | compatibility matrix is generated |
| FR-LIFE-002 | Breaking changes must include migration guide, before/after fixtures, rollback plan, and deprecation window | P2 | release pack blocks missing migration |
| FR-LIFE-003 | Old bundles must remain readable after minor version upgrade | P2 | old bundle replay fixture passes |
| FR-LIFE-004 | Deprecated field use must produce warning with removal version and replacement | P2 | deprecated fixture produces expected warning |
| FR-LIFE-005 | Legal hold and retention must survive migration without deleting protected metadata | P3 | migration fixture preserves legal hold |

### 7.15 Company Rollout and Adoption Requirements

Company use requires more than a working checker. The product must support
multi-repository rollout, staged adoption, exception handling, and adoption
evidence so internal platform teams can deploy HATE without turning every repo
into a one-off project.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-ROLL-001 | Rollout waves must define target repos, owners, policy template, entry criteria, exit criteria, and rollback plan | P2 | rollout wave fixture shows staged adoption and failed-wave rollback |
| FR-ROLL-002 | Repo onboarding status must distinguish not-started, bootstrapping, evidence-missing, policy-blocked, active, and suspended | P2 | status transition matrix rejects illegal jumps |
| FR-ROLL-003 | Exceptions must be time-bound, owner-backed, scoped to repo/policy/evidence class, and visible in release pack | P2 | expired exception blocks product-ready |
| FR-ROLL-004 | Adoption reports must aggregate repo coverage, active blockers, open risk debt, and time-to-green without raw code or test names | P2 | portfolio report passes privacy fixture |

### 7.16 CI, SCM, and Repository Provider Coverage

The product must not hide provider-specific work behind the word `generic`.
Enterprise adoption requires explicit behavior for common SCM and CI systems,
including permission boundaries, artifact ownership, annotations, and reruns.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-CI-001 | Provider contracts must cover GitHub, GitLab, Azure DevOps, Jenkins, CircleCI, Bitbucket, Buildkite, and generic local imports | P1-P2 | provider matrix has positive and denied-permission fixtures |
| FR-CI-002 | Each provider must define commit identity, PR/MR identity, run attempt, artifact lifetime, annotation target, and rerun semantics | P1-P2 | identity normalization fixture is deterministic |
| FR-CI-003 | Missing or ambiguous provider identity must become input failure, not silent advisory output | P1 | ambiguous run fixture is hard DQ or input failure by profile |
| FR-CI-004 | Provider integrations must declare minimum permissions and deny broad/admin scopes unless explicitly required | P1 | overbroad permission fixture is denied |

### 7.17 Language and Test Runner Coverage

Adapter coverage must match real polyglot company repositories. The product may
stage support by milestone, but the PRD must name the required runner families
so implementation cannot stop at Python and JavaScript.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-LANG-001 | Test result support must include Python, JavaScript/TypeScript, Java/Kotlin, Go, .NET, Rust, C/C++, Ruby, and PHP runner families | P1-P3 | runner family corpus records supported, partial, and unsupported states |
| FR-LANG-002 | .NET xUnit/NUnit/MSTest, Rust nextest/libtest, CTest, Cypress, Mocha, RSpec, PHPUnit, and monorepo task runners must have dialect entries | P2-P3 | dialect matrix fixture prevents untracked parser assumptions |
| FR-LANG-003 | Unsupported runner output must produce a capability gap with remediation, not malformed evidence | P1 | unsupported runner fixture emits adapter capability gap |
| FR-LANG-004 | Runner support claims must be tied to conformance fixtures and release notes | P2 | docs claim without conformance fixture blocks product-ready |

### 7.18 Real Repository Evaluation Requirements

Real repository evaluation must become a recurring product quality loop rather
than an occasional manual trial. It must cover repository size, language mix,
CI provider, history, failure modes, and regression trends.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-REEVAL-001 | Evaluation roster must include small, medium, large, monorepo, polyglot, flaky, artifact-heavy, and security-heavy repositories | P1 | roster fixture labels repo class and allowed data exposure |
| FR-REEVAL-002 | Evaluation runs must record baseline, current result, regression, timeout, parser gap, and manual review outcome | P1 | regression fixture produces blocked evaluation report |
| FR-REEVAL-003 | Timeout and resource budgets must be per repo class and must not hide missing evidence | P1 | timeout fixture records incomplete evidence as hold |
| FR-REEVAL-004 | Evaluation trend must feed roadmap priority without exposing customer source or raw test content | P2 | trend report uses aggregate safe fields only |

### 7.19 Organizational Governance Requirements

Enterprise quality gates are operated by people and committees, not only by
code. HATE must model policy approval, exception review, periodic audit, and
delegation boundaries as first-class requirements.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-GOV-001 | Policy templates must have author, approver, effective date, review cadence, affected repo set, and rollback owner | P2 | policy template without approver is hold |
| FR-GOV-002 | Exception requests must require owner, expiry, rationale, affected risks, compensating evidence, and reviewer decision | P2 | exception missing compensating evidence blocks product-ready |
| FR-GOV-003 | Governance review packets must list policy drift, expired exceptions, repeated waivers, and unresolved high-risk debt | P2 | governance packet fixture ranks blockers |
| FR-GOV-004 | Delegation rules must prevent service accounts or single roles from approving their own quality exceptions | P2 | self-approval fixture is denied |

### 7.20 Security Procurement and Trust Package Requirements

Company adoption usually requires a security/procurement packet before broad
rollout. HATE must produce and validate safe trust evidence without leaking
customer artifacts or overstating certification.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-PROC-001 | Security review packet must include architecture, data flow, data classes, subprocessors, encryption, secrets handling, and retention summary | P2 | packet fixture rejects missing data flow |
| FR-PROC-002 | Compliance claims must distinguish implemented control, inherited control, external attestation, roadmap, and unsupported claim | P2 | unsupported certification claim blocks product-ready |
| FR-PROC-003 | Vulnerability response requirements must define intake, severity, SLA, customer notice, fixed version, and exception expiry | P2 | overdue critical vulnerability blocks release pack |
| FR-PROC-004 | Procurement export must contain only safe summaries and approved evidence references | P2 | raw artifact in procurement packet is denied |

### 7.21 Value Measurement and ROI Requirements

The product must measure whether it improves quality work. Product analytics
alone is insufficient; HATE needs quality outcome metrics that justify company
adoption while preserving privacy.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-VALUE-001 | Value reports must track review time saved, risk debt burn-down, release blocker lead time, repeat finding rate, and avoided unsupported claims | P2 | value report fixture computes aggregate deltas |
| FR-VALUE-002 | ROI metrics must be explainable from safe evidence refs and must not use raw source, raw test names, or individual developer ranking | P2 | privacy fixture denies individual leaderboard |
| FR-VALUE-003 | Quality outcome metrics must separate detection volume from meaningful fixed risk | P2 | noisy finding fixture does not improve value score |
| FR-VALUE-004 | Executive summaries must include limitations, confidence, sample size, and missing baseline warnings | P2 | missing baseline produces soft gap or hold |

### 7.22 Daily Developer Experience Requirements

Developers need fast, actionable, low-noise feedback where they already work.
The product must define PR comments, IDE/CLI loops, notifications, suppression
UX, and recommendation quality so HATE is usable every day.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-DX-001 | PR/MR feedback must group findings by fix action, risk impact, owner, and blocking status with stable deep links | P1 | PR comment fixture has actionable grouping and no raw secret |
| FR-DX-002 | CLI and IDE flows must support local explain, local fixture replay, recommendation preview, and offline-safe mode | P2 | offline local fixture produces same deterministic recommendation |
| FR-DX-003 | Suppression UX must require reason, owner, expiry, affected sourceRefs, and alternative evidence | P1 | broad suppression fixture is denied |
| FR-DX-004 | Recommendation quality must be evaluated for precision, duplication, stale refs, and fix verification outcome | P2 | bad recommendation fixture lowers recommendation quality report |

### 7.23 Core Analysis Expansion Requirements

HATE must grow as an evidence analysis engine, not only as an adapter/report
collector. These requirements are functional requirements for what the product
can analyze, infer, classify, reconcile, and explain from test evidence.

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-ANALYSIS-001 | Impact analysis must infer affected tests, requirements, risks, owners, and evidence from changed files using dependency, import, ownership, and history signals | P1 | changed dependency fixture produces affected-test candidates with confidence and sourceRefs |
| FR-ANALYSIS-002 | Test recommendation must propose add, modify, rerun, or manual-review actions with required oracle, test layer, risk ref, and verification command | P1 | missing-oracle fixture produces actionable recommendation, not generic advice |
| FR-ANALYSIS-003 | Flaky classification must separate code, test, environment, infrastructure, timeout, order-dependent, and unknown flake classes from retry/history/environment evidence | P1 | environment-flake fixture is not misclassified as product pass |
| FR-ANALYSIS-004 | Oracle classification must distinguish exact value, invariant, property, metamorphic, snapshot, approval, contract, mutation-backed, manual, and no-oracle evidence | P1 | snapshot-only critical risk remains hold unless semantic guard exists |
| FR-ANALYSIS-005 | Evidence synthesis must combine execution, coverage, mutation, contract, static finding, artifact, and manual evidence into risk-level and requirement-level confidence | P1 | contradictory weak evidence does not inflate readiness |
| FR-ANALYSIS-006 | Test code quality analysis must detect duplicate tests, overbroad snapshot assertions, huge fixture dependency, nondeterministic time/random/network usage, sleeps, and order dependence | P1 | sleep-based test fixture emits test-quality finding |
| FR-ANALYSIS-007 | Execution environment diff analysis must compare OS, runtime, browser, container image, dependency lock, env vars, cache, service dependency, and shard topology across attempts | P1 | runtime-version drift fixture explains result change |
| FR-ANALYSIS-008 | Cross-evidence contradiction detection must surface inconsistent signals between pass/fail tests, coverage, mutation, contract, static findings, artifact safety, and release claims | P1 | pass-with-critical-finding fixture blocks readiness |
| FR-ANALYSIS-009 | Historical regression analysis must detect recurring failures, trend degradation, risk debt burn-up, flaky rate drift, parser regression, and evidence quality regression | P2 | recurring failure fixture links prior runs and blocks overclaim |
| FR-ANALYSIS-010 | Multi-audience report generation must derive developer, QA, release, QEG, and machine summaries from the same canonical evidence without recomputing verdicts | P2 | audience report fixture keeps identical sourceRefs across views |
| FR-ANALYSIS-011 | Fixture and corpus quality detection must flag stale fixtures, expected-output leakage, fixture-name coupling risk, duplicate cases, weak negative coverage, and schema drift | P1 | fixture-name-coupled expected fixture is hold |
| FR-ANALYSIS-012 | Adapter capability diff must compare raw input samples against normalized output to identify dropped fields, unsupported dialect features, lossy transforms, and capability claim drift | P1 | lossy adapter fixture emits capability diff finding |

## 8. Non-Functional Requirements

| ID | Category | Requirement | Target |
|---|---|---|---|
| NFR-001 | Determinism | Same input/schema/profile produces same deterministic artifacts | 100% deterministic for declared artifacts |
| NFR-002 | Scale | Single run supports 100k tests, 10M coverage line hits, 100k artifacts metadata | design and load fixture required |
| NFR-003 | Performance | Standard PR precheck finishes within 5 minutes | P95 in CI fixture |
| NFR-004 | Local-first | P0/P1 local path works without network/SaaS/QEG runtime | required |
| NFR-005 | Security | No secret/PII/raw path in public surfaces | zero known leak |
| NFR-006 | Availability | Hosted API/dashboard target monthly 99.9% | Enterprise/Regulated |
| NFR-007 | Compatibility | Minor schema versions are backward compatible | migration tests |
| NFR-008 | Observability | Each pipeline stage emits latency/error/DQ/safety counters | metrics fixture |
| NFR-009 | Accessibility | Severity/status must not rely on color only | dashboard UAT |
| NFR-010 | Privacy | Telemetry never includes raw test title/body/path/artifact content | prohibited signal tests |
| NFR-011 | Auditability | Every product-ready claim has evidence refs | release pack validation |
| NFR-012 | Supportability | Diagnostic bundle is sufficient for first-line triage | support UAT |
| NFR-013 | Adoption scalability | 500 repositories can be staged through rollout waves without global policy mutation | rollout portfolio fixture |
| NFR-014 | Provider coverage | Each claimed CI/SCM provider has identity, permission, artifact, and rerun contract tests | provider matrix |
| NFR-015 | Value accountability | Quality value reports show confidence and limitations, not only activity volume | value report UAT |
| NFR-016 | Developer feedback latency | Local explain and PR summary generation stay fast enough for daily PR use | P95 latency budget by repo class |
| NFR-017 | Analysis explainability | Every inferred affected test, recommendation, flake class, contradiction, and confidence score has sourceRefs and confidence rationale | analysis fixture |
| NFR-018 | No hidden inference | Inference failures must become explicit unknown/hold findings, not silent pass or readiness inflation | negative analysis fixture |

## 9. Data Requirements

| Data Entity | Required attributes | Retention/Safety |
|---|---|---|
| Organization | id, name, edition, policies, entitlements | tenant-scoped |
| Workspace | id, org_id, region, policy refs | tenant-scoped |
| Repository | repo_ref, provider, default branch, owners | internal |
| Run | run_id, attempt, commit, base, CI metadata, profile | audit retained |
| EvidenceBundle | hash, schema, inputs, outputs, sourceRefs | immutable |
| TestRecord | canonical id, status, duration, retry, oracle metadata | normalized |
| CoverageSlice | file, line/branch, context, test refs | no raw source body |
| Artifact | id, hash, type, classification, safety checks | classification-based |
| RiskDebt | id, severity, status, owner, age, sourceRefs | lifecycle tracked |
| TestIntegritySignal | signal id, severity, refs, decision impact | product-ready blocker |
| AuditEvent | actor, action, target, before/after, hash link | append-only |
| ConnectorResult | provider, status, errors, non_gating, hash before/after | non-gating |
| RolloutWave | wave id, repo set, owners, entry/exit criteria, rollback state | portfolio scoped |
| ProviderIntegration | provider, permission set, identity mapping, artifact policy, rerun policy | tenant scoped |
| RunnerDialect | language, runner, format, support state, conformance fixture refs | public metadata |
| GovernanceException | owner, expiry, rationale, affected risks, compensating evidence | audit retained |
| TrustPacket | data flow, controls, attestations, unsupported claims, safe evidence refs | export safe |
| ValueMetric | metric id, aggregate value, baseline, confidence, limitations | no individual ranking |
| DeveloperFeedback | finding group, action, deep link, suppression state, recommendation quality | repo scoped |
| ImpactAnalysis | changed refs, affected tests, affected requirements, confidence, rationale | source-backed |
| TestRecommendation | action, target, risk refs, required oracle, command, verification status | no generic advice |
| FlakyClassification | class, attempts, history refs, environment deltas, confidence | explainable |
| OracleAssessment | oracle class, semantic guard, risk coverage, confidence | risk scoped |
| EvidenceSynthesis | requirement/risk confidence, contributing evidence, contradictions, limits | no hidden inflation |
| TestQualityFinding | pattern, affected test, severity, readiness effect, remediation | test scoped |
| EnvironmentDiff | runtime, image, dependency, cache, service, shard deltas | attempt scoped |
| ContradictionFinding | evidence refs, contradiction type, blocking effect, sourceRefs | release scoped |
| FixtureQualityFinding | fixture id, issue type, coupling risk, stale status, schema drift | corpus scoped |
| AdapterCapabilityDiff | adapter id, raw field, normalized field, loss type, claim drift | conformance scoped |

## 10. Authorization Requirements

| Role | Must be able to | Must not be able to |
|---|---|---|
| Viewer | read safe summaries and aggregate dashboards | read restricted/raw artifacts |
| Developer | run precheck, view own repo evidence, import local bundle | change org policy or approval |
| QA Lead | manage risk debt and manual requests | override QEG verdict |
| Release Manager | generate release candidate pack | modify canonical bundle |
| Security Reviewer | view quarantine/security findings | approve release alone |
| Platform Admin | manage org/profile/adapter/retention/connectors | alter immutable evidence silently |
| Auditor | read evidence room and audit log | mutate evidence or policy |
| Service Account | perform configured automation | replace human review record |
| Governance Reviewer | approve policy templates and scoped exceptions | approve own exception or bypass expiry |
| Procurement Reviewer | read trust packet and safe evidence summaries | access raw artifacts or customer code |
| Engineering Manager | view aggregate adoption and value reports | view individual developer ranking from HATE telemetry |

## 11. Acceptance and UAT

| Acceptance ID | Scope | Required evidence |
|---|---|---|
| AC-REQ-001 | Developer PR loop | CI summary, recommendation, fixed rerun |
| AC-REQ-002 | QA high-risk oracle | risk_without_oracle fixture, manual request |
| AC-REQ-003 | Test integrity | focused-test, mock-abuse, no-assertion, fixture-coupling fixtures |
| AC-REQ-004 | Artifact safety | secret/PII/path/archive/external URL fixtures |
| AC-REQ-005 | QEG boundary | validate/import refs and verdict_modified_by_hate=false |
| AC-REQ-006 | Replay/audit | frozen bundle replay and compare |
| AC-REQ-007 | API/dashboard | contract tests and UI UAT per required view |
| AC-REQ-008 | RBAC/audit/retention | allow/deny, hash chain, legal hold fixtures |
| AC-REQ-009 | Connector non-gating | connector failure leaves canonical hash unchanged |
| AC-REQ-010 | Release pack | required reports, open risks, unsupported claims |
| AC-REQ-011 | Support/ops | safe diagnostic, error catalog, migration/rollback |
| AC-REQ-012 | Commercial truthfulness | unsupported claim blocks product-ready |
| AC-REQ-013 | UI workflow | overview/risk/evidence/adapter/artifact/doctor/risk-debt/release/admin views with empty/error/stale/authz states |
| AC-REQ-014 | API contract | request/response/error/pagination/filter/authz/idempotency/versioning contract tests |
| AC-REQ-015 | Adapter corpus | dialect matrix and conformance report for test/coverage/static/contract/mutation/artifact adapters |
| AC-REQ-016 | Scale and performance | 100k test / 10M coverage / 100k artifact metadata design fixture and measured budgets |
| AC-REQ-017 | Observability | structured metrics/logs/alerts/support diagnostics/telemetry privacy fixtures |
| AC-REQ-018 | Lifecycle compatibility | schema/store/API/profile/adapter/view-model migration, deprecation, rollback fixtures |
| AC-REQ-019 | Company rollout | rollout wave, repo status, exception expiry, portfolio adoption fixtures |
| AC-REQ-020 | CI/SCM provider coverage | provider identity, permission, artifact lifetime, annotation, rerun fixtures |
| AC-REQ-021 | Language and runner coverage | polyglot runner dialect matrix and unsupported runner capability-gap fixtures |
| AC-REQ-022 | Real repository evaluation | recurring roster, baseline, regression, timeout, trend fixtures |
| AC-REQ-023 | Organizational governance | policy approval, exception review, delegation denial, governance packet fixtures |
| AC-REQ-024 | Security procurement and trust packet | security review packet, compliance claim, vulnerability SLA, safe procurement export fixtures |
| AC-REQ-025 | Value measurement and ROI | safe aggregate value metrics, confidence, limitation, missing baseline fixtures |
| AC-REQ-026 | Daily developer experience | PR/MR feedback, local explain, suppression UX, recommendation quality fixtures |
| AC-REQ-027 | Impact analysis | changed dependency, ownership, history, affected-test confidence fixtures |
| AC-REQ-028 | Test recommendation | add/modify/rerun/manual actions with oracle and command verification fixtures |
| AC-REQ-029 | Flaky classification | code/test/environment/infrastructure/order/timeout flake fixtures |
| AC-REQ-030 | Oracle classification | exact/invariant/property/metamorphic/snapshot/contract/manual/no-oracle fixtures |
| AC-REQ-031 | Evidence synthesis | risk and requirement confidence with contradiction and weak-evidence fixtures |
| AC-REQ-032 | Test code quality | duplicate, snapshot-only, huge fixture, nondeterministic, sleep/order fixtures |
| AC-REQ-033 | Environment diff | OS/runtime/browser/container/cache/env/shard drift fixtures |
| AC-REQ-034 | Cross-evidence contradiction | pass-with-critical-finding, coverage-up-mutation-down, contract-schema conflict fixtures |
| AC-REQ-035 | Historical regression | recurring failure, trend degradation, parser regression, risk debt burn-up fixtures |
| AC-REQ-036 | Multi-audience reports | developer/QA/release/QEG/machine views from identical sourceRefs fixtures |
| AC-REQ-037 | Fixture corpus quality | stale, duplicate, expected leakage, fixture-name coupling, schema drift fixtures |
| AC-REQ-038 | Adapter capability diff | raw-vs-normalized field loss and capability claim drift fixtures |

## 12. Release Stage Requirements

| Stage | Entry criteria | Exit criteria |
|---|---|---|
| Prototype | P0a/P0b local fixture exists | golden path and QEG export pass |
| Internal Alpha | adapter expansion and risk graph available | 3 internal repos replayable |
| Private Beta | local store, test integrity, artifact safety, doctor stable | 3 customer-like repos pass UAT |
| Team GA | GitHub Action, adapter SDK, QEG export, support docs, daily developer feedback, provider matrix | no open P0/P1 product blockers and developer feedback UAT pass |
| Enterprise Ready | API/dashboard/RBAC/audit/retention/connectors, rollout waves, governance, DR, value reporting ready | enterprise-control-report and rollout/governance reports pass |
| Regulated Ready | assurance/evidence room/legal hold/compliance pack, trust packet, dependency compliance, procurement export ready | auditor and procurement walkthrough pass |

## 13. Requirement Traceability

Every requirement must trace to:

- source requirement ID
- specification section
- implementation task ID
- schema/API contract when applicable
- fixture IDs
- positive and negative tests
- UAT acceptance ID
- product-ready evidence report

No requirement is accepted when it has only prose and no fixture/test/evidence path.

### 13.1 Requirement Family Traceability Matrix

| Requirement family | Journeys | Acceptance IDs | Product-grade tasks | Evidence reports |
|---|---|---|---|---|
| `FR-ING-*` | J-DEV, J-REL, J-ADM | AC-REQ-001, AC-REQ-015 | HATE-PG-001, HATE-PG-002 | adapter-conformance-report, schema-validation-report |
| `FR-GRAPH-*` | J-QA, J-REL, J-AUD | AC-REQ-002, AC-REQ-006, AC-REQ-010 | HATE-PG-003 | product-readiness-report, release-candidate-pack |
| `FR-TI-*` | J-DEV, J-QA, J-REL | AC-REQ-003 | HATE-PG-013 | test-integrity-report |
| `FR-SEC-*` | J-DEV, J-SEC, J-REL | AC-REQ-004 | HATE-PG-004 | security-quarantine-report |
| `FR-STO-*` | J-AUD, J-REL | AC-REQ-006, AC-REQ-018 | HATE-PG-005 | store-replay-report |
| `FR-API-*`, `FR-APIX-*` | J-DEV, J-QA, J-REL, J-ADM | AC-REQ-007, AC-REQ-014 | HATE-PG-007 | api-contract-report |
| `FR-UI-*` | J-DEV, J-QA, J-REL, J-ADM | AC-REQ-013 | HATE-PG-008 | dashboard-uat-report |
| `FR-ENT-*` | J-ADM, J-AUD, J-REL | AC-REQ-008, AC-REQ-009 | HATE-PG-009, HATE-PG-010 | enterprise-control-report |
| `FR-OPS-*`, `FR-OBS-*` | J-SUP, J-REL, J-ADM | AC-REQ-011, AC-REQ-017 | HATE-PG-011 | support-ops-report |
| `FR-SCALE-*` | J-DEV, J-QA, J-REL | AC-REQ-016 | HATE-PG-001, HATE-PG-003, HATE-PG-005, HATE-PG-007, HATE-PG-008, HATE-PG-014 | scale-performance-report |
| `FR-LIFE-*` | J-AUD, J-ADM, J-REL | AC-REQ-018 | HATE-PG-005, HATE-PG-011, HATE-PG-012, HATE-PG-015 | migration-compatibility-report |
| `FR-OPS-005`, `FR-OPS-006` | J-REL, J-SUP | AC-REQ-010, AC-REQ-012 | HATE-PG-011, HATE-PG-012, HATE-PG-016 | release-candidate-pack, commercial-truthfulness-report |
| `FR-ROLL-*` | J-ADM, J-SUP, J-REL | AC-REQ-019 | HATE-GAP-041 | rollout-adoption-report |
| `FR-CI-*` | J-DEV, J-ADM, J-REL | AC-REQ-020 | HATE-GAP-042 | provider-integration-report |
| `FR-LANG-*` | J-DEV, J-QA, J-REL | AC-REQ-021 | HATE-GAP-043 | runner-dialect-coverage-report |
| `FR-REEVAL-*` | J-QA, J-REL, J-AUD | AC-REQ-022 | HATE-GAP-044 | real-repo-evaluation-report |
| `FR-GOV-*` | J-ADM, J-AUD, J-REL | AC-REQ-023 | HATE-GAP-045 | governance-review-report |
| `FR-PROC-*` | J-SEC, J-AUD, J-REL | AC-REQ-024 | HATE-GAP-046 | security-procurement-report |
| `FR-VALUE-*` | J-SUP, J-REL, J-ADM | AC-REQ-025 | HATE-GAP-047 | value-measurement-report |
| `FR-DX-*` | J-DEV, J-QA | AC-REQ-026 | HATE-GAP-048 | developer-experience-report |
| `FR-ANALYSIS-001` | J-DEV, J-QA, J-REL | AC-REQ-027 | HATE-GAP-049 | impact-analysis-report |
| `FR-ANALYSIS-002` | J-DEV, J-QA | AC-REQ-028 | HATE-GAP-050 | test-recommendation-report |
| `FR-ANALYSIS-003` | J-DEV, J-QA, J-REL | AC-REQ-029 | HATE-GAP-051 | flaky-classification-report |
| `FR-ANALYSIS-004` | J-QA, J-REL | AC-REQ-030 | HATE-GAP-052 | oracle-classification-report |
| `FR-ANALYSIS-005` | J-QA, J-REL, J-AUD | AC-REQ-031 | HATE-GAP-053 | evidence-synthesis-report |
| `FR-ANALYSIS-006` | J-DEV, J-QA | AC-REQ-032 | HATE-GAP-054 | test-quality-report |
| `FR-ANALYSIS-007` | J-DEV, J-SUP, J-REL | AC-REQ-033 | HATE-GAP-055 | environment-diff-report |
| `FR-ANALYSIS-008` | J-QA, J-REL, J-AUD | AC-REQ-034 | HATE-GAP-056 | contradiction-report |
| `FR-ANALYSIS-009` | J-QA, J-REL, J-AUD | AC-REQ-035 | HATE-GAP-057 | historical-regression-report |
| `FR-ANALYSIS-010` | J-DEV, J-QA, J-REL | AC-REQ-036 | HATE-GAP-058 | audience-report-pack |
| `FR-ANALYSIS-011` | J-QA, J-AUD | AC-REQ-037 | HATE-GAP-059 | fixture-quality-report |
| `FR-ANALYSIS-012` | J-ADM, J-QA | AC-REQ-038 | HATE-GAP-060 | adapter-capability-diff-report |

### 13.2 Acceptance Evidence Minimum

Each `AC-REQ-*` acceptance must define:

- user journey step IDs
- positive fixture IDs
- negative fixture IDs
- expected product status impact
- required evidence report
- UAT reviewer role
- CI command or manual-bb gate reference

An acceptance ID with no negative fixture is incomplete. An acceptance ID with no user journey is
not product-grade acceptance.

## 14. Requirement Completion Gate

This requirements definition is complete only when:

- README and `SPECIFICATION.md` reference this document as a priority source
- product-grade specification maps implementation work packages back to requirement IDs
- task breakdown contains requirement-driven implementation tasks
- every product-ready claim has acceptance and evidence report requirements
- current implementation limitations are explicit and cannot be mistaken for product-ready
- `PRODUCT_REQUIREMENTS_500K_READINESS_AUDIT.md` records three independent checks:
  scope coverage, implementation/acceptance traceability, and overclaim/product-ready claim safety
- `USER_STORY_MAP.md`, `ACCEPTANCE_CRITERIA_MATRIX.md`, `API_REQUIREMENTS.md`,
  `UI_WORKFLOW_REQUIREMENTS.md`, `DATA_RETENTION_LEGAL_REQUIREMENTS.md`,
  `SCALE_PERFORMANCE_REQUIREMENTS.md`, and `IMPLEMENTATION_EPIC_BREAKDOWN.md`
  exist and are referenced from this document or README
