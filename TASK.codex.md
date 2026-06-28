---
task_id: HATE-IMPLEMENTATION-PREP
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# HATE 実装準備 Task Seed

## メタデータ

```yaml
task_id: HATE-IMPLEMENTATION-PREP
repo: https://github.com/RNA4219/harness-auto-test-evidence
base_branch: main
priority: P1
langs: [multi]
```

## Objective

`workflow-cookbook` 様式に沿って、`harness-auto-test-evidence` の実装に入れる
最小文書構造とタスク分解を作成し、MVP 実装に直結する状態を作る。

## Scope

- In
  - `README.md`
  - `docs/process/BLUEPRINT.md`
  - `docs/process/GUARDRAILS.md`
  - `docs/process/RUNBOOK.md`
  - `docs/process/EVALUATION.md`
  - `docs/process/WORKFLOW_COOKBOOK_INTEGRATION.md`
  - `docs/process/ENTERPRISE_PRODUCT_REQUIREMENTS.md`
  - `docs/process/ENTERPRISE_DOMAIN_MODEL.md`
  - `docs/process/PRODUCT_ERROR_TAXONOMY.md`
  - `docs/process/P0A_GOLDEN_PATH.md`
  - `docs/process/SCHEMA_REGISTRY_CONTRACT.md`
  - `docs/process/ADAPTER_SDK_CONTRACT.md`
  - `docs/process/RISK_DEBT_REGISTER.md`
  - `docs/process/PRIVACY_QUARANTINE_CONTRACT.md`
  - `docs/process/HOSTED_READ_MODEL_API.md`
  - `docs/process/RELEASE_MIGRATION_POLICY.md`
  - `docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md`
  - `docs/process/CUSTOMER_DOCUMENTATION_CONTRACT.md`
  - `docs/process/SLO_INCIDENT_RESPONSE_CONTRACT.md`
  - `docs/process/CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md`
  - `docs/process/SECURITY_REVIEW_TRUST_CONTRACT.md`
  - `docs/process/PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md`
  - `docs/process/DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md`
  - `docs/process/PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md`
  - `docs/process/ACCESSIBILITY_LOCALIZATION_CONTRACT.md`
  - `docs/process/LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md`
  - `docs/process/AUDIT_FIXTURE_ASSURANCE_CONTRACT.md`
  - `docs/process/REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md`
  - `TASK.codex.md` 内の作業分解
  - `docs/research/deep-research-report.md` と実装準備資産の整合
- Out
  - 実際のアダプタ実装（収集/変換/export のコード）
  - CI 設定ファイル更新

## Requirements

- Behavior
  - ドキュメントが日本語で統一されていること
  - 文書間で scope / I/O / 受入条件の矛盾がないこと
  - 主要 KPI と DQ をタスクとして明記すること
- I/O Contract
  - Input: 事前調査結果、既存要件、依存 repo 方針
  - Output: 実装準備済みの workflow-cookbook 5点セット + Task Seed
- Constraints
  - 既存資料を壊さない（ファイル追加中心）
  - 受入条件は EVALUATION と一致させる

## Affected Paths

- README.md
- docs/process/BLUEPRINT.md
- docs/process/GUARDRAILS.md
- docs/process/RUNBOOK.md
- docs/process/EVALUATION.md
- docs/process/WORKFLOW_COOKBOOK_INTEGRATION.md
- docs/process/ENTERPRISE_PRODUCT_REQUIREMENTS.md
- docs/process/ENTERPRISE_DOMAIN_MODEL.md
- docs/process/PRODUCT_ERROR_TAXONOMY.md
- docs/process/P0A_GOLDEN_PATH.md
- docs/process/SCHEMA_REGISTRY_CONTRACT.md
- docs/process/ADAPTER_SDK_CONTRACT.md
- docs/process/RISK_DEBT_REGISTER.md
- docs/process/PRIVACY_QUARANTINE_CONTRACT.md
- docs/process/HOSTED_READ_MODEL_API.md
- docs/process/RELEASE_MIGRATION_POLICY.md
- docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md
- docs/process/CUSTOMER_DOCUMENTATION_CONTRACT.md
- docs/process/SLO_INCIDENT_RESPONSE_CONTRACT.md
- docs/process/CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md
- docs/process/SECURITY_REVIEW_TRUST_CONTRACT.md
- docs/process/PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md
- docs/process/DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md
- docs/process/PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md
- docs/process/ACCESSIBILITY_LOCALIZATION_CONTRACT.md
- docs/process/LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md
- docs/process/AUDIT_FIXTURE_ASSURANCE_CONTRACT.md
- docs/process/REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md
- docs/research/deep-research-report.md
- TASK.codex.md

