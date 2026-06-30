"""Tests for HATE-GAP-038 accessibility and localization evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.a11y_l10n import build_a11y_l10n_report, evaluate_a11y_l10n_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "a11y-l10n"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "a11y-l10n-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "a11y-l10n-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_038_fixture_paths_exist() -> None:
    assert (FIXTURES / "locale-fallback-safe" / "fixture.json").is_file()
    assert (FIXTURES / "color-only-severity-denied" / "fixture.json").is_file()


def test_locale_fallback_safe_fixture_passes() -> None:
    result = evaluate_a11y_l10n_fixture(_fixture("locale-fallback-safe"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_color_only_severity_denied_fixture_holds() -> None:
    result = evaluate_a11y_l10n_fixture(_fixture("color-only-severity-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "a11y_l10n_color_only_severity_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_message_catalog_holds() -> None:
    report = build_a11y_l10n_report({
        "message_catalog_present": False,
        "stable_message_ids": True,
        "supported_locales": ["en-US"],
        "requested_locale": "en-US",
        "fallback_locale": "en-US",
        "fallback_used": False,
        "keyboard_navigation_checked": True,
        "color_contrast_checked": True,
        "color_only_severity_used": False,
        "screen_reader_labels_present": True,
        "translation_stale": False,
    })

    assert report["overall_status"] == "hold"
    assert "a11y_l10n_message_catalog_missing" in _codes(report)


def test_unstable_message_ids_holds() -> None:
    report = build_a11y_l10n_report({
        "message_catalog_present": True,
        "stable_message_ids": False,
        "supported_locales": ["en-US"],
        "requested_locale": "en-US",
        "fallback_locale": "en-US",
        "fallback_used": False,
        "keyboard_navigation_checked": True,
        "color_contrast_checked": True,
        "color_only_severity_used": False,
        "screen_reader_labels_present": True,
        "translation_stale": False,
    })

    assert report["overall_status"] == "hold"
    assert "a11y_l10n_message_ids_unstable" in _codes(report)


def test_missing_locale_fallback_holds() -> None:
    report = build_a11y_l10n_report({
        "message_catalog_present": True,
        "stable_message_ids": True,
        "supported_locales": ["en-US", "ja-JP"],
        "requested_locale": "ja-JP",
        "fallback_locale": "",
        "fallback_used": False,
        "keyboard_navigation_checked": True,
        "color_contrast_checked": True,
        "color_only_severity_used": False,
        "screen_reader_labels_present": True,
        "translation_stale": False,
    })

    assert report["overall_status"] == "hold"
    assert "a11y_l10n_locale_fallback_missing" in _codes(report)


def test_missing_keyboard_navigation_check_holds() -> None:
    report = build_a11y_l10n_report({
        "message_catalog_present": True,
        "stable_message_ids": True,
        "supported_locales": ["en-US"],
        "requested_locale": "en-US",
        "fallback_locale": "en-US",
        "fallback_used": False,
        "keyboard_navigation_checked": False,
        "color_contrast_checked": True,
        "color_only_severity_used": False,
        "screen_reader_labels_present": True,
        "translation_stale": False,
    })

    assert report["overall_status"] == "hold"
    assert "a11y_l10n_keyboard_check_missing" in _codes(report)


def test_missing_screen_reader_labels_holds() -> None:
    report = build_a11y_l10n_report({
        "message_catalog_present": True,
        "stable_message_ids": True,
        "supported_locales": ["en-US"],
        "requested_locale": "en-US",
        "fallback_locale": "en-US",
        "fallback_used": False,
        "keyboard_navigation_checked": True,
        "color_contrast_checked": True,
        "color_only_severity_used": False,
        "screen_reader_labels_present": False,
        "translation_stale": False,
    })

    assert report["overall_status"] == "hold"
    assert "a11y_l10n_screen_reader_labels_missing" in _codes(report)


def test_a11y_l10n_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["a11y-l10n-report"] == "schemas/HATE/v1/a11y-l10n-report.schema.json"