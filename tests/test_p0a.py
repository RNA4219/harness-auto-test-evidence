from __future__ import annotations

import json
import shutil
from pathlib import Path

from hate.p0a import PrecheckError, generate_p0a
from hate.p0a_support import _schema_validation_hits


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
    assert len(test_lines) == 2
    assert len(coverage_lines) == 2

    test_record = json.loads(test_lines[0])
    db_test_record = json.loads(test_lines[1])
    coverage_record = json.loads(coverage_lines[0])
    db_coverage_record = json.loads(coverage_lines[1])
    assert test_record["payload"]["canonical_test_id"] == "junit:tests/test_auth.py::test_login"
    assert db_test_record["payload"]["canonical_test_id"] == "junit:tests/test_db.py::test_connection"
    assert coverage_record["payload"]["file"] == "src/auth.py"
    assert coverage_record["payload"]["line_hits"] == {"10": 1, "11": 1, "20": 0}
    assert db_coverage_record["payload"]["file"] == "src/db.py"
    assert db_coverage_record["payload"]["line_hits"] == {"5": 1, "6": 1, "7": 1}
    audit = read_json(tmp_path / "record.json")
    assert all(ref.startswith("fixture:/") or ref.startswith("workspace:/") for ref in audit["payload"]["source_refs"])
    assert "C:/Users" not in json.dumps(audit)