## Local Commands

- `git status --short`
- 文書差分確認（`git diff -- README.md TASK.codex.md docs/process docs/research/deep-research-report.md`）

## Plan

1. ドキュメント間の役割を固定し、共通参照を追加
2. P0→P1→P2 の実装順を BLUEPRINT に明記
3. DQ / AETE / HATE precheck / QEG export を TASK で粒度分解
4. 実装前に受入条件を EVALUATION へ反映
5. MVP を P0a / P0b に分割し、最小 local-first precheck から実装できるようにする
6. adapter capability / adapter-AETE profile / artifact safety / QEG fixture を追加タスク化する
7. QEG が担う Gate policy / waiver / approval / retention / immutability /
   schema migration を HATE 側で再実装しない責務境界を固定する
8. RanD / KanoMode の requirements packet / audit packet を任意入力として扱い、
   要件妥当性・検収可能性・外部証跡に対する自動テスト裏付けを出せるようにする
9. shipyard-cp の WorkerResult / RunSystemPacket / run-audit refs へ HATE の
   evidence bundle を添付できるようにし、acceptance / integrate 前の客観証跡にする
10. workflow-cookbook の Task Seed / Acceptance / Evidence / Birdseye / workflow plugin
    へ接続できる `workflow-*` artifact を定義する
11. P1a/P2 拡張候補として replay / compare / explain / recommend / doctor /
    artifact resolver / schema registry / adapter conformance fixtures /
    adapter registry / profile inheritance / manual-bb bridge / PR annotation /
    artifact budget / attestation を backlog 化し、P0 の local-first precheck を
    肥大化させない
12. Enterprise product readiness として ICP / persona / product surface / edition /
    enterprise controls / compliance / supportability / product readiness gates を
    `ENTERPRISE_PRODUCT_REQUIREMENTS.md` に分離し、P0/P1 の証跡契約を肥大化させない
13. Packaging / entitlement、customer-facing docs、SLO / incident response を
    正本契約へ分離し、調達・運用・説明責任を P0/P1 の local-first 証跡契約から独立させる
14. Customer success / adoption、security review / trust、product telemetry / analytics を
    正本契約へ分離し、導入成功・審査対応・改善計測を canonical evidence から派生する補助層に留める
15. Data residency / deployment、product governance / roadmap、accessibility /
    localization を正本契約へ分離し、採用時の運用制約・意思決定・利用可能性を
    P0/P1 の証跡判定から独立させる
16. Legal / commercial contracting、audit fixture / assurance、requirements portfolio を
    正本契約へ分離し、外部約束・監査再現性・実装順の肥大化を管理する

## Notes

