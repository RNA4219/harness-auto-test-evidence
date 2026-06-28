---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Guardrails & 行動指針

## 目的

- 設計破綻を避けるため、`harness-auto-test-evidence` 実装時の
  境界・評価軸・破壊的変更を明確化する。
- `coverage` 過信を避け、証跡品質評価（AETE）を主軸に据える。

## 原則

- 小さな差分で進める（1 周期あたり 2 ファイル + 100 行程度を目安）
- `code-to-gate` / `manual-bb-test-harness` / `quality-evidence-graph` を
  置き換えない。接続層として役割分担する。
- QEG が担う Gate policy / waiver / approval / retention / immutability /
  schema migration / source-backed Gate reason を HATE 側で再実装しない。
  HATE は自動テスト証跡の optional evidence producer / normalizer に徹する。
- RanD / KanoMode が出す requirements audit verdict は HATE 側で上書きしない。
  HATE は requirement / acceptance / risk に対する自動テスト証跡の有無、
  不足、AETE 根拠だけを出す。
- shipyard-cp の state machine / worker dispatch / publish approval を HATE 側で
  再実装しない。HATE は `WorkerResult` / `RunSystemPacket` / audit refs へ
  添付できる evidence bundle を出す。
- workflow-cookbook の Task Seed / Acceptance / Evidence / Birdseye / workflow plugin
  checker を HATE 側で再実装しない。HATE は cookbook へ渡せる
  `workflow-*` artifact の生成に留める。
- Enterprise product readiness は `docs/process/ENTERPRISE_PRODUCT_REQUIREMENTS.md` に集約し、
  hosted dashboard / enterprise connector / admin console を P0/P1 の必須依存にしない。
  HATE の正本価値は local-first evidence bundle の再計算性に置く。
- Packaging / entitlement は feature boundary と usage の説明であり、HATE precheck
  decision、QEG verdict、canonical evidence bundle を変更する根拠にしない。
- Customer-facing documentation は実装状態を超えた完了表現を避け、source contract と
  verification がない手順を正本化しない。
- Incident response は追跡 record と containment を追加する運用であり、既存の
  canonical evidence / sourceRefs / hash を削除・改変して障害を隠さない。
- Customer success / adoption 指標は導入支援と更新判断の補助であり、HATE precheck
  decision や QEG verdict を成功指標に合わせて変更しない。
- Security review / trust packet は説明資料であり、customer source code、secret、PII、
  unsafe artifact を含めず、QEG の approval / waiver を置き換えない。
- Product telemetry / analytics は opt-in / aggregate / minimum necessary を基本とし、
  telemetry off でも local-first precheck と QEG export が成立する。
- Data residency / deployment は展開方式とデータ所在地の制約であり、region や
  deployment mode を理由に evidence eligibility や QEG verdict を変更しない。
- Product governance / roadmap は意思決定の追跡であり、candidate / committed / released を
  customer docs や release notes で混同しない。
- Accessibility / localization は UX / docs 品質の契約であり、翻訳によって stable code、
  schema field、record_id、adapter id を変えない。
- Legal / commercial contracting は約束と例外の追跡であり、unsupported / planned capability を
  available と表現しない。
- Audit fixture / assurance は再計算可能性の提示であり、QEG の Gate policy / waiver /
  approval / immutability を置き換えない。
- Requirements portfolio は実装順の運営であり、P2/P3 productization を P0a/P0b の
  必須依存にしない。
- 全 artifact に以下を必須付与:
  - `schema_version`
  - `commit_sha`
  - `run_id` または `run_attempt`
  - `created_at`
  - `sha256`（可能な範囲）
- 証跡整合を崩す入力は「可視化優先」せず `DQ` または `disqualified` 扱いにする。
- 外部システム連携は任意実装とし、まず local-first を優先する。

## 実装制約

