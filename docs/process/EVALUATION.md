---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Evaluation

## Acceptance Criteria

### 共通

- `BLUEPRINT.md` の In/Out と実装の実体が一致している
- フル実装の不足仕様は `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md` を正本とし、
  adapter、profile、schema、storage、hosted API、dashboard、RBAC/audit、
  external export、QEG live連携、release candidate pack の仕様が閉じている
- 実装作業の粒度は `IMPLEMENTATION_TASK_BREAKDOWN.md` を正本とし、
  code / schema / fixture / test / docs が揃うまで `implemented` または
  `accepted` と表現しない
- 仕様書、fixture、advisory artifact だけで実装完了を主張しない。
  各 phase の完了主張は `FULL_IMPLEMENTATION_SPEC_GAP_CLOSURE.md` の
  「完了主張ルール」に従う
- 全 JSON / NDJSON record が共通 envelope（`schema_version`, `record_type`, `record_id`, `run_id`, `run_attempt`, `commit_sha`, `created_at`, `source_tool`, `source_version`, `sha256`, `redaction_status`, `payload`）を持つ
- DQ ルール（最低 HATE-DQ-01, 02, 03, 05, 07, 10, 15）を実装し、`hard_dq` / `soft_gap` の severity と HATE precheck / QEG export への影響が再現可能
- adapter / AETE profile の既定 `dq.enabled` に HATE-DQ-01, 02, 03, 05, 07, 10, 15 が含まれている
- HATE が QEG の Gate policy / waiver / approval / retention / immutability /
  schema migration を再実装していないことを確認できる
- HATE が QEG optional evidence producer / normalizer として、QEG の
  `validate / gate / record` に渡せる成果物を出す
- Allure / ReportPortal / Codecov / SonarQube などの外部 export adapter は non-gating optional として扱われ、未設定でも local-first の precheck 判定が完了する
- Enterprise product readiness 要件は `ENTERPRISE_PRODUCT_REQUIREMENTS.md` を正本とし、
  hosted / enterprise / compliance 機能が未実装でも P0/P1 の local-first
  precheck / QEG export を妨げない
- Packaging / entitlement / usage meter は `PACKAGING_ENTITLEMENT_CONTRACT.md` を正本とし、
  edition や契約状態が HATE precheck decision / QEG verdict を変更しない
- Customer documentation は `CUSTOMER_DOCUMENTATION_CONTRACT.md` を正本とし、
  required docs の audience、source_contracts、review date、verification を追跡できる
- SLO / incident response は `SLO_INCIDENT_RESPONSE_CONTRACT.md` を正本とし、
  hosted outage や incident record が canonical bundle を改変しない
- Customer success / adoption は `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` を正本とし、
  adoption status や renewal readiness が HATE precheck decision / QEG verdict を変更しない
- Security review / trust は `SECURITY_REVIEW_TRUST_CONTRACT.md` を正本とし、
  trust packet が customer source code、secret、PII、unsafe artifact を含まない
- Product telemetry / analytics は `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` を正本とし、
  telemetry off でも local CLI / precheck / QEG export が完了する
- Data residency / deployment は `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` を正本とし、
  region / deployment mode が evidence eligibility や QEG verdict を変更しない
- Product governance / roadmap は `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` を正本とし、
  roadmap status が実装済み表現や customer docs と矛盾しない
- Accessibility / localization は `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` を正本とし、
  accessibility / localization report が HATE precheck decision / QEG verdict を変更しない
- Legal / commercial contracting は `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` を正本とし、
  commercial commitment が実装状態や source contract と矛盾しない
- Audit fixture / assurance は `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` を正本とし、
  audit fixture が synthetic / redacted / safe-to-share の状態を持つ
- Requirements portfolio は `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` を正本とし、
  P0a/P0b が P2/P3 productization に依存しないことを検出できる

### P0a

- P0a の最小成果物（`HATE-run.json`, `HATE-test-results.ndjson`, `HATE-coverage.ndjson`, `artifact-manifest.json`, `precheck-decision.json`, `record.json`）だけで local-first precheck 判定が完了する
- P0a golden path は `P0A_GOLDEN_PATH.md` を正本とし、
  `fixtures/golden/p0a-minimal/input` と `expected` の契約を持つ
- P0a の HATE precheck 出力は `precheck-decision.json` を正規名とし、
  既存互換が必要な場合のみ `gate-decision.json` を alias として生成できる
