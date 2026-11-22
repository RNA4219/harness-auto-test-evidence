"""生成bundleのschema不適合を保存前に止め、既存成果物を保持する。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hate import cli
from hate.p0b import ExportError, export_qeg

SOURCE = Path("fixtures/golden/p0b-qeg-minimal/input")
EXPECTED = Path("fixtures/golden/p0b-qeg-minimal/expected")


def _fixture(tmp_path):
    root = tmp_path / "input"
    shutil.copytree(SOURCE, root)
    return root


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize(("target", "value", "diagnostic"), [
    ("created_at", value, "$.metadata.createdAt") for value in ("", None, 42, False, [], {})
] + [
    ("risk_title", value, ".label") for value in (None, 0, False, [], {"text": "invalid label type"})
] + [
    ("risk_refs", value, ".sourceRefs") for value in ("not-an-array", True, [None], [""])
])
def test_invalid_generated_bundle_stops_api_and_cli_before_all_writes(target, value, diagnostic, tmp_path, capsys):
    root = _fixture(tmp_path)
    path = root / ("p0a/HATE-run.json" if target == "created_at" else "diff-risk-test.json")
    record = _read(path)
    if target == "created_at":
        record["created_at"] = value
    else:
        record["risks"][0]["title" if target == "risk_title" else "source_refs"] = value
    _write(path, record)
    out = tmp_path / "existing"
    shutil.copytree(EXPECTED, out)
    (out / "risk-debt-register.json").write_bytes(b"previous risk debt")
    (out / "manual-bb-bridge-requests.jsonl").write_bytes(b"previous manual bridge")
    before, inputs = _snapshot(out), _snapshot(root)
    for destination in (out, tmp_path / "new"):
        with pytest.raises(ExportError) as caught:
            export_qeg(root, destination)
        error = caught.value
        assert error.exit_code == 1 and diagnostic in str(error)
        assert error.report["error"] == "generated_bundle_schema_invalid"
        assert error.report["qeg_schema_compatibility"]["valid"] is False
        assert any(diagnostic in detail for detail in error.report["qeg_schema_compatibility"]["errors"])
        assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(destination)]) == 1
        stderr = capsys.readouterr().err
        assert "HATE-E-EXPORT" in stderr and "qeg-bundle.json" in stderr and diagnostic in stderr
        assert "Traceback" not in stderr
    assert _snapshot(out) == before and _snapshot(root) == inputs
    assert not (tmp_path / "new").exists()


def test_schema_diagnostics_are_bounded_but_api_keeps_all_errors(tmp_path, capsys):
    root = _fixture(tmp_path)
    path = root / "diff-risk-test.json"
    record = _read(path)
    record["risks"] = [{"risk_id": f"invalid-{index}", "title": {}, "source_refs": ["spec.md"]} for index in range(12)]
    _write(path, record)
    with pytest.raises(ExportError) as caught:
        export_qeg(root, tmp_path / "out")
    errors = caught.value.report["qeg_schema_compatibility"]["errors"]
    assert len(errors) == 12
    assert all(error in str(caught.value) for error in errors[:8])
    assert all(error not in str(caught.value) for error in errors[8:])
    assert "4 more schema errors" in str(caught.value)
    assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(tmp_path / "out")]) == 1
    assert "4 more schema errors" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("partial", [True, False])
def test_valid_full_and_partial_exports_still_validate_and_write(partial, tmp_path):
    root = _fixture(tmp_path)
    if partial:
        path = root / "p0a/HATE-test-results.ndjson"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows[:1]), encoding="utf-8")
    out = tmp_path / "out"
    result = export_qeg(root, out)
    assert result["exit_code"] == 0 and result["export_status"] == ("partial" if partial else "success")
    assert _read(out / "qeg-export-report.json")["qeg_schema_compatibility"] == {
        "schema": "schemas/HATE/v1/qeg-bundle.schema.json", "valid": True, "errors": [],
    }
    assert all((out / name).is_file() for name in result["generated"])


def test_validator_internal_failure_is_not_hidden_or_written(tmp_path, monkeypatch):
    root = _fixture(tmp_path)

    def fail_validation(bundle):
        raise RuntimeError("validator internal failure")

    monkeypatch.setattr("hate.p0b_outputs._validate_qeg_bundle_schema", fail_validation)
    with pytest.raises(RuntimeError, match="validator internal failure"):
        export_qeg(root, tmp_path / "out")
    assert not (tmp_path / "out").exists()
