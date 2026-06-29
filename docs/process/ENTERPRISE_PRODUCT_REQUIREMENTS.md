---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Enterprise Product Requirements

## 1. 目的

この文書は `harness-auto-test-evidence` を、実装準備用ハブから
enterprise-ready なプロダクト水準へ引き上げるための要件正本である。

ここでいう enterprise-ready なプロダクト水準は、大企業・規制産業の
調達、監査、運用、セキュリティ審査、サポート、契約更新に耐える
製品品質を意味する。

HATE のプロダクト定義は次の通り。

- 自動テスト証跡を収集・正規化・信頼評価し、QEG に渡せる形へ変換する
- release Gate の最終正本ではなく、検証可能な optional evidence producer である
- 開発者、QA、SRE、セキュリティ、監査、経営層が同じ evidence bundle を
  それぞれの粒度で読めるようにする

## 2. 顧客と利用者

### 2.1 Ideal Customer Profile

| ICP | 課題 | HATE が提供する価値 |
|---|---|---|
| 成長中の SaaS 企業 | リリース品質と監査証跡が人手依存 | CI 証跡を再現可能な audit bundle にする |
| regulated SaaS / fintech / healthcare | テスト結果、ログ、承認、保持が分断 | artifact safety と QEG 接続で統制可能な証跡にする |
| 大規模 monorepo 組織 | 変更範囲とテスト証跡の対応が見えない | diff / risk / test / evidence の traceability を出す |
| AI coding agent 運用組織 | agent 生成変更の品質説明が弱い | agent run / task / evidence を自動テスト証跡と結線する |
| SI / enterprise platform team | 複数 repo / 複数言語の品質判断が属人化 | local-first な共通 envelope と adapter で統合する |

### 2.2 Personas

| Persona | 主要ジョブ | 必須アウトカム |
|---|---|---|
| Developer | PR の証跡不足を短時間で直す | 何を追加すべきかが `recommend` で分かる |
| QA Lead | risk ごとの証跡充足を確認する | risk coverage matrix と gap が説明可能 |
| SRE / Release Manager | release 前の自動証跡を確認する | HATE precheck と QEG export が再現可能 |
| Security Engineer | artifact と SARIF の安全性を確認する | secret / unsafe artifact が漏れない |
| Compliance / Auditor | 後から同じ判断を再計算する | frozen bundle / record / provenance が揃う |
| Engineering Executive | 品質投資と release risk を見る | product KPI と trend が読める |
| Platform Admin | org / repo / policy / retention を運用する | RBAC、audit log、profile、adapter 管理ができる |

## 3. Product Surface

HATE は次の surface を持つ。

| Surface | 用途 | 初期優先度 |
|---|---|---|
| CLI | local-first collect / normalize / precheck / export | P0 |
| GitHub Action | CI で evidence bundle と summary を生成 | P0b |
| JSON / NDJSON API | QEG / workflow-cookbook / shipyard-cp 連携 | P0 |
| Static report | job summary / HTML / Markdown | P0b |
| Adapter SDK | 新しい test runner / coverage / artifact の追加 | P1 |
| Web dashboard | evidence map、risk matrix、trend、admin | P2 |
| REST API | org / repo / run / evidence / profile / audit query | P2 |
| Admin console | org, RBAC, retention, connector, policy drift | P2 |
| Enterprise connectors | SSO, SCIM, SIEM, data warehouse, ticketing | P3 |

## 4. 商用パッケージ

| Edition | 対象 | 境界 |
|---|---|---|
| OSS / Local | 個人・小規模 repo | CLI、schema、fixtures、local precheck |
| Team | チーム CI | GitHub Action、summary、QEG export、adapter registry |
| Enterprise | 監査・統制が必要な組織 | RBAC、SSO、retention、audit log、dashboard、API |
| Regulated | 高規制領域 | attestation、immutability、private artifact storage、compliance pack |