- `precheck-decision.json` の decision enum は `eligible`, `conditional`,
  `ineligible`, `hard_dq` に限定され、CLI / schema / adapter failure は
  decision ではなく exit code 1 として扱われる
- P0a の `artifact-manifest.json` は、存在する artifact について `sha256`, `redaction_status`, `retention`, `size_bytes`, `public_exposure` を持つ
- P0a の `artifact-manifest.json` は、存在する artifact について公開可否判断のための `classification`, `redaction_rule_version`, `safe_for_summary` を持つ
- P0a/P0b の artifact safety は、secret scan、MIME / 拡張子整合、
  archive 展開制限、symlink / path traversal、外部 URL 参照の検査結果を
  manifest または診断 report に残す
- P0a では Playwright trace/screenshot/video/log が存在しない入力でも precheck 判定が完了する
- P0a Quickstart は外部 SaaS、ネットワーク、QEG runtime、SSO、dashboard なしで
  5 分以内に golden fixture を実行できる

### P0b

- `artifact-manifest.json` が存在し、Playwright trace/screenshot/video/log の参照がある場合に壊れていない
- `evidence-map.json` が diff-risk-test エッジを持つ
- QEG export (`qeg-bundle.json`) が最低項目を満たす
- QEG export は minimal valid bundle fixture で互換性を検証できる

### P1a

- AETE の 8 次元 rubric が 0 / 1 / 3 / 5 の離散値で実装され、欠損値が DQ か任意証跡の 0 点かを区別できる
- AETE score が `rubric_version`, `profile_version`, `score_confidence`,
  `calibration_status` を持ち、未校正 score を release Gate 正本として扱わないことを
  summary と JSON で確認できる
- test result が `canonical_test_id`, `identity_components`, `aliases` を持ち、
  rename / parameterized test / matrix 差分が履歴比較で説明可能になる
- adapter capability manifest により、adapter ごとの未対応粒度（flaky 判定、coverage context、artifact hash など）を summary と JSON に明示できる
- adapter / AETE profile により、DQ、AETE threshold、必須 artifact、manual 補完条件を再現可能に切り替えられる
- matrix / shard / retry aggregation が決定的で、同一 test case の複数結果を
  `stable`, `flaky`, `failed`, `inconclusive` などへ再現可能に集約できる
- path normalization が workspace 相対 path、container path、Windows path、
  package root の差を吸収し、QEG の sourceRefs / artifact metadata に接続できる
- `HATE replay` が frozen bundle から AETE / DQ / QEG export を再計算し、
  同一入力では同一結果を返せる
- `HATE compare` が base/head、前回 run、baseline の差分から trust delta、
  DQ 増減、risk coverage 低下を出せる
- `HATE explain` が `why-excluded`, `why-soft-gap`, `why-score-changed` を
  risk / test / evidence 単位で説明できる
- `HATE recommend` が不足 evidence に対して追加すべき test layer、Pact、
  mutation、Playwright、manual 補完候補を出せる
- `HATE doctor` が adapter / schema / path / provenance / QEG fixture の
  事前診断を実行し、結果を summary と `doctor-report.json` に出せる
- artifact resolver が local path、CI artifact URL、Windows path、
  container path、workspace 相対 path を同じ規則で解決し、
  `artifact-resolver-map.json` と QEG sourceRefs の整合を確認できる
- schema registry が `HATE/v1` JSON Schema、互換性テスト、
  deprecated field 方針を保持し、schema drift を検出でき、
  `SCHEMA_REGISTRY_CONTRACT.md` と整合している
- adapter conformance fixtures が JUnit / LCOV / SARIF / Playwright などの
  正常・破損・欠損・retry/matrix 混在入力で adapter 最低準拠を検証できる
- adapter registry が capability、必須/任意 artifact、既知制限、fixture、
  profile 対応を summary と JSON に出せる
- adapter SDK が `ADAPTER_SDK_CONTRACT.md` に従い、manifest、required interface、
  failure contract、conformance report を検証できる
- profile inheritance が `default -> strict -> release` の継承、差分表示、
  profile drift 検出を再現可能に扱える
- risk debt register が `RISK_DEBT_REGISTER.md` に従い、soft gap、manual 補完要求、
  conditional candidate を owner、age、sourceRefs、recommended_actions 付きで追跡できる

### P1b

- RanD `requirements_packet.json` / `requirements_audit_packet.json` を任意入力として受け取り、
  requirement / KPI / acceptance / risk / gate_verdict と HATE evidence を結線できる
