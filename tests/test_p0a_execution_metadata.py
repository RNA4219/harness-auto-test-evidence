"""各test adapterの実行証跡をP0a→P0b→P1aで確認する。"""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET

import pytest

from hate import cli
from hate.p0a import PrecheckError, generate_p0a
from hate.p0a_io import _stable_sha256
from hate.p0a_test_adapters import parse_junit_xml
from hate.p0b import export_qeg
from hate.p1a import evaluate_trust

FAMILIES = ("junit", "pytest", "vitest", "jest")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_report(source, family, rows):
    if family == "junit":
        suite = ET.Element("testsuite", name="suite")
        for row in rows:
            case = ET.SubElement(suite, "testcase", name=row.get("_name", "same"), file=row.get("_file", "tests/test_auth.py"))
            if row.get("status") in {"failed", "skipped", "error"}:
                ET.SubElement(case, "failure" if row["status"] == "failed" else row["status"])
            properties = ET.SubElement(case, "properties")
            for field, value in row.items():
                if field != "status" and not field.startswith("_"):
                    ET.SubElement(properties, "property", name=field, value=json.dumps(value) if not isinstance(value, str) else value)
        path = source / "junit.xml"
        path.write_text(ET.tostring(suite, encoding="unicode"), encoding="utf-8")
        return path
    if family == "pytest":
        data = {"tests": [
            {"nodeid": f"{row.get('_file', 'tests/test_auth.py')}::{row.get('_name', 'same')}", "outcome": row.get("status", "passed"),
             **{key: value for key, value in row.items() if key != "status" and not key.startswith("_")}}
            for row in rows
        ]}
    else:
        data = {"testResults": [
            {"name": row.get("_file", "tests/test_auth.py"), "assertionResults": [
                {"fullName": row.get("_name", "same"), "title": row.get("_name", "same"), "status": row.get("status", "passed"),
                 **{key: value for key, value in row.items() if key != "status" and not key.startswith("_")}},
            ]}
            for row in rows
        ]}
    path = source / f"{family}-report.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _source(tmp_path, family, rows, *, keep_junit=False):
    source = tmp_path / "input"
    shutil.copytree("fixtures/golden/p0a-minimal/input", source)
    if family != "junit" and not keep_junit:
        (source / "junit.xml").unlink()
    path = _write_report(source, family, rows)
    return source, path