- 実装に進む前に、以下の初期タスクを `TASK-HATE-*.md` などとして分解する
  - HATE-MVP-001: provenance と共通 record envelope 整備
  - HATE-MVP-002: JUnit / LCOV の canonical 化
  - HATE-MVP-003: artifact-manifest + precheck-decision（HATE precheck）+ record.json の P0a 導線
    （`gate-decision.json` は既存互換 alias として扱う）
  - HATE-MVP-004: SARIF / Playwright artifact / diff-risk-test の P0b 拡張
  - HATE-MVP-005: QEG export と minimal valid bundle fixture の監査整合
  - HATE-MVP-006: P1a adapter capability manifest の定義と未対応粒度の可視化
  - HATE-MVP-007: P1a adapter / AETE profile（default / strict / release / experimental）の定義
  - HATE-MVP-008: P0a/P0b artifact safety（classification / redaction rule / safe_for_summary）の導入
    （secret scan、MIME / 拡張子整合、archive 展開制限、symlink / path traversal、
    外部 URL 参照の安全確認を含む）
  - HATE-MVP-009: P1a baseline / history index の最小設計
  - HATE-MVP-010: P1a evidence explain / gap recommendation の設計
  - HATE-MVP-011: QEG 責務境界（Gate policy / waiver / approval / retention /
    immutability / schema migration は QEG に委譲）の fixture / docs 検証
  - HATE-MVP-012: P1a matrix / shard / retry aggregation の決定的集約
  - HATE-MVP-013: P1a coverage / SARIF / JUnit / Playwright artifact の path normalization
  - HATE-MVP-014: P1b RanD `requirements_packet.json` /
    `requirements_audit_packet.json` ingest と schema 最小 validation
  - HATE-MVP-015: P1b `requirement-evidence-alignment.json` の設計
    （requirement / KPI / acceptance / risk / gate_verdict と HATE evidence の結線）
  - HATE-MVP-016: P1b RanD Requirement Definition Gate verdict を HATE が上書きしない
    責務境界 fixture の追加
  - HATE-MVP-017: P1b shipyard-cp `WorkerResult` / `RunSystemPacket` mapping と
    `shipyard-run-evidence.json` の設計
  - HATE-MVP-018: P1b shipyard-cp state machine / publish approval / worker dispatch を
    HATE が再実装しない責務境界 fixture の追加
  - HATE-MVP-019: P1b `workflow-task-seed.json` と
    `workflow-acceptance-record.json` の設計
  - HATE-MVP-020: P1b `workflow-evidence.jsonl` の設計
    （HATE run / qeg / aete / dq artifact refs を Evidence 互換へ写像）
  - HATE-MVP-021: P1b `workflow-docs-stale.json` と
    `workflow-birdseye-map.json` の設計
  - HATE-MVP-022: P1b workflow-cookbook の checker / plugin host /
    Birdseye 生成器を HATE が再実装しない責務境界 fixture の追加
  - HATE-MVP-023: P1a `HATE replay` の設計
    （frozen bundle から AETE / DQ / QEG export を再計算し、監査・回帰確認に使う）
  - HATE-MVP-024: P1a `HATE compare` の設計
    （base/head、前回 run、baseline との差分で trust delta / DQ 増減 / risk coverage 低下を出す）
  - HATE-MVP-025: P1a `HATE explain` の拡張
    （`why-excluded`, `why-soft-gap`, `why-score-changed` を risk/test/evidence 単位で説明する）
  - HATE-MVP-026: P1a `HATE recommend` の設計
    （不足 evidence から追加すべき test layer / Pact / mutation / Playwright / manual 補完を提案する）
  - HATE-MVP-027: P1a adapter registry の設計
    （capability、必須/任意 artifact、既知制限、fixture、profile 対応を一覧化する）
  - HATE-MVP-028: P1a profile inheritance の設計
    （`default -> strict -> release` の継承、差分表示、profile drift 検出を行う）
  - HATE-MVP-029: P1b manual-bb bridge の設計
    （high-risk gap を `manual-bb-test-harness` 向け manual 補完要求へ変換する）
  - HATE-MVP-030: P2 PR annotation export の設計
    （changed high-risk path 単位で Job Summary / PR annotation に説明を出す）
  - HATE-MVP-031: P2 artifact budget report の設計
    （trace / video / coverage / SARIF の容量、保持期限、公開可否、上限超過を可視化する）
  - HATE-MVP-032: P2 signed evidence / attestation の設計
    （provenance 署名や SLSA / in-toto 風 attestation へ接続する）
  - HATE-MVP-033: P1a `HATE doctor` の設計
    （adapter / schema / path / provenance / QEG fixture の事前診断を summary と JSON に出す）
  - HATE-MVP-034: P1a artifact resolver の設計
    （local path / CI artifact URL / Windows path / container path / workspace 相対 path を一貫解決する）
  - HATE-MVP-035: P1a schema registry の設計
    （`HATE/v1` JSON Schema、互換性テスト、deprecated field 方針を管理する）
  - HATE-MVP-036: P1a adapter conformance fixtures の設計
    （JUnit / LCOV / SARIF / Playwright などの正常・破損・欠損・retry/matrix 混在 fixture で最低準拠を検証する）
  - HATE-MVP-037: P1a canonical test identity の設計
    （`canonical_test_id`, `identity_components`, `aliases` により rename /
    parameterized test / matrix の履歴断絶を抑制する）
  - HATE-MVP-038: P1a AETE score confidence / calibration metadata の設計
    （`rubric_version`, `profile_version`, `score_confidence`,
    `calibration_status` を出し、未校正 score の過信を防ぐ）
  - HATE-MVP-039: P1a 小フェーズ分割の反映
    （P1a-1 診断基盤、P1a-2 再現性、P1a-3 説明と改善に分けて
    doctor / resolver / schema / identity / replay / explain / recommend を実装順へ並べる）
  - HATE-MVP-040: P0a golden path contract の固定
    （`P0A_GOLDEN_PATH.md` に従い `fixtures/golden/p0a-minimal` の input /
    expected、decision enum、DQ fixture、summary safety を実装契約化する）
  - HATE-MVP-041: P1a schema registry contract の固定
    （`SCHEMA_REGISTRY_CONTRACT.md` に従い schema version、field policy、
    fixture matrix、migration policy を実装契約化する）
  - HATE-MVP-042: P1a adapter SDK contract の固定
    （`ADAPTER_SDK_CONTRACT.md` に従い manifest、required interface、
    failure contract、conformance report を実装契約化する）
  - HATE-MVP-043: P1a risk debt register contract の固定
    （`RISK_DEBT_REGISTER.md` に従い soft gap、manual 補完要求、
    conditional candidate の継続追跡を実装契約化する）
  - HATE-MVP-044: P1a privacy / quarantine contract の固定
    （`PRIVACY_QUARANTINE_CONTRACT.md` に従い artifact safety、
    privacy report、quarantine、summary/export 制御を実装契約化する）
  - HATE-MVP-045: P2 hosted read model / API contract の固定
    （`HOSTED_READ_MODEL_API.md` に従い REST API、dashboard、RBAC、
    source bundle、stale cache、read model consistency を実装契約化する）
  - HATE-MVP-046: P2 release / migration policy の固定
    （`RELEASE_MIGRATION_POLICY.md` に従い release gates、migration artifacts、
    compatibility matrix、rollback policy を実装契約化する）
  - HATE-MVP-047: P2 packaging / entitlement contract の固定
    （`PACKAGING_ENTITLEMENT_CONTRACT.md` に従い edition、entitlement、
    usage meter、over-limit、procurement artifact を実装契約化する）
  - HATE-MVP-048: P2 customer documentation contract の固定
    （`CUSTOMER_DOCUMENTATION_CONTRACT.md` に従い required docs、audience、
    source_contracts、freshness、verification を実装契約化する）
  - HATE-MVP-049: P2 SLO / incident response contract の固定
    （`SLO_INCIDENT_RESPONSE_CONTRACT.md` に従い SLO、incident class、
    severity、containment、communication、postmortem を実装契約化する）
  - HATE-MVP-050: P2 customer success / adoption contract の固定
    （`CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` に従い onboarding、adoption stage、
    success plan、adoption health、renewal readiness を実装契約化する）
  - HATE-MVP-051: P2 security review / trust contract の固定
    （`SECURITY_REVIEW_TRUST_CONTRACT.md` に従い trust packet、control mapping、
    vulnerability handling、security review record を実装契約化する）
  - HATE-MVP-052: P2 product telemetry / analytics contract の固定
    （`PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` に従い opt-in telemetry、
    allowed / prohibited signal、retention、analytics outputs を実装契約化する）
  - HATE-MVP-053: P2 data residency / deployment contract の固定
    （`DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` に従い deployment mode、
    residency profile、data class routing、backup / recovery を実装契約化する）
  - HATE-MVP-054: P2 product governance / roadmap contract の固定
    （`PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` に従い roadmap item、
    decision record、customer request、deprecation decision を実装契約化する）
  - HATE-MVP-055: P2 accessibility / localization contract の固定
    （`ACCESSIBILITY_LOCALIZATION_CONTRACT.md` に従い accessibility target、
    message catalog、locale fallback、stable identifier を実装契約化する）
  - HATE-MVP-056: P2 legal / commercial contracting contract の固定
    （`LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` に従い commercial commitment、
    procurement response、contract exception、commercial risk を実装契約化する）
  - HATE-MVP-057: P2 audit fixture / assurance contract の固定
    （`AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` に従い audit fixture、
    assurance pack、auditor walkthrough、evidence room を実装契約化する）
  - HATE-MVP-058: P1/P2 requirements portfolio operating model の固定
    （`REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` に従い tier、stage、
    WIP、dependency、portfolio health を実装契約化する）
  - HATE-PROD-001: P0a golden fixture と Quickstart の固定
    （Time to First Evidence を 5 分以内にするため、docs / schema / examples /
    tests が同じ golden input を参照する）
  - HATE-PROD-002: `PRODUCT_ERROR_TAXONOMY.md` に基づく product error code taxonomy と remediation catalog の設計
  - HATE-PROD-003: `ENTERPRISE_DOMAIN_MODEL.md` に基づく org / workspace /
    project / repo / run / bundle / profile / audit event の domain model 設計
  - HATE-PROD-004: `ADAPTER_SDK_CONTRACT.md` に基づく adapter SDK と conformance suite の公開可能化
  - HATE-PROD-005: `RISK_DEBT_REGISTER.md` に基づく risk debt register の設計
  - HATE-PROD-006: `PRIVACY_QUARANTINE_CONTRACT.md` に基づく privacy report と artifact quarantine の設計
  - HATE-PROD-007: `HOSTED_READ_MODEL_API.md` に基づく hosted dashboard / REST API / read model の設計
  - HATE-PROD-008: RBAC / audit log / retention policy の設計
  - HATE-PROD-009: SSO / SCIM / SIEM / data warehouse / ticketing connector の設計
  - HATE-PROD-010: compliance control mapping と security review pack の設計
  - HATE-PROD-011: `PACKAGING_ENTITLEMENT_CONTRACT.md` に基づく pricing /
    packaging / edition boundary の文書化
  - HATE-PROD-012: support diagnostic bundle と incident class の設計
  - HATE-PROD-013: `RELEASE_MIGRATION_POLICY.md` に基づく release / migration / rollback policy の設計
  - HATE-PROD-014: entitlement manifest / usage meter / over-limit handling の設計
  - HATE-PROD-015: `CUSTOMER_DOCUMENTATION_CONTRACT.md` に基づく
    customer-facing docs 体系と freshness governance の設計
  - HATE-PROD-016: `SLO_INCIDENT_RESPONSE_CONTRACT.md` に基づく
    SLO / incident response / status communication / postmortem の設計
  - HATE-PROD-017: `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` に基づく
    adoption plan / health / renewal readiness の設計
  - HATE-PROD-018: `SECURITY_REVIEW_TRUST_CONTRACT.md` に基づく
    trust packet / security review / vulnerability handling の設計
  - HATE-PROD-019: `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` に基づく
    privacy-safe telemetry / product metrics / analytics governance の設計
  - HATE-PROD-020: `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` に基づく
    data residency / private deployment / recovery の設計
  - HATE-PROD-021: `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` に基づく
    roadmap governance / product decision record / customer request register の設計
  - HATE-PROD-022: `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` に基づく
    accessibility / localization / inclusive docs の設計
  - HATE-PROD-023: `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` に基づく
    commercial commitment / contract exception / procurement response の設計
  - HATE-PROD-024: `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` に基づく
    audit fixture / assurance pack / evidence room の設計
  - HATE-PROD-025: `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` に基づく
    requirements portfolio / WIP / dependency governance の設計
- 追加後は必要に応じて `workflow-cookbook` 既存の Task seed 形式へ展開