商用化しても、P0 の local-first precheck と canonical schema は閉じた SaaS 機能に
依存させない。ローカルで再計算できることが監査価値の中心である。
edition、entitlement、usage meter、over-limit、procurement artifact の詳細契約は
`PACKAGING_ENTITLEMENT_CONTRACT.md` を正本とする。
customer success / adoption は `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md`、
security review / trust は `SECURITY_REVIEW_TRUST_CONTRACT.md`、
product telemetry / analytics は `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` を
それぞれ正本とする。
data residency / deployment は `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md`、
product governance / roadmap は `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md`、
accessibility / localization は `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` を
それぞれ正本とする。
legal / commercial contracting は `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md`、
audit fixture / assurance は `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md`、
requirements portfolio は `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` を
それぞれ正本とする。

## 5. Enterprise Product Functional Requirements

| ID | 要件 | 優先度 |
|---|---|---|
| PRD-01 | 5 分以内に最小 repo で `collect -> normalize -> precheck -> report` を完了する onboarding path を持つ | P0 |
| PRD-02 | `fixtures/golden/p0a-minimal` を製品の golden path とし、docs / schema / examples / tests が同じ入力を参照する | P0 |
| PRD-03 | GitHub Action で PR summary、artifact upload、QEG export を生成できる | P0b |
| PRD-04 | `doctor` が adapter / schema / path / provenance / QEG fixture の問題を product error code と修復提案で出す | P1 |
| PRD-05 | `recommend` が不足 evidence を test layer / owner / risk / sourceRefs に結びつける | P1 |
| PRD-06 | org / workspace / project / repo / run / evidence の domain model を定義する | P1 |
| PRD-07 | adapter SDK と conformance suite により、外部 adapter が互換性を自己検証できる | P1 |
| PRD-08 | Web dashboard が evidence map、risk coverage matrix、DQ trend、artifact budget を表示する | P2 |
| PRD-09 | REST API が runs、evidence、profiles、DQ、artifact metadata、audit refs を query できる | P2 |
| PRD-10 | RBAC により admin / maintainer / developer / auditor / viewer の権限を分離する | P2 |
| PRD-11 | SSO / SCIM / org audit log を enterprise connector として提供する | P3 |
| PRD-12 | SIEM / data warehouse / ticketing 連携で DQ、risk debt、unsafe artifact を外部運用へ流せる | P3 |
| PRD-13 | account-level retention / legal hold / export / deletion request を表現できる | P3 |
| PRD-14 | 製品内の summary と QEG export が同じ canonical bundle から生成されることを保証する | P0b |
| PRD-15 | OSS / Team / Enterprise / Regulated の機能境界と非依存保証を文書化する | P1 |
| PRD-16 | entitlement manifest と usage report を持ち、契約状態が precheck / QEG verdict を変更しない | P2 |
| PRD-17 | customer-facing docs の required set、freshness、verification を追跡できる | P2 |
| PRD-18 | incident class、severity、status communication、postmortem を evidence refs に紐づける | P2 |
| PRD-19 | adoption stage、success plan、adoption gap、renewal readiness を追跡できる | P2 |
| PRD-20 | security review record、trust packet、control mapping、vulnerability handling を提供できる | P2 |
| PRD-21 | privacy-safe telemetry と aggregate product analytics を opt-in で提供できる | P2 |
| PRD-22 | deployment mode、residency profile、data class routing、backup / recovery を表現できる | P2 |
| PRD-23 | roadmap item、product decision record、customer request register、deprecation decision を追跡できる | P2 |
| PRD-24 | dashboard、docs、CLI summary、support materials の accessibility / localization 状態を追跡できる | P2 |
| PRD-25 | commercial commitment、procurement response、contract exception、renewal risk を追跡できる | P2 |
| PRD-26 | audit fixture、assurance pack、auditor walkthrough、evidence room を提供できる | P2 |
| PRD-27 | requirements portfolio の tier、stage、WIP、dependency、portfolio health を追跡できる | P1 |

## 6. Enterprise Non-Functional Requirements