- 既存ドキュメント契約を壊さず追加を優先
- schema 変更は `record` と `acceptance` に追跡可能にする
- 外部 API 利用は最小限とし、secret / パス / token を `record` へ平文保存しない
- HATE precheck の正規出力名は `precheck-decision.json` とし、
  `gate-decision.json` は既存互換 alias に留める。いずれも release Gate 正本と
  混同しない。判定ロジックに曖昧なデフォルト値を残さない
- 失敗時は `hard fail` / `soft fail` を分離し、exit code を分かりやすくする
- adapter が取得できない証跡粒度は capability manifest に明示し、
  AETE の欠損を暗黙の成功として扱わない
- DQ、AETE threshold、必須 artifact、manual 補完条件は HATE の
  adapter / AETE profile に束縛し、実行時の雰囲気で判定を変えない。
  最終 Gate policy は QEG に委譲する
- AETE score は `rubric_version`, `profile_version`, `score_confidence`,
  `calibration_status` を必ず添え、未校正 score を release Gate の客観判定として
  表現しない
- public summary には `safe_for_summary=false` の artifact path や
  redaction 未完了の trace / screenshot / video / log を出さない
- public summary / QEG export / external export には、secret scan、MIME / 拡張子整合、
  archive 展開制限、symlink / path traversal、外部 URL 参照の安全確認に失敗した
  artifact 参照を出さない
- QEG export は minimal valid bundle fixture で互換性を確認してから
  gate / record の正本入力として扱う
- RanD audit packet と結線する場合は、`no_go` / `conditional_go` issue を
  `coverage` や `passed tests` だけで `go` 相当に変換しない
- shipyard-cp へ渡す場合は advisory evidence として扱い、Shipyard 側の
  `acceptance`, `integrate`, `publish` の状態遷移条件を HATE が変更しない
- workflow-cookbook へ渡す場合は、完了表現が実装状態を超えないようにし、
  Task Seed、Acceptance、Evidence の参照連鎖を欠損させない
- matrix / shard / retry aggregation は決定的に実装し、同じ入力で異なる
  aggregate status を出さない
- test identity は `canonical_test_id`, `identity_components`, `aliases` を使って
  明示し、rename / parameterized test / matrix による履歴の断絶を暗黙に扱わない
- path normalization は QEG sourceRefs / artifact metadata へ渡す前に完了させる
- `HATE doctor` / artifact resolver / schema registry /
  adapter conformance fixtures は診断・参照解決・互換性確認の補助機能とし、
  QEG の `validate / gate / record` や release approval の代替にしない
- hosted dashboard / REST API / enterprise connector は canonical bundle から派生する
  read model とし、HATE 独自の release approval 正本を持たない
- product error code、support diagnostic bundle、privacy report、risk debt register は
  運用補助であり、QEG の Gate policy / waiver / approval を上書きしない
- `PRODUCT_ERROR_TAXONOMY.md` の error code は user-facing failure の説明用であり、
  QEG verdict や HATE precheck decision の enum を勝手に増やさない
- `ENTERPRISE_DOMAIN_MODEL.md` の org / workspace / project model は hosted read model
  の境界であり、P0/P1 local bundle の必須入力にしない
- `SCHEMA_REGISTRY_CONTRACT.md` は HATE output schema の前段契約であり、
  QEG 本体の schema migration 正本を置き換えない
- `ADAPTER_SDK_CONTRACT.md` に従う adapter は normalized evidence を生成するだけで、
  HATE precheck decision や QEG verdict を直接決めない
- `RISK_DEBT_REGISTER.md` の risk debt は不足証跡の継続追跡であり、
  waiver / approval / release decision として扱わない
- `PRIVACY_QUARANTINE_CONTRACT.md` の quarantine は unsafe artifact の隔離と
  説明であり、artifact の安全性を未確認のまま summary / export に出さない
- `HOSTED_READ_MODEL_API.md` の dashboard / API は canonical bundle から派生する
  read model であり、HATE precheck decision や QEG verdict を上書きしない
