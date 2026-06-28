from __future__ import annotations

import json
from pathlib import Path

from hate.p0a import PrecheckError, generate_p0a


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INPUT = ROOT / "fixtures" / "golden" / "p0a-minimal" / "input"
DQ_ROOT = ROOT / "fixtures" / "golden" / "p0a-minimal"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p0a_generates_minimal_evidence(tmp_path: Path) -> None:
    result = generate_p0a(FIXTURE_INPUT, tmp_path, source_version="test")

    assert result["decision"] == "eligible"
    assert (tmp_path / "HATE-run.json").exists()
    assert (tmp_path / "HATE-test-results.ndjson").exists()
    assert (tmp_path / "HATE-coverage.ndjson").exists()
    assert (tmp_path / "artifact-manifest.json").exists()
    assert (tmp_path / "precheck-decision.json").exists()
    assert (tmp_path / "record.json").exists()
    assert (tmp_path / "summary.md").exists()

    precheck = read_json(tmp_path / "precheck-decision.json")
    assert precheck["payload"]["decision"] == "eligible"
    assert precheck["payload"]["qeg_export_phase"] == "P0b"

    test_lines = (tmp_path / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()
    coverage_lines = (tmp_path / "HATE-coverage.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(test_lines) == 1
    assert len(coverage_lines) == 1

    test_record = json.loads(test_lines[0])
    coverage_record = json.loads(coverage_lines[0])
    assert test_record["payload"]["canonical_test_id"] == "junit:tests/test_auth.py::test_login"
    assert coverage_record["payload"]["file"] == "src/auth.py"
    assert coverage_record["payload"]["line_hits"] == {"10": 1, "11": 1, "20": 0}


def test_p0a_hard_dq_when_commit_sha_missing(tmp_path: Path) -> None:
    assert_dq_fixture("dq-01-sha-missing", "HATE-DQ-001", tmp_path)


def test_p0a_hard_dq_when_junit_is_malformed(tmp_path: Path) -> None:
    assert_dq_fixture("dq-02-junit-malformed", "HATE-DQ-002", tmp_path)


def test_p0a_hard_dq_when_artifact_ref_is_missing(tmp_path: Path) -> None:
    assert_dq_fixture("dq-03-artifact-missing", "HATE-DQ-003", tmp_path)


def test_p0a_hard_dq_when_coverage_exists_without_tests(tmp_path: Path) -> None:
    assert_dq_fixture("dq-08-coverage-only", "HATE-DQ-008", tmp_path)


def test_p0a_hard_dq_when_record_generation_is_blocked(tmp_path: Path) -> None:
    assert_dq_fixture("dq-15-record-missing", "HATE-DQ-015", tmp_path)


def assert_dq_fixture(fixture_name: str, expected_code: str, tmp_path: Path) -> None:
    input_dir = DQ_ROOT / fixture_name
    try:
        generate_p0a(input_dir, tmp_path / fixture_name, source_version="test")
    except PrecheckError as exc:
        assert exc.exit_code == 2
        assert exc.decision is not None
        assert exc.decision["payload"]["decision"] == "hard_dq"
        codes = [hit["code"] for hit in exc.decision["payload"]["dq_hits"]]
        assert expected_code in codes
    else:
        raise AssertionError("expected PrecheckError")
