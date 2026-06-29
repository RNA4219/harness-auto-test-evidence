---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Release and Migration Policy

## 1. 目的

HATE は evidence bundle、schema、adapter、profile、QEG export との互換性を持つ。
この文書は release、deprecation、migration、rollback、compatibility matrix の契約を
定義する。

## 2. Release Channels

| Channel | 用途 | 互換性期待 |
|---|---|---|
| experimental | adapter / profile 実験 | breaking change 可 |
| preview | early adopter | migration note 必須 |
| stable | team / enterprise default | semver と後方互換 |
| long-term | regulated / audit-heavy | security fix と critical bug fix 中心 |

## 3. Versioned Surfaces

| Surface | Version | Policy |
|---|---|---|
| CLI | semver | breaking command change は major |
| JSON Schema | `schema_version` | `SCHEMA_REGISTRY_CONTRACT.md` に従う |
| Registry | `registry_version` | patch / minor / major |
| Adapter SDK | semver | required interface change は major |
| Adapter | semver | manifest と output schema に従う |
| Profile | `profile_version` | profile diff と migration note 必須 |
| AETE rubric | `rubric_version` | score migration / replay impact を明記 |
| QEG export | `qeg_export_version` | QEG compatibility matrix 必須 |
| Error taxonomy | `error_taxonomy_version` | code meaning を breaking change しない |

## 4. Deprecation Policy

| Item | Minimum notice | Required metadata |
|---|---:|---|
| field | 1 minor | `deprecated_since`, `remove_after`, `replacement` |
| CLI option | 1 minor | warning and replacement |
| adapter capability | 1 minor | replacement capability |
| profile key | 1 minor | profile migration note |
| schema major | 1 stable release | migration guide |

## 5. Migration Artifacts

| Artifact | 目的 |
|---|---|
| `migration-guide.md` | human-readable migration |
| `schema-diff.json` | machine-readable schema diff |
| `profile-diff.json` | profile change impact |
| `replay-impact.json` | frozen bundle replay の score / DQ 差分 |
| `compatibility-matrix.json` | CLI / schema / adapter / QEG / profile の互換表 |
| `release-evidence.json` | release validation evidence |

## 6. Release Gates

| Gate | 必須 evidence |
|---|---|
| RG-1 Schema | schema registry valid / diff reviewed |
| RG-2 Fixture | P0a golden path and invalid fixtures pass |
| RG-3 Adapter | adapter conformance fixtures pass |
| RG-4 Replay | frozen bundle replay impact documented |
| RG-5 QEG | QEG minimal fixture compatible |
| RG-6 Security | privacy / quarantine fixtures pass |
| RG-7 Docs | migration / release note / error taxonomy updated |
| RG-8 Rollback | previous stable can read or reject safely |

## 7. Rollback Policy

Rollback は data loss を避ける。

- canonical bundle は immutable とする
- rollback しても old bundle を破壊しない
- unsupported future schema は safe reject する
- migration は dry-run を持つ
- migration は source bundle と migrated bundle の hash を記録する
- rollback note は release-evidence に残す

## 8. Compatibility Matrix

```json
{
  "cli_version": "1.2.0",
  "schema_versions": ["HATE/v1"],
  "adapter_sdk_versions": ["1.x"],
  "qeg_export_versions": ["QEG/v1"],
  "profile_versions": ["default/v1", "release/v1"],
  "supported_until": "2026-12-31"
}
```

## 9. Release Notes Requirements

Release notes は最低限、次を持つ。

- summary
- breaking changes
- deprecated fields / options
- migration steps
- compatibility matrix
- known issues
- security notes
- artifact safety changes
- QEG compatibility
- rollback instructions

## 10. Acceptance

- release は RG-1..RG-8 の evidence を持つ
- release candidate pack は product readiness、test integrity、artifact safety、
  safe diagnostic bundle、store manifest、scale performance、API contract、
  dashboard UAT、enterprise control、support ops、migration compatibility、
  commercial truthfulness の required report checklist を持つ
- release candidate pack は required report 欠落、依存 hard DQ、open manual review、
  unsupported commercial claim、quarantined / unsafe artifact export、QEG approval claim
  を hard DQ blocker として保持する
- evidence room manifest は safe artifact だけを included に置き、secret / PII /
  quarantined / unsafe artifact を excluded に残す
- pack hash は sorted report ids / hashes / sourceRefs から deterministic に再計算できる
- breaking change は migration guide を持つ
- deprecated field は removal window と replacement を持つ
- replay impact が score / DQ / QEG export 差分を説明できる
- previous stable が unsupported future schema を safe reject できる
- release note が compatibility matrix と rollback instruction を持つ

## 11. Retention / Legal Hold Migration Guard

Migration は retention policy id と legal hold metadata を preserved field として
扱う。migration dry-run で `before_migration.legal_hold` と
`after_migration.legal_hold` が一致しない場合、release evidence は
`legal_hold_lost` を hard DQ として扱う。

Expired retention は migration 中に artifact body を削除しない。出力は
metadata-only の purge eligibility として表現し、canonical bundle、audit event、
sourceRefs、legal hold metadata を再計算可能なまま残す。

## 12. Migration Compatibility Report

`migration-compatibility-report` は migration dry-run の正本証跡である。
各 decision は source version、target version、decision、readiness effect、
reason、source hash、migrated hash、sourceRefs preserved、legal hold preserved、
canonical source mutated、findings、sourceRefs を持つ。

Patch / minor compatible な `HATE/v1.*` は pass として扱える。ただし sourceRefs、
legal hold、source hash、canonical source immutability のいずれかが破られた場合は
schema version が互換でも hard DQ とする。unsupported major version は release /
regulated profile では hard DQ、default profile では hold とし、silent pass しない。

## 13. Legal Hold Transition Evidence

Legal hold migration は `legal_hold_transitions` として
`migration-compatibility-report` に残す。operation は migration、replay、export、
purge/delete、retention transition を区別する。

Active legal hold が存在する resource では、migration / replay が legal hold metadata
を落とすこと、export が raw mutation を伴うこと、purge/delete が実行されること、
retention transition が `retain` 以外へ進むことを hard DQ とする。retain の
retention transition は legal hold metadata が保持される限り pass として扱える。

## 14. Release Candidate Pack

`release-candidate-pack` は release approval ではなく、release readiness の
証跡束である。HATE は QEG approval、publish approval、manual review approval を
代替しない。QEG は `qeg_refs` として参照できるが、`qeg_approval_claimed` は常に
false でなければならない。

pack は required reports、report hashes、verdict、blockers、manual review state、
commercial claim state、QEG refs、evidence room manifest、legal hold summary、
sign-off metadata、sourceRefs、pack_hash を持つ。missing required report、open
manual review、unsupported commercial claim、dependency hard DQ、unsafe artifact
export attempt は release_ready=false とする。