- `requirement-evidence-alignment.json` が requirement ごとの
  `testability`, `implementation_alignment`, `evidence_coverage`,
  `unverified_acceptance`, `source_refs` を持つ
- RanD audit の `no_go` / `conditional_go` issue を HATE が独自に上書きせず、
  自動テスト証跡の有無と不足理由だけを出力できる
- shipyard-cp `WorkerResult` / `RunSystemPacket` / task-run-audit refs を任意入力として受け取り、
  `shipyard-run-evidence.json` に HATE artifact refs、AETE summary、DQ summary を添付できる
- shipyard-cp の state machine / publish approval / worker dispatch を HATE が再実装していないことを確認できる
- `workflow-task-seed.json` が HATE-MVP-* を workflow-cookbook Task Seed 互換の
  `task_id`, `objective`, `scope`, `requirements`, `affected_paths`,
  `local_commands`, `acceptance_refs` へ写像できる
- `workflow-acceptance-record.json` が acceptance record 互換の
  `acceptance_id`, `task_id`, `scope`, `acceptance_criteria`,
  `evidence_refs`, `verification_result` を持つ
- `workflow-evidence.jsonl` が HATE の run / qeg / aete / dq artifact refs を
  Evidence 互換の 1 行 1 record として出せる
- `workflow-docs-stale.json` が docs / schema / fixture の freshness を記録し、
  stale の場合に required action を出せる
- `workflow-birdseye-map.json` が HATE docs / adapters / schemas / fixtures の
  node 候補と deps を持つ
- HATE が workflow-cookbook の acceptance checker、workflow plugin host、
  Birdseye/Codemap 生成器を再実装していないことを確認できる
- manual-bb bridge が high-risk gap を `manual-bb-test-harness` 向けの
  manual 補完要求として出力でき、HATE が手動テスト実施そのものを代替しない

### P2

- PR annotation export が changed high-risk path 単位で HATE explain / DQ /
  AETE summary を出せる
- artifact budget report が trace / video / coverage / SARIF の容量、保持期限、
  公開可否、上限超過を summary と JSON に出せる
- signed evidence / attestation は optional とし、未設定でも P0/P1 の
  local-first precheck / QEG export を妨げない
- product error code taxonomy が user-facing failure に stable code と
  remediation を付与でき、`PRODUCT_ERROR_TAXONOMY.md` と整合している
- risk debt register が soft gap / manual 補完要求 / conditional candidate を
  owner、risk、age、sourceRefs 付きで追跡できる
- privacy report / artifact quarantine が unsafe artifact を summary / QEG export /
  external export から隔離でき、`PRIVACY_QUARANTINE_CONTRACT.md` と整合している
- hosted dashboard / REST API / read model は canonical bundle から派生し、
  HATE 独自の release approval 正本を持たず、`HOSTED_READ_MODEL_API.md` と整合している
- release / migration policy が `RELEASE_MIGRATION_POLICY.md` に従い、
  release gate、migration artifact、rollback、compatibility matrix を持つ
- entitlement manifest / usage report は canonical bundle を隠さず、
  over-limit を warning / hosted upload block / connector warning として説明できる
- customer docs index は required docs、audience、source_contracts、review cadence、
  verification status を持つ
- incident record / SLO report は severity、class、affected surface、owner、timeline、
  containment、evidence_refs を持つ
- adoption plan / adoption health report は milestone、owner、acceptance_refs、
  adoption gap、renewal readiness を持つ
- security review record / trust packet は scope、control mapping、SBOM、
  vulnerability report、open findings、expiry を持つ
- telemetry event / analytics report は allowed signal のみを含み、
  prohibited signal を送信前 safety check で拒否できる
- residency profile / deployment topology は deployment mode、data plane、
  control plane、data class routing、network、backup / recovery を持つ
- roadmap item / decision record は source_refs、personas、value、risk、
  acceptance_refs、decision rationale を持つ
- accessibility / localization report は surface、target、violations、message catalog、
  locale fallback、source doc version を持つ
- commercial commitment / contract exception は source_refs、source_contracts、
  owner、status、verification_refs、expiry を持つ
- audit fixture manifest / assurance pack は source_contracts、expected_output_refs、
  verification_commands、safe_to_share、finding status を持つ
- requirements portfolio item / portfolio health report は tier、stage、owner、
  acceptance_refs、dependencies、WIP、stale contract を持つ

### P3 / Enterprise Product Readiness

