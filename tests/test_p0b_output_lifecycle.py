"""P0bの再実行と補助成果物の失敗で、古い証跡や混在した出力を残さない。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hate import cli
from hate.p0b import ExportError, export_qeg

SOURCE = Path("fixtures/golden/p0b-qeg-minimal/input")
SIDECARS = {"risk-debt-register.json", "manual-bb-bridge-requests.jsonl"}


def _fixture(tmp_path):
    root = tmp_path / "input"
    shutil.copytree(SOURCE, root)
    return root


def _partial(root):
    path = root / "p0a/HATE-test-results.ndjson"
    original = path.read_bytes()
    rows = [json.loads(line) for line in original.splitlines() if line.strip()]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows[:1]), encoding="utf-8")
    return original


def _snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _existing(tmp_path, root):
    out = tmp_path / "existing"
    export_qeg(root, out)
    (out / "operator-notes.md").write_bytes(b"keep this note")
    (out / "archive").mkdir()
    (out / "archive/risk-debt-register.json").write_bytes(b"keep historical evidence")
    return out


def _assert_rejected(root, out, tmp_path, capsys, diagnostic):
    before, inputs = _snapshot(out), _snapshot(root)
    for destination in (out, tmp_path / "new"):
        with pytest.raises(ExportError) as caught:
            export_qeg(root, destination)
        assert caught.value.exit_code == 1 and diagnostic in str(caught.value)
        assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(destination)]) == 1
        stderr = capsys.readouterr().err
        assert "HATE-E-EXPORT" in stderr and diagnostic in stderr and "Traceback" not in stderr
        assert _snapshot(out) == before and _snapshot(root) == inputs
        assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("other_gap", [False, True])
def test_resolved_missing_execution_retires_only_owned_sidecars(other_gap, tmp_path, capsys):
    root = _fixture(tmp_path)
    original = _partial(root)
    out = _existing(tmp_path, root)
    assert SIDECARS <= {path.name for path in out.iterdir()}
    (root / "p0a/HATE-test-results.ndjson").write_bytes(original)
    if other_gap:
        path = root / "diff-risk-test.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["risks"][0]["source_refs"] = []
        path.write_text(json.dumps(record), encoding="utf-8")
    inputs = _snapshot(root)
    assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(out)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["export_status"] == ("partial" if other_gap else "success")
    assert result["missing_executions"] == 0
    assert SIDECARS.isdisjoint(result["generated"])
    assert all(not (out / name).exists() for name in SIDECARS)
    assert {p.name for p in out.iterdir() if p.is_file()} == {*result["generated"], "operator-notes.md"}
    assert (out / "operator-notes.md").read_bytes() == b"keep this note"
    assert (out / "archive/risk-debt-register.json").read_bytes() == b"keep historical evidence"
    assert _snapshot(root) == inputs
    before = _snapshot(out)
    export_qeg(root, out)
    assert _snapshot(out) == before


def test_partial_rerun_replaces_both_sidecars_with_current_gap(tmp_path):
    root = _fixture(tmp_path)
    original = _partial(root)
    out = _existing(tmp_path, root)
    assert "risk-db-high" in (out / "manual-bb-bridge-requests.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in original.splitlines() if line.strip()]
    (root / "p0a/HATE-test-results.ndjson").write_text("".join(json.dumps(row) + "\n" for row in rows[1:]), encoding="utf-8")
    result = export_qeg(root, out)
    assert result["missing_executions"] == 1 and SIDECARS <= set(result["generated"])
    debt = json.loads((out / "risk-debt-register.json").read_text(encoding="utf-8"))
    bridge = [json.loads(line) for line in (out / "manual-bb-bridge-requests.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [item["risk_id"] for item in debt["items"]] == ["risk-auth-high"]
    assert [item["risk_id"] for item in bridge] == ["risk-auth-high"]


@pytest.mark.parametrize("builder", ["_build_risk_debt_register", "_build_manual_bridge_requests"])
def test_builder_internal_failure_preserves_existing_and_new_output(builder, tmp_path, monkeypatch):
    root = _fixture(tmp_path)
    _partial(root)
    out = _existing(tmp_path, root)
    before, inputs = _snapshot(out), _snapshot(root)

    def fail(*args, **kwargs):
        raise RuntimeError("supplemental output builder failed")

    monkeypatch.setattr(f"hate.p0b_outputs.{builder}", fail)
    for destination in (out, tmp_path / "new"):
        with pytest.raises(RuntimeError, match="supplemental output builder failed"):
            export_qeg(root, destination)
        assert _snapshot(out) == before and _snapshot(root) == inputs
        assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("artifact", ["qeg-bundle.json", "diff-risk-test.json", "risk-debt-register.json"])
def test_unencodable_output_is_rejected_before_opening_any_file(artifact, tmp_path, capsys):
    root = _fixture(tmp_path)
    _partial(root)
    out = _existing(tmp_path, root)
    if artifact == "risk-debt-register.json":
        path = root / "risk-debt-lifecycle.json"
        record = {"items": [{"risk_id": "risk-db-high", "owner": "\ud800"}]}
    else:
        path = root / "diff-risk-test.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        if artifact == "qeg-bundle.json":
            record["risks"][0]["title"] = "\ud800"
        else:
            record["extension_note"] = "\ud800"
    path.write_text(json.dumps(record), encoding="utf-8")
    _assert_rejected(root, out, tmp_path, capsys, f"Cannot serialize {artifact}")


@pytest.mark.parametrize("value", [float("nan"), {"not JSON serializable"}])
def test_last_jsonl_serialization_failure_preserves_all_outputs(value, tmp_path, capsys, monkeypatch):
    root = _fixture(tmp_path)
    _partial(root)
    out = _existing(tmp_path, root)
    monkeypatch.setattr("hate.p0b_outputs._build_manual_bridge_requests", lambda *args: [{"invalid": value}])
    _assert_rejected(root, out, tmp_path, capsys, "Cannot serialize manual-bb-bridge-requests.jsonl")


@pytest.mark.parametrize("raw_age", ["null", "true", "false", '"8"', '"unknown"', "[]", "{}", "-1", "0.5", "1.00000000000000001", "1e-999", "-1e-999"])
@pytest.mark.parametrize("historical", [False, True])
def test_invalid_lifecycle_age_has_position_and_preserves_output(raw_age, historical, tmp_path, capsys):
    root = _fixture(tmp_path)
    _partial(root)
    out = _existing(tmp_path, root)
    identity = '"debt_id":"past-debt","risk_id":"past-risk"' if historical else '"risk_id":"risk-db-high"'
    (root / "risk-debt-lifecycle.json").write_text('{"items":[{' + identity + ',"age_days":' + raw_age + ' }]}', encoding="utf-8")
    _assert_rejected(root, out, tmp_path, capsys, "risk-debt-lifecycle.json: $.items[0].age_days")


@pytest.mark.parametrize(("items", "diagnostic"), [
    (None, "$.items must"), ({}, "$.items must"), ("items", "$.items must"),
    ([None], "$.items[0] must"), ([False], "$.items[0] must"), ([[]], "$.items[0] must"),
])
def test_declared_lifecycle_structure_is_checked_without_current_gaps(items, diagnostic, tmp_path, capsys):
    root = _fixture(tmp_path)
    out = _existing(tmp_path, root)
    (root / "risk-debt-lifecycle.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    _assert_rejected(root, out, tmp_path, capsys, diagnostic)


@pytest.mark.parametrize(("raw_age", "expected"), [("0", 0), ("0.0", 0), ("8.0", 8), ("9007199254740993.0", 9007199254740993)])
def test_exact_nonnegative_lifecycle_age_is_preserved(raw_age, expected, tmp_path):
    root = _fixture(tmp_path)
    _partial(root)
    (root / "risk-debt-lifecycle.json").write_text('{"items":[{"risk_id":"risk-db-high","age_days":' + raw_age + ' }]}', encoding="utf-8")
    inputs = _snapshot(root)
    out = tmp_path / "out"
    export_qeg(root, out)
    record = json.loads((out / "risk-debt-register.json").read_text(encoding="utf-8"))
    assert type(record["items"][0]["age_days"]) is int
    assert record["items"][0]["age_days"] == expected
    assert _snapshot(root) == inputs