- `RELEASE_MIGRATION_POLICY.md` の release gates は HATE 自身の互換性確認であり、
  QEG の release Gate policy や approval を代替しない
- `PACKAGING_ENTITLEMENT_CONTRACT.md` の entitlement は hosted / support / usage の
  有効範囲を表すだけで、evidence eligibility や QEG verdict を上書きしない
- `CUSTOMER_DOCUMENTATION_CONTRACT.md` の docs freshness は運用検査であり、
  outdated docs を根拠に実装済み・検証済みと表現しない
- `SLO_INCIDENT_RESPONSE_CONTRACT.md` の incident response は status communication、
  containment、postmortem の追跡であり、障害対象の evidence record を改変しない
- `CUSTOMER_SUCCESS_ADOPTION_CONTRACT.md` の adoption gap は導入課題であり、
  evidence gap / risk debt / incident と混同しない
- `SECURITY_REVIEW_TRUST_CONTRACT.md` の trust packet は canonical evidence から派生する
 説明であり、sourceRefs / hash / QEG record を加工しない
- `PRODUCT_TELEMETRY_ANALYTICS_CONTRACT.md` の telemetry は customer code、
  artifact content、raw path、test title、secret、PII を収集しない
- `DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md` の deployment mode は data flow の違いであり、
  local-first precheck と frozen bundle replay を必須依存にしない
- `PRODUCT_GOVERNANCE_ROADMAP_CONTRACT.md` の roadmap communication は実装状態を超えて
  available / released と表現しない
- `ACCESSIBILITY_LOCALIZATION_CONTRACT.md` の localized message は human-readable text のみを
  対象とし、machine-readable identifier を変えない
- `LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md` の commercial commitment は source contract と
  verification がない状態で customer-facing commitment にしない
- `AUDIT_FIXTURE_ASSURANCE_CONTRACT.md` の assurance pack は open finding / limitation を隠さない
- `REQUIREMENTS_PORTFOLIO_OPERATING_MODEL.md` の prioritization rule は HATE precheck decision /
  QEG verdict を変更しない

## 非機能ガード

- 同一入力に対して AETE / precheck 判定は決定的（deterministic）であること
- `run_id` 変更時に、同一履歴が混線しないこと
- matrix / shard / retry の順序差で AETE / aggregate status が変わらないこと
- 監査可能な履歴を残すため JSONL / NDJSON を優先採用
- baseline / history index を導入する場合も、run 単位 record と履歴参照を
  混在させない
- P2/P3 productization を進める場合も、P0a golden path が外部 SaaS、
  SSO、dashboard、RBAC、課金、enterprise connector に依存しないこと
- Entitlement / over-limit / support plan の差で local-first precheck 結果が変わらないこと
- Hosted outage 時も local CLI と frozen bundle replay が継続できること
- Customer-facing docs は release / schema / adapter / security policy の変更と同じ cadence で
  stale check されること
- Adoption / renewal readiness は owner、milestone、source_refs を持つこと
- Trust packet は freshness policy と open finding の owner / due date を持つこと
- Telemetry event は送信前に prohibited signal safety check を通すこと
- Residency profile は data class routing と owner を持つこと
- Roadmap item は source_refs、decision status、owner を持つこと
- Accessibility / localization report は target surface、review date、owner を持つこと
- Commercial commitment は status、expiry、owner、verification_refs を持つこと
- Audit fixture は expected output、verification command、safe_to_share を持つこと
- Portfolio item は tier、stage、dependencies、acceptance_refs を持つこと

## 例外条件

- 証跡欠損（artifact hash 不在、coverage 破損、timestamp 破れ）時は即時 DQ
- 重要な risk に対して実行証跡が 0 件のケースは、manual 補完を要求

## リマインダー

- 変更前に `harness-auto-test-evidence/BLUEPRINT.md` の Scope/I/O を再確認すること
- 変更後に `TASK` も update し、`EVALUATION.md` の受入と紐づけること