def _pipeline(source, tmp_path):
    root = tmp_path / "pipeline"
    result = generate_p0a(source, root / "p0a")
    assert result["decision"] == "eligible"
    records = [json.loads(line) for line in (root / "p0a/HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()]
    for record in records:
        assert record["sha256"] == "sha256:" + _stable_sha256({**record, "sha256": ""})
    export_qeg(root, root / "export")
    result = evaluate_trust(root / "export/qeg-bundle.json", root / "export/qeg-export-report.json", root / "trust")
    return records, result, _read(root / "trust/retry-aggregation.json"), _read(root / "trust/aete-score.json")


@pytest.mark.parametrize("family", FAMILIES)
def test_retry_matrix_and_shards_survive_every_adapter(family, tmp_path):
    rows = [{"status": status, "retry_index": retry, "matrix": {"os": system}, "shard_index": shard, "shard_total": 2}
            for system in ("linux", "windows") for retry in (0, 1) for shard in (0, 1)
            for status in ["failed" if system == "linux" and retry == shard == 0 else "passed"]]
    source, path = _source(tmp_path, family, rows)
    original = path.read_bytes()
    records, result, aggregation, score = _pipeline(source, tmp_path)
    assert path.read_bytes() == original
    assert len({record["record_id"] for record in records}) == len(rows)
    assert all(record["payload"]["retry_index"] == row["retry_index"] for record, row in zip(records, rows, strict=True))
    assert all("flaky" not in record["payload"] for record in records)
    assert not any(record["payload"].get("parser_diagnostics") for record in records)
    assert sorted(item["aggregate_status"] for item in aggregation["aggregates"]) == ["flaky_passed", "stable_passed"]
    assert aggregation["summary"]["matrix_group_count"] == 2
    assert aggregation["summary"]["missing_shard_count"] == 0
    assert score["dimensions"]["determinism_flakiness"] == 0
    assert result["trust_status"] == "partial"


@pytest.mark.parametrize("family", FAMILIES)
def test_alias_coordinates_and_explicit_false_are_retained(family, tmp_path):
    source, _ = _source(tmp_path, family, [
        {"attempt_index": 0, "matrix_values": {"os": "linux"}, "shard_index": 0, "shard_count": 1, "flaky": False},
        {"attempt_index": 1, "matrix_values": {"os": "linux"}, "shard_index": 0, "shard_count": 1, "flaky": False},
    ])
    records, _, aggregation, score = _pipeline(source, tmp_path)
    assert all(record["payload"]["flaky"] is False for record in records)
    assert all(record["payload"]["shard_total"] == 1 for record in records)
    assert aggregation["aggregates"][0]["aggregate_status"] == "stable_passed"
    assert score["dimensions"]["determinism_flakiness"] == 5


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize(("field", "value"), [
    ("retry_index", 1.9), ("retry_index", True), ("retry_index", -1),
    ("shard_count", 0), ("shard_index", 0.5), ("matrix", []), ("flaky", "maybe"),
])
def test_invalid_metadata_becomes_hard_dq_even_with_another_valid_adapter(family, field, value, tmp_path, capsys):
    source, _ = _source(tmp_path, family, [{field: value}], keep_junit=True)
    if family == "junit":
        _write_report(source, "pytest", [{}])
    out = tmp_path / "out"
    with pytest.raises(PrecheckError) as exc:
        generate_p0a(source, out)
    assert exc.value.exit_code == 2
    decision = _read(out / "precheck-decision.json")["payload"]
    assert decision["decision"] == "hard_dq" and not decision["qeg_export_allowed"]
    assert any(hit["code"] == "HATE-DQ-002" and field in hit["message"] for hit in decision["dq_hits"])
    assert cli.main(["p0a", "--input", str(source), "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("token", ["0.99999999999999999", "1.00000000000000001", "-1e-999"])
def test_fractional_retry_lexemes_are_not_rounded_to_integers(family, token, tmp_path):
    source, path = _source(tmp_path, family, [{"retry_index": "REPLACE_NUMBER"}])
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("REPLACE_NUMBER" if family == "junit" else '"REPLACE_NUMBER"', token), encoding="utf-8")
    with pytest.raises(PrecheckError) as exc:
        generate_p0a(source, tmp_path / "out")
    assert exc.value.exit_code == 2


@pytest.mark.parametrize("family", ["pytest", "vitest", "jest"])
def test_json_record_ids_distinguish_files_retries_and_identical_observations(family, tmp_path):
    rows = [{"_file": "tests/a.py", "retry_index": 0}, {"_file": "tests/a.py", "retry_index": 1},
            {"_file": "tests/b.py"}, {"_file": "tests/b.py"}]
    source, _ = _source(tmp_path, family, rows)
    records, _, aggregation, _ = _pipeline(source, tmp_path)
    assert len(records) == len({record["record_id"] for record in records}) == 4
    assert aggregation["summary"]["inconclusive_count"] == 1
    _write_report(source, family, list(reversed(rows)))
    generate_p0a(source, tmp_path / "reordered")
    reordered = [json.loads(line) for line in (tmp_path / "reordered/HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()]
    assert sorted(record["record_id"] for record in records) == sorted(record["record_id"] for record in reordered)


def test_record_ids_are_unique_across_json_adapter_families(tmp_path):
    source, _ = _source(tmp_path, "pytest", [{}], keep_junit=True)
    for family in ("vitest", "jest"):
        _write_report(source, family, [{}])
    records, _, _, _ = _pipeline(source, tmp_path)
    assert len({record["record_id"] for record in records}) == len(records) == 5


def test_junit_duplicate_diagnostics_apply_only_to_the_same_execution_coordinates():
    xml = '''<testsuite><testcase name="same" retry_index="0"/>
      <testcase name="same" retry_index="1"/><testcase name="same" retry_index="1"/>
      <testcase name="same" retry_index="1" shard_index="0" shard_total="1"/>
      <testcase name="same" retry_index="1"><properties><property name="matrix" value='{"os":"linux"}'/></properties></testcase>
    </testsuite>'''
    parsed = parse_junit_xml(xml)
    assert parsed["parser_diagnostics"]["duplicate_ids"] == ["junit:unknown.py::same"]
    assert [bool(test.get("parser_diagnostics")) for test in parsed["tests"]] == [False, True, True, False, False]


@pytest.mark.parametrize("family", FAMILIES)
def test_flaky_declaration_without_mixed_history_is_not_a_stable_pass(family, tmp_path):
    source, _ = _source(tmp_path, family, [{"flaky": True}])
    _, result, aggregation, score = _pipeline(source, tmp_path)
    assert aggregation["aggregates"][0]["aggregate_status"] == "inconclusive"
    assert aggregation["summary"]["declared_flaky_count"] == 1
    assert aggregation["summary"]["flaky_count"] == 0
    assert score["dimensions"]["determinism_flakiness"] == 0
    assert result["score_confidence"] == "medium"


@pytest.mark.parametrize("family", ["pytest", "vitest", "jest"])
def test_native_retry_count_is_preserved_without_inventing_history_or_flaky(family, tmp_path):
    count = {"reruns": 2} if family == "pytest" else {"meta": {"retryCount": 2}}
    source, _ = _source(tmp_path, family, [count])
    records, result, aggregation, score = _pipeline(source, tmp_path)
    assert records[0]["payload"]["retry_count"] == 2
    assert "retry_index" not in records[0]["payload"] and "flaky" not in records[0]["payload"]
    assert aggregation["aggregates"][0]["aggregate_status"] == "inconclusive"
    assert any(issue["issue"] == "reported_retry_history_missing" for issue in aggregation["issues"])
    assert score["dimensions"]["determinism_flakiness"] == 1
    assert result["score_confidence"] == "medium"


@pytest.mark.parametrize("family", ["pytest", "vitest", "jest"])
def test_native_retry_count_with_complete_passing_history_is_stable(family, tmp_path):
    count = {"reruns": 1} if family == "pytest" else {"meta": {"retryCount": 1}}
    source, _ = _source(tmp_path, family, [{**count, "retry_index": index} for index in (0, 1)])
    _, _, aggregation, score = _pipeline(source, tmp_path)
    assert aggregation["aggregates"][0]["aggregate_status"] == "stable_passed"
    assert aggregation["summary"]["declared_flaky_count"] == 0
    assert score["dimensions"]["determinism_flakiness"] == 5


@pytest.mark.parametrize("family", ["pytest", "vitest", "jest"])
@pytest.mark.parametrize("count", [True, -1, 1.5, "1"])
def test_native_retry_count_requires_an_exact_nonnegative_json_integer(family, count, tmp_path):
    metadata = {"reruns": count} if family == "pytest" else {"meta": {"retryCount": count}}
    source, _ = _source(tmp_path, family, [metadata], keep_junit=True)
    with pytest.raises(PrecheckError) as exc:
        generate_p0a(source, tmp_path / "out")
    assert exc.value.exit_code == 2
    assert any("retry_count" in hit["message"] for hit in _read(tmp_path / "out/precheck-decision.json")["payload"]["dq_hits"])


@pytest.mark.parametrize("family", ["vitest", "jest"])
@pytest.mark.parametrize("metadata", [
    {"retry_index": 0, "meta": {"attempt_index": 1}}, {"retry_count": 1, "meta": {"retryCount": 2}},
    {"matrix": {"os": "linux"}, "meta": {"matrix_values": {"os": "windows"}}},
])
def test_top_level_and_meta_conflicts_are_not_overwritten(family, metadata, tmp_path):
    source, _ = _source(tmp_path, family, [metadata])
    with pytest.raises(PrecheckError):
        generate_p0a(source, tmp_path / "out")
    assert any("conflicting" in hit["message"] for hit in _read(tmp_path / "out/precheck-decision.json")["payload"]["dq_hits"])


@pytest.mark.parametrize("attributes", [
    'retry="0" retry_index="1"', 'retry_index="0"><properties><property name="retry_index" value="1"/></properties></testcase><testcase name="other"',
])
def test_junit_attribute_and_property_conflicts_are_diagnosed(attributes):
    parsed = parse_junit_xml(f'<testsuite><testcase name="same" {attributes}/></testsuite>')
    assert parsed["tests"] == []
    assert "conflicting" in parsed["parser_diagnostics"]["error"]


@pytest.mark.parametrize("value", ["0001", "1.0", "1e0", str(10**309)])
def test_junit_integral_numbers_are_preserved_without_float_conversion(value):
    parsed = parse_junit_xml(f'<testsuite><testcase name="same" retry_index="{value}"/></testsuite>')
    assert "error" not in parsed["parser_diagnostics"]
    assert parsed["tests"][0]["retry_index"] == (10**309 if len(value) > 300 else 1)
