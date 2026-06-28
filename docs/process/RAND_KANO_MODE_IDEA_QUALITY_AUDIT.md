---
intent_id: INT-HATE-IDEA-QUALITY-KANO-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# RanD Kano Mode アイデア品質監査

## 1. 目的

この文書は、HATE の要件定義文書ではなく、プロダクトアイデアそのものの品質を
RanD Kano Mode で監査した証跡である。

本監査は、実装完了、release gate、要件定義品質 Go を意味しない。
対象は「このアイデアは作る価値があり、最初の検証単位へ落とせているか」である。

## 2. アイデア要約

HATE は、CI / 自動テスト / coverage / SARIF / artifact の証跡を、
QEG が扱える optional evidence bundle へ正規化する前段ハーネスである。

狙いは、品質ゲートを新しく作ることではなく、既存 CI 証跡を
`diff / risk / test / evidence` の関係として説明可能にし、release review や
監査で使える証跡へ変換することである。

## 3. RanD Kano Mode 結果

| 指標 | 値 |
|---|---:|
| total | 8 |
| go | 4 |
| conditional_go | 4 |
| no_go | 0 |
| overall_assessment | `conditional_go` |

機械可読証跡:

- `docs/process/rand-kano-mode-idea-quality-audit.json`
- `docs/process/rand-kano-mode-idea-quality-kano.json`

## 4. 判定

アイデア品質は `conditional_go` とする。

コア pain、差別化、P0a wedge、技術的実現性は Go 水準にある。
一方で、Kano Mode としては、外部ユーザー実証、買い手向けの比較表現、最初の支払い理由、
魅力品質の扱いに補強余地がある。

## 5. Go 項目

| ID | 観点 | 判定 | 理由 |
|---|---|---|---|
| IDEA-QUAL-001 | 自動テスト証跡をrelease判断へ使える形に構造化する pain | go | 品質判断の説明責任に直結し、CI evidence の未整理問題が明確 |
| IDEA-QUAL-002 | QEG前段の evidence normalizer という差別化 | go | gate本体を再実装しない境界が明確 |
| IDEA-QUAL-003 | P0a golden path の検証 wedge | go | local-first、fixture、precheck、own-output validationで最小検証できる |
| IDEA-QUAL-007 | 技術的実現性 | go | phase分解、schema、fixture、Shipyard task packet があり big-bang を避けている |

## 6. Conditional-Go 項目

| ID | 観点 | 理由 | Go 化条件 |
|---|---|---|---|
| IDEA-QUAL-004 | AETE / DQ / risk debt の魅力品質 | 強い delighter だが、P0 must-be 化するとMVPが重くなる | P0a/P0bから外し、P1a以降の魅力品質として扱う |
| IDEA-QUAL-005 | ターゲットユーザーの実証シグナル | QA lead / release manager / platform engineer の実pain証跡が不足 | persona別に problem statement を集め、Kano分類を再判定する |
| IDEA-QUAL-006 | 市場ポジション | 差分自体はあるが、既存CI/品質SaaSとの補完/非代替関係を買い手向けに一枚で説明する資料がない | reporting / coverage / gate / evidence graph feed の4軸比較を作る |
| IDEA-QUAL-008 | 商用焦点 | enterprise構想は厚いが、初期の支払い理由が散りやすい | 初期仮説を「release reviewでCI証跡説明に時間がかかるチーム」に限定する |

## 7. Kano 解釈

| Kano分類 | HATEでの扱い |
|---|---|
| must_be | CI証跡を壊さず正規化し、local-firstでprecheckできること |
| performance | QEG optional evidence、sourceRefs、risk/test/evidence結線の精度 |
| attractive | AETE explain、doctor、recommend、risk debt、enterprise trust packet |
| indifferent候補 | 初期P0における多SaaS export、過剰なdashboard、重いenterprise運用 |

## 8. アイデア Go 条件

次を満たしたら、RanD Kano Mode でアイデア品質を再監査する。

- persona別に最低 5 件の problem statement を集める
- P0a demo で「CIログだけでは見えないrelease riskが説明できる」ことを示す
- 既存ツールとの補完/非代替関係を4軸で明文化する
- 初期commercial hypothesisを1文に固定する
- AETE / doctor / recommend をP1a以降の delighter として明確に分離する

## 9. 結論

HATE のアイデアは、作る価値のある筋がある。
特に「QEGの前段でCI evidenceを正規化する」という位置取りと、
P0a golden path の検証単位は良い。

ただし現時点では、顧客実証と買い手向けの比較表現が不足しているため `conditional_go` とする。
次に詰めるべきは仕様の密度ではなく、誰のどの痛みがどれだけ強いかを示す証跡である。