- `ENTERPRISE_PRODUCT_REQUIREMENTS.md` が ICP、persona、product surface、edition、
  enterprise controls、supportability、documentation、product readiness gates を持つ
- org / workspace / project / repo / run / attempt / evidence bundle / profile /
  audit event の domain model が `ENTERPRISE_DOMAIN_MODEL.md` で定義されている
- RBAC が admin / maintainer / developer / auditor / viewer を分離し、
  auditor は read-only として扱える
- audit log が profile 変更、adapter 追加、export、artifact access、
  override request を記録できる
- retention / legal hold / customer export / deletion request の要件が
  artifact classification と結びついている
- SSO / SCIM / SIEM / data warehouse / ticketing connector は optional enterprise
  connector とし、未設定でも local-first precheck を妨げない
- support diagnostic bundle は secret / PII / unsafe artifact を含まず、
  version、profile、schema、adapter、DQ、doctor 結果を含められる
- privacy / quarantine policy が artifact classification と retention / export /
  diagnostic bundle の出力可否に効く
- hosted read model は canonical bundle から再構築でき、stale cache を明示できる
- release channel、deprecation、migration guide、rollback policy が
  compatibility matrix と結びついている
- edition / entitlement / procurement artifact が feature boundary と usage meter に結びつき、
  local-first evidence bundle の再計算性を損なわない
- customer-facing documentation が quickstart、concepts、CLI、schema、security、
  migration、support、compliance の required docs を持ち、stale 状態を説明できる
- incident response が data exposure、wrong eligibility、evidence corruption、
  hosted outage、connector degradation、schema / adapter regression を分類できる
- customer success が Discover / Prove / Integrate / Govern / Scale / Renew の
  adoption stage と success metric を追跡できる
- security review / trust packet が data flow、control mapping、privacy summary、
  SBOM、vulnerability handling、subprocessor、attestation summary を説明できる
- product telemetry が opt-in / aggregate / minimum necessary の原則で
  product metrics、capacity、docs improvement、error trend を測定できる
- data residency / deployment が local only、CI attached、hosted read model、
  private tenant、customer managed、air-gapped export の差を説明できる
- product governance が customer request、roadmap item、decision record、
  deprecation decision、roadmap communication を追跡できる
- accessibility / localization が dashboard、docs、CLI summary、support materials に
  適用され、stable code / schema field / record_id を翻訳で変えない
- legal / commercial commitment が procurement response、support plan、data residency、
  security trust packet、entitlement と矛盾しない
- audit fixture / assurance pack が auditor walkthrough、evidence room、open finding、
  limitation、expected outputs を説明できる
- requirements portfolio が Core Evidence、Trust Hardening、Workflow Integration、
  Product Operations、Enterprise Adoption、Governance Scale の tier を持つ
- PRG-0 から PRG-6 までの Product Readiness Gate が定義され、
  Enterprise Product Ready の判定が sales 資料ではなく検証可能な artifact / metric に基づく

## KPIs

- AETE 計算の再現率: 同一入力で同一 score
- DQ 抜け率: 重要 DQ 対象（coverage-only, execution missing, stale）を 0% へ低減
- Precheck 完了ラグ: 主要証跡ファイル生成→ HATE precheck 判定まで 5 分以内（ローカル）
- 可読性: summary（Markdown）と機械可読（JSON/NDJSON）の出力共存
- 外部連携非依存率: 外部 SaaS 未設定でも P0 precheck 判定が 100% 完了
- artifact 安全性: public summary に secret / token / 未 redaction artifact path が出ない
- adapter 明示性: 未対応 capability が hidden gap にならず 100% manifest に記録される
- QEG 互換性: minimal fixture が HATE/QEG 双方で validate できる
- 責務分離: HATE の出力が QEG の統制入力に従い、HATE 独自の release approval /
  waiver / retention 正本を持たない
- 集約再現性: matrix / shard / retry が同一入力で同一 aggregate status になる
- path 解決率: QEG sourceRefs / artifact metadata へ渡す path が 100% 正規化済みになる
- 要件裏付け率: RanD audit packet 内の `go` / `conditional_go` 要件について、
  acceptance criteria と自動テスト evidence の結線率を記録できる
- 監査上書き率: RanD `no_go` issue を HATE が `go` 相当に上書きするケースが 0%
- Shipyard 添付率: HATE の主要 artifact refs が `shipyard-run-evidence.json` に
  100% 記録され、run / audit refs と結線される
- Workflow traceability: HATE-MVP-* の 100% が Task Seed 互換 artifact から
  acceptance / evidence refs へ辿れる
- Workflow stale 可視性: HATE の主要 docs / schema / fixture の stale 状態が
  `workflow-docs-stale.json` に 100% 記録される
- Replay 再現性: frozen bundle の再計算結果が同一 profile / schema で 100% 一致する
- Compare 有効性: trust delta / DQ 増減 / risk coverage 低下が差分 summary に記録される
- Recommendation traceability: 推奨された追加証跡が risk / gap / source_refs に紐づく
- Doctor 有効性: adapter / schema / path / provenance / QEG fixture の問題が
  `doctor-report.json` に分類付きで記録される
- Artifact resolver 整合性: summary、artifact manifest、QEG sourceRefs が
  同じ解決済み artifact 参照へ辿れる
- Schema registry 健全性: `HATE/v1` schema と fixture の互換性が検証され、
  deprecated field が明示される
- Adapter conformance: 主要 adapter の正常・破損・欠損 fixture が
  capability manifest と矛盾しない
- Adapter SDK readiness: adapter manifest / required interface / failure contract /
  conformance report が受入可能である
- Risk debt traceability: soft gap / manual 補完要求 / conditional candidate が
  owner、age、sourceRefs、recommended_actions に紐づく
- Artifact budget 可視性: 大容量 artifact と retention / public exposure の状態が
  summary と JSON に記録される
- AETE calibration 可視性: 未校正 / 仮重みの score が summary と JSON で識別できる
- Test identity 安定性: rename / parameterized / matrix 入力でも canonical test identity が
  再現可能に生成される
- Artifact threat coverage: secret、MIME、archive、symlink、path traversal、外部 URL 参照の
  検査結果が hidden gap にならない
- Time to First Evidence: 初回導入から P0a golden path の
  `precheck-decision.json` 生成まで 5 分以内
- Evidence Eligibility Rate: hard DQ なしで export 可能な run の割合を記録できる
- High-Risk Evidence Coverage: high-risk changed path に直接証跡がある割合を記録できる
- Risk Debt Aging: soft gap / manual 補完要求が未解消で残る期間を記録できる
- Support Deflection: `doctor` / docs / remediation catalog で解決できた問題の割合を記録できる
- Product Readiness Gate Coverage: PRG-0..PRG-6 の各 gate が artifact / metric /
  acceptance criteria へ紐づく
- Privacy quarantine effectiveness: unsafe artifact の 100% が summary / export /
  diagnostic bundle から除外される
- Read model rebuildability: hosted read model が canonical bundle から再構築可能
- Migration safety: breaking change の 100% が migration guide と rollback note を持つ
- Entitlement safety: edition / entitlement / over-limit が precheck decision / QEG verdict を
  変更しない
- Documentation freshness: required customer-facing docs の stale / missing / broken source contract を
  100% 検出できる
- Incident response traceability: Sev1 / Sev2 incident の ack、containment、
  communication、postmortem が evidence_refs と owner に紐づく
- Adoption health: target repo の Discover / Prove / Integrate / Govern / Scale / Renew が
  owner / milestone / next_action に紐づく
- Trust packet freshness: trust packet の data flow / controls / SBOM / vulnerabilities /
  subprocessors が freshness policy に従う
- Telemetry privacy safety: prohibited signal が telemetry event に混入するケースが 0%
- Residency safety: deployment mode / region / connectivity 設定で canonical bundle の
  再計算性が失われるケースが 0%
- Roadmap truthfulness: roadmap status と docs / release notes / customer communication の
  矛盾が 0 件
- Accessibility / localization readiness: target surface の accessibility report と
  localization report が review date / owner を持つ
- Commercial commitment truthfulness: unsupported / planned commitment が available と表現されるケースが 0 件
- Audit fixture reproducibility: audit fixture の expected output を verification command で再計算できる
- Portfolio health: owner 不在、acceptance 不足、P0 dependency leak、WIP 超過を検出できる

## Test Outline

- 単体:
  - 正規化 adapter の変換単体
  - DQ 判定ルール
  - 共通 envelope validation
  - artifact manifest の hash / redaction / retention validation
  - artifact safety の secret scan / MIME 整合 / archive 展開制限 /
    symlink / path traversal / 外部 URL 参照 validation
  - P1a: AETE スコア集計ロジック
  - P1a: AETE score confidence / calibration metadata validation
  - P1a: canonical test identity / aliases 生成
  - adapter capability manifest の validation
  - adapter / AETE profile の threshold / DQ 切替
  - replay / compare / explain / recommend の出力生成
  - HATE doctor の診断結果生成
  - artifact resolver の path / URL / artifact ref 解決
  - schema registry の JSON Schema / 互換性 / deprecated field validation
  - adapter conformance fixtures による最低準拠 validation
  - adapter SDK manifest / required interface / failure contract validation
  - risk debt register の status / aging / owner / sourceRefs validation
  - adapter registry と profile inheritance の validation
  - matrix / shard / retry aggregation
  - path normalization
  - RanD requirements packet / audit packet の schema 最小 validation
  - requirement-evidence alignment の生成
  - manual-bb bridge の補完要求生成
  - shipyard-cp WorkerResult / RunSystemPacket mapping
  - workflow-task-seed / workflow-acceptance-record / workflow-evidence の schema 最小 validation
  - workflow-docs-stale / workflow-birdseye-map の生成
  - artifact budget report の集計
- product error code taxonomy と remediation catalog の validation
  - risk debt register の owner / age / sourceRefs validation
  - privacy report / artifact quarantine の validation
  - privacy / quarantine safety check と output policy の validation
  - domain model（org / workspace / project / repo / run / bundle / profile）の schema validation
  - support diagnostic bundle の secret / PII / unsafe artifact exclusion validation
  - hosted read model API response envelope / source refs / RBAC validation
  - release / migration policy の RG-1..RG-8 evidence validation
  - entitlement manifest / usage report の edition / limit / over-limit validation
  - customer docs index の audience / source_contracts / review date / verification validation
  - incident record / SLO report の severity / status / timeline / evidence_refs validation
  - adoption plan / renewal readiness の milestone / owner / adoption gap validation
  - security review record / trust packet の control mapping / open finding / freshness validation
  - telemetry event の allowed / prohibited signal / retention / redaction_status validation
  - residency profile / deployment topology の data class routing / network / recovery validation
  - roadmap item / product decision record の source_refs / acceptance_refs / status validation
  - accessibility report / localization report の target / locale fallback / stable id validation
  - commercial commitment / contract exception の source_contracts / verification_refs / expiry validation
  - audit fixture manifest / assurance pack の safe_to_share / expected output / finding status validation
  - requirements portfolio item / health report の tier / stage / dependency / WIP validation
- 結合:
  - Run→Collect→Normalize→Precheck→Export のパイプライン
  - P0b: QEG export fixture による node / edge 最低項目の検証
  - P0b: HATE optional evidence を QEG fixture に取り込み、QEG `validate / gate / record`
    相当で破綻しないこと
  - P0a 最小入力だけでの local-first precheck 判定
  - P0a golden fixture の input / expected 差分が説明可能であること
  - P0a DQ fixture（sha missing、malformed JUnit、artifact missing、
    coverage-only、record missing）が期待 decision / exit code を返すこと
  - P1b: RanD audit packet fixture を入力し、要件ごとの evidence gap が再現可能に出ること
  - P1b: shipyard RunSystemPacket fixture に HATE artifact refs を添付し、advisory evidence として保存可能な JSON が出ること
  - P1b: workflow-cookbook 接続 fixture から Task Seed / Acceptance / Evidence の参照連鎖が生成されること
  - P1a: frozen bundle を replay して AETE / DQ / QEG export が再現されること
  - P1a: base/head fixture を compare して trust delta / DQ 増減 / risk coverage 低下が出ること
  - P1a: doctor / resolver / schema registry / conformance fixtures が
    summary と JSON の双方で診断結果を出すこと
  - P1a: adapter SDK conformance report が adapter manifest / expected output /
    failure taxonomy と矛盾しないこと
  - P1a: risk debt register が recurring gap と closed gap を再現可能に説明できること
  - P1b: high-risk gap から manual-bb 補完要求が生成されること
  - P2: optional な PR annotation / attestation 未設定でも local-first precheck が完了すること
  - P2/P3: hosted dashboard / REST API / enterprise connector 未設定でも canonical
    bundle の replay と QEG export が変わらないこと
  - P2/P3: hosted read model を canonical bundle から再構築できること
  - P2/P3: unsafe artifact が summary / QEG export / external export /
    diagnostic bundle に漏れないこと
  - P2/P3: migration dry-run が schema / profile / adapter / QEG export 差分を説明できること
  - P2/P3: over-limit / entitlement 変更が local-first precheck と QEG export を変えないこと
  - P2/P3: stale docs / broken source contract が customer docs index と workflow-docs-stale に出ること
  - P2/P3: Sev1 / Sev2 incident fixture から containment / status update / postmortem due date が出ること
  - P2/P3: adoption fixture から first evidence、integration gap、renewal readiness が説明できること
  - P2/P3: security review fixture から trust packet と open finding の状態が説明できること
  - P2/P3: telemetry off / aggregate / support bundle の各 mode で privacy boundary が守られること
  - P2/P3: private tenant / customer managed / air-gapped fixture でも local-first precheck が変わらないこと
  - P2/P3: roadmap decision fixture が customer request / docs / release migration と矛盾しないこと
  - P2/P3: accessibility / localization fixture で color-only status、missing translation、
    unstable translated identifier を検出できること
  - P2/P3: commercial commitment fixture で unsupported commitment と contract exception を検出できること
  - P2/P3: audit fixture から expected output を再計算し、assurance summary に open finding を表示できること
  - P2/P3: requirements portfolio fixture で P0 dependency leak、WIP 超過、owner 不在を検出できること
  - P3: product-readiness fixture から PRG-0..PRG-6 の未達項目が説明できること