| ID | 要件 | 目標 |
|---|---|---|
| ENR-01 | Availability | hosted dashboard / API は月次 99.9% を目標にする |
| ENR-02 | Local determinism | local precheck は同一入力・同一 profile で 100% 同一出力 |
| ENR-03 | Performance | P0a golden fixture は 30 秒以内、標準 PR は 5 分以内 |
| ENR-04 | Scale | 1 run あたり 100k test case、10M coverage line hit まで設計上扱える |
| ENR-05 | Data isolation | org / workspace / repo 間で artifact と audit refs が混線しない |
| ENR-06 | Security | secret / token / unsafe artifact path を public summary に出さない |
| ENR-07 | Compliance | SOC2 / ISO27001 監査で説明できる control mapping を持つ |
| ENR-08 | Privacy | PII / secret / customer path の分類、redaction、export 制御を持つ |
| ENR-09 | Observability | pipeline stage、adapter failure、DQ、latency、artifact safety を計測する |
| ENR-10 | Supportability | error code、diagnostic bundle、version info、profile diff を出せる |
| ENR-11 | Compatibility | schema minor version は後方互換、breaking change は migration guide 必須 |
| ENR-12 | Cost control | artifact size、retention、storage class、egress の budget report を持つ |
| ENR-13 | Documentation freshness | required docs の stale / broken reference / overclaim を検出する |
| ENR-14 | Incident response | Sev1 / Sev2 の acknowledgement、containment、communication、postmortem を追跡する |
| ENR-15 | Adoption traceability | rollout / renewal の milestone、owner、next_action を追跡する |
| ENR-16 | Trust freshness | trust packet、SBOM、vulnerability report、subprocessor 情報を鮮度管理する |
| ENR-17 | Telemetry privacy | customer code、artifact content、raw path、test title、secret、PII を収集しない |
| ENR-18 | Residency safety | deployment mode / region で canonical bundle の再計算性を損なわない |
| ENR-19 | Roadmap truthfulness | roadmap、docs、release notes、customer communication が矛盾しない |
| ENR-20 | Accessibility / localization | stable identifier を変えずに human-readable surface を利用可能にする |
| ENR-21 | Commercial truthfulness | planned / unsupported capability を available と表現しない |
| ENR-22 | Audit reproducibility | audit fixture から expected output を再計算できる |
| ENR-23 | Portfolio discipline | P0a/P0b が P2/P3 productization に依存しない |

## 7. Security / Compliance Controls

| Control | 要件 |
|---|---|
| Identity | SSO / SCIM / service account / short-lived token を想定する |
| Authorization | RBAC と least privilege を前提に、auditor は read-only とする |
| Audit log | profile 変更、adapter 追加、export、artifact access、override request を記録する |
| Secrets | artifact と logs を secret scan し、検出時は quarantine する |
| Data retention | artifact type / classification / customer policy ごとに retention を分ける |
| Immutability | frozen bundle と audit record は改ざん検知可能な hash chain を持つ |
| Network | 外部 URL artifact は SSRF を避けるため allowlist / denylist / metadata IP block を持つ |
| Privacy | public summary には safe field のみ出し、unsafe path / token / PII を出さない |
| Incident | unsafe artifact leak、schema drift、wrong eligibility を incident class として扱う |
| Vendor review | data flow、subprocessor、encryption、backup、deletion の説明資料を持つ |
| Trust packet | data flow、controls、privacy、SBOM、vulnerability、subprocessor を source_refs 付きで出す |
| Telemetry | opt-in、aggregate、minimum necessary を前提に prohibited signal を拒否する |
| Residency | data class routing、region boundary、network、backup / recovery を説明する |
| Governance | roadmap decision、customer request、deprecation を source_refs 付きで記録する |
| Accessibility | DQ / severity / incident status を color-only signal にしない |
| Contracting | commercial commitment と exception を source contract へ接続する |
| Assurance | audit fixture と evidence room は unsafe artifact を含めない |
| Portfolio | owner / acceptance / dependency / WIP を追跡する |

### 7.1 RBAC / Audit Projection Contract

`enterprise-control-report` は connector dry-run に加えて、local-first の
RBAC decision と audit event projection を保持する。対象 resource は
run、artifact、report、manual_review、export、admin、audit とし、role は
admin、maintainer、reviewer、auditor、viewer を最小集合とする。

RBAC decision は `actor`、`role`、`action`、`resource`、`decision`、
`reason`、`allowed_scope`、`sourceRefs` を持ち、precheck / QEG / release の
readiness verdict を変更してはならない。quarantined artifact は raw content
ではなく safe metadata のみを許可し、raw export は deny として audit event に
接続する。

