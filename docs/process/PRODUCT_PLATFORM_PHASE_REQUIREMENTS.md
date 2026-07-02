---
intent_id: INT-HATE-PRODUCT-PLATFORM-PHASE-REQUIREMENTS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-07-01
next_review_due: 2026-07-15
---

# Product Platform Phase Requirements

本書は HATE を PoC から会社利用可能な品質評価基盤へ進めるための
5フェーズ要件定義正本である。

対象フェーズ:

- 評価基盤フェーズ: real-repo 評価を複数 repo に継続適用し、score/history/regression を固める
- 運用基盤フェーズ: findings、risk debt、manual review、owner/due date、accepted debt expiry を一元化する
- 拡張基盤フェーズ: detector を plugin 化し、profile / policy / threshold を外部設定できるようにする
- 利用面フェーズ: CLI だけでなく、read model、JSON API、HTML report、dashboard を作る
- 大規模化フェーズ: cache、parallel execution、incremental scan、repo roster scheduler、artifact store を入れる

詳細仕様は `PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md`、実装分解は
`PRODUCT_PLATFORM_PHASE_IMPLEMENTATION_PACKETS.md` を正本とする。
物理 store、policy config、RBAC、dashboard、benchmark fixture は以下を
詳細正本とする。

- `PLATFORM_STORE_SCHEMA_SPEC.md`
- `PLATFORM_POLICY_CONFIG_SPEC.md`
- `PLATFORM_RBAC_MATRIX_SPEC.md`
- `PLATFORM_DASHBOARD_WIREFRAME_SPEC.md`
- `PLATFORM_BENCHMARK_FIXTURE_SPEC.md`
- `PLATFORM_CONNECTOR_SYNC_SPEC.md`
- `PLATFORM_PLUGIN_SANDBOX_SPEC.md`

## 1. Product Principles

| Principle ID | Principle | Requirement |
|---|---|---|
| PPH-PRIN-001 | 評価は継続証跡である | 1回の成功ではなく、履歴、baseline、regression、drift を保存する |
| PPH-PRIN-002 | 外部 repo は評価対象であって修正対象ではない | owned と external を roster で分離し、external hold を勝手に修正しない |
| PPH-PRIN-003 | 運用情報は一元化する | finding、risk debt、manual review、owner、due date、expiry を別々の report に閉じ込めない |
| PPH-PRIN-004 | detector は設定可能である | profile、policy、threshold は code fork なしで変更できる |
| PPH-PRIN-005 | 利用面は証跡を薄めない | dashboard/API/HTML は raw evidence ではなく canonical report の view model で表現する |
| PPH-PRIN-006 | 大規模化は証跡完全性を落とさない | cache/parallel/incremental は sourceRefs、hash、decision rationale を保持する |
| PPH-PRIN-007 | 正本と投影を分離する | API、dashboard、tracker、HTML は canonical store の projection であり、正本状態を直接上書きしない |

## 2. Personas

| Persona ID | Persona | Primary Need | Blocking Pain |
|---|---|---|---|
| PPH-PER-QA | QA Lead | 複数 repo の評価傾向とリリース阻害理由を見る | repo ごとのログを手で読む必要がある |
| PPH-PER-REL | Release Manager | regression と accepted debt expiry を release 前に判断する | hold の責任者、期限、根拠が分散している |
| PPH-PER-PLAT | Platform Engineer | detector/profile/policy を組織標準として管理する | detector 追加がコード改修と密結合している |
| PPH-PER-DEV | Developer | 自分が直すべき finding と oracle 不足を知る | dashboard なしでは JSON artifact を追う必要がある |
| PPH-PER-AUD | Auditor | 過去の判定、手動判断、expiry、例外理由を再確認する | 履歴と manual review が統合されていない |
| PPH-PER-EXEC | Engineering Executive | 品質投資の成果、risk debt、repo health trend を見る | 点のテスト成功しか見えない |

## 3. Phase A: 評価基盤 Requirements

### 3.1 Scope

