"""Tests for coverage dialect parser corpus - HATE-PG-001C."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hate.adapters.coverage import parse_coverage_file
from hate.p0a import PrecheckError, generate_p0a


ROOT = Path(__file__).resolve().parents[1]


def test_coveragepy_json_preserves_contexts() -> None:
    result = parse_coverage_file(ROOT / "fixtures/adapters/coveragepy/input/coverage.json", "coverage.py")

    parser_payload = next(item for item in result["coverage_slices"] if item["file"] == "src/parser.py")
    assert parser_payload["line_hits"]["10"] == 1
    assert {"test_id": "tests/unit/test_parser.py::test_parse_valid", "line": 10} in parser_payload["contexts"]
    assert result["parser_diagnostics"] == []


def test_coveragepy_show_contexts_false_is_hard_failure(tmp_path: Path) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps({"meta": {"show_contexts": False}, "files": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="show_contexts: true"):
        parse_coverage_file(path, "coverage.py")


def test_coveragepy_partial_contexts_remain_visible_as_warning() -> None:
    result = parse_coverage_file(ROOT / "fixtures/adapters/coveragepy/partial/coverage.json", "coverage.py")

    assert result["coverage_slices"]
    assert any(item["code"] == "contextless_lines" for item in result["parser_diagnostics"])


def test_lcov_line_and_branch_mapping() -> None:
    result = parse_coverage_file(ROOT / "fixtures/golden/p0a-minimal/input/lcov.info", "lcov")

    auth = next(item for item in result["coverage_slices"] if item["file"] == "src/auth.py")
    assert auth["line_hits"] == {"10": 1, "11": 1, "20": 0}
    assert auth["branch_hits"] == [
        {"line": 10, "block": 0, "branch": 0, "hits": 1},
        {"line": 10, "block": 0, "branch": 1, "hits": 0},
    ]
    assert auth["contexts"] == [{"test_id": "junit:tests/test_example.py::test_example"}]


def test_cobertura_xml_path_and_line_mapping() -> None:
    result = parse_coverage_file(ROOT / "fixtures/adapters/coverage/cobertura/input/cobertura.xml", "cobertura")

    service = next(item for item in result["coverage_slices"] if item["file"] == "src/auth/service.py")
    fallback = next(item for item in result["coverage_slices"] if item["file"] == "src/auth/TokenStore")
    assert service["line_hits"] == {"10": 1, "11": 0}
    assert fallback["line_hits"] == {"20": 3}


def test_coveragepy_xml_alias_uses_cobertura_mapping() -> None:
    result = parse_coverage_file(ROOT / "fixtures/adapters/coverage/coveragepy-xml/coverage.xml", "coveragepy-xml")

    [payload] = result["coverage_slices"]
    assert payload["format"] == "cobertura"
    assert payload["file"] == "src/coverage_xml.py"
    assert payload["line_hits"] == {"3": 1}


def test_jacoco_xml_branch_mapping() -> None:
    result = parse_coverage_file(ROOT / "fixtures/adapters/coverage/jacoco/input/jacoco.xml", "jacoco")

    [payload] = result["coverage_slices"]
    assert payload["file"] == "com/example/auth/AuthService.java"
    assert payload["line_hits"] == {"12": 1, "13": 0}
    assert payload["branch_hits"] == [{"line": 13, "block": 0, "branch": 1, "hits": 0}]


def test_coverage_path_normalization_for_windows_fixture() -> None:
    result = parse_coverage_file(ROOT / "fixtures/adapters/coverage/cobertura/windows-path/cobertura.xml", "cobertura")

    files = {item["file"] for item in result["coverage_slices"]}
    assert "src/win/path.py" in files


def test_malformed_json_and_xml_fail_explicitly(tmp_path: Path) -> None:
    bad_json = tmp_path / "coverage.json"
    bad_json.write_text("{", encoding="utf-8")
    bad_xml = ROOT / "fixtures/adapters/coverage/cobertura/malformed/cobertura.xml"

    with pytest.raises(json.JSONDecodeError):
        parse_coverage_file(bad_json, "coverage.py")
    with pytest.raises(Exception):
        parse_coverage_file(bad_xml, "cobertura")


def test_coverage_only_fixture_does_not_become_product_ready(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures/golden/p0a-minimal/dq-08-coverage-only"

    with pytest.raises(PrecheckError) as exc:
        generate_p0a(fixture, tmp_path / "out", source_version="coverage-corpus-test")

    assert exc.value.exit_code == 2
    assert exc.value.decision is not None
    assert any(hit["code"] == "HATE-DQ-008" for hit in exc.value.decision["payload"]["dq_hits"])


def test_coverage_fixture_corpus_covers_required_dialects_and_negatives() -> None:
    fixture_root = ROOT / "fixtures" / "adapters" / "coverage"
    expected = {
        "coveragepy-json",
        "coveragepy-xml",
        "lcov",
        "cobertura",
        "jacoco",
        "branch-coverage",
        "partial-contexts",
        "windows-paths",
        "container-paths",
        "malformed-json",
        "malformed-xml",
        "show-contexts-false",
        "contextless-lines",
        "unknown-file-path",
        "coverage-only-no-test-results",
    }

    assert expected <= {path.name for path in fixture_root.iterdir() if path.is_dir()}
