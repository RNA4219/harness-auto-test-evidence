"""retryの順序、matrixの分離、shardの完全性を公開P1a APIで検証する。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hate import cli, p1a
from hate.schema_resources import read_schema, validate_schema_instance

FIXTURE = Path("fixtures/golden/p0b-qeg-minimal/expected")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle(rows):
    bundle = _read(FIXTURE / "qeg-bundle.json")
    bundle["nodes"] = [{"id": "test:1", "kind": "test", "label": "test",
                        "data": {"canonical_test_id": "pytest:tests/test_a.py::test_a"}, "sourceRefs": ["tests.json"]}]
    bundle["edges"] = []
    for index, data in enumerate(rows):
        node_id = f"execution:{index}"
        bundle["nodes"].append({"id": node_id, "kind": "execution_evidence", "label": "execution",
                                "data": data, "sourceRefs": ["tests.json"]})
        bundle["edges"].append({"kind": "evidenced_by", "from": "test:1", "to": node_id,
                                "traceability": {"sourceRefs": ["tests.json"], "confidence": "high", "assumptions": []}})
    return bundle


def _run(bundle, tmp_path, operation=p1a.evaluate_trust):
    path, out = tmp_path / "bundle.json", tmp_path / "out"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    before = path.read_bytes()
    result = operation(path, FIXTURE / "qeg-export-report.json", out)
    assert path.read_bytes() == before
    aggregation = _read(out / "retry-aggregation.json")
    assert not validate_schema_instance(aggregation, read_schema("retry-aggregation.schema.json"))
    return result, aggregation, _read(out / "aete-score.json"), _read(out / "doctor-report.json")


@pytest.mark.parametrize(("rows", "status", "determinism"), [
    ([], "inconclusive", 1),
    ([{"status": "passed"}], "stable_passed", 3),
    ([{"status": "failed"}], "failed", 3),
    ([{"status": "error"}], "failed", 3),
    ([{"status": "skipped"}], "inconclusive", 1),
    ([{"status": "passed", "retry_index": 2}], "inconclusive", 1),
    ([{"status": "failed", "retry_index": 0}, {"status": "passed", "retry_index": 2}], "inconclusive", 1),
    ([{"status": "failed"}, {"status": "passed"}], "inconclusive", 1),
    ([{"status": "passed", "retry_index": 0}, {"status": "passed", "retry_index": 0}], "inconclusive", 1),
    ([{"status": "unknown", "retry_index": 0}, {"status": "passed", "retry_index": 1}], "inconclusive", 1),
    ([{"status": "skipped", "retry_index": 0}, {"status": "passed", "retry_index": 1}], "inconclusive", 1),
    ([{"status": "failed", "retry_index": 0}, {"status": "passed", "retry_index": 1}], "flaky_passed", 0),
    ([{"status": "passed", "retry_index": 0}, {"status": "failed", "retry_index": 1}], "flaky_failed", 0),
    ([{"status": "passed", "retry_index": 0}, {"status": "passed", "retry_index": 1}], "stable_passed", 5),
])
def test_retry_results_and_scoring_share_the_same_execution_evidence(rows, status, determinism, tmp_path):
    result, aggregation, score, doctor = _run(_bundle(rows), tmp_path)
    assert len(aggregation["aggregates"]) == 1
    assert aggregation["aggregates"][0]["aggregate_status"] == status
    assert score["dimensions"]["determinism_flakiness"] == determinism
    if status == "inconclusive" or status.startswith("flaky"):
        assert result["trust_status"] == "partial"
        assert any(finding["category"] == "retry" for finding in doctor["findings"])
    if status == "inconclusive":
        assert result["score_confidence"] == "medium"


@pytest.mark.parametrize(("rows", "expected", "missing"), [
    ([{"status": "passed", "shard_index": 0, "shard_total": 2}], "inconclusive", True),
    ([{"status": "passed", "shard_index": 1, "shard_total": 2}, {"status": "passed", "shard_index": 2, "shard_total": 2}], "inconclusive", True),
    ([{"status": "passed", "shard_index": 0, "shard_total": 2}, {"status": "passed", "shard_index": 0, "shard_total": 2}], "inconclusive", True),
    ([{"status": "passed", "shard_total": 1}], "inconclusive", True),
    ([{"status": "passed", "shard_index": 0}], "inconclusive", False),
    ([{"status": "passed", "shard_index": 0, "shard_total": 1}, {"status": "passed", "shard_index": 1, "shard_total": 2}], "inconclusive", False),
    ([{"status": "failed", "shard_index": 0, "shard_total": 2}, {"status": "passed", "shard_index": 1, "shard_total": 2}], "failed", False),
    ([{"status": "passed", "shard_index": 0, "shard_total": 2}, {"status": "passed", "shard_index": 1, "shard_total": 2}], "stable_passed", False),
    ([{"status": "passed", "retry_index": 0, "shard_index": 0, "shard_total": 2},
      {"status": "passed", "retry_index": 1, "shard_index": 1, "shard_total": 2}], "inconclusive", True),
])
def test_shards_are_complete_per_retry_with_valid_unique_zero_based_indices(rows, expected, missing, tmp_path):
    _, aggregation, _, _ = _run(_bundle(rows), tmp_path)
    aggregate = aggregation["aggregates"][0]
    assert aggregate["aggregate_status"] == expected
    assert aggregate["shards"]["missing"] is missing
    assert aggregation["summary"]["missing_shard_count"] == int(missing)


def test_parallel_shards_are_reduced_before_retry_history(tmp_path):
    rows = [{"status": status, "retry_index": retry, "shard_index": shard, "shard_total": 2}
            for retry, shard, status in [(0, 0, "failed"), (0, 1, "passed"), (1, 0, "passed"), (1, 1, "passed")]]
    _, aggregation, _, _ = _run(_bundle(rows), tmp_path)
    aggregate = aggregation["aggregates"][0]
    assert aggregate["aggregate_status"] == "flaky_passed"
    assert [attempt["status"] for attempt in aggregate["attempt_results"]] == ["failed", "passed"]


def test_matrix_environments_do_not_overwrite_or_become_retry_of_each_other(tmp_path):
    bundle = _bundle([{"status": "failed", "matrix": {"os": "linux"}}, {"status": "passed", "matrix": {"os": "windows"}}])
    bundle["nodes"][0]["data"]["matrix"] = {"python": "3.12"}
    result, aggregation, _, _ = _run(bundle, tmp_path)
    states = {item["matrix"]["os"]: item["aggregate_status"] for item in aggregation["aggregates"]}
    assert states == {"linux": "failed", "windows": "stable_passed"}
    assert all(item["matrix"]["python"] == "3.12" for item in aggregation["aggregates"])
    assert aggregation["summary"]["flaky_count"] == 0
    assert result["trust_status"] == "success"
    bundle["nodes"].reverse()
    bundle["edges"].reverse()
    assert _run(bundle, tmp_path)[1] == aggregation


def test_same_canonical_identity_is_grouped_across_test_node_aliases_and_duplicate_edges(tmp_path):
    bundle = _bundle([{"status": "failed", "retry_index": 0}, {"status": "passed", "retry_index": 1}])
    alias = copy.deepcopy(bundle["nodes"][0])
    alias["id"] = "test:alias"
    bundle["nodes"].append(alias)
    bundle["edges"][1]["from"] = alias["id"]
    bundle["edges"].append(copy.deepcopy(bundle["edges"][0]))
    _, aggregation, _, _ = _run(bundle, tmp_path)
    assert len(aggregation["aggregates"]) == 1
    aggregate = aggregation["aggregates"][0]
    assert aggregate["test_node_ids"] == ["test:1", "test:alias"]
    assert aggregate["raw_statuses"] == ["failed", "passed"]
    assert aggregate["aggregate_status"] == "flaky_passed"


def test_retry_and_shard_aliases_use_identical_normalized_numbers(tmp_path):
    bundle = _bundle([{"status": "failed", "attempt_index": 0.0, "shard_index": 0.0, "shard_count": 1.0},
                      {"status": "passed", "attempt_index": 1.0, "shard_index": 0.0, "shard_count": 1.0}])
    _, aggregation, _, _ = _run(bundle, tmp_path)
    aggregate = aggregation["aggregates"][0]
    assert aggregate["aggregate_status"] == "flaky_passed"
    assert [item["retry_index"] for item in aggregate["retry_attempts"]] == [0, 1]
    assert aggregate["shards"] == {"observed": ["0"], "expected_count": 1, "missing": False}


OPERATIONS = {"trust": p1a.evaluate_trust, "replay": p1a.replay_trust, "doctor": p1a.doctor_trust,
              "explain": p1a.explain_trust, "recommend": p1a.recommend_trust}


@pytest.mark.parametrize("command", OPERATIONS)
@pytest.mark.parametrize(("field", "value"), [
    ("retry_index", True), ("retry_index", -1), ("retry_index", 0.5), ("retry_index", "1"),
    ("attempt_index", None), ("shard_index", False), ("shard_index", -1), ("shard_total", 0),
    ("shard_count", 1.5), ("shard_total", float("inf")), ("matrix", []), ("matrix_values", "linux"),
    ("status", {}), ("flaky", "false"), ("flaky", 1),
    ("retry_count", True), ("retry_count", -1), ("retry_count", 1.5), ("retry_count", "1"),
])
def test_malformed_execution_metadata_is_diagnosed_before_output(command, field, value, tmp_path, capsys):
    bundle = _bundle([{"status": "passed", field: value}])
    path, out = tmp_path / "bundle.json", tmp_path / "out"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    out.mkdir()
    sentinel = out / "aete-score.json"
    sentinel.write_bytes(b"previous score")
    saved = sentinel.read_bytes(), sentinel.stat().st_mtime_ns
    with pytest.raises(p1a.TrustError) as caught:
        OPERATIONS[command](path, FIXTURE / "qeg-export-report.json", out)
    assert caught.value.exit_code == 1 and field in str(caught.value)
    assert "nodes[1].data" in str(caught.value)
    args = ["trust", "evaluate"] if command == "trust" else [command]
    assert cli.main([*args, "--bundle", str(path), "--report", str(FIXTURE / "qeg-export-report.json"), "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert not captured.out and "HATE-E-" in captured.err
    assert (sentinel.read_bytes(), sentinel.stat().st_mtime_ns) == saved
    assert list(out.iterdir()) == [sentinel]


@pytest.mark.parametrize("data", [
    {"retry_index": 0, "attempt_index": 1}, {"shard_total": 1, "shard_count": 2},
    {"matrix": {"os": "linux"}, "matrix_values": {"os": "windows"}},
])
def test_conflicting_aliases_cannot_hide_another_declared_value(data, tmp_path):
    with pytest.raises(p1a.TrustError, match="conflict"):
        _run(_bundle([{"status": "passed", **data}]), tmp_path)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("field", ["retry_index", "retry_count", "shard_index", "shard_total"])
def test_retry_numbers_are_checked_before_float_rounding(field, tmp_path):
    bundle = _bundle([{"status": "passed", field: "RAW_NUMBER"}])
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle).replace('"RAW_NUMBER"', '1.00000000000000001'), encoding="utf-8")
    with pytest.raises(p1a.TrustError, match=field):
        p1a.evaluate_trust(path, FIXTURE / "qeg-export-report.json", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_undeclared_canonical_identity_does_not_merge_unrelated_test_nodes(tmp_path):
    bundle = _bundle([])
    bundle["nodes"][0]["data"] = {}
    other = copy.deepcopy(bundle["nodes"][0])
    other["id"] = "test:other"
    bundle["nodes"].append(other)
    _, aggregation, _, _ = _run(bundle, tmp_path)
    assert len(aggregation["aggregates"]) == 2
    assert len({item["aggregation_key"] for item in aggregation["aggregates"]}) == 2
    assert aggregation["summary"]["inconclusive_count"] == 2


def test_large_declared_shard_count_does_not_require_allocating_expected_indices(tmp_path):
    _, aggregation, _, _ = _run(_bundle([{"status": "passed", "shard_index": 0, "shard_total": 10**12}]), tmp_path)
    aggregate = aggregation["aggregates"][0]
    assert aggregate["aggregate_status"] == "inconclusive"
    assert next(issue for issue in aggregate["issues"] if issue["issue"] == "missing_shards")["missing_count"] == 10**12 - 1


@pytest.mark.parametrize("field", ["matrix", "matrix_values"])
def test_test_node_matrix_is_also_validated(field, tmp_path):
    bundle = _bundle([])
    bundle["nodes"][0]["data"][field] = []
    with pytest.raises(p1a.TrustError, match=field):
        _run(bundle, tmp_path)
    assert not (tmp_path / "out").exists()


def test_replay_preserves_aggregation_and_soft_gap_diagnosis(tmp_path):
    bundle = _bundle([{"status": "passed", "shard_index": 0, "shard_total": 2}])
    first = _run(bundle, tmp_path)
    replayed = _run(bundle, tmp_path, p1a.replay_trust)
    assert replayed[1:] == first[1:]
    p1a.doctor_trust(tmp_path / "bundle.json", FIXTURE / "qeg-export-report.json", tmp_path / "doctor")
    assert _read(tmp_path / "doctor" / "doctor-report.json") == first[3]


@pytest.mark.parametrize("rows", [
    [{"status": "passed", "flaky": True}],
    [{"status": "passed", "retry_count": 2}],
    [{"status": "failed", "retry_index": 0, "flaky": True}, {"status": "passed", "retry_index": 1, "flaky": False}],
])
def test_flaky_declarations_and_retry_counts_survive_replay_and_doctor(rows, tmp_path):
    bundle = _bundle(rows)
    first = _run(bundle, tmp_path)
    second = _run(bundle, tmp_path, p1a.replay_trust)
    assert first[1:] == second[1:]
    p1a.doctor_trust(tmp_path / "bundle.json", FIXTURE / "qeg-export-report.json", tmp_path / "doctor")
    assert _read(tmp_path / "doctor/doctor-report.json") == first[3]
    if len(rows) > 1:
        assert first[1]["summary"]["flaky_count"] == 1
        assert first[1]["aggregates"][0]["aggregate_status"] == "flaky_passed"
    else:
        assert first[1]["aggregates"][0]["aggregate_status"] == "inconclusive"