| Requirement ID | Requirement | Acceptance ID |
|---|---|---|
| PPH-EVAL-001 | real-repo roster を複数 repo、repo class、owned/external、suite kind、timeout profile で管理できる | PPH-AC-EVAL-001 |
| PPH-EVAL-002 | 各評価 run は run_id、source_version、roster hash、environment fingerprint、started/finished timestamp を保存する | PPH-AC-EVAL-002 |
| PPH-EVAL-003 | 評価結果は score、status、regression status、record_count、runtime、timeout、failure_kind を履歴として保存する | PPH-AC-EVAL-003 |
| PPH-EVAL-004 | baseline と current を比較し、pass to hold、record count collapse、runtime drift、new failure kind を regression として検出する | PPH-AC-EVAL-004 |
| PPH-EVAL-005 | external repo の hold は HATE implementation failure と分離し、external finding として保存する | PPH-AC-EVAL-005 |
| PPH-EVAL-006 | score は単純加算ではなく、evidence strength、risk criticality、freshness、regression penalty、manual debt penalty を合成する | PPH-AC-EVAL-006 |
| PPH-EVAL-007 | 履歴は repo、suite、profile、branch/source_version、time window で検索できる | PPH-AC-EVAL-007 |
| PPH-EVAL-008 | run が timeout した場合、子プロセス cleanup、partial output excerpt、timeout reason を保存する | PPH-AC-EVAL-008 |
| PPH-EVAL-009 | baseline の作成、昇格、凍結、失効は承認イベントと根拠付きで管理する | PPH-AC-EVAL-009 |
| PPH-EVAL-010 | run output は redaction と deterministic normalization を通して保存し、secret/PII/local absolute path を漏らさない | PPH-AC-EVAL-010 |

### 3.2 Non-Functional Requirements

| Requirement ID | Requirement |
|---|---|
| PPH-EVAL-NFR-001 | 100 repo / 1000 suite の履歴検索で P95 2秒以内を目標にする |
| PPH-EVAL-NFR-002 | run report は raw secret/PII/artifact body を保存しない |
| PPH-EVAL-NFR-003 | 同じ roster hash と source_version の再実行は比較可能な stable output を生成する |
| PPH-EVAL-NFR-004 | Windows、Linux、macOS の command summary parser 差分を dialect として扱う |

## 4. Phase B: 運用基盤 Requirements

### 4.1 Scope

| Requirement ID | Requirement | Acceptance ID |
|---|---|---|
| PPH-OPS-001 | finding、risk debt、manual review request、accepted decision を single operating record model に統合する | PPH-AC-OPS-001 |
| PPH-OPS-002 | 全 finding は owner、due_date、severity、readiness_effect、sourceRef、lifecycle_state を持つ | PPH-AC-OPS-002 |
| PPH-OPS-003 | risk debt は accepted、expired、revoked、superseded、resolved の状態遷移を持つ | PPH-AC-OPS-003 |
| PPH-OPS-004 | accepted debt expiry を日次または evaluation run 時に検出し、hard DQ / hold / soft gap へ反映する | PPH-AC-OPS-004 |
| PPH-OPS-005 | manual review は required_decision、blocking、reviewer、decision_reason、expiry_date、evidence_refs を保存する | PPH-AC-OPS-005 |
| PPH-OPS-006 | owner 未設定、期限切れ、根拠なし manual review は No-Go finding として扱う | PPH-AC-OPS-006 |
| PPH-OPS-007 | finding は duplicate/supersede/merge 可能で、履歴の監査 trail を失わない | PPH-AC-OPS-007 |
| PPH-OPS-008 | Slack/GitHub/issue tracker への同期は canonical operating record から生成し、外部 tracker を正本にしない | PPH-AC-OPS-008 |
| PPH-OPS-009 | finding escalation、通知、SLA breach は policy に基づき生成し、通知失敗も operating event として残す | PPH-AC-OPS-009 |
| PPH-OPS-010 | operating event は retention/legal hold/migration/rebuild 後も状態再構築できる | PPH-AC-OPS-010 |

### 4.2 Non-Functional Requirements

| Requirement ID | Requirement |
|---|---|
| PPH-OPS-NFR-001 | operating record は append-only audit event と current projection を分離する |
| PPH-OPS-NFR-002 | accepted debt 変更は actor、reason、before/after、sourceRef を必須とする |
| PPH-OPS-NFR-003 | lifecycle projection は同一 event stream から再構築できる |
| PPH-OPS-NFR-004 | owner と due date は optional 表示ではなく readiness 判定に影響する |

## 5. Phase C: 拡張基盤 Requirements

### 5.1 Scope

