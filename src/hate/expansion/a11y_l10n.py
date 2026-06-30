"""Accessibility and localization evaluation for HATE-GAP-038."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class A11yL10nFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_a11y_l10n_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_a11y_l10n_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "a11y-l10n-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_a11y_l10n_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "a11y-l10n-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["a11y-l10n"])
    a11y_config = _normalize_a11y_config(input_data.get("a11y_config", input_data))
    findings = _findings_for(a11y_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "a11y-l10n-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "a11y_config": a11y_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "message_catalog_present": a11y_config["message_catalog_present"],
            "stable_message_ids": a11y_config["stable_message_ids"],
            "fallback_used": a11y_config["fallback_used"],
            "keyboard_navigation_checked": a11y_config["keyboard_navigation_checked"],
            "color_contrast_checked": a11y_config["color_contrast_checked"],
            "color_only_severity_used": a11y_config["color_only_severity_used"],
            "screen_reader_labels_present": a11y_config["screen_reader_labels_present"],
            "translation_stale": a11y_config["translation_stale"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_a11y_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    supported_locales = [
        str(locale) for locale in config.get("supported_locales", []) if str(locale)
    ]
    return {
        "message_catalog_present": bool(config.get("message_catalog_present", False)),
        "stable_message_ids": bool(config.get("stable_message_ids", False)),
        "supported_locales": supported_locales,
        "requested_locale": str(config.get("requested_locale") or ""),
        "fallback_locale": str(config.get("fallback_locale") or ""),
        "fallback_used": bool(config.get("fallback_used", False)),
        "keyboard_navigation_checked": bool(config.get("keyboard_navigation_checked", False)),
        "color_contrast_checked": bool(config.get("color_contrast_checked", False)),
        "color_only_severity_used": bool(config.get("color_only_severity_used", False)),
        "screen_reader_labels_present": bool(config.get("screen_reader_labels_present", False)),
        "translation_stale": bool(config.get("translation_stale", False)),
        "translation_last_reviewed_at": str(config.get("translation_last_reviewed_at") or ""),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[A11yL10nFinding]:
    findings: list[A11yL10nFinding] = []
    if not config["message_catalog_present"]:
        findings.append(_finding(
            "a11y_l10n_message_catalog_missing",
            "Accessibility and localization requires message catalog.",
            source_ref,
        ))
    if not config["stable_message_ids"]:
        findings.append(_finding(
            "a11y_l10n_message_ids_unstable",
            "Accessibility and localization requires stable message IDs.",
            source_ref,
        ))
    if config["requested_locale"] and not config["fallback_locale"]:
        findings.append(_finding(
            "a11y_l10n_locale_fallback_missing",
            "Accessibility and localization requires locale fallback.",
            source_ref,
        ))
    if not config["keyboard_navigation_checked"]:
        findings.append(_finding(
            "a11y_l10n_keyboard_check_missing",
            "Accessibility and localization requires keyboard navigation check.",
            source_ref,
        ))
    if not config["color_contrast_checked"]:
        findings.append(_finding(
            "a11y_l10n_color_contrast_missing",
            "Accessibility and localization requires color contrast check.",
            source_ref,
        ))
    if config["color_only_severity_used"]:
        findings.append(_finding(
            "a11y_l10n_color_only_severity_denied",
            "Color-only severity encoding is denied by accessibility policy.",
            source_ref,
        ))
    if not config["screen_reader_labels_present"]:
        findings.append(_finding(
            "a11y_l10n_screen_reader_labels_missing",
            "Accessibility and localization requires screen reader labels.",
            source_ref,
        ))
    if config["translation_stale"]:
        findings.append(_finding(
            "a11y_l10n_translation_stale",
            "Translation stale requires review.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> A11yL10nFinding:
    return A11yL10nFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )