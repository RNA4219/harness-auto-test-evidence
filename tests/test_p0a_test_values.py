"""テスト識別値・実行時間の不正入力と標準report形式を検証する。"""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from hate import cli
from hate.p0a import PrecheckError, generate_p0a
from hate.p0a_test_adapters import _parse_jest_json, _parse_pytest_json, _parse_vitest_json, parse_junit_xml
from hate.p0b import ExportError, export_qeg

FAMILIES = ("junit", "pytest", "vitest", "jest")
JSON_PARSERS = {"pytest": _parse_pytest_json, "vitest": _parse_vitest_json, "jest": _parse_jest_json}
SOURCE = Path("fixtures/golden/p0a-minimal/input")


def _write_report(root, family, changes):
    if family == "junit":
        suite = ET.Element("testsuite", name="suite")
        attrs = {"name": "test", "file": "tests/test_auth.py", "time": "0.25", **changes}
        ET.SubElement(suite, "testcase", **{key: str(value) for key, value in attrs.items() if value is not None})
        path = root / "junit.xml"
        path.write_text(ET.tostring(suite, encoding="unicode"), encoding="utf-8")
        return path
    if family == "pytest":
        data = {"tests": [{"nodeid": "tests/test_auth.py::test", "outcome": "passed", "duration": 0.25, **changes}]}
    else:
        fields = {key: value for key, value in changes.items() if key != "suite_name"}
        data = {"testResults": [{"name": changes.get("suite_name", "tests/auth.test.js"), "assertionResults": [
            {"fullName": "suite test", "title": "test", "status": "passed", "duration": 250, **fields},
        ]}]}
    path = root / f"{family}-report.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _source(tmp_path, family, changes):
    root = tmp_path / "input"
    shutil.copytree(SOURCE, root)
    path = _write_report(root, family, changes)
    if family == "junit":
        _write_report(root, "pytest", {})
    return root, path