- 補助:
  - 変更ファイルなし run の再現チェック（deterministic）
  - 不正な入力を与えた場合の `hard_dq` / evidence ineligible 判定
  - 外部 adapter 未設定時にも local-first precheck が完了すること
  - high-risk path に実行証跡が 0 件のとき no-go candidate または manual 補完要求になること
  - public summary に `safe_for_summary=false` の artifact 参照が出ないこと
  - unsafe artifact が summary / QEG sourceRefs / export alias に漏れないこと

## 検証チェックリスト

- [ ] `TASK.codex.md` の Task Seed が実装順で消化されている
- [ ] 主要出力（`HATE-*.json`, `qeg-bundle.json`, `record.json`）が生成される
- [ ] 主要 JSON / NDJSON record が共通 envelope を満たす
- [ ] DQ 発生時と non-DQ 時の判定差分が明確
- [ ] `hard_dq` / `soft_gap` の挙動が adapter / AETE profile と一致している
- [ ] P1a では AETE 8 次元 rubric の採点根拠が `aete-score.json` に残る
- [ ] P1a では AETE の score confidence / calibration status が JSON と summary に残る
- [ ] P1a では canonical test identity が rename / parameterized / matrix fixture で検証されている
- [ ] artifact manifest に hash / redaction / retention / exposure 情報が残る
- [ ] artifact manifest に classification / redaction rule / summary 公開可否が残る
- [ ] artifact safety が secret / MIME / archive / symlink / path traversal / 外部 URL 参照を検査している
- [ ] P1a では adapter capability manifest が未対応粒度を明示している
- [ ] P1a では adapter / AETE profile ごとの DQ / AETE / manual 補完条件が fixture で検証されている
- [ ] P1a では matrix / shard / retry aggregation が fixture で検証されている
- [ ] P1a では path normalization が QEG sourceRefs / artifact metadata と整合している
- [ ] P1a では `HATE doctor` が adapter / schema / path / provenance /
      QEG fixture の診断結果を出せる
- [ ] P1a では artifact resolver が summary / manifest / QEG sourceRefs の
      artifact 参照を同じ規則で解決している
- [ ] P1a では schema registry が `HATE/v1` schema と deprecated field 方針を持つ
- [ ] P1a では adapter conformance fixtures が正常・破損・欠損・retry/matrix
      混在入力を検証できる
- [ ] P1a では `SCHEMA_REGISTRY_CONTRACT.md` の field policy / fixture matrix /
      version policy が実装契約に反映されている
- [ ] P1a では `ADAPTER_SDK_CONTRACT.md` の manifest / interface / failure contract /
      conformance report が実装契約に反映されている
- [ ] P1a では `RISK_DEBT_REGISTER.md` の debt type / status / aging /
      recommendation link が実装契約に反映されている
- [ ] P0b では QEG minimal valid bundle fixture が検証されている
- [ ] QEG が担う Gate policy / waiver / approval / retention / immutability /
      schema migration を HATE が重複実装していない
