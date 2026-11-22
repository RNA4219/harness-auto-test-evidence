"""P0a/P0bの実recordからP1aまで、複数実行の証跡を検証する。"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from hate import cli
from hate.p0a import generate_p0a
from hate.p0b import ExportError, export_qeg
from hate.p1a import evaluate_trust

FIXTURE = Path("fixtures/golden/p0b-qeg-minimal/input")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _input(tmp_path):
    root = tmp_path / "input"
    shutil.copytree(FIXTURE, root)
    path = root / "p0a/HATE-test-results.ndjson"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return root, path, records


def _write(path, records):
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def _observations(record, rows):
    records = []
    for index, row in enumerate(rows):
        item = copy.deepcopy(record)
        item["record_id"] += f"-observation-{index}"
        item["payload"].update(row)
        records.append(item)
    return records


def _pipeline(root, tmp_path):
    out = tmp_path / "export"
    export_qeg(root, out)
    result = evaluate_trust(out / "qeg-bundle.json", out / "qeg-export-report.json", tmp_path / "trust")
    return (
        result, _read(out / "qeg-bundle.json"), _read(tmp_path / "trust/retry-aggregation.json"),
        _read(tmp_path / "trust/aete-score.json"), _read(tmp_path / "trust/doctor-report.json"),
    )


@pytest.mark.parametrize(("rows", "expected"), [
    ([{"status": "failed", "retry_index": 0}, {"status": "passed", "retry_index": 1}], ["flaky_passed"]),
    ([{"status": "passed", "retry_index": 0}, {"status": "passed", "retry_index": 1}], ["stable_passed"]),
    ([{"status": "failed", "matrix": {"os": "linux"}}, {"status": "passed", "matrix": {"os": "windows"}}], ["failed", "stable_passed"]),
    ([{"status": "failed", "shard_index": 0, "shard_total": 2},
      {"status": "passed", "shard_index": 1, "shard_total": 2}], ["failed"]),
    ([{"status": "passed", "shard_index": 0, "shard_total": 2}], ["inconclusive"]),
    ([{"status": "passed", "retry_index": 1}], ["inconclusive"]),
    ([{"status": "passed"}, {"status": "passed"}], ["inconclusive"]),
    ([{"status": "failed", "attempt_index": 0.0, "matrix_values": {"os": "linux"}, "shard_index": 0.0, "shard_count": 1.0},
      {"status": "passed", "attempt_index": 1.0, "matrix_values": {"os": "linux"}, "shard_index": 0.0, "shard_count": 1.0}], ["flaky_passed"]),
])
def test_export_preserves_observation_coordinates_through_trust(rows, expected, tmp_path):
    root, path, originals = _input(tmp_path)
    records = _observations(originals[0], rows)
    _write(path, records + originals[1:])
    before = path.read_bytes()
    result, bundle, aggregation, score, doctor = _pipeline(root, tmp_path)
    assert path.read_bytes() == before
    nodes = bundle["nodes"]
    assert len({node["id"] for node in nodes}) == len(nodes)
    assert len([node for node in nodes if node["kind"] == "test"]) == len(originals)
    executions = [node for node in nodes if node["kind"] == "execution_evidence"]
    assert len(executions) == len(records) + len(originals) - 1
    assert {node["data"]["source_record_id"] for node in executions} == {record["record_id"] for record in records + originals[1:]}
    assert all(len(node["data"]["source_record_sha256"]) == 64 for node in executions)
    aggregates = [item for item in aggregation["aggregates"] if "test_login" in item["normalized_canonical_test_id"]]
    assert sorted(item["aggregate_status"] for item in aggregates) == sorted(expected)
    assert sum(len(item["retry_attempts"]) for item in aggregates) == len(records)
    assert not any(finding.get("issue") in {"duplicate_node_id", "unresolved_edge_endpoint"} for finding in doctor["findings"])
    if "flaky_passed" in expected:
        assert score["dimensions"]["determinism_flakiness"] == 0
        assert result["trust_status"] == "partial"
    if "inconclusive" in expected:
        assert score["dimensions"]["determinism_flakiness"] == 1


def test_execution_ids_and_bundle_are_order_independent_and_exact_records_are_idempotent(tmp_path):
    root, path, originals = _input(tmp_path)
    records = _observations(originals[0], [{"retry_index": 0}, {"retry_index": 1}]) + originals[1:]
    _write(path, records)
    export_qeg(root, tmp_path / "first")
    _write(path, list(reversed(records)) + [copy.deepcopy(records[0])])
    export_qeg(root, tmp_path / "second")
    for name in ("qeg-bundle.json", "evidence-map.json", "qeg-export-report.json"):
        assert _read(tmp_path / "first" / name) == _read(tmp_path / "second" / name)


def test_duplicate_source_record_id_does_not_drop_distinct_results(tmp_path):
    root, path, originals = _input(tmp_path)
    records = _observations(originals[0], [{"status": "failed", "retry_index": 0}, {"status": "passed", "retry_index": 1}])
    records[1]["record_id"] = records[0]["record_id"]
    _write(path, records + originals[1:])
    _, bundle, aggregation, _, _ = _pipeline(root, tmp_path)
    matching = [node for node in bundle["nodes"] if node["data"].get("source_record_id") == records[0]["record_id"]]
    assert len(matching) == len({node["id"] for node in matching}) == 2
    assert aggregation["summary"]["flaky_count"] == 1


@pytest.mark.parametrize("field", ["framework", "file", "identity_components", "parameters"])
def test_conflicting_test_identity_is_rejected_before_outputs(field, tmp_path):
    root, path, originals = _input(tmp_path)
    rows = [{field: {"name": "first"} if field in {"identity_components", "parameters"} else "first"},
            {field: {"name": "second"} if field in {"identity_components", "parameters"} else "second"}]
    _write(path, _observations(originals[0], rows))
    with pytest.raises(ExportError, match=f"conflicting payload.{field}"):
        export_qeg(root, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(("field", "value"), [
    ("retry_index", True), ("retry_index", -1), ("retry_index", 1.5), ("retry_index", "1"),
    ("attempt_index", None), ("shard_index", False), ("shard_total", 0), ("shard_count", 2.5),
    ("matrix", []), ("matrix_values", "linux"), ("status", []), ("flaky", "false"),
    ("canonical_test_id", " "), ("canonical_test_id", 4), ("identity_components", []),
])
def test_invalid_record_metadata_is_reported_by_api_and_cli_without_overwriting(field, value, tmp_path, capsys):
    root, path, records = _input(tmp_path)
    records[0]["payload"][field] = value
    _write(path, records)
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "qeg-bundle.json"
    sentinel.write_bytes(b"previous output")
    with pytest.raises(ExportError, match=field) as exc:
        export_qeg(root, out)
    assert exc.value.exit_code == 1
    assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert field in captured.err + captured.out
    assert "Traceback" not in captured.err + captured.out
    assert sentinel.read_bytes() == b"previous output"


@pytest.mark.parametrize("token", ["0.99999999999999999", "1.00000000000000001", "-1e-999", "1e999", "NaN", "Infinity"])
def test_retry_number_lexeme_is_validated_before_float_rounding(token, tmp_path):
    root, path, records = _input(tmp_path)
    records[0]["payload"]["retry_index"] = "REPLACE_NUMBER"
    _write(path, records)
    path.write_text(path.read_text(encoding="utf-8").replace('"REPLACE_NUMBER"', token), encoding="utf-8")
    with pytest.raises(ExportError, match="HATE-test-results.ndjson:1"):
        export_qeg(root, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("row", ["null", "[]", '{"payload":null}', '{"payload":{}}', '{"payload":', '{"record_id":false,"payload":{"canonical_test_id":"a"}}'])
def test_malformed_record_has_line_number_and_no_output(row, tmp_path):
    root, path, _ = _input(tmp_path)
    path.write_text("\n" + row + "\n", encoding="utf-8")
    with pytest.raises(ExportError, match="HATE-test-results.ndjson:2"):
        export_qeg(root, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("fields", [
    {"retry_index": 0, "attempt_index": 1}, {"shard_total": 1, "shard_count": 2},
    {"matrix": {"os": "linux"}, "matrix_values": {"os": "windows"}},
])
def test_conflicting_aliases_are_rejected_at_export(fields, tmp_path):
    root, path, records = _input(tmp_path)
    records[0]["payload"].update(fields)
    _write(path, records)
    with pytest.raises(ExportError, match="conflicting"):
        export_qeg(root, tmp_path / "out")


def test_explicit_flaky_metadata_is_retained_per_execution(tmp_path):
    root, path, records = _input(tmp_path)
    records[0]["payload"]["flaky"] = True
    records[1]["payload"]["flaky"] = False
    _write(path, records)
    export_qeg(root, tmp_path / "out")
    executions = [node for node in _read(tmp_path / "out/qeg-bundle.json")["nodes"] if node["kind"] == "execution_evidence"]
    assert {node["data"]["source_record_id"]: node["data"]["flaky"] for node in executions} == {
        records[0]["record_id"]: True, records[1]["record_id"]: False,
    }


def test_real_p0b_execution_to_artifact_edges_are_accepted_by_trust(tmp_path):
    root, path, records = _input(tmp_path)
    manifest = Path("fixtures/adapters/playwright/evidence/artifact-manifest.json")
    shutil.copy2(manifest, root / "p0a/artifact-manifest.json")
    records[0]["payload"]["artifacts"] = [artifact["artifact_id"] for artifact in _read(manifest)["artifacts"]]
    _write(path, records)
    result, bundle, _, score, doctor = _pipeline(root, tmp_path)
    kinds = {node["id"]: node["kind"] for node in bundle["nodes"]}
    assert any(kinds.get(edge["from"]) == "execution_evidence" and kinds.get(edge["to"]) == "evidence_artifact" for edge in bundle["edges"])
    assert any(kinds.get(edge["from"]) == "test" and kinds.get(edge["to"]) == "evidence_artifact" for edge in bundle["edges"])
    assert not any(finding.get("issue") == "edge_kind_mismatch" for finding in doctor["findings"])
    assert score["dimensions"]["traceability_lineage"] == 5
    assert result["trust_status"] == "success"


def test_junit_retry_records_survive_the_full_p0a_p0b_p1a_pipeline(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(Path("fixtures/golden/p0a-minimal/input"), source)
    (source / "junit.xml").write_text(
        '<testsuite name="pytest"><testcase name="test_login" file="tests/test_auth.py" retry_index="0"><failure/></testcase>'
        '<testcase name="test_login" file="tests/test_auth.py" retry_index="1"/>'
        '<testcase name="test_connection" file="tests/test_db.py"/></testsuite>', encoding="utf-8",
    )
    root, _, _ = _input(tmp_path)
    generated = generate_p0a(source, root / "p0a")
    assert generated["exit_code"] == 0
    _, bundle, aggregation, score, _ = _pipeline(root, tmp_path)
    assert len([node for node in bundle["nodes"] if node["kind"] == "test"]) == 2
    assert len([node for node in bundle["nodes"] if node["kind"] == "execution_evidence"]) == 3
    assert aggregation["summary"]["flaky_count"] == 1
    assert score["dimensions"]["determinism_flakiness"] == 0