Audit event は read、export、review、quarantine、release、admin operation を
記録し、`actor`、`action`、`resource`、`decision`、`reason`、`timestamp`、
`sourceRefs` を必須とする。必須 audit event が欠ける場合は enterprise report
上の hold finding とし、core evidence verdict の上書きには使わない。

## 8. Domain Model

Enterprise-ready なプロダクトでは、単発 run ではなく account model が必要である。

| Entity | 説明 |
|---|---|
| Organization | 契約、SSO、retention、billing、policy の単位 |
| Workspace | org 内の product / business unit 境界 |
| Project | repo 群と QEG / workflow / shipyard 接続の単位 |
| Repository | source control repo |
| Run | CI / local / agent 実行の単位 |
| Attempt | rerun / retry の単位 |
| EvidenceBundle | HATE が生成する immutable bundle |
| Artifact | trace / screenshot / video / coverage / SARIF / logs |
| Profile | adapter / AETE / DQ / retention / summary safety の設定 |
| Adapter | ingest / normalize / export の plugin |
| RiskDebt | soft_gap / manual 補完 / conditional candidate の継続追跡 |
| AuditEvent | profile 変更、bundle export、artifact access などの監査イベント |

## 9. Product Metrics

| Metric | 意味 |
|---|---|
| Time to First Evidence | 初回 install から `precheck-decision.json` 生成までの時間 |
| Evidence Eligibility Rate | hard DQ なしで export 可能な run の割合 |
| High-Risk Evidence Coverage | high-risk changed path に直接証跡がある割合 |
| Unsafe Artifact Block Rate | unsafe artifact を summary/export から止めた割合 |
| Recommendation Acceptance Rate | `recommend` が提案した追加証跡が採用された割合 |
| Replay Reproducibility | frozen bundle replay が同一結果になる割合 |
| Adapter Conformance Rate | adapter が conformance fixture を満たす割合 |
| QEG Compatibility Rate | HATE bundle が QEG validate を通る割合 |
| Risk Debt Aging | soft gap / manual 補完要求が未解消で残る期間 |
| Support Deflection | `doctor` / docs で解決できた問題の割合 |
| Entitlement Safety | entitlement / over-limit 変更で precheck / QEG verdict が変わらない割合 |
| Documentation Freshness | required docs の fresh / verified / source-linked 比率 |
| Incident Response Traceability | Sev1 / Sev2 の owner / timeline / evidence refs / postmortem が揃う割合 |
| Adoption Health | adoption stage と blocked adoption gap の状態 |
| Trust Packet Freshness | trust packet 必須 artifact の鮮度 |
| Telemetry Privacy Safety | prohibited signal が telemetry event に混入しない割合 |
| Residency Safety | deployment mode / region 変更で precheck / QEG export が変わらない割合 |
| Roadmap Truthfulness | roadmap status と customer-facing docs の矛盾がない割合 |
| Accessibility Readiness | target surface の accessibility / localization report が揃う割合 |
| Commercial Commitment Truthfulness | unsupported / planned commitment が available と表現されない割合 |
| Audit Fixture Reproducibility | fixture から expected output を再計算できる割合 |
| Portfolio Health | owner 不在 / acceptance 不足 / P0 dependency leak / WIP 超過の件数 |

## 10. Product Readiness Gates

| Gate | 完了条件 |
|---|---|
| PRG-0: Prototype | `P0A_GOLDEN_PATH.md` の P0a golden fixture が local で再現可能 |
| PRG-1: Internal Alpha | 3 つ以上の repo で P0b QEG export が通る |
| PRG-2: Private Beta | 3 つ以上の adapter が conformance suite を通る |
| PRG-3: Team GA | GitHub Action、summary、QEG export、doctor、docs が安定 |
| PRG-4: Enterprise Ready | RBAC、audit log、retention、dashboard、support bundle が揃う |
| PRG-5: Regulated Ready | attestation、immutability、legal hold、compliance mapping が揃う |
| PRG-6: Enterprise Product Ready | enterprise sales / security review / support / SLO / customer docs / adoption / trust / residency / accessibility / contract / audit / portfolio metrics が揃う |

## 11. Support / Operations Requirements

| ID | 要件 |
|---|---|
| OPS-01 | すべての user-facing failure は stable error code と remediation を持つ |
| OPS-02 | `HATE doctor --bundle` 相当で support に渡せる diagnostic bundle を生成する |
| OPS-03 | diagnostic bundle は secret / PII / unsafe artifact を含めない |
| OPS-04 | schema / adapter / profile / QEG 互換性の version matrix を公開する |
| OPS-05 | release notes は breaking change、migration、deprecated field を明示する |
| OPS-06 | `SLO_INCIDENT_RESPONSE_CONTRACT.md` に従って support target、incident severity、known issue、rollback policy を文書化する |
| OPS-07 | customer environment で再現できない issue のため synthetic fixture を生成できる |
| OPS-08 | `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` に従って adoption plan / health / renewal readiness を作る |
| OPS-09 | `SECURITY_REVIEW_TRUST_CONTRACT.md` に従って trust packet と security review record を作る |
| OPS-10 | `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` に従って privacy-safe analytics を運用する |
| OPS-11 | `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` に従って residency profile と deployment topology を作る |
| OPS-12 | `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` に従って roadmap item と decision record を作る |
| OPS-13 | `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` に従って accessibility / localization report を作る |
| OPS-14 | `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` に従って commercial commitment / exception register を作る |
| OPS-15 | `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` に従って audit fixture / assurance pack を作る |
| OPS-16 | `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` に従って portfolio health report を作る |

## 12. Documentation Requirements

| Doc | 目的 |
|---|---|
| Quickstart | 5 分で P0a golden path を実行する |
| Concepts | Evidence, DQ, AETE, QEG, profile, artifact safety を説明する |
| Adapter Guide | adapter SDK と conformance fixture の作り方 |
| Security Guide | artifact safety、redaction、retention、summary safety |
| Admin Guide | org / repo / profile / RBAC / audit log の運用 |
| API Reference | schema、CLI、REST、JSON / NDJSON contract |
| Migration Guide | schema version、deprecated field、profile drift |
| Compliance Pack | SOC2 / ISO / regulated review 向け control mapping |
| Troubleshooting | error code、doctor output、common failure の修復 |

required docs、audience、source_contracts、freshness、verification の詳細契約は
`CUSTOMER_DOCUMENTATION_CONTRACT.md` を正本とする。

## 13. Enterprise Product Backlog

| ID | 内容 | 優先度 |
|---|---|---|
| HATE-PROD-001 | `P0A_GOLDEN_PATH.md` に従って P0a golden fixture と Quickstart を固定する | P0 |
| HATE-PROD-002 | `PRODUCT_ERROR_TAXONOMY.md` に従って product error code taxonomy と remediation catalog を作る | P1 |
| HATE-PROD-003 | `ENTERPRISE_DOMAIN_MODEL.md` に従って domain model schema（org/workspace/project/repo/run/bundle/profile）を定義する | P1 |
| HATE-PROD-004 | `ADAPTER_SDK_CONTRACT.md` に従って adapter SDK と conformance suite を公開できる形にする | P1 |
| HATE-PROD-005 | `RISK_DEBT_REGISTER.md` に従って risk debt register を設計する | P1 |
| HATE-PROD-006 | `PRIVACY_QUARANTINE_CONTRACT.md` に従って privacy report と artifact quarantine を設計する | P1 |
| HATE-PROD-007 | `HOSTED_READ_MODEL_API.md` に従って hosted dashboard / API の read model を設計する | P2 |
| HATE-PROD-008 | RBAC / audit log / retention policy を設計する | P2 |
| HATE-PROD-009 | SSO / SCIM / SIEM / warehouse connector を設計する | P3 |
| HATE-PROD-010 | compliance control mapping と security review pack を作る | P3 |
| HATE-PROD-011 | product pricing / packaging / edition boundary を文書化する | P3 |
| HATE-PROD-012 | support diagnostic bundle と incident class を定義する | P2 |
| HATE-PROD-013 | `RELEASE_MIGRATION_POLICY.md` に従って release / migration / rollback policy を定義する | P2 |
| HATE-PROD-014 | `PACKAGING_ENTITLEMENT_CONTRACT.md` に従って entitlement manifest / usage meter / over-limit handling を設計する | P2 |
| HATE-PROD-015 | `CUSTOMER_DOCUMENTATION_CONTRACT.md` に従って customer-facing docs 体系と freshness governance を設計する | P2 |
| HATE-PROD-016 | `SLO_INCIDENT_RESPONSE_CONTRACT.md` に従って SLO / incident response / status communication / postmortem を設計する | P2 |
| HATE-PROD-017 | `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` に従って adoption plan / health / renewal readiness を設計する | P2 |
| HATE-PROD-018 | `SECURITY_REVIEW_TRUST_CONTRACT.md` に従って trust packet / security review / vulnerability handling を設計する | P2 |
| HATE-PROD-019 | `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` に従って privacy-safe telemetry / product analytics を設計する | P2 |
| HATE-PROD-020 | `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` に従って data residency / deployment / recovery を設計する | P2 |
| HATE-PROD-021 | `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` に従って roadmap governance / decision record を設計する | P2 |
| HATE-PROD-022 | `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` に従って accessibility / localization を設計する | P2 |
| HATE-PROD-023 | `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` に従って contracting / procurement response を設計する | P2 |
| HATE-PROD-024 | `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` に従って audit fixture / assurance pack を設計する | P2 |
| HATE-PROD-025 | `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` に従って requirements portfolio / WIP governance を設計する | P1 |

## 14. SSO / SCIM Dry-Run Connector Contract

SSO / SCIM connector は enterprise enablement であり、P0/P1 の precheck や
product-ready verdict を上書きしない。実装は dry-run を既定とし、外部 IdP /
SCIM endpoint への live network call は行わない。

- SSO dry-run は issuer / audience / claim / group / role mapping を検証する。
- missing required claim、unsupported claim、invalid issuer は hold/manual review として報告する。
- SCIM dry-run は user/group create/update preview を出すが、delete/purge 系の destructive action は denied action とする。
- disabled connector と connector failure は non-gating warning とし、canonical bundle を変更しない。
- diagnostic には connector token、client secret、private URL、raw artifact を含めない。
- SIEM / warehouse / ticketing / support connector は safe payload preview のみを出し、unsafe artifact export は hard DQ として止める。
- evidence は `enterprise-control-report.json` の connector dry-run section と audit refs に残す。

## 14. Non-Goals

- HATE が QEG の release Gate 正本、waiver、approval、immutability を再実装しない
- HATE が full ALM / test management suite にならない
- HATE が外部 SaaS 未導入で local-first precheck を実行できない状態にしない
- HATE が customer source code や artifact 本体を必ず hosted service に送る設計にしない
- HATE が AETE score を単独の release approval として扱わない
- HATE が entitlement / over-limit を evidence eligibility の根拠として扱わない
- HATE が customer-facing docs で未実装機能を実装済みのように表現しない
- HATE が incident response を理由に canonical evidence / sourceRefs / hash を改変しない
- HATE が adoption health や renewal readiness を evidence eligibility の根拠として扱わない
- HATE が trust packet に customer source code、secret、PII、unsafe artifact を含めない
- HATE が telemetry のために customer code、artifact content、raw path、test title を収集しない
- HATE が region / deployment mode を evidence eligibility の根拠として扱わない
- HATE が roadmap candidate を released として customer-facing docs に出さない
- HATE が localization により schema field、error code、record_id、adapter id を変更しない
- HATE が unsupported / planned commitment を available として procurement response に出さない
- HATE が assurance pack から open finding や limitation を隠さない
- HATE が P2/P3 productization を理由に P0a/P0b local-first loop を遅らせない

## 15. 実装順の原則

1. P0a golden path を executable fixture に落とす
2. P0b QEG export と summary を同一 bundle から生成する
3. P1a 診断基盤で adapter / schema / artifact safety の事故を減らす
4. P1a 再現性で replay / compare / test identity / baseline を固める
5. P1a 説明と改善で explain / recommend / risk debt を足す
6. P2 で dashboard / API / RBAC / audit log / entitlement / customer docs /
   incident response / adoption / trust / telemetry / residency / roadmap /
   accessibility / contracting / assurance を設計する
7. requirements portfolio で WIP、dependency、P0 leak を継続監視する
8. P3 で enterprise connector、compliance pack、support operations を足す
