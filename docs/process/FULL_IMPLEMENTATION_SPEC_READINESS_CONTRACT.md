---
intent_id: INT-HATE-FULL-IMPL-SPEC-READINESS-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Full Implementation Specification Readiness Contract

## 1. 目的

この文書は、RanD KanoMode の Requirement Definition Gate を「実装完了判定」ではなく
「フル実装仕様書の準備完了判定」として通すための判定境界を固定する。

実装完了 claim は、`MANUAL_BB_GATE_FULL_IMPLEMENTATION.md` の No-Go を満たすまで禁止する。
一方で仕様書 readiness claim は、P0a〜P3 の task、artifact、schema、fixture、
acceptance、No-Go trigger、責務境界が揃っていれば Go にできる。

## 2. Readiness Criteria

| Area | Spec readiness Go condition |
|---|---|
| P0a local-first | P0a artifact / DQ / CLI / fixture contract が明示されている |
| P0b QEG export | QEG bundle / evidence-map / diff-risk-test / completeness / fixture contract が明示されている |
| P1a trust hardening | AETE / adapter capability / identity / aggregation / resolver / replay command contract が明示されている |
| P1b workflow integration | RanD / Shipyard / workflow / manual-bb bridge のartifactと上書き禁止が明示されている |
| P2/P3 readiness | canonical bundle から派生するproduct readiness artifactが明示され、P0/P1依存でない |
| Boundary | QEG / RanD / Shipyard / workflow-cookbook / manual-bb のGate権限を再実装しない |

## 3. RanD Audit Mapping

RanD `implementation_alignment` は、この readiness audit では「現コード実装」ではなく
「要求から実装作業へ移せる仕様整合」を表す。

| Value | Meaning in readiness audit |
|---|---|
| high | task, artifact, acceptance, fixture, failure behavior, boundary が揃っている |
| medium | task and artifact are present, but fixture or failure behavior is incomplete |
| low | major artifact or acceptance contract missing |
| unknown | downstream evidence not linked |

## 4. No-Go Preservation

仕様書 readiness が Go になっても、次は変えない。

- full implementation completion remains No-Go until executable artifacts exist
- RanD audit packet for implementation completion remains evidence, not release approval
- QEG / Shipyard / manual-bb verdicts are not overwritten
- product readiness is not claimed without generated metrics
- commercial / procurement / release wording is not treated as true unless
  `commercial-truthfulness-report` links the claim to implemented evidence, source contract refs,
  implementation refs, sourceRefs, and a release-eligible blocker state
- manual review can document an exception, but cannot auto-waive unsupported commercial claims

## 5. Commercial Claim Boundary

仕様書 readiness の claim と実装済み product claim は分離する。

| Claim type | Allowed wording | Required evidence |
|---|---|---|
| spec readiness | task / artifact / schema / fixture / acceptance が揃っている | this contract + packet refs |
| implemented capability | implemented / available / supported | executable implementation refs + evidence report refs |
| planned capability | planned / candidate / roadmap | source contract refs + non-available wording |
| unsupported capability | unsupported / not available | blocker state in commercial truthfulness report |

README、release note、API doc、procurement response、sales material は、
`commercial-truthfulness-report` の `release_eligible=true` でない限り implemented
または available と表現しない。

## 6. Release Candidate Pack Boundary

`release-candidate-pack` は full implementation 完了宣言ではなく、required evidence
reports が揃い、blocker が可視化されていることを示す release readiness artifact である。

pack が `verdict=ready` でも QEG approval、Shipyard publish approval、manual-bb approval、
human legal sign-off を上書きしない。pack が `verdict=blocked` の場合、missing report、
open hard DQ、open manual review、unsupported commercial claim、unsafe evidence room
artifact、QEG approval claim のいずれかを blocker として説明できなければならない。

## 7. Source Contracts

- `SPECIFICATION.md`
- `SPECIFICATION_SHIPYARD_FULL_IMPLEMENTATION_DRAFT.md`
- `P0B_QEG_EXPORT_IMPLEMENTATION_CONTRACT.md`
- `P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md`
- `MANUAL_BB_GATE_FULL_IMPLEMENTATION.md`
- `RAND_KANO_MODE_FULL_IMPLEMENTATION_AUDIT.md`