- [ ] P1b では RanD `requirements_audit_packet.json` と HATE evidence map の結線が検証されている
- [ ] P1b では RanD の Requirement Definition Gate verdict を HATE が上書きしていない
- [ ] P1b では `requirement-evidence-alignment.json` が requirement ごとの未検証 acceptance と source_refs を持つ
- [ ] P1b では shipyard-cp `RunSystemPacket` / `WorkerResult` fixture から `shipyard-run-evidence.json` を生成できる
- [ ] P1b では HATE が shipyard-cp の state machine / publish approval / worker dispatch を重複実装していない
- [ ] P1b では `workflow-task-seed.json` から HATE-MVP-* と acceptance refs を辿れる
- [ ] P1b では `workflow-acceptance-record.json` が acceptance record 必須 field を満たす
- [ ] P1b では `workflow-evidence.jsonl` が HATE artifact refs と DQ / AETE summary を保持する
- [ ] P1b では `workflow-docs-stale.json` が stale docs / schema / fixture を検出できる
- [ ] P1b では `workflow-birdseye-map.json` が HATE docs / schema / fixture の依存候補を出せる
- [ ] P1b では HATE が workflow-cookbook の checker / plugin host / Birdseye 生成器を重複実装していない
- [ ] P0a 最小成果物だけで local-first precheck 判定が完了する
- [ ] `P0A_GOLDEN_PATH.md` の input / expected / decision enum / DQ fixture が
      docs と tests から同じ契約として参照されている
- [ ] P0a Quickstart が外部 SaaS、QEG runtime、SSO、dashboard なしで実行できる
- [ ] 外部 SaaS adapter 未設定でも P0 の local-first precheck 判定が通る
- [ ] `RUNBOOK.md` の手順が最新化されている
- [ ] レビューで `coverage` が単独評価になっていないことを確認
- [ ] `ENTERPRISE_PRODUCT_REQUIREMENTS.md` が product / enterprise / compliance /
      supportability 要件の正本として参照されている
- [ ] P2/P3 productization が local-first precheck と QEG export の必須依存になっていない
- [ ] product error code と remediation が user-facing failure に紐づく
- [ ] `PRODUCT_ERROR_TAXONOMY.md` の core error code、summary policy、
      diagnostic bundle 契約が受入条件に反映されている
- [ ] `ENTERPRISE_DOMAIN_MODEL.md` の scope、role、classification、retention、
      audit event、read model が受入条件に反映されている
- [ ] risk debt register が soft gap / manual 補完要求を継続追跡できる
- [ ] support diagnostic bundle が secret / PII / unsafe artifact を含まない
- [ ] PRG-0..PRG-6 の Product Readiness Gate が artifact / metric で検証可能
- [ ] `PRIVACY_QUARANTINE_CONTRACT.md` の classification / safety checks /
      quarantine / output policy が受入条件に反映されている
- [ ] `HOSTED_READ_MODEL_API.md` の source artifact / API response / RBAC /
      consistency rule が受入条件に反映されている
- [ ] `RELEASE_MIGRATION_POLICY.md` の release gates / migration artifacts /
      compatibility matrix / rollback policy が受入条件に反映されている
- [ ] `PACKAGING_ENTITLEMENT_CONTRACT.md` の edition / entitlement / usage meter /
      over-limit / procurement artifact が受入条件に反映されている
- [ ] `CUSTOMER_DOCUMENTATION_CONTRACT.md` の required docs / audience /
      source_contracts / freshness / verification が受入条件に反映されている
- [ ] `SLO_INCIDENT_RESPONSE_CONTRACT.md` の SLO / incident class / severity /
      containment / communication / postmortem が受入条件に反映されている
- [ ] `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` の adoption stage / success plan /
      adoption health / renewal readiness が受入条件に反映されている
- [ ] `SECURITY_REVIEW_TRUST_CONTRACT.md` の trust packet / control mapping /
      vulnerability handling / freshness が受入条件に反映されている
- [ ] `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` の telemetry mode / allowed signal /
      prohibited signal / retention / analytics outputs が受入条件に反映されている
- [ ] `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` の deployment mode / residency profile /
      data class routing / backup / recovery が受入条件に反映されている
- [ ] `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` の roadmap item / decision record /
      customer request / deprecation decision が受入条件に反映されている
- [ ] `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` の accessibility target / message catalog /
      locale fallback / stable identifiers が受入条件に反映されている
- [ ] `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` の commitment register /
      procurement response / contract exception / commercial risk が受入条件に反映されている
- [ ] `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` の audit fixture / assurance pack /
      evidence room / audit finding が受入条件に反映されている
- [ ] `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` の tier / stage / WIP /
      dependency / portfolio health が受入条件に反映されている