| Requirement ID | Requirement | Acceptance ID |
|---|---|---|
| PPH-EXT-001 | detector は plugin manifest、capability、input contract、output contract、version を宣言する | PPH-AC-EXT-001 |
| PPH-EXT-002 | detector plugin は local built-in、workspace plugin、organization policy plugin をロードできる | PPH-AC-EXT-002 |
| PPH-EXT-003 | profile、policy、threshold は JSON/YAML config から解決し、default/strict/release/custom をサポートする | PPH-AC-EXT-003 |
| PPH-EXT-004 | threshold は detector_id、signal_id、risk class、repo class、suite kind ごとに override できる | PPH-AC-EXT-004 |
| PPH-EXT-005 | plugin は sandboxed execution、timeout、resource limit、deterministic output validation を受ける | PPH-AC-EXT-005 |
| PPH-EXT-006 | plugin output は canonical finding/evidence schema に正規化され、不明 field は compatibility envelope に隔離する | PPH-AC-EXT-006 |
| PPH-EXT-007 | plugin conformance suite は positive/negative/malformed/backward-compat fixtures を必須にする | PPH-AC-EXT-007 |
| PPH-EXT-008 | policy drift は config hash と evaluated effective policy を保存して説明できる | PPH-AC-EXT-008 |
| PPH-EXT-009 | plugin API は semver、互換性 matrix、migration note、deprecated field policy を持つ | PPH-AC-EXT-009 |
| PPH-EXT-010 | release/regulated profile は plugin signature、allowlist、trust source を検証してから実行する | PPH-AC-EXT-010 |

### 5.2 Non-Functional Requirements

| Requirement ID | Requirement |
|---|---|
| PPH-EXT-NFR-001 | plugin failure は全体クラッシュではなく detector failure finding として隔離する |
| PPH-EXT-NFR-002 | release profile では unsigned/untrusted plugin を実行しない |
| PPH-EXT-NFR-003 | plugin API は semver と migration note を持つ |
| PPH-EXT-NFR-004 | config resolution は explainable で、どの値がどの file から来たかを出力する |

## 6. Phase D: 利用面 Requirements

### 6.1 Scope

| Requirement ID | Requirement | Acceptance ID |
|---|---|---|
| PPH-UX-001 | CLI は run、history、compare、findings、debt、review、policy、serve、report を提供する | PPH-AC-UX-001 |
| PPH-UX-002 | read model は runs、repos、findings、risk-debt、manual-review、score-history、policies を query できる | PPH-AC-UX-002 |
| PPH-UX-003 | JSON API は pagination、filter、sort、stale marker、RBAC denial、error taxonomy を持つ | PPH-AC-UX-003 |
| PPH-UX-004 | HTML report は single-run report、portfolio summary、regression diff、manual review brief を生成する | PPH-AC-UX-004 |
| PPH-UX-005 | dashboard は portfolio health、repo trend、open findings、expired debt、policy drift、external holds を表示する | PPH-AC-UX-005 |
| PPH-UX-006 | UI は loading、empty、partial、stale、permission denied、unsafe artifact hidden の状態を明示する | PPH-AC-UX-006 |
| PPH-UX-007 | dashboard/API は unsafe artifact body、secret、PII、external raw URL を表示しない | PPH-AC-UX-007 |
| PPH-UX-008 | auditor view は decision replay、sourceRefs、manual decision trail、policy version を辿れる | PPH-AC-UX-008 |
| PPH-UX-009 | API/dashboard は role、tenant、resource scope に基づく RBAC matrix と negative tests を持つ | PPH-AC-UX-009 |
| PPH-UX-010 | HTML report と read model は offline/self-contained、performance budget、schema compatibility を検証する | PPH-AC-UX-010 |

### 6.2 Non-Functional Requirements

| Requirement ID | Requirement |
|---|---|
| PPH-UX-NFR-001 | read model query P95 は local store 10万 finding で 2秒以内を目標にする |
| PPH-UX-NFR-002 | HTML report はネットワークなしで閲覧できる self-contained mode を持つ |
| PPH-UX-NFR-003 | API response は schema version と request_id を必ず含める |
| PPH-UX-NFR-004 | dashboard は canonical store から派生し、独自判定ロジックを持たない |

## 7. Phase E: 大規模化 Requirements

### 7.1 Scope

