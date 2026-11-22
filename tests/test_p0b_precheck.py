"""precheckの不許可・不正な許可宣言でQEG出力を更新しない。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hate import cli
from hate.p0b import ExportError, export_qeg

FIELDS = ("decision", "exit_code", "dq_hits", "soft_gaps", "reasons", "qeg_export_allowed")


def _input(tmp_path):
    root = tmp_path / "input"
    shutil.copytree(Path("fixtures/golden/p0b-qeg-minimal/input"), root)
    path = root / "p0a/precheck-decision.json"
    return root, path, json.loads(path.read_text(encoding="utf-8"))


def _snapshot(directory):
    return {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def _assert_rejected(root, tmp_path, capsys, code, diagnostic):
    # 既存成果物の内容とファイル集合を保持し、新しい出力先も作成しない。
    out = tmp_path / "existing"
    shutil.copytree(Path("fixtures/golden/p0b-qeg-minimal/expected"), out)
    before, inputs = _snapshot(out), _snapshot(root)
    for destination in (out, tmp_path / "new"):
        with pytest.raises(ExportError) as caught:
            export_qeg(root, destination)
        assert caught.value.exit_code == code
        assert diagnostic in str(caught.value)
        assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(destination)]) == code
        stderr = capsys.readouterr().err
        assert "Traceback" not in stderr
        if code == 2:
            assert "reason" in json.loads(stderr)
        else:
            assert "HATE-E-EXPORT" in stderr and diagnostic in stderr
    assert not (tmp_path / "new").exists()
    assert _snapshot(out) == before
    assert _snapshot(root) == inputs


@pytest.mark.parametrize("decision", ["eligible", "conditional", "ineligible", "hard_dq"])
@pytest.mark.parametrize("allowed", [True, False])
@pytest.mark.parametrize("exit_code", [0, 2])
@pytest.mark.parametrize("dq_hits", [[], [{"code": "HATE-DQ-002", "message": "adapter failed"}]])
def test_only_consistent_permission_exports(decision, allowed, exit_code, dq_hits, tmp_path, capsys):
    root, path, record = _input(tmp_path)
    payload = record["payload"]
    payload.update(decision=decision, qeg_export_allowed=allowed, exit_code=exit_code, dq_hits=dq_hits)
    if decision == "conditional":
        payload["soft_gaps"] = [{"code": "optional_evidence_missing", "message": "optional evidence unavailable"}]
    path.write_text(json.dumps(record), encoding="utf-8")
    if decision in {"eligible", "conditional"} and allowed and exit_code == 0 and not dq_hits:
        before = _snapshot(root)
        assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(tmp_path / "out")]) == 0
        bundle = json.loads((tmp_path / "out/qeg-bundle.json").read_text(encoding="utf-8"))
        verdict = next(node["data"] for node in bundle["nodes"] if node["kind"] == "gate_verdict")
        assert verdict["decision"] == decision and verdict["qeg_export_allowed"] is True
        assert bundle["metadata"]["debugOnly"] is False
        assert _snapshot(root) == before
    else:
        _assert_rejected(root, tmp_path, capsys, 2, "QEG export not allowed")


@pytest.mark.parametrize("field", FIELDS)
def test_missing_permission_field_is_input_error(field, tmp_path, capsys):
    root, path, record = _input(tmp_path)
    del record["payload"][field]
    path.write_text(json.dumps(record), encoding="utf-8")
    _assert_rejected(root, tmp_path, capsys, 1, f"payload.{field}")


@pytest.mark.parametrize(("field", "value", "diagnostic"), [
    ("decision", value, "decision") for value in (None, "", "unknown", True, [], {})
] + [
    ("qeg_export_allowed", value, "qeg_export_allowed") for value in (None, "false", "true", 0, 1, [], {})
] + [
    ("exit_code", value, "exit_code") for value in (None, False, True, "0", 1, -1, 0.5, [], {})
] + [
    (field, value, field) for field in ("dq_hits", "soft_gaps", "reasons") for value in (None, {}, "")
] + [
    ("dq_hits", [None], "dq_hits[0]"),
    ("soft_gaps", ["gap"], "soft_gaps[0]"),
    ("reasons", [1], "reasons[0]"),
])
def test_malformed_permission_is_located_input_error(field, value, diagnostic, tmp_path, capsys):
    root, path, record = _input(tmp_path)
    record["payload"][field] = value
    path.write_text(json.dumps(record), encoding="utf-8")
    _assert_rejected(root, tmp_path, capsys, 1, f"precheck-decision.json: payload.{diagnostic}")


@pytest.mark.parametrize(("token", "expected"), [
    ("0.0", 0), ("-0", 0), ("0e0", 0), ("2.0", 2), ("2e0", 2),
    ("1e-9999", 1), ("-1e-9999", 1), ("2.00000000000000001", 1),
    ("1.99999999999999999", 1),
])
def test_exit_code_checks_original_json_number(token, expected, tmp_path, capsys):
    root, path, record = _input(tmp_path)
    text = json.dumps(record)
    assert text.count('"exit_code": 0') == 1
    path.write_text(text.replace('"exit_code": 0', f'"exit_code": {token}'), encoding="utf-8")
    if expected == 0:
        export_qeg(root, tmp_path / "out")
        assert (tmp_path / "out/qeg-bundle.json").is_file()
    else:
        diagnostic = "QEG export not allowed" if expected == 2 else "payload.exit_code"
        _assert_rejected(root, tmp_path, capsys, expected, diagnostic)


def test_hard_dq_keeps_existing_denial_report(tmp_path):
    root, path, record = _input(tmp_path)
    # 許可フラグとの矛盾があってもhard DQは通さない。
    record["payload"]["decision"] = "hard_dq"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ExportError) as caught:
        export_qeg(root, tmp_path / "out")
    assert caught.value.report == {"decision": "hard_dq", "reason": "P0a precheck disqualified"}
