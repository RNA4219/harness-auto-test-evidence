from __future__ import annotations

import json
import shutil
from pathlib import Path

from hate.p0a import generate_p0a
from hate.p0b import export_qeg


ROOT = Path(__file__).resolve().parents[1]
P0A_MINIMAL_INPUT = ROOT / "fixtures" / "golden" / "p0a-minimal" / "input"
P0B_DIFF_RISK = ROOT / "fixtures" / "golden" / "p0b-qeg-minimal" / "input" / "diff-risk-test.json"


def test_p0a_computes_evidence_strength_from_history_and_stryker(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    out_dir = tmp_path / "p0a"
    shutil.copytree(P0A_MINIMAL_INPUT, input_dir)
    (input_dir / "evidence-strength-config.json").write_text(
        json.dumps({"recent_run_limit": 4}),
        encoding="utf-8",
    )
    (input_dir / "run-history.json").write_text(
        json.dumps(
            {
                "runs": [
                    {"tests": [{"test_id": "junit:tests/test_auth.py::test_login", "status": "passed"}]},
                    {"tests": [{"test_id": "junit:tests/test_auth.py::test_login", "status": "failed"}]},
                    {"tests": [{"test_id": "junit:tests/test_auth.py::test_login", "status": "passed"}]},
                ]
            }
        ),
        encoding="utf-8",
    )
    (input_dir / "mutation.json").write_text(
        json.dumps(
            {
                "mutants": [
                    {
                        "id": "mut-auth-killed",
                        "status": "Killed",
                        "sourceFilePath": "src/auth.py",
                        "location": {"start": {"line": 10}},
                        "mutatorName": "BooleanLiteral",
                        "coveredBy": ["junit:tests/test_auth.py::test_login"],
                        "killedBy": ["junit:tests/test_auth.py::test_login"],
                    },
                    {
                        "id": "mut-auth-survived",
                        "status": "Survived",
                        "sourceFilePath": "src/auth.py",
                        "location": {"start": {"line": 11}},
                        "mutatorName": "ConditionalExpression",
                        "coveredBy": ["junit:tests/test_auth.py::test_login"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = generate_p0a(input_dir, out_dir, source_version="strength-test")

    assert result["decision"] == "eligible"
    strength = _read_ndjson(out_dir / "HATE-evidence-strength.ndjson")
    auth = next(record["payload"] for record in strength if record["payload"]["test_id"] == "junit:tests/test_auth.py::test_login")
    assert auth["flake_score"] == 0.6667
    assert auth["mutation_score"] == 0.5
    assert auth["sample_size"] == 4
    assert {item["kind"] for item in auth["inputs"]} == {"run_history", "test_results", "mutation"}

    mutations = _read_ndjson(out_dir / "HATE-mutation.ndjson")
    assert [record["payload"]["mutation_id"] for record in mutations] == ["mut-auth-killed", "mut-auth-survived"]
    assert "C:/Users" not in (out_dir / "HATE-mutation.ndjson").read_text(encoding="utf-8")
    assert "C:\\Users" not in (out_dir / "HATE-mutation.ndjson").read_text(encoding="utf-8")


def test_p0a_records_unknown_evidence_strength_explicitly(tmp_path: Path) -> None:
    out_dir = tmp_path / "p0a"

    generate_p0a(P0A_MINIMAL_INPUT, out_dir, source_version="strength-unknown-test")

    strength = _read_ndjson(out_dir / "HATE-evidence-strength.ndjson")
    assert len(strength) == 2
    for record in strength:
        payload = record["payload"]
        assert payload["flake_score"] == "unknown"
        assert payload["mutation_score"] == "unknown"
        assert payload["sample_size"] == 1
        assert payload["inputs"] == [{"kind": "test_results", "sourceRef": "HATE-test-results.ndjson"}]


def test_p0b_exports_evidence_strength_into_qeg_bundle(tmp_path: Path) -> None:
    p0a_out = tmp_path / "p0a"
    fixture_dir = tmp_path / "fixture"
    qeg_out = tmp_path / "qeg"

    generate_p0a(P0A_MINIMAL_INPUT, p0a_out, source_version="strength-export-test")
    fixture_dir.mkdir()
    shutil.copytree(p0a_out, fixture_dir / "p0a")
    shutil.copy2(P0B_DIFF_RISK, fixture_dir / "diff-risk-test.json")

    result = export_qeg(fixture_dir, qeg_out)

    assert result["export_status"] == "success"
    bundle = _read_json(qeg_out / "qeg-bundle.json")
    strength_nodes = [node for node in bundle["nodes"] if node["kind"] == "evidence_strength"]
    assert len(strength_nodes) == 2
    assert all(node["data"]["flake_score"] == "unknown" for node in strength_nodes)
    assert any(edge["kind"] == "has_strength" for edge in bundle["edges"])
    assert any(item["kind"] == "HATE-evidence-strength" for item in bundle["metadata"]["inputArtifacts"])

    report = _read_json(qeg_out / "qeg-export-report.json")
    assert report["evidence_strength_distribution"]["total"] == 2
    assert report["evidence_strength_distribution"]["flake_unknown"] == 2

    evidence_map = _read_json(qeg_out / "evidence-map.json")
    assert len(evidence_map["evidence_strength"]) == 2
    assert len(evidence_map["links"]["has_strength"]) == 2


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_ndjson(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
