"""Tests for HATE-GAP-012 real repository evaluation reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from hate.cli import main
from hate.evaluation import build_real_repo_evaluation_report, evaluate_real_repo_fixture
from hate.evaluation import real_repo
from hate.evaluation.real_repo import run_real_repo_roster


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "evaluation" / "real-repo"
PLATFORM_EVALUATION_FIXTURE_ROOT = ROOT / "fixtures" / "platform" / "evaluation"
SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-evaluation-report.schema.json"
RUN_SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-evaluation-run-report.schema.json"
ROSTER_V2_SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-roster-v2.schema.json"
RUN_HISTORY_SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-run-history-entry.schema.json"
HISTORY_INGEST_SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-history-ingest-report.schema.json"
HISTORY_QUERY_SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-history-query-report.schema.json"
SCORE_SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-score-report.schema.json"
BASELINE_EVENT_SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-baseline-event.schema.json"
BASELINE_GOVERNANCE_SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-baseline-governance-report.schema.json"
REGISTRY_PATH = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name / "fixture.json").read_text(encoding="utf-8"))


def test_contract_fixture_paths_exist() -> None:
    for name in ["baseline-pass", "regression-detected", "timeout-recorded", "subset-labeled"]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()
    for name in [
        "roster-v2-valid",
        "roster-v2-invalid-ownership",
        "history-store-ingest",
        "history-store-query-filter",
        "runtime-drift",
        "new-failure-kind",
        "external-repo-hold",
        "score-model-balanced",
        "score-model-penalty-cap",
        "redacted-deterministic-output",
        "timeout-cleanup",
    ]:
        assert (PLATFORM_EVALUATION_FIXTURE_ROOT / name / "fixture.json").exists()


def test_roster_v2_fixture_contracts() -> None:
    valid = json.loads((PLATFORM_EVALUATION_FIXTURE_ROOT / "roster-v2-valid" / "fixture.json").read_text(encoding="utf-8"))
    invalid = json.loads((PLATFORM_EVALUATION_FIXTURE_ROOT / "roster-v2-invalid-ownership" / "fixture.json").read_text(encoding="utf-8"))

    entries = real_repo._normalize_roster_entries(valid["input"])
    assert len(entries) == valid["expected"]["normalized_entries"]
    assert entries[0]["ownership_scope"] == valid["expected"]["ownership_scope"]
    assert entries[0]["suite_id"] == valid["expected"]["suite_id"]

    try:
        real_repo._normalize_roster_entries(invalid["input"])
    except ValueError as exc:
        assert invalid["expected"]["error_contains"] in str(exc)
    else:
        raise AssertionError("invalid ownership fixture must be rejected")


def test_baseline_pass_fixture_is_pass() -> None:
    fixture = load_fixture("baseline-pass")

    result = evaluate_real_repo_fixture(fixture)
    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert result["finding_code"] == ""
    assert report["overall_status"] == "pass"
    assert report["timeout_ms"] == 900000
    assert report["summary"]["regression_detected"] is False


def test_decision_downgrade_detects_regression() -> None:
    fixture = load_fixture("regression-detected")

    result = evaluate_real_repo_fixture(fixture)
    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert result["finding_code"] == fixture["expected"]["finding_code"]
    assert report["overall_status"] == "hold"
    assert report["findings"][0]["code"] == "real_repo_regression_detected"


def test_timeout_is_retained_as_hold_evidence() -> None:
    fixture = load_fixture("timeout-recorded")

    result = evaluate_real_repo_fixture(fixture)
    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert result["finding_code"] == fixture["expected"]["finding_code"]
    assert report["timeout_recorded"] is True
    assert report["summary"]["timeout_recorded"] is True


def test_subset_label_is_visible_and_does_not_prove_full_suite() -> None:
    fixture = load_fixture("subset-labeled")

    result = evaluate_real_repo_fixture(fixture)
    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert report["subset"]["is_subset"] is True
    assert report["subset"]["limitation_visible"] is True
    assert report["subset"]["proves_full_suite"] is False


def test_parser_failure_record_count_collapse_runtime_and_unsafe_artifact_hold() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "stress-repo",
        "baseline_decision": "eligible",
        "current_decision": "eligible",
        "baseline_record_count": 100,
        "current_record_count": 10,
        "parser_status": "failed",
        "runtime_ms": 901000,
        "runtime_budget_ms": 900000,
        "unsafe_artifact_findings": 1,
    })

    codes = {finding["code"] for finding in report["findings"]}
    assert report["overall_status"] == "hold"
    assert "real_repo_parser_failure" in codes
    assert "real_repo_record_count_collapse" in codes
    assert "real_repo_runtime_budget_exceeded" in codes
    assert "real_repo_unsafe_artifact_finding" in codes


def test_command_failure_is_hold_evidence() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "failing-repo",
        "baseline_decision": "pass",
        "current_decision": "hold",
        "command_exit_code": 1,
    })

    codes = {finding["code"] for finding in report["findings"]}
    assert report["overall_status"] == "hold"
    assert "real_repo_command_failed" in codes


def test_dependency_network_blocked_is_classified() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "network-blocked-repo",
        "baseline_decision": "pass",
        "current_decision": "hold",
        "command_exit_code": 1,
        "failure_kind": "dependency_network_blocked",
    })

    codes = {finding["code"] for finding in report["findings"]}
    assert "real_repo_command_failed" in codes
    assert "real_repo_dependency_network_blocked" in codes


def test_unlabeled_subset_is_hold() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "subset-repo",
        "baseline_decision": "eligible",
        "current_decision": "eligible",
        "subset": True,
    })

    assert report["overall_status"] == "hold"
    assert report["findings"][0]["code"] == "real_repo_subset_unlabeled"


def test_real_repo_regression_engine_detects_runtime_drift() -> None:
    fixture = json.loads((PLATFORM_EVALUATION_FIXTURE_ROOT / "runtime-drift" / "fixture.json").read_text(encoding="utf-8"))

    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["expected"]["regression_class"] in report["summary"]["regression_classes"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}
    assert report["regressions"][0]["evidence"]["baseline_runtime_ms"] == 1000


def test_real_repo_regression_engine_detects_new_failure_kind() -> None:
    fixture = json.loads((PLATFORM_EVALUATION_FIXTURE_ROOT / "new-failure-kind" / "fixture.json").read_text(encoding="utf-8"))

    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["expected"]["regression_class"] in report["summary"]["regression_classes"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}
    assert report["regressions"][0]["evidence"]["current_failure_kind"] == "dependency_network_blocked"


def test_real_repo_external_hold_is_not_implementation_failure() -> None:
    fixture = json.loads((PLATFORM_EVALUATION_FIXTURE_ROOT / "external-repo-hold" / "fixture.json").read_text(encoding="utf-8"))

    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["expected"]["regression_class"] in report["summary"]["regression_classes"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}
    assert report["external_hold"]["detected"] is True
    assert report["external_hold"]["implementation_failure"] is fixture["expected"]["implementation_failure"]


def test_real_repo_owned_failure_is_not_external_hold() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "owned-repo",
        "ownership_scope": "owned",
        "baseline_decision": "pass",
        "current_decision": "hold",
        "failure_kind": "dependency_network_blocked",
        "command_exit_code": 1,
    })

    assert report["overall_status"] == "hold"
    assert "external_hold_detected" not in report["summary"]["regression_classes"]
    assert report["external_hold"]["detected"] is False


def test_schema_and_registry_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    run_schema = json.loads(RUN_SCHEMA_PATH.read_text(encoding="utf-8"))
    roster_v2_schema = json.loads(ROSTER_V2_SCHEMA_PATH.read_text(encoding="utf-8"))
    run_history_schema = json.loads(RUN_HISTORY_SCHEMA_PATH.read_text(encoding="utf-8"))
    history_ingest_schema = json.loads(HISTORY_INGEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    history_query_schema = json.loads(HISTORY_QUERY_SCHEMA_PATH.read_text(encoding="utf-8"))
    score_schema = json.loads(SCORE_SCHEMA_PATH.read_text(encoding="utf-8"))
    baseline_event_schema = json.loads(BASELINE_EVENT_SCHEMA_PATH.read_text(encoding="utf-8"))
    baseline_governance_schema = json.loads(BASELINE_GOVERNANCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "real-repo-evaluation-report"
    assert set(schema["required"]) >= {"repo_id", "baseline", "current", "timeout_recorded", "subset", "regressions", "external_hold"}
    assert run_schema["properties"]["record_type"]["const"] == "real-repo-evaluation-run-report"
    assert set(run_schema["required"]) >= {"repo_count", "hold_count", "generated_reports", "summary", "run_id", "roster_hash"}
    assert roster_v2_schema["properties"]["record_type"]["const"] == "real-repo-roster-v2"
    assert run_history_schema["properties"]["record_type"]["const"] == "real-repo-run-history-entry"
    assert history_ingest_schema["properties"]["record_type"]["const"] == "real-repo-history-ingest-report"
    assert history_query_schema["properties"]["record_type"]["const"] == "real-repo-history-query-report"
    assert score_schema["properties"]["record_type"]["const"] == "real-repo-score-report"
    assert baseline_event_schema["properties"]["record_type"]["const"] == "real-repo-baseline-event"
    assert baseline_governance_schema["properties"]["record_type"]["const"] == "real-repo-baseline-governance-report"
    assert set(score_schema["required"]) >= {"score", "score_breakdown", "decision_basis", "release_approval"}
    assert any(record["record_type"] == "real-repo-evaluation-report" for record in registry["records"])
    assert any(record["record_type"] == "real-repo-evaluation-run-report" for record in registry["records"])
    assert any(record["record_type"] == "real-repo-roster-v2" for record in registry["records"])
    assert any(record["record_type"] == "real-repo-run-history-entry" for record in registry["records"])
    assert any(record["record_type"] == "real-repo-history-ingest-report" for record in registry["records"])
    assert any(record["record_type"] == "real-repo-history-query-report" for record in registry["records"])
    assert any(record["record_type"] == "real-repo-score-report" for record in registry["records"])
    assert any(record["record_type"] == "real-repo-baseline-event" for record in registry["records"])
    assert any(record["record_type"] == "real-repo-baseline-governance-report" for record in registry["records"])


def test_run_real_repo_roster_generates_pass_fail_and_timeout_reports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [
            {
                "repo_id": "pass-repo",
                "path": str(repo),
                "command": [sys.executable, "-c", "print('ok')"],
                "timeout_ms": 5000,
            },
            {
                "repo_id": "fail-repo",
                "path": str(repo),
                "command": [sys.executable, "-c", "raise SystemExit(2)"],
                "timeout_ms": 5000,
            },
            {
                "repo_id": "timeout-repo",
                "path": str(repo),
                "command": [sys.executable, "-c", "import time; time.sleep(1)"],
                "timeout_ms": 50,
                "subset": True,
                "subset_label": "smoke timeout probe",
            },
        ]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out", source_version="test")

    assert manifest["record_type"] == "real-repo-evaluation-run-report"
    assert manifest["overall_status"] == "hold"
    assert manifest["repo_count"] == 3
    assert manifest["hold_count"] == 2
    assert "real-repo-pass-repo.json" in manifest["generated_reports"]
    assert manifest["summary"]["held_repos"] == ["fail-repo", "timeout-repo"]

    fail_report = json.loads((tmp_path / "out" / "real-repo-fail-repo.json").read_text(encoding="utf-8"))
    timeout_report = json.loads((tmp_path / "out" / "real-repo-timeout-repo.json").read_text(encoding="utf-8"))
    assert {finding["code"] for finding in fail_report["findings"]} >= {
        "real_repo_regression_detected",
        "real_repo_command_failed",
    }
    assert timeout_report["timeout_recorded"] is True
    assert timeout_report["current"]["timeout_cleanup"]["timeout_reason"] == "command_timeout_exceeded"
    assert timeout_report["current"]["timeout_cleanup"]["cleanup_attempted"] is True
    assert timeout_report["current"]["timeout_cleanup"]["cleanup_method"] in {"taskkill_tree", "os_kill"}
    assert "real_repo_timeout_recorded" in {finding["code"] for finding in timeout_report["findings"]}


def test_real_repo_cli_run_writes_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "cli-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", "print('cli')"],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    exit_code = main(["real-repo", "run", "--roster", str(roster), "--out", str(tmp_path / "out")])

    assert exit_code == 0
    manifest = json.loads((tmp_path / "out" / "real-repo-evaluation-run-report.json").read_text(encoding="utf-8"))
    assert manifest["overall_status"] == "pass"
    assert manifest["generated_reports"] == ["real-repo-cli-repo.json"]
    assert manifest["run_id"].startswith("run-")
    assert manifest["roster_hash"].startswith("sha256:")
    assert manifest["policy_hash"].startswith("policy-")
    assert manifest["environment_fingerprint"]["python"]
    assert (tmp_path / "out" / "real-repo-run-history.jsonl").exists()


def test_real_repo_runner_supports_roster_v2_suites_and_identity(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster-v2.json"
    roster.write_text(json.dumps({
        "schema_version": "HATE/v1",
        "record_type": "real-repo-roster-v2",
        "roster_id": "unit-roster",
        "source_version": "v2-source",
        "default_policy_ref": "policy://default",
        "repositories": [{
            "repo_id": "v2-repo",
            "path": str(repo),
            "ownership_scope": "owned",
            "repo_class": "small",
            "suites": [{
                "suite_id": "unit",
                "suite_kind": "unit",
                "command": [sys.executable, "-c", "print('4 passed in 0.1s')"],
                "timeout_profile": "small",
                "subset": False,
            }],
        }],
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-v2-repo-unit.json").read_text(encoding="utf-8"))
    history = [
        json.loads(line)
        for line in (tmp_path / "out" / "real-repo-run-history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert manifest["overall_status"] == "pass"
    assert manifest["roster_hash"].startswith("sha256:")
    assert report["suite_id"] == "unit"
    assert report["ownership_scope"] == "owned"
    assert report["run_id"].startswith("real-repo-run-")
    assert report["policy_hash"].startswith("policy-")
    assert report["environment_fingerprint"]["os"]
    assert history[0]["record_type"] == "real-repo-run-history-entry"
    assert history[0]["suite_id"] == "unit"
    assert history[0]["record_count"] == 4


def test_real_repo_runner_rejects_invalid_roster_v2_ownership(tmp_path: Path) -> None:
    roster = tmp_path / "bad-roster-v2.json"
    roster.write_text(json.dumps({
        "schema_version": "HATE/v1",
        "record_type": "real-repo-roster-v2",
        "roster_id": "bad",
        "source_version": "bad",
        "default_policy_ref": "policy://default",
        "repositories": [{
            "repo_id": "bad-repo",
            "path": str(tmp_path),
            "ownership_scope": "mine",
            "repo_class": "small",
            "suites": [{
                "suite_id": "unit",
                "suite_kind": "unit",
                "command": [sys.executable, "-c", "print('ok')"],
                "timeout_profile": "small",
                "subset": False,
            }],
        }],
    }), encoding="utf-8")

    try:
        run_real_repo_roster(roster, tmp_path / "out")
    except ValueError as exc:
        assert "invalid ownership_scope" in str(exc)
    else:
        raise AssertionError("invalid roster v2 ownership must be rejected")


def test_real_repo_runner_tolerates_non_utf8_command_output(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "encoding-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\x82')"],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "pass"
    report = json.loads((tmp_path / "out" / "real-repo-encoding-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["command_exit_code"] == 0


def test_real_repo_runner_classifies_dependency_network_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    failure_text = (
        "Failed to build package; Failed to resolve requirements from build-system.requires; "
        "Failed to fetch: https://pypi.org/simple/setuptools/; tcp connect error"
    )
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "network-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", f"import sys; sys.stderr.write({failure_text!r}); raise SystemExit(1)"],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "hold"
    report = json.loads((tmp_path / "out" / "real-repo-network-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["failure_kind"] == "dependency_network_blocked"
    assert "Failed to fetch" in report["current"]["command_excerpt"]
    assert "real_repo_dependency_network_blocked" in {finding["code"] for finding in report["findings"]}


def test_real_repo_runner_ignores_network_text_when_command_passes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    benign_negative_test_output = (
        "Failed to build package; Failed to resolve requirements from build-system.requires; "
        "Failed to fetch: https://pypi.org/simple/setuptools/; tcp connect error; "
        "2 passed in 0.1s"
    )
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "passing-negative-tests-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", f"print({benign_negative_test_output!r})"],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "pass"
    report = json.loads((tmp_path / "out" / "real-repo-passing-negative-tests-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["failure_kind"] == ""
    assert report["findings"] == []


def test_real_repo_runner_extracts_pytest_record_counts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "summary-repo",
            "path": str(repo),
            "command": [
                sys.executable,
                "-c",
                "print('================ 1436 passed, 11 skipped in 108.14s ================')",
            ],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "pass"
    report = json.loads((tmp_path / "out" / "real-repo-summary-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["record_count"] == 1447
    assert report["current"]["command_summary"] == {
        "passed": 1436,
        "skipped": 11,
        "total_tests": 1447,
    }
    assert report["summary"]["executed_record_count"] == 1447


def test_real_repo_runner_extracts_failed_pytest_record_counts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "failed-summary-repo",
            "path": str(repo),
            "command": [
                sys.executable,
                "-c",
                "print('1 failed, 66 passed in 1.21s'); raise SystemExit(1)",
            ],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "hold"
    report = json.loads((tmp_path / "out" / "real-repo-failed-summary-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["record_count"] == 67
    assert report["current"]["command_summary"]["failed"] == 1
    assert report["current"]["command_summary"]["passed"] == 66


def test_real_repo_runner_prefers_vitest_tests_summary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    vitest_output = (
        'WARN Result validation failed errors [{"code":"semantic_error"}]\\n'
        " Test Files  106 passed | 1 skipped (107)\\n"
        "      Tests  2266 passed | 15 skipped (2281)\\n"
        "   Duration  22.91s\\n"
    )
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "vitest-summary-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", f"print({vitest_output!r})"],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "pass"
    report = json.loads((tmp_path / "out" / "real-repo-vitest-summary-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["record_count"] == 2281
    assert report["current"]["runner_dialect"] == "vitest"
    assert "semantic_error" in report["current"]["runner_parser"]["ignored_noise"]
    assert report["current"]["command_summary"] == {
        "passed": 2266,
        "skipped": 15,
        "total_tests": 2281,
    }


def test_real_repo_runner_extracts_bun_test_record_counts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    bun_output = (
        "bun test v1.3.12\\n"
        " 57 pass\\n"
        " 0 fail\\n"
        " 106 expect() calls\\n"
        "Ran 57 tests across 10 files. [644.00ms]\\n"
    )
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "bun-summary-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", f"print({bun_output!r})"],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "pass"
    report = json.loads((tmp_path / "out" / "real-repo-bun-summary-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["record_count"] == 57
    assert report["current"]["runner_dialect"] == "bun"
    assert report["current"]["command_summary"] == {
        "passed": 57,
        "total_tests": 57,
    }


def test_real_repo_runner_ignores_bun_non_summary_error_logs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    bun_output = (
        "ERROR handler emitted 500 errors while exercising retry paths\\n"
        "bun test v1.3.12\\n"
        " 57 pass\\n"
        " 0 fail\\n"
        " 0 error\\n"
        "Ran 57 tests across 10 files. [644.00ms]\\n"
    )
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "bun-noisy-summary-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", f"print({bun_output!r})"],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "pass"
    report = json.loads((tmp_path / "out" / "real-repo-bun-noisy-summary-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["record_count"] == 57
    assert report["current"]["runner_dialect"] == "bun"
    assert "handler emitted" in report["current"]["runner_parser"]["ignored_noise"]
    assert report["current"]["command_summary"] == {
        "passed": 57,
        "total_tests": 57,
    }


def test_real_repo_runner_uses_repo_class_timeout_defaults(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "large-repo",
            "repo_class": "large",
            "path": str(repo),
            "command": [sys.executable, "-c", "print('1 passed in 0.1s')"],
        }]
    }), encoding="utf-8")

    run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-large-repo.json").read_text(encoding="utf-8"))
    assert report["repo_class"] == "large"
    assert report["timeout_ms"] == 2_700_000
    assert report["runtime_budget_ms"] == 2_700_000


def test_real_repo_runner_prefers_explicit_timeout_over_repo_class(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "large-repo",
            "repo_class": "large",
            "path": str(repo),
            "command": [sys.executable, "-c", "print('1 passed in 0.1s')"],
            "timeout_ms": 1234,
        }]
    }), encoding="utf-8")

    run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-large-repo.json").read_text(encoding="utf-8"))
    assert report["timeout_ms"] == 1234
    assert report["runtime_budget_ms"] == 1234


def test_real_repo_runner_isolates_parent_python_environment(monkeypatch) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", "C:/parent/.venv")
    monkeypatch.setenv("PYTHONPATH", "C:/parent/src")
    monkeypatch.setenv("PYTHONHOME", "C:/parent/python")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "C:/parent/.venv")
    monkeypatch.setenv("PATH", "C:/bin")

    env = real_repo._isolated_command_env()

    assert env["PATH"] == "C:/bin"
    assert "VIRTUAL_ENV" not in env
    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert "UV_PROJECT_ENVIRONMENT" not in env


def test_real_repo_runner_applies_roster_env_overrides(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "env-repo",
            "path": str(repo),
            "command": [
                sys.executable,
                "-c",
                "import os; print('HOME=' + os.environ['HOME']); print('1 passed in 0.1s')",
            ],
            "env": {
                "HOME": str(tmp_path / "home"),
                "IGNORED_NON_STRING": 123,
            },
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "pass"
    report = json.loads((tmp_path / "out" / "real-repo-env-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["record_count"] == 1


def test_real_repo_manifest_sums_executed_records(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [
            {
                "repo_id": "summary-a",
                "path": str(repo),
                "command": [sys.executable, "-c", "print('2 passed in 0.1s')"],
                "timeout_ms": 5000,
            },
            {
                "repo_id": "summary-b",
                "path": str(repo),
                "command": [sys.executable, "-c", "print('3 passed, 1 skipped in 0.1s')"],
                "timeout_ms": 5000,
            },
        ]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "pass"
    assert manifest["summary"]["executed_record_count"] == 6
    assert manifest["summary"]["held_repos"] == []


def test_windows_command_shim_is_resolved(monkeypatch) -> None:
    monkeypatch.setattr(real_repo.os, "name", "nt")
    monkeypatch.setattr(real_repo.shutil, "which", lambda name: "C:/Program Files/nodejs/npm.cmd" if name == "npm.cmd" else None)

    command = real_repo._normalize_command(["npm", "test"])

    assert command == ["C:/Program Files/nodejs/npm.cmd", "test"]