| Requirement ID | Requirement | Acceptance ID |
|---|---|---|
| PPH-SCALE-001 | cache は input hash、tool version、policy hash、environment fingerprint で key を作る | PPH-AC-SCALE-001 |
| PPH-SCALE-002 | parallel execution は repo/suite/detector 単位で依存関係と resource budget を守る | PPH-AC-SCALE-002 |
| PPH-SCALE-003 | incremental scan は changed files、risk map、dependency graph、previous evidence を使い範囲を決める | PPH-AC-SCALE-003 |
| PPH-SCALE-004 | repo roster scheduler は interval、cron、manual trigger、backoff、lease、retry、cancellation を持つ | PPH-AC-SCALE-004 |
| PPH-SCALE-005 | artifact store は content-addressed storage、quarantine、retention、legal hold、GC を提供する | PPH-AC-SCALE-005 |
| PPH-SCALE-006 | large monorepo run は partial result と resume token を保存し、timeout 後に再開できる | PPH-AC-SCALE-006 |
| PPH-SCALE-007 | cache hit は evidence freshness と policy compatibility を検証し、過期 cache を pass 扱いしない | PPH-AC-SCALE-007 |
| PPH-SCALE-008 | scheduler と artifact store は audit event を出し、read model から参照できる | PPH-AC-SCALE-008 |
| PPH-SCALE-009 | platform store は backup/restore、projection rebuild、corruption detection、schema migration を持つ | PPH-AC-SCALE-009 |
| PPH-SCALE-010 | 1000 repo / 100万 finding 級の容量計画、partitioning、benchmark、degradation mode を定義する | PPH-AC-SCALE-010 |

### 7.2 Non-Functional Requirements

| Requirement ID | Requirement |
|---|---|
| PPH-SCALE-NFR-001 | 1000 repo roster を分割 scheduling できる |
| PPH-SCALE-NFR-002 | 100万 finding の current projection rebuild を実行可能な batch job として設計する |
| PPH-SCALE-NFR-003 | artifact store は raw access approval なしに unsafe body を返さない |
| PPH-SCALE-NFR-004 | incremental scan は skipped scope を明示し、full-suite 証明と混同しない |

## 8. Acceptance Criteria Matrix

| Acceptance ID | Requirement Group | Must Prove |
|---|---|---|
| PPH-AC-EVAL-001 | roster model | owned/external、repo class、suite kind、timeout profile を schema で検証 |
| PPH-AC-EVAL-002 | run identity | run_id、roster hash、environment fingerprint が run manifest に保存される |
| PPH-AC-EVAL-003 | history | 同一 repo の複数 run を保存し、trend query が返る |
| PPH-AC-EVAL-004 | regression | baseline pass/current hold、record collapse、runtime drift を hold として検出 |
| PPH-AC-EVAL-005 | external repo | external hold が HATE implementation failure と分離される |
| PPH-AC-EVAL-006 | score | freshness/regression/manual debt penalty を含む説明可能 score が生成される |
| PPH-AC-EVAL-007 | search | repo/suite/profile/time window 検索ができる |
| PPH-AC-EVAL-008 | timeout | timeout cleanup と excerpt が残る |
| PPH-AC-EVAL-009 | baseline governance | baseline approval/freeze/expiry/revoke が audit event として残る |
| PPH-AC-EVAL-010 | output safety | secret/PII/local path が redacted され、normalization が deterministic である |
| PPH-AC-OPS-001 | operating model | finding/debt/review が同一 projection に現れる |
| PPH-AC-OPS-002 | ownership | owner/due_date 欠落が hold/hard DQ になる |
| PPH-AC-OPS-003 | debt lifecycle | accepted→expired→resolved 等の状態遷移が replay できる |
| PPH-AC-OPS-004 | expiry | expired accepted debt が evaluation/readiness に反映される |
| PPH-AC-OPS-005 | manual review | required_decision と evidence_refs が保存される |
| PPH-AC-OPS-006 | invalid review | ownerなし/根拠なし/期限切れが No-Go finding になる |
| PPH-AC-OPS-007 | dedupe | duplicate/supersede 後も audit trail が残る |
| PPH-AC-OPS-008 | tracker sync | external tracker ではなく canonical record から同期される |
| PPH-AC-OPS-009 | escalation | SLA breach と通知失敗が operating event として残る |
| PPH-AC-OPS-010 | lifecycle retention | retention/legal hold/migration/rebuild 後も projection が再構築できる |
| PPH-AC-EXT-001 | plugin manifest | detector manifest が schema validation される |
| PPH-AC-EXT-002 | loader | built-in/workspace/org plugin を解決できる |
| PPH-AC-EXT-003 | policy config | profile/policy/threshold を外部 config から解決できる |
| PPH-AC-EXT-004 | override | detector/repo/risk/suite 単位 threshold override が効く |
| PPH-AC-EXT-005 | sandbox | timeout/resource failure が finding 化される |
| PPH-AC-EXT-006 | normalization | plugin output が canonical finding に正規化される |
| PPH-AC-EXT-007 | conformance | plugin conformance fixtures が positive/negative/malformed を含む |
| PPH-AC-EXT-008 | drift | effective policy と hash が保存される |
| PPH-AC-EXT-009 | API migration | semver compatibility と migration note が検証される |
| PPH-AC-EXT-010 | plugin trust | unsigned/unallowlisted plugin が release/regulated profile で拒否される |
| PPH-AC-UX-001 | CLI | run/history/compare/findings/debt/review/policy/serve/report が使える |
| PPH-AC-UX-002 | read model | primary resources を query できる |
| PPH-AC-UX-003 | JSON API | pagination/filter/sort/RBAC/error contract がある |
| PPH-AC-UX-004 | HTML report | single-run/portfolio/regression/manual brief が生成される |
| PPH-AC-UX-005 | dashboard | health/trend/findings/debt/policy/external hold を表示 |
| PPH-AC-UX-006 | UI states | loading/empty/partial/stale/RBAC denied/unsafe hidden を表現 |
| PPH-AC-UX-007 | safe display | secret/PII/raw unsafe artifact を出さない |
| PPH-AC-UX-008 | audit view | replay/sourceRefs/manual trail/policy version を辿れる |
| PPH-AC-UX-009 | RBAC | role/tenant/resource scope の許可・拒否 matrix が通る |
| PPH-AC-UX-010 | offline/performance | offline HTML、read-model performance、schema compatibility が検証される |
| PPH-AC-SCALE-001 | cache key | input/tool/policy/environment hash で cache key を作る |
| PPH-AC-SCALE-002 | parallel | dependency/resource budget を守る parallel run |
| PPH-AC-SCALE-003 | incremental | changed scope と skipped scope を説明できる |
| PPH-AC-SCALE-004 | scheduler | interval/cron/manual/backoff/lease/retry/cancel を持つ |
| PPH-AC-SCALE-005 | artifact store | CAS/quarantine/retention/legal hold/GC を持つ |
| PPH-AC-SCALE-006 | resume | partial result と resume token で再開できる |
| PPH-AC-SCALE-007 | cache freshness | stale/incompatible cache が pass に使われない |
| PPH-AC-SCALE-008 | audit | scheduler/artifact event が read model で参照できる |
| PPH-AC-SCALE-009 | store recovery | backup/restore/rebuild/migration が sourceRefs と legal hold を保持する |
| PPH-AC-SCALE-010 | capacity | 1000 repo / 100万 finding benchmark と degradation mode が定義される |

