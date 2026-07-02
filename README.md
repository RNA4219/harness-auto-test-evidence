---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# harness-auto-test-evidence

## 1. 役割

`harness-auto-test-evidence` は、自動テスト証跡の収集・正規化・QEG 接続を
`workflow-cookbook` の運用型様式で扱う local-first CLI / fixture 実装です。
現在は P0a/P0b/P1a/P1b/P2/P3 の advisory artifact 生成までを実装済みです。
ただし、これは product-ready / enterprise-ready を意味しません。製品グレードの
要件定義は `docs/process/PRODUCT_REQUIREMENTS_DEFINITION.md`、実装粒度、No-Go、
fixture/test minimum、API/UI/store/enterprise 完了条件は
`docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md` を正本とします。

- 変更点
  - CI で得られる自動テスト信号（JUnit/Playwright/coverage/SARIF/etc）を受け取り、正規化
- 目的
  - `code-to-gate` の差分・リスク情報に接続した「証拠連携ハーネス」を構築
- 最終連携
  - `quality-evidence-graph`（QEG）への export を正本とし、必要に応じて
    `agent-state-gate` / `agent-gatefield` へ QEG 判定後の Gate 記録を接続する

## 1.1 QEG との責務境界

HATE は QEG の前段として、自動テスト証跡を収集・正規化し、AETE と
artifact manifest を付与して QEG が検証できる optional evidence に変換する。

- HATE が担うもの
  - P0a: JUnit / LCOV の最小 ingest、artifact manifest、precheck、record、summary
  - P0b: QEG optional evidence export、risk debt、manual-bb bridge、unsafe artifact quarantine
  - Evidence strength: 直近 run 履歴、retry/replay 由来の pass/fail 遷移、mutation evidence から
    `evidence_strength` を算出し、unknown を明示したうえで QEG bundle へ付与する
  - P1a: AETE、doctor、resolver、identity、retry、replay / compare / explain / recommend
  - P1b: RanD / Shipyard / workflow-cookbook 向け advisory artifact mapping
  - P2/P3: product readiness、hosted read model envelope、enterprise advisory artifact
  - DQ 001/002/003/005/007/008/010/015 の local fixture / control による再現
  - QEG fixture と互換する `qeg-bundle.json` / optional evidence export
- QEG に委譲するもの
  - Gate policy、waiver、approval、retention、immutability、schema migration
  - `evidence_strength` のしきい値、release / Gate 判定、go / hold / block への反映
  - source-backed Gate reason、DQ 優先、release 判定、record 正本化

## 2. 参照する文書

- [BLUEPRINT.md](docs/process/BLUEPRINT.md)
- [SPECIFICATION.md](docs/process/SPECIFICATION.md)
- [PRODUCT_REQUIREMENTS_DEFINITION.md](docs/process/PRODUCT_REQUIREMENTS_DEFINITION.md)
- [PRODUCT_REQUIREMENTS_500K_READINESS_AUDIT.md](docs/process/PRODUCT_REQUIREMENTS_500K_READINESS_AUDIT.md)
- [PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md](docs/process/PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md)
- [TEST_INTEGRITY_IMPLEMENTATION_SPEC.md](docs/process/TEST_INTEGRITY_IMPLEMENTATION_SPEC.md)
- [ENTERPRISE_CONTROL_STATE_TRANSITION_SPEC.md](docs/process/ENTERPRISE_CONTROL_STATE_TRANSITION_SPEC.md)
- [RELEASE_CANDIDATE_PACK_VALIDATOR_SPEC.md](docs/process/RELEASE_CANDIDATE_PACK_VALIDATOR_SPEC.md)
- [USER_STORY_MAP.md](docs/process/USER_STORY_MAP.md)
- [ACCEPTANCE_CRITERIA_MATRIX.md](docs/process/ACCEPTANCE_CRITERIA_MATRIX.md)
- [API_REQUIREMENTS.md](docs/process/API_REQUIREMENTS.md)
- [UI_WORKFLOW_REQUIREMENTS.md](docs/process/UI_WORKFLOW_REQUIREMENTS.md)
- [DATA_RETENTION_LEGAL_REQUIREMENTS.md](docs/process/DATA_RETENTION_LEGAL_REQUIREMENTS.md)
- [SCALE_PERFORMANCE_REQUIREMENTS.md](docs/process/SCALE_PERFORMANCE_REQUIREMENTS.md)
- [IMPLEMENTATION_EPIC_BREAKDOWN.md](docs/process/IMPLEMENTATION_EPIC_BREAKDOWN.md)
- [GLM_IMPLEMENTATION_DISPATCH_PACK.md](docs/process/GLM_IMPLEMENTATION_DISPATCH_PACK.md)
- [FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md](docs/process/FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md)
- [IMPLEMENTATION_TASK_BREAKDOWN.md](docs/process/IMPLEMENTATION_TASK_BREAKDOWN.md)
- [PRODUCT_GRADE_IMPLEMENTATION_SPEC.md](docs/process/PRODUCT_GRADE_IMPLEMENTATION_SPEC.md)
- [IMPLEMENTATION_ROADMAP_CHECKLIST.md](docs/process/IMPLEMENTATION_ROADMAP_CHECKLIST.md)
- [RUNBOOK.md](docs/process/RUNBOOK.md)
- [GUARDRAILS.md](docs/process/GUARDRAILS.md)
- [EVALUATION.md](docs/process/EVALUATION.md)
- [WORKFLOW_COOKBOOK_INTEGRATION.md](docs/process/WORKFLOW_COOKBOOK_INTEGRATION.md)
- [HATE file-reference codemap](docs/birdseye/README.md)
- [ENTERPRISE_PRODUCT_REQUIREMENTS.md](docs/process/ENTERPRISE_PRODUCT_REQUIREMENTS.md)
- [ENTERPRISE_DOMAIN_MODEL.md](docs/process/ENTERPRISE_DOMAIN_MODEL.md)
- [PRODUCT_ERROR_TAXONOMY.md](docs/process/PRODUCT_ERROR_TAXONOMY.md)
- [P0A_GOLDEN_PATH.md](docs/process/P0A_GOLDEN_PATH.md)
- [SCHEMA_REGISTRY_CONTRACT.md](docs/process/SCHEMA_REGISTRY_CONTRACT.md)
- [ADAPTER_SDK_CONTRACT.md](docs/process/ADAPTER_SDK_CONTRACT.md)
- [RISK_DEBT_REGISTER.md](docs/process/RISK_DEBT_REGISTER.md)
- [PRIVACY_QUARANTINE_CONTRACT.md](docs/process/PRIVACY_QUARANTINE_CONTRACT.md)
- [HOSTED_READ_MODEL_API.md](docs/process/HOSTED_READ_MODEL_API.md)
- [RELEASE_MIGRATION_POLICY.md](docs/process/RELEASE_MIGRATION_POLICY.md)
- [PACKAGING_ENTITLEMENT_CONTRACT.md](docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md)
- [CUSTOMER_DOCUMENTATION_CONTRACT.md](docs/process/CUSTOMER_DOCUMENTATION_CONTRACT.md)
- [SLO_INCIDENT_RESPONSE_CONTRACT.md](docs/process/SLO_INCIDENT_RESPONSE_CONTRACT.md)
- [CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md](docs/process/CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md)
- [SECURITY_REVIEW_TRUST_CONTRACT.md](docs/process/SECURITY_REVIEW_TRUST_CONTRACT.md)
- [PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md](docs/process/PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md)
- [DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md](docs/process/DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md)
- [PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md](docs/process/PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md)
- [ACCESSIBILITY_LOCALIZATION_CONTRACT.md](docs/process/ACCESSIBILITY_LOCALIZATION_CONTRACT.md)
- [LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md](docs/process/LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md)
- [AUDIT_FIXTURE_ASSURANCE_CONTRACT.md](docs/process/AUDIT_FIXTURE_ASSURANCE_CONTRACT.md)
- [REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md](docs/process/REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md)
- [TASK.codex.md](TASK.codex.md)
- [deep-research-report.md](docs/research/deep-research-report.md)