def test_p0a_ingests_generic_ci_context(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "ci" / "generic" / "input"
    result = generate_p0a(fixture, tmp_path / "generic-ci-output", source_version="generic-ci-test")

    assert result["decision"] == "eligible"
    run = read_json(tmp_path / "generic-ci-output" / "HATE-run.json")
    assert run["payload"]["repository"] == "RNA4219/generic-sample"
    assert run["payload"]["workflow"] == "generic-ci.yml"
    assert run["payload"]["job"] == "linux-py310"
    assert run["payload"]["ci"] == {
        "provider": "generic-ci",
        "run_id": "generic-2001",
        "run_attempt": 2,
        "actor": "generic-runner",
        "ref": "refs/heads/feature/generic-ci",
    }

    audit = read_json(tmp_path / "generic-ci-output" / "record.json")
    assert any(ref.endswith("/ci-context.json") for ref in audit["payload"]["source_refs"])
    assert not any(ref.endswith("/github-context.json") for ref in audit["payload"]["source_refs"])


def test_p0a_ingests_generic_ci_context_file_name_alias(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "ci" / "generic" / "generic-file-name"
    result = generate_p0a(fixture, tmp_path / "generic-ci-alias-output", source_version="generic-ci-test")

    assert result["decision"] == "eligible"
    run = read_json(tmp_path / "generic-ci-alias-output" / "HATE-run.json")
    assert run["payload"]["ci"]["provider"] == "generic-ci"
    assert run["payload"]["ci"]["run_id"] == "generic-2003"
    test_lines = (tmp_path / "generic-ci-alias-output" / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(test_lines) == 1


def test_p0a_generic_ci_missing_required_context_field_fails(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "ci" / "generic" / "missing-required"

    try:
        generate_p0a(fixture, tmp_path / "generic-ci-missing-output", source_version="generic-ci-test")
    except PrecheckError as exc:
        assert exc.exit_code == 1
        assert "ci-context.json missing fields: job" in str(exc)
    else:
        raise AssertionError("expected PrecheckError for missing generic CI context field")


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


def test_p0a_hard_dq_when_profile_control_dq_triggers_fire(tmp_path: Path) -> None:
    input_dir = tmp_path / "dq-control-input"
    shutil.copytree(FIXTURE_INPUT, input_dir)
    (input_dir / "dq-control.json").write_text(
        json.dumps(
            {
                "unresolved_flaky_over_threshold": True,
                "high_risk_without_execution": True,
                "unresolved_high_critical_sarif": True,
            }
        ),
        encoding="utf-8",
    )

    try:
        generate_p0a(input_dir, tmp_path / "dq-control-output", source_version="test")
    except PrecheckError as exc:
        assert exc.exit_code == 2
        assert exc.decision is not None
        codes = {hit["code"] for hit in exc.decision["payload"]["dq_hits"]}
        assert {"HATE-DQ-005", "HATE-DQ-007", "HATE-DQ-010"}.issubset(codes)
    else:
        raise AssertionError("expected PrecheckError")


def test_p0a_ingests_cobertura_jacoco_and_sarif(tmp_path: Path) -> None:
    input_dir = tmp_path / "adapter-input"
    shutil.copytree(FIXTURE_INPUT, input_dir)
    (input_dir / "cobertura.xml").write_text(
        """<?xml version="1.0"?>
<coverage>
  <packages><package name="pkg"><classes>
    <class name="Auth" filename="src/auth_extra.py">
      <lines><line number="30" hits="1"/><line number="31" hits="0"/></lines>
    </class>
  </classes></package></packages>
</coverage>
""",
        encoding="utf-8",
    )
    (input_dir / "jacoco.xml").write_text(
        """<?xml version="1.0"?>
<report name="jacoco">
  <package name="src"><sourcefile name="service.py">
    <line nr="7" mi="0" ci="1" mb="0" cb="0"/>
    <line nr="8" mi="1" ci="0" mb="1" cb="0"/>
  </sourcefile></package>
</report>
""",
        encoding="utf-8",
    )
    (input_dir / "results.sarif").write_text(
        json.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {"driver": {"name": "semgrep", "rules": [{"id": "WARN001", "name": "Warning Rule"}]}},
                        "results": [
                            {
                                "ruleId": "WARN001",
                                "level": "warning",
                                "message": {"text": "non-blocking finding"},
                                "locations": [
                                    {
                                        "physicalLocation": {
                                            "artifactLocation": {"uri": "src/auth.py"},
                                            "region": {"startLine": 10},
                                        }
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = generate_p0a(input_dir, tmp_path / "adapter-output", source_version="test")

    assert result["decision"] == "eligible"
    assert "HATE-static.sarif" in result["generated"]
    coverage_lines = (tmp_path / "adapter-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8").splitlines()
    coverage = [json.loads(line)["payload"] for line in coverage_lines]
    assert any(record["format"] == "cobertura" and record["file"] == "src/auth_extra.py" for record in coverage)
    assert any(record["format"] == "jacoco" and record["file"] == "src/service.py" for record in coverage)
    sarif = read_json(tmp_path / "adapter-output" / "HATE-static.sarif")
    assert sarif["version"] == "2.1.0"


def test_p0a_cobertura_adapter_hardening(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "coverage" / "cobertura" / "input"
    result = generate_p0a(fixture, tmp_path / "cobertura-output", source_version="test")

    assert result["decision"] == "eligible"
    coverage_lines = (tmp_path / "cobertura-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8").splitlines()
    coverage = [json.loads(line)["payload"] for line in coverage_lines]
    cobertura = [record for record in coverage if record["format"] == "cobertura"]
    assert {record["file"] for record in cobertura} == {"src/auth/service.py", "src/auth/TokenStore"}
    assert cobertura[0]["contexts"] == [{"test_id": "junit:tests/test_auth.py::test_login"}]


def test_p0a_cobertura_partial_is_eligible(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "coverage" / "cobertura" / "partial"
    result = generate_p0a(fixture, tmp_path / "cobertura-partial-output", source_version="test")

    assert result["decision"] == "eligible"
    coverage_lines = (tmp_path / "cobertura-partial-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8").splitlines()
    coverage = [json.loads(line)["payload"] for line in coverage_lines]
    assert [record["file"] for record in coverage if record["format"] == "cobertura"] == ["src/partial/useful.py"]


def test_p0a_cobertura_windows_path_is_public_safe(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "coverage" / "cobertura" / "windows-path"
    result = generate_p0a(fixture, tmp_path / "cobertura-windows-output", source_version="test")

    assert result["decision"] == "eligible"
    output_text = (tmp_path / "cobertura-windows-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8")
    assert "C:/Users" not in output_text
    assert "C:\\Users" not in output_text
    coverage = [json.loads(line)["payload"] for line in output_text.splitlines()]
    assert any(record["format"] == "cobertura" and record["file"] == "src/win/path.py" for record in coverage)


def test_p0a_cobertura_malformed_is_hard_dq(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "coverage" / "cobertura" / "malformed"
    try:
        generate_p0a(fixture, tmp_path / "cobertura-malformed-output", source_version="test")
    except PrecheckError as exc:
        assert exc.exit_code == 2
        assert exc.decision is not None
        hits = exc.decision["payload"]["dq_hits"]
        assert any(hit["code"] == "HATE-DQ-002" and hit["source_ref"] == "cobertura.xml" for hit in hits)
    else:
        raise AssertionError("expected PrecheckError for malformed Cobertura XML")


def test_p0a_jacoco_adapter_hardening(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "coverage" / "jacoco" / "input"
    result = generate_p0a(fixture, tmp_path / "jacoco-output", source_version="test")

    assert result["decision"] == "eligible"
    coverage_lines = (tmp_path / "jacoco-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8").splitlines()
    coverage = [json.loads(line)["payload"] for line in coverage_lines]
    jacoco = [record for record in coverage if record["format"] == "jacoco"]
    assert len(jacoco) == 1
    assert jacoco[0]["file"] == "com/example/auth/AuthService.java"
    assert jacoco[0]["line_hits"] == {"12": 1, "13": 0}
    assert jacoco[0]["branch_hits"] == [{"line": 13, "block": 0, "branch": 1, "hits": 0}]


def test_p0a_jacoco_partial_is_eligible(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "coverage" / "jacoco" / "partial"
    result = generate_p0a(fixture, tmp_path / "jacoco-partial-output", source_version="test")

    assert result["decision"] == "eligible"
    coverage_lines = (tmp_path / "jacoco-partial-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8").splitlines()
    coverage = [json.loads(line)["payload"] for line in coverage_lines]
    assert [record["file"] for record in coverage if record["format"] == "jacoco"] == ["com/example/partial/Useful.java"]


def test_p0a_jacoco_windows_path_is_public_safe(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "coverage" / "jacoco" / "windows-path"
    result = generate_p0a(fixture, tmp_path / "jacoco-windows-output", source_version="test")

    assert result["decision"] == "eligible"
    output_text = (tmp_path / "jacoco-windows-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8")
    assert "C:/Users" not in output_text
    assert "C:\\Users" not in output_text
    coverage = [json.loads(line)["payload"] for line in output_text.splitlines()]
    assert any(record["format"] == "jacoco" and record["file"] == "src/main/java/com/example/win/WinPath.java" for record in coverage)


def test_p0a_jacoco_malformed_is_hard_dq(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "coverage" / "jacoco" / "malformed"
    try:
        generate_p0a(fixture, tmp_path / "jacoco-malformed-output", source_version="test")
    except PrecheckError as exc:
        assert exc.exit_code == 2
        assert exc.decision is not None
        hits = exc.decision["payload"]["dq_hits"]
        assert any(hit["code"] == "HATE-DQ-002" and hit["source_ref"] == "jacoco.xml" for hit in hits)
    else:
        raise AssertionError("expected PrecheckError for malformed JaCoCo XML")


def test_p0a_artifact_safe_fixture_has_stable_security_checks(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "artifacts" / "safe"
    result = generate_p0a(fixture, tmp_path / "artifact-safe-output", source_version="test")

    assert result["decision"] == "eligible"
    manifest = read_json(tmp_path / "artifact-safe-output" / "artifact-manifest.json")
    artifact = manifest["artifacts"][0]
    assert artifact["artifact_id"] == "artifact-report"
    assert artifact["safe_for_summary"] is True
    assert artifact["public_exposure"] == "summary"
    assert artifact["security_checks"]["path_exists"] == "pass"
    assert artifact["security_checks"]["secret_scan"] == "pass"
    assert artifact["security_checks"]["external_url_scan"] == "pass"
    assert artifact["security_checks"]["path_traversal_scan"] == "pass"
    assert artifact["security_checks"]["symlink_scan"] == "pass"
    quarantine = read_json(tmp_path / "artifact-safe-output" / "quarantine-report.json")
    assert quarantine["quarantined_artifacts"] == []


def test_p0a_artifact_secret_is_quarantined_and_summary_safe(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "artifacts" / "secret"
    result = generate_p0a(fixture, tmp_path / "artifact-secret-output", source_version="test")

    assert result["decision"] == "eligible"
    manifest = read_json(tmp_path / "artifact-secret-output" / "artifact-manifest.json")
    artifact = manifest["artifacts"][0]
    assert artifact["safe_for_summary"] is False
    assert artifact["public_exposure"] == "none"
    assert artifact["security_checks"]["secret_scan"] == "fail"
    quarantine = read_json(tmp_path / "artifact-secret-output" / "quarantine-report.json")
    assert quarantine["quarantined_artifacts"][0]["reasons"] == ["secret"]
    summary = (tmp_path / "artifact-secret-output" / "summary.md").read_text(encoding="utf-8")
    assert "abcdefghijklmnop1234567890" not in summary
    assert "api_key" not in summary


def test_p0a_artifact_external_url_is_quarantined_and_redacted(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "artifacts" / "external-url"
    result = generate_p0a(fixture, tmp_path / "artifact-url-output", source_version="test")

    assert result["decision"] == "eligible"
    manifest_text = (tmp_path / "artifact-url-output" / "artifact-manifest.json").read_text(encoding="utf-8")
    assert "https://example.invalid/private/trace.zip" not in manifest_text
    manifest = json.loads(manifest_text)
    artifact = manifest["artifacts"][0]
    assert artifact["path"] == "redacted/external-url/artifact-external-trace"
    assert artifact["safe_for_summary"] is False
    assert artifact["security_checks"]["external_url_scan"] == "fail"
    quarantine = read_json(tmp_path / "artifact-url-output" / "quarantine-report.json")
    assert set(quarantine["quarantined_artifacts"][0]["reasons"]) == {"external_url", "unsafe_archive"}
    summary = (tmp_path / "artifact-url-output" / "summary.md").read_text(encoding="utf-8")
    assert "https://example.invalid" not in summary


def test_p0a_artifact_path_traversal_is_quarantined_and_redacted(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "artifacts" / "path-traversal"
    result = generate_p0a(fixture, tmp_path / "artifact-traversal-output", source_version="test")

    assert result["decision"] == "eligible"
    manifest_text = (tmp_path / "artifact-traversal-output" / "artifact-manifest.json").read_text(encoding="utf-8")
    assert "../private/trace.zip" not in manifest_text
    manifest = json.loads(manifest_text)
    artifact = manifest["artifacts"][0]
    assert artifact["path"] == "redacted/path-traversal/artifact-traversal"
    assert artifact["safe_for_summary"] is False
    assert artifact["security_checks"]["path_traversal_scan"] == "fail"
    quarantine = read_json(tmp_path / "artifact-traversal-output" / "quarantine-report.json")
    assert set(quarantine["quarantined_artifacts"][0]["reasons"]) == {"path_traversal", "unsafe_archive"}
    summary = (tmp_path / "artifact-traversal-output" / "summary.md").read_text(encoding="utf-8")
    assert "../private" not in summary


def test_p0a_artifact_symlink_fixture_is_quarantined(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "artifacts" / "symlink"
    result = generate_p0a(fixture, tmp_path / "artifact-symlink-output", source_version="test")

    assert result["decision"] == "eligible"
    manifest = read_json(tmp_path / "artifact-symlink-output" / "artifact-manifest.json")
    artifact = next(item for item in manifest["artifacts"] if item["artifact_id"] == "artifact-symlink-trace")
    assert artifact["path"] == "redacted/symlink/artifact-symlink-trace"
    assert artifact["safe_for_summary"] is False
    assert artifact["security_checks"]["symlink_scan"] == "fail"
    quarantine = read_json(tmp_path / "artifact-symlink-output" / "quarantine-report.json")
    assert quarantine["quarantined_artifacts"][0]["reasons"] == ["symlink"]


def test_p0a_artifact_archive_is_quarantined(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "artifacts" / "archive"
    result = generate_p0a(fixture, tmp_path / "artifact-archive-output", source_version="test")

    assert result["decision"] == "eligible"
    manifest = read_json(tmp_path / "artifact-archive-output" / "artifact-manifest.json")
    artifact = manifest["artifacts"][0]
    assert artifact["kind"] == "trace"
    assert artifact["safe_for_summary"] is False
    assert artifact["security_checks"]["archive_scan"] == "fail"
    quarantine = read_json(tmp_path / "artifact-archive-output" / "quarantine-report.json")
    assert quarantine["quarantined_artifacts"][0]["reasons"] == ["unsafe_archive"]


def test_p0a_schema_validation_accepts_unknown_fields_per_registry_policy(tmp_path: Path) -> None:
    result = generate_p0a(FIXTURE_INPUT, tmp_path / "schema-valid-output", source_version="test")

    assert result["decision"] == "eligible"
    run_record = read_json(tmp_path / "schema-valid-output" / "HATE-run.json")
    run_record["payload"]["unknown_preserved_field"] = "kept-for-forward-compat"
    assert _schema_validation_hits([run_record]) == []


def test_p0a_schema_validation_invalid_decision_enum_is_dq_015(tmp_path: Path) -> None:
    generate_p0a(FIXTURE_INPUT, tmp_path / "schema-invalid-decision-output", source_version="test")
    precheck = read_json(tmp_path / "schema-invalid-decision-output" / "precheck-decision.json")
    precheck["payload"]["decision"] = "go"

    hits = _schema_validation_hits([precheck])

    assert any(hit["code"] == "HATE-DQ-015" and "decision" in hit["message"] for hit in hits)


def test_p0a_schema_validation_missing_required_envelope_field_is_dq_015(tmp_path: Path) -> None:
    generate_p0a(FIXTURE_INPUT, tmp_path / "schema-missing-field-output", source_version="test")
    run_record = read_json(tmp_path / "schema-missing-field-output" / "HATE-run.json")
    del run_record["record_id"]

    hits = _schema_validation_hits([run_record])

    assert any(hit["code"] == "HATE-DQ-015" and "record_id is required" in hit["message"] for hit in hits)


def test_p0a_default_profile_preserves_current_behavior(tmp_path: Path) -> None:
    result = generate_p0a(FIXTURE_INPUT, tmp_path / "profile-default-output", source_version="test", profile="default")

    assert result["decision"] == "eligible"
    profile_report = read_json(tmp_path / "profile-default-output" / "profile-report.json")
    assert profile_report["profile"] == "default"
    assert profile_report["qeg_gate_policy"] is False
    assert profile_report["decision_impact"]["hard_dq_codes"] == []


def test_p0a_strict_profile_marks_unsafe_artifact_as_soft_gap(tmp_path: Path) -> None:
    fixture = tmp_path / "strict-fixture"
    shutil.copytree(FIXTURE_INPUT, fixture)
    artifact_dir = fixture / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    (artifact_dir / "secret-log.txt").write_text('api_key = "abcdefghijklmnop1234567890"', encoding="utf-8")
    result = generate_p0a(fixture, tmp_path / "profile-strict-output", source_version="test", profile="strict")

    assert result["decision"] == "conditional"
    precheck = read_json(tmp_path / "profile-strict-output" / "precheck-decision.json")
    assert precheck["payload"]["exit_code"] == 0
    assert precheck["payload"]["soft_gaps"][0]["gap_id"] == "unsafe_artifact_profile_gap"
    profile_report = read_json(tmp_path / "profile-strict-output" / "profile-report.json")
    assert profile_report["profile"] == "strict"
    assert profile_report["inherits"] == ["default", "strict"]


def test_p0a_release_profile_rejects_unsafe_artifacts(tmp_path: Path) -> None:
    fixture = tmp_path / "release-fixture"
    shutil.copytree(FIXTURE_INPUT, fixture)
    artifact_dir = fixture / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    (artifact_dir / "secret-log.txt").write_text('api_key = "abcdefghijklmnop1234567890"', encoding="utf-8")
    try:
        generate_p0a(fixture, tmp_path / "profile-release-output", source_version="test", profile="release")
    except PrecheckError as exc:
        assert exc.exit_code == 2
        assert exc.decision is not None
        codes = [hit["code"] for hit in exc.decision["payload"]["dq_hits"]]
        assert "HATE-DQ-018" in codes
        profile_report = read_json(tmp_path / "profile-release-output" / "profile-report.json")
        assert profile_report["profile"] == "release"
        assert profile_report["qeg_gate_policy"] is False
    else:
        raise AssertionError("expected release profile to reject unsafe artifact")


def test_p0a_experimental_profile_observes_without_dq(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "adapters" / "artifacts" / "secret"
    result = generate_p0a(fixture, tmp_path / "profile-experimental-output", source_version="test", profile="experimental")

    assert result["decision"] == "eligible"
    precheck = read_json(tmp_path / "profile-experimental-output" / "precheck-decision.json")
    assert precheck["payload"]["dq_hits"] == []
    assert precheck["payload"]["soft_gaps"] == []


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


def test_p0a_ingests_pytest_json_report(tmp_path: Path) -> None:
    pytest_fixture = ROOT / "fixtures" / "adapters" / "test-results" / "pytest" / "input"
    result = generate_p0a(pytest_fixture, tmp_path / "pytest-output", source_version="pytest-test")

    assert result["decision"] == "eligible"
    test_lines = (tmp_path / "pytest-output" / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()
    pytest_records = [json.loads(line) for line in test_lines]

    # Should have pytest test records
    pytest_results = [r for r in pytest_records if r["payload"]["framework"] == "pytest"]
    assert len(pytest_results) >= 2

    # Check for flaky and retry attributes
    flaky_record = next((r for r in pytest_results if r["payload"].get("flaky")), None)
    assert flaky_record is not None
    assert flaky_record["payload"]["status"] == "passed"

    # Check retry_index exists
    retry_record = next((r for r in pytest_results if r["payload"].get("retry_index")), None)
    assert retry_record is not None


def test_p0a_ingests_vitest_json_report(tmp_path: Path) -> None:
    vitest_fixture = ROOT / "fixtures" / "adapters" / "test-results" / "vitest" / "input"
    result = generate_p0a(vitest_fixture, tmp_path / "vitest-output", source_version="vitest-test")

    assert result["decision"] == "eligible"
    test_lines = (tmp_path / "vitest-output" / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()
    vitest_records = [json.loads(line) for line in test_lines]

    vitest_results = [r for r in vitest_records if r["payload"]["framework"] == "vitest"]
    assert len(vitest_results) >= 2

    # Check for flaky attribute
    flaky_record = next((r for r in vitest_results if r["payload"].get("flaky")), None)
    assert flaky_record is not None


def test_p0a_ingests_jest_json_report(tmp_path: Path) -> None:
    jest_fixture = ROOT / "fixtures" / "adapters" / "test-results" / "jest" / "input"
    result = generate_p0a(jest_fixture, tmp_path / "jest-output", source_version="jest-test")

    assert result["decision"] == "eligible"
    test_lines = (tmp_path / "jest-output" / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()
    jest_records = [json.loads(line) for line in test_lines]

    jest_results = [r for r in jest_records if r["payload"]["framework"] == "jest"]
    assert len(jest_results) >= 2

    # Check for snapshot failure marker
    snapshot_record = next((r for r in jest_results if r["payload"].get("failure_type") == "snapshot_mismatch"), None)
    assert snapshot_record is not None


def test_p0a_ingests_coveragepy_with_contexts(tmp_path: Path) -> None:
    coveragepy_fixture = ROOT / "fixtures" / "adapters" / "coveragepy" / "input"
    result = generate_p0a(coveragepy_fixture, tmp_path / "coveragepy-output", source_version="coveragepy-test")

    assert result["decision"] == "eligible"
    coverage_lines = (tmp_path / "coveragepy-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8").splitlines()
    coverage_records = [json.loads(line) for line in coverage_lines]

    coveragepy_results = [r for r in coverage_records if r["payload"]["format"] == "coverage.py"]
    assert len(coveragepy_results) >= 1

    # Check contexts are object array with test_id
    for record in coveragepy_results:
        contexts = record["payload"]["contexts"]
        assert isinstance(contexts, list)
        for ctx in contexts:
            assert isinstance(ctx, dict)
            assert "test_id" in ctx
            assert isinstance(ctx["test_id"], str)


def test_p0a_coveragepy_show_contexts_false_is_hard_dq(tmp_path: Path) -> None:
    """coverage.json with show_contexts=false is hard DQ (HATE-DQ-002) in default profile."""
    missing_context_fixture = ROOT / "fixtures" / "adapters" / "coveragepy" / "missing-context"
    try:
        generate_p0a(missing_context_fixture, tmp_path / "missing-context-output", source_version="test")
    except PrecheckError as exc:
        assert exc.exit_code == 2
        codes = [hit["code"] for hit in exc.decision["payload"]["dq_hits"]]
        assert "HATE-DQ-002" in codes
        # Verify the DQ message mentions show_contexts
        messages = [hit["message"] for hit in exc.decision["payload"]["dq_hits"]]
        assert any("show_contexts" in msg for msg in messages)
    else:
        raise AssertionError("expected PrecheckError for show_contexts=false")


def test_p0a_coveragepy_partial_contexts_is_eligible(tmp_path: Path) -> None:
    """coverage.json with show_contexts=true and partial/missing contexts per line is eligible."""
    partial_fixture = ROOT / "fixtures" / "adapters" / "coveragepy" / "partial"
    result = generate_p0a(partial_fixture, tmp_path / "partial-output", source_version="test")

    assert result["decision"] == "eligible"
    coverage_lines = (tmp_path / "partial-output" / "HATE-coverage.ndjson").read_text(encoding="utf-8").splitlines()
    coverage_records = [json.loads(line) for line in coverage_lines]

    coveragepy_results = [r for r in coverage_records if r["payload"]["format"] == "coverage.py"]
    assert len(coveragepy_results) >= 1

    # Verify contexts extracted from available lines
    contexts = coveragepy_results[0]["payload"]["contexts"]
    assert isinstance(contexts, list)
    # Should have test_ids from lines 10, 11, 21 (line 20 empty, line 30 null)
    test_ids = [ctx["test_id"] for ctx in contexts]
    assert "tests/unit/test_parser.py::test_parse_valid" in test_ids
    assert "tests/unit/test_parser.py::test_parse_edge_cases" in test_ids


def test_p0a_pytest_malformed_raises_dq(tmp_path: Path) -> None:
    malformed_fixture = ROOT / "fixtures" / "adapters" / "test-results" / "pytest" / "malformed"
    input_dir = tmp_path / "pytest-malformed-input"
    shutil.copytree(malformed_fixture, input_dir)
    # Add required github-context.json
    shutil.copy2(ROOT / "fixtures" / "golden" / "p0a-minimal" / "input" / "github-context.json", input_dir)

    try:
        generate_p0a(input_dir, tmp_path / "pytest-malformed-output", source_version="test")
    except PrecheckError as exc:
        assert exc.exit_code == 2
        codes = [hit["code"] for hit in exc.decision["payload"]["dq_hits"]]
        assert "HATE-DQ-002" in codes
    else:
        raise AssertionError("expected PrecheckError for malformed pytest")


def test_p0a_pytest_without_junit_is_eligible(tmp_path: Path) -> None:
    """pytest-report.json alone (no junit.xml) should be eligible."""
    pytest_fixture = ROOT / "fixtures" / "adapters" / "test-results" / "pytest" / "no-junit"
    result = generate_p0a(pytest_fixture, tmp_path / "pytest-no-junit-output", source_version="pytest-test")

    assert result["decision"] == "eligible"
    test_lines = (tmp_path / "pytest-no-junit-output" / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()
    pytest_records = [json.loads(line) for line in test_lines]

    pytest_results = [r for r in pytest_records if r["payload"]["framework"] == "pytest"]
    assert len(pytest_results) >= 2


def test_p0a_vitest_without_junit_is_eligible(tmp_path: Path) -> None:
    """vitest-report.json alone (no junit.xml) should be eligible."""
    vitest_fixture = ROOT / "fixtures" / "adapters" / "test-results" / "vitest" / "no-junit"
    result = generate_p0a(vitest_fixture, tmp_path / "vitest-no-junit-output", source_version="vitest-test")

    assert result["decision"] == "eligible"
    test_lines = (tmp_path / "vitest-no-junit-output" / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()
    vitest_records = [json.loads(line) for line in test_lines]

    vitest_results = [r for r in vitest_records if r["payload"]["framework"] == "vitest"]
    assert len(vitest_results) >= 2


def test_p0a_jest_without_junit_is_eligible(tmp_path: Path) -> None:
    """jest-report.json alone (no junit.xml) should be eligible."""
    jest_fixture = ROOT / "fixtures" / "adapters" / "test-results" / "jest" / "no-junit"
    result = generate_p0a(jest_fixture, tmp_path / "jest-no-junit-output", source_version="jest-test")

    assert result["decision"] == "eligible"
    test_lines = (tmp_path / "jest-no-junit-output" / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()
    jest_records = [json.loads(line) for line in test_lines]

    jest_results = [r for r in jest_records if r["payload"]["framework"] == "jest"]
    assert len(jest_results) >= 2