## 9. No-Go Rules

- score が根拠 breakdown なしの単純加算なら評価基盤完了と呼ばない。
- finding、risk debt、manual review が別々の未接続 report のままなら運用基盤完了と呼ばない。
- detector 追加に本体コード編集が必須なら拡張基盤完了と呼ばない。
- CLI の JSON 出力しかなく、read model/API/HTML/dashboard がないなら利用面完了と呼ばない。
- `hate platform ...` が存在せず、real-repo / store / product / expansion の個別コマンドを利用者が
  手でつなぐ必要があるなら platform 利用面完了と呼ばない。
- product-grade status が docs-only skeleton の `no_go` 固定で、実装証跡、テスト証跡、
  実リポジトリ検証、QEG smoke、残摩擦を再計算しないなら product-grade 完了と呼ばない。
- cache/parallel/incremental が sourceRefs や policy hash を落とすなら大規模化完了と呼ばない。
- external repo hold を勝手に修正して pass を作る運用は評価証跡として無効とする。
- RBAC、retention/legal hold、baseline approval、plugin trust、backup/restore が
  acceptance に落ちていない場合、会社利用可能な仕様完了とは呼ばない。
- store schema、policy config、RBAC matrix、dashboard wireframe、benchmark fixture
  が正本仕様として存在しない場合、実装投入可能とは呼ばない。

## 9.1 Immediate Platform Closure Requirements

The first post-PoC closure increment must cover the following before further
feature work is counted as company-operable:

| Requirement ID | Requirement | Acceptance |
|---|---|---|
| PPH-UX-CLI-001 | `hate platform run` wraps real-repo roster execution and emits the same run manifest without weakening timeout, output safety, or external hold semantics. | CLI smoke creates `real-repo-evaluation-run-report.json`. |
| PPH-UX-CLI-002 | `hate platform history` queries the real-repo history store with repo/suite/status/time filters. | Query returns `real-repo-history-query-report`. |
| PPH-UX-CLI-003 | `hate platform compare` compares two real-repo run manifests or report files and emits added/removed/changed status, record count, runtime, and dialect deltas. | Pass-to-hold or record collapse is visible as a comparison finding. |
| PPH-UX-CLI-004 | `hate platform findings`, `debt`, and `review` project report directories into operator-readable JSON lists while preserving sourceRefs and not recomputing verdicts. | Empty lists are explicit; missing input is an error. |
| PPH-UX-CLI-005 | `hate platform policy explain` evaluates platform policy config and returns effective profile, threshold, plugin trust, retention, and scheduler decisions. | Existing policy fixtures pass through the platform CLI. |
| PPH-UX-CLI-006 | `hate platform report html` generates an offline, self-contained HTML summary from platform reports without raw unsafe artifact bodies. | HTML file contains status/finding summaries and source refs only. |
| PPH-GRADE-001 | Product-grade status recalculates from docs, mapped implementation files, mapped tests, latest real-repo bulk validation, and QEG smoke evidence. | Summary is no longer hard-coded `no_go`; residual blockers are explicit. |
| PPH-GRADE-002 | Product-grade status must stay below product-ready while unresolved real-data friction exists, including env cache friction, held owned repos, or build/typecheck-only checks without oracle inflation. | Status may be `conditional_go`, but `product_ready` remains false until blockers are cleared. |
| PPH-OPS-CLI-001 | `hate platform schedule` plans recurring runs with cache TTL, retry budget, and resume tokens so 100+ repos do not require blind full reruns. | Fresh pass entries become `cache_hit`; held entries plan bounded retries. |
| PPH-OPS-CLI-002 | `hate platform assign` projects findings into owner/due-date/SLA queues and holds missing owner or overdue work. | Missing owner/due date and breached SLA are emitted as findings. |
| PPH-OPS-CLI-003 | `hate platform plugin run` loads a plugin manifest, optionally executes a local command, and always routes output through sandbox trust/resource/output checks. | Malformed, unsigned, over-budget, crashed, or unsafe plugins cannot be hidden as pass. |
| PPH-OPS-CLI-004 | `hate platform score` computes explainable platform scores from real-repo history/reports using freshness, regression, manual debt, timeout, unsafe artifact, and oracle confidence. | Build/typecheck-only evidence lowers oracle confidence and does not inflate executable-test readiness. |

No-Go additions:

- A scheduler that always reruns every suite, has no resume token, or drops held
  suite retry context is not operationally acceptable.
- Findings without owner/due-date/SLA visibility are not acceptable for daily
  operation.
- Plugin support that only documents sandbox policy but cannot load and run a
  manifest is not platform runtime support.
- Score output without a component/penalty breakdown is not acceptable.

## 10. Traceability

| Phase | Requirements | Detail spec section | Implementation packet prefix |
|---|---|---|---|
| 評価基盤 | PPH-EVAL-* | `PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md#phase-a-evaluation-foundation` | PPH-PKT-EVAL-* |
| 運用基盤 | PPH-OPS-* | `PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md#phase-b-operations-foundation` | PPH-PKT-OPS-* |
| 拡張基盤 | PPH-EXT-* | `PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md#phase-c-extension-foundation` | PPH-PKT-EXT-* |
| 利用面 | PPH-UX-* | `PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md#phase-d-consumption-surfaces` | PPH-PKT-UX-* |
| 大規模化 | PPH-SCALE-* | `PRODUCT_PLATFORM_PHASE_DETAIL_SPEC.md#phase-e-scale-foundation` | PPH-PKT-SCALE-* |

| Physical Detail | Covers |
|---|---|
| `PLATFORM_STORE_SCHEMA_SPEC.md` | run history, operating projection, artifact metadata, scheduler, recovery |
| `PLATFORM_POLICY_CONFIG_SPEC.md` | profile, threshold, plugin trust, retention, scheduler budget |
| `PLATFORM_RBAC_MATRIX_SPEC.md` | role, tenant, resource, action authorization |
| `PLATFORM_DASHBOARD_WIREFRAME_SPEC.md` | view inventory, state matrix, dashboard view models |
| `PLATFORM_BENCHMARK_FIXTURE_SPEC.md` | deterministic large-scale fixture generation and degradation |
| `PLATFORM_CONNECTOR_SYNC_SPEC.md` | GitHub/Slack/tracker/webhook sync payloads and failure handling |
| `PLATFORM_PLUGIN_SANDBOX_SPEC.md` | plugin execution modes, resource limits, trust denial, failure isolation |