## 3. 進行方針（workflow-cookbook 適合）

- まず `BLUEPRINT.md` で範囲と I/O 契約を固定
- 次に `SPECIFICATION.md` で QEG export / workflow artifact / DQ / AETE の実装契約を確認
- 次に `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md` で仕様不足がないことを確認し、
  `IMPLEMENTATION_TASK_BREAKDOWN.md` の実装単位を順番に消化
- `TASK.codex.md` は初期 Task Seed として扱い、実装作業の正本分解は
  `IMPLEMENTATION_TASK_BREAKDOWN.md` に寄せる
- `RUNBOOK.md` の最短実行手順で検証を回し、`EVALUATION.md` で完了判定
- 文書は実運用に耐えるよう最小維持、完了資産は履歴へ移す（完了記録を蓄積する）

## 3.1 自動検収

- 全体回帰: `uv run pytest`
- HATE 自身の E2E 検収: `uv run pytest tests/test_acceptance_pipeline.py`
- compile check: `uv run python -m compileall src tests`
- HATE file-reference codemap 更新: `uv run python tools/codemap/update.py`
- HATE file-reference codemap 鮮度確認: `uv run python tools/codemap/update.py --check`
- CI: `.github/workflows/ci.yml` で compile と pytest を実行する

E2E 検収は `hate p0a -> hate export qeg -> hate trust evaluate -> hate workflow map -> hate product readiness`
を一時ディレクトリ上で実行し、`partial` / `conditional` / `hold` の降格、override 禁止、
絶対パス漏れなし、golden fixture を汚さないことを確認する。

## 4. 状態

- local/advisory artifact 実装: P0a/P0b/P1a/P1b/P2/P3 の証跡生成は実装済み
- platform CLI 導線: `hate platform run/history/compare/findings/debt/review/policy/report/serve` を実装済み。既存の real-repo / history / policy / read model / HTML report 導線を platform 操作面へ統合している。
- platform operations 導線: `hate platform schedule/assign/score/plugin run` を実装済み。cache TTL、retry、resume token、owner/due-date/SLA、plugin sandbox 実行、freshness/regression/manual debt/oracle confidence の説明可能 score を扱う。
- product-grade 実装: 13 product-grade 領域は requirement/spec、実装参照、テスト参照を再計算し、実データ検証と QEG smoke を統合して `conditional_go` まで判定する。残摩擦がある限り `product_ready` は `false` のまま維持する。
- 現在の回帰: `uv run pytest -q` で 1500+ tests pass
- 現在の release readiness: local/advisory artifact の fixture 上では P2/P3 report を生成でき、product-grade は `conditional_go`。product-ready / enterprise-ready / regulated-ready の最終主張には QEG release approval と、実データ運用摩擦の継続観測が必要。
- 対象外: hosted SaaS runtime、実 dashboard frontend、enterprise connector runtime、QEG / Shipyard の release / publish approval 正本