def _assert_dq(root, tmp_path, diagnostic, capsys):
    original = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    out = tmp_path / "run/p0a"
    with pytest.raises(PrecheckError) as caught:
        generate_p0a(root, out)
    assert caught.value.exit_code == 2
    decision = json.loads((out / "precheck-decision.json").read_text(encoding="utf-8"))["payload"]
    assert decision["decision"] == "hard_dq" and decision["qeg_export_allowed"] is False
    assert any(hit["code"] == "HATE-DQ-002" and diagnostic in hit["message"] for hit in decision["dq_hits"])
    assert cli.main(["p0a", "--input", str(root), "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    with pytest.raises(ExportError) as denied:
        export_qeg(out.parent, tmp_path / "export")
    assert denied.value.exit_code == 2 and not (tmp_path / "export").exists()
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == original


@pytest.mark.parametrize("value", [None, False, 17, [], {}, "", "   "])
@pytest.mark.parametrize("family", ["pytest", "vitest", "jest"])
def test_invalid_test_identity_is_not_stringified(family, value, tmp_path, capsys):
    field = "nodeid" if family == "pytest" else "fullName"
    root, _ = _source(tmp_path, family, {field: value})
    _assert_dq(root, tmp_path, field, capsys)


@pytest.mark.parametrize("family", ["vitest", "jest"])
@pytest.mark.parametrize(("field", "value", "diagnostic"), [
    ("suite_name", None, ".name"), ("suite_name", " ", ".name"), ("suite_name", {}, ".name"),
    ("title", None, ".title"), ("title", [], ".title"), ("title", False, ".title"),
    ("ancestorTitles", "suite", ".ancestorTitles"), ("ancestorTitles", [None], ".ancestorTitles[0]"),
])
def test_assertion_identity_components_are_checked(family, field, value, diagnostic, tmp_path, capsys):
    root, _ = _source(tmp_path, family, {field: value})
    _assert_dq(root, tmp_path, diagnostic, capsys)


@pytest.mark.parametrize("name", [None, "", " "])
def test_junit_missing_name_does_not_invent_case_identity(name, tmp_path, capsys):
    root, path = _source(tmp_path, "junit", {"name": name})
    parsed = parse_junit_xml(path.read_text(encoding="utf-8"))
    assert parsed["tests"] == [] and ".name" in parsed["parser_diagnostics"]["error"]
    _assert_dq(root, tmp_path, "testcase/1.name", capsys)


@pytest.mark.parametrize("family", ["pytest", "vitest", "jest"])
@pytest.mark.parametrize("value", [True, False, "5", {}, [], -1, -0.0001])
def test_invalid_json_duration_is_not_coerced_or_rounded_away(family, value, tmp_path, capsys):
    root, _ = _source(tmp_path, family, {"duration": value})
    _assert_dq(root, tmp_path, ".duration", capsys)


@pytest.mark.parametrize("value", ["oops", "", "NaN", "Infinity", "-0.0001", "-1e-999", "1e999", "1e99999999999999999999", "1_000"])
def test_invalid_junit_duration_returns_diagnostic_and_hard_dq(value, tmp_path, capsys):
    root, path = _source(tmp_path, "junit", {"time": value})
    parsed = parse_junit_xml(path.read_text(encoding="utf-8"))
    assert parsed["tests"] == [] and ".time" in parsed["parser_diagnostics"]["error"]
    _assert_dq(root, tmp_path, "testcase/1.time", capsys)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize(("seconds", "milliseconds", "expected"), [
    ("0.00050000000000000001", "0.50000000000000001", 1),
    ("0.00149999999999999999", "1.49999999999999999", 1),
    ("0.0025", "2.5", 2),
    ("9007199254740.993", "9007199254740993.0", 9007199254740993),
])
def test_duration_quantization_uses_original_decimal(family, seconds, milliseconds, expected, tmp_path):
    token = seconds if family in {"junit", "pytest"} else milliseconds
    path = _write_report(tmp_path, family, {"time" if family == "junit" else "duration": "NUMBER"})
    path.write_text(path.read_text(encoding="utf-8").replace("NUMBER" if family == "junit" else '"NUMBER"', token), encoding="utf-8")
    if family == "junit":
        assert parse_junit_xml(path.read_text(encoding="utf-8"))["tests"][0]["duration_ms"] == expected
    else:
        context = json.loads((SOURCE / "github-context.json").read_text(encoding="utf-8"))
        assert JSON_PARSERS[family](path, context, "2026-09-10T00:00:00Z", "test")[0]["payload"]["duration_ms"] == expected


@pytest.mark.parametrize("family", ["jest", "vitest"])
@pytest.mark.parametrize("status", ["passed", "skipped"])
def test_native_null_duration_is_unknown_and_survives_export(family, status, tmp_path):
    root, _ = _source(tmp_path, family, {"duration": None, "status": status})
    run = tmp_path / "run"
    assert generate_p0a(root, run / "p0a")["decision"] == "eligible"
    records = [json.loads(line) for line in (run / "p0a/HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()]
    payload = next(record["payload"] for record in records if record["payload"]["framework"] == family)
    assert payload["status"] == status and payload["duration_ms"] == 0
    diagnostic = payload["parser_diagnostics"]
    assert diagnostic[0]["code"] == "duration_not_reported" and diagnostic[0]["sourceRef"].endswith(".duration")
    export_qeg(run, run / "export")
    bundle = json.loads((run / "export/qeg-bundle.json").read_text(encoding="utf-8"))
    execution = next(node for node in bundle["nodes"] if node["kind"] == "execution_evidence" and node["label"].endswith(payload["canonical_test_id"]))
    assert execution["data"]["parser_diagnostics"] == diagnostic


@pytest.mark.parametrize(("stages", "expected"), [
    ({"setup": {"duration": 0.01}, "call": {"duration": 0.25}, "teardown": {"duration": 0.02}}, 280),
    ({"setup": {"duration": 0.0004}, "call": {"duration": 0.0004}, "teardown": {"duration": 0.0004}}, 1),
    ({"setup": {"duration": 0.123, "outcome": "failed"}}, 123),
])
def test_pytest_native_stage_durations_are_summed_before_rounding(stages, expected, tmp_path):
    root, path = _source(tmp_path, "pytest", {})
    data = json.loads(path.read_text(encoding="utf-8"))
    test = data["tests"][0]
    test.pop("duration")
    test.update(stages)
    path.write_text(json.dumps(data), encoding="utf-8")
    run = tmp_path / "run"
    generate_p0a(root, run / "p0a")
    export_qeg(run, run / "export")
    bundle = json.loads((run / "export/qeg-bundle.json").read_text(encoding="utf-8"))
    execution = next(node for node in bundle["nodes"] if node["kind"] == "execution_evidence" and "pytest:" in node["label"])
    assert execution["data"]["duration_ms"] == expected


@pytest.mark.parametrize("value", [None, False, [], {"duration": "bad"}, {"duration": -0.0001}])
def test_invalid_pytest_stage_is_not_hidden_by_top_level_duration(value, tmp_path, capsys):
    root, _ = _source(tmp_path, "pytest", {"call": value})
    _assert_dq(root, tmp_path, ".call", capsys)


@pytest.mark.parametrize("family", FAMILIES)
def test_omitted_duration_keeps_legacy_default(family, tmp_path):
    path = _write_report(tmp_path, family, {"time": None} if family == "junit" else {})
    if family == "junit":
        assert parse_junit_xml(path.read_text(encoding="utf-8"))["tests"][0]["duration_ms"] == 0
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        row = data["tests"][0] if family == "pytest" else data["testResults"][0]["assertionResults"][0]
        row.pop("duration")
        path.write_text(json.dumps(data), encoding="utf-8")
        context = json.loads((SOURCE / "github-context.json").read_text(encoding="utf-8"))
        assert JSON_PARSERS[family](path, context, "2026-09-10T00:00:00Z", "test")[0]["payload"]["duration_ms"] == 0


@pytest.mark.parametrize("family", ["pytest", "vitest", "jest"])
def test_negative_underflow_duration_is_rejected_from_original_token(family, tmp_path, capsys):
    root, path = _source(tmp_path, family, {"duration": "NUMBER"})
    path.write_text(path.read_text(encoding="utf-8").replace('"NUMBER"', "-1e-999"), encoding="utf-8")
    _assert_dq(root, tmp_path, ".duration", capsys)


def test_pytest_null_duration_is_not_a_native_nullable_field(tmp_path, capsys):
    root, _ = _source(tmp_path, "pytest", {"duration": None})
    _assert_dq(root, tmp_path, ".duration", capsys)


def test_pytest_explicit_duration_does_not_add_stages_twice(tmp_path):
    path = _write_report(tmp_path, "pytest", {"duration": 0.25, "call": {"duration": 0.25}, "setup": {"duration": 0.01}})
    context = json.loads((SOURCE / "github-context.json").read_text(encoding="utf-8"))
    payload = _parse_pytest_json(path, context, "2026-09-10T00:00:00Z", "test")[0]["payload"]
    assert payload["duration_ms"] == 250


@pytest.mark.parametrize("family", ["jest", "vitest"])
@pytest.mark.parametrize("case", ["title_only", "full_name_only", "empty_title", "unicode"])
def test_valid_assertion_identity_fallbacks_keep_original_names(family, case, tmp_path):
    path = _write_report(tmp_path, family, {})
    data = json.loads(path.read_text(encoding="utf-8"))
    assertion = data["testResults"][0]["assertionResults"][0]
    if case == "title_only":
        assertion.pop("fullName")
    elif case == "full_name_only":
        assertion.pop("title")
    elif case == "empty_title":
        assertion["title"] = ""
    else:
        assertion.update(fullName="組合せ 名前[値=日本語]", title="名前[値=日本語]", ancestorTitles=["組合せ"])
    path.write_text(json.dumps(data), encoding="utf-8")
    context = json.loads((SOURCE / "github-context.json").read_text(encoding="utf-8"))
    payload = JSON_PARSERS[family](path, context, "2026-09-10T00:00:00Z", "test")[0]["payload"]
    expected_full_name = assertion.get("fullName", assertion.get("title"))
    assert payload["canonical_test_id"] == f"{family}:tests/auth.test.js::{expected_full_name}"
    assert payload["identity_components"]["name"] == assertion.get("title", expected_full_name)
    assert payload["identity_components"]["ancestors"] == assertion.get("ancestorTitles", [])
