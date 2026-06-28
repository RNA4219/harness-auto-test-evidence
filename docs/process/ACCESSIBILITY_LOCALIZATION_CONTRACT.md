---
intent_id: INT-HATE-001
owner: RNA4219
status: active
last_reviewed_at: 2026-06-28
next_review_due: 2026-07-28
---

# Accessibility and Localization Contract

## 1. 目的

HATE の dashboard、docs、CLI output、support materials における accessibility と
localization の契約を定義する。成熟プロダクトでは、監査担当、開発者、管理者、
support 担当が、言語・環境・支援技術の違いに左右されず主要情報へ到達できる必要がある。

この文書は user experience / documentation quality の契約であり、HATE precheck decision、
QEG verdict、release approval を置き換えない。

## 2. 原則

- accessibility は hosted dashboard だけでなく docs / CLI summary / exported report にも適用する
- WCAG 2.2 AA を web surface の基準ターゲットとする
- localization は canonical schema / error code / record_id を翻訳しない
- human-readable message は locale に応じて切り替えられる
- translation は実装状態を超えた機能説明を追加しない

## 3. Surfaces

| Surface | Accessibility target | Localization target |
|---|---|---|
| CLI output | readable text, no color-only signal | message catalog |
| Markdown summary | headings, tables, alt text where applicable | locale-specific summary |
| Hosted dashboard | WCAG 2.2 AA target | UI message catalog |
| API docs | semantic headings, examples | translated guides where maintained |
| Customer docs | accessible structure | locale-specific docs set |
| Support bundle summary | plain language, no image-only evidence | support locale where available |
| Error remediation | stable code + localized message | code stable, message translated |

## 4. Accessibility Requirements

| Area | Requirement |
|---|---|
| Keyboard | dashboard workflows are keyboard reachable |
| Focus | visible focus and logical order |
| Contrast | text / UI contrast meets configured target |
| Non-color signal | DQ / severity / incident status is not color-only |
| Screen reader | controls expose name / role / value |
| Status message | long-running run / export / incident updates are announced |
| Table readability | evidence matrix and risk tables have headers |
| Motion | animations are nonessential or reducible |
| Error guidance | error code, message, remediation, docs link are text-readable |
| Exported report | Markdown / HTML reports preserve headings and link text |

## 5. Localization Requirements

| Area | Requirement |
|---|---|
| Message catalog | user-facing text has message id and default locale |
| Stable identifiers | schema field, error code, record_id, adapter id are not localized |
| Locale fallback | missing translation falls back to default locale with warning |
| Date / time | locale-aware display, ISO-8601 preserved in JSON |
| Numbers / units | localized display, canonical units preserved in JSON |
| Docs parity | translated docs carry source doc version and review date |
| Support content | known issue / remediation translation links back to source contract |
| Screenshot text | screenshots are not the only source of required information |

## 6. Accessibility Report

```json
{
  "schema_version": "HATE/v1",
  "record_type": "accessibility_report",
  "surface": "dashboard|docs|cli|summary|support_bundle",
  "target": "WCAG_2_2_AA|configured",
  "checked_at": "2026-06-28T00:00:00Z",
  "checks": [],
  "violations": [],
  "waivers": [],
  "owner": "string",
  "next_review_due": "2026-07-28"
}
```

## 7. Localization Report

```json
{
  "schema_version": "HATE/v1",
  "record_type": "localization_report",
  "locale": "ja-JP",
  "source_locale": "en-US",
  "message_catalog_version": "2026.06",
  "coverage": {
    "messages_total": 100,
    "messages_translated": 90
  },
  "missing_messages": [],
  "stale_docs": [],
  "owner": "string"
}
```

## 8. Acceptance

- dashboard / docs / CLI summary が accessibility target と surface を持つ
- DQ / severity / incident status が color-only signal にならない
- stable code / schema field / record_id が翻訳で変わらない
- locale fallback が missing translation を隠さず warning を出す
- translated docs が source doc version、review date、source_contracts を持つ
- accessibility / localization report は HATE precheck decision / QEG verdict を変更しない
