from __future__ import annotations

import json
import sys
from pathlib import Path

from hate.evaluation import build_real_repo_evaluation_report
from hate.evaluation.real_repo import run_real_repo_roster
from hate.evaluation.runner_dialects import parse_runner_summary


def test_missing_test_dependency_is_classified() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "node-oss",
        "ownership_scope": "external",
        "current_decision": "hold",
        "command_exit_code": 1,
        "failure_kind": "missing_test_dependency",
    })

    codes = {finding["code"] for finding in report["findings"]}
    assert "real_repo_missing_test_dependency" in codes
    assert "real_repo_regression_detected" not in codes
    assert report["external_hold"]["detected"] is True


def test_runner_config_mismatch_is_classified() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "pytest-oss",
        "current_decision": "hold",
        "command_exit_code": 4,
        "failure_kind": "runner_config_mismatch",
    })

    assert "real_repo_runner_config_mismatch" in {finding["code"] for finding in report["findings"]}


def test_test_failure_kind_is_classified() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "failing-tests",
        "current_decision": "hold",
        "command_exit_code": 1,
        "failure_kind": "test_failure",
    })

    assert "real_repo_test_failure" in {finding["code"] for finding in report["findings"]}


def test_pytest_partial_progress_is_preserved_without_total_count() -> None:
    parsed = parse_runner_summary(
        "........................................................................ [ 22%]\n"
        "........................................................x............... [ 45%]\n"
    )

    assert parsed["dialect"] == "pytest"
    assert parsed["parser_status"] == "partial"
    assert parsed["summary"] == {
        "partial_progress_percent": 45,
        "partial_progress_observed": 1,
    }


def test_partial_runner_progress_finding_is_visible() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "timeout-with-progress",
        "current_decision": "hold",
        "command_exit_code": 124,
        "failure_kind": "timeout",
        "timeout_recorded": True,
        "runner_dialect": "pytest",
        "runner_parser": {"parser_status": "partial", "ignored_noise": []},
        "command_summary": {"partial_progress_percent": 45, "partial_progress_observed": 1},
    })

    assert report["current"]["runner_parser"]["parser_status"] == "partial"
    assert report["current"]["command_summary"]["partial_progress_percent"] == 45
    assert "real_repo_runner_partial_progress_observed" in {finding["code"] for finding in report["findings"]}


def test_unbaselined_external_hold_does_not_emit_regression_noise() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "external-oss",
        "ownership_scope": "external",
        "current_decision": "hold",
        "command_exit_code": 1,
        "failure_kind": "missing_test_dependency",
    })

    assert report["external_hold"]["detected"] is True
    assert report["summary"]["regression_classes"] == ["external_hold_detected"]
    codes = {finding["code"] for finding in report["findings"]}
    assert "real_repo_external_hold_detected" in codes
    assert "real_repo_failure_kind_new" not in codes
    assert "real_repo_regression_detected" not in codes


def test_real_repo_runner_classifies_missing_test_dependency(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    failure_text = "'mocha' is not recognized as an internal or external command, operable program or batch file."
    roster.write_text(json.dumps({
        "record_type": "real-repo-roster-v2",
        "repositories": [{
            "repo_id": "external-node-repo",
            "path": str(repo),
            "ownership_scope": "external",
            "repo_class": "small",
            "suites": [{
                "suite_id": "npm-test",
                "suite_kind": "unit",
                "command": [sys.executable, "-c", f"import sys; sys.stderr.write({failure_text!r}); raise SystemExit(1)"],
                "timeout_ms": 5000,
            }],
        }],
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    assert manifest["overall_status"] == "hold"
    report = json.loads((tmp_path / "out" / "real-repo-external-node-repo-npm-test.json").read_text(encoding="utf-8"))
    assert report["baseline"]["decision"] == ""
    assert report["current"]["failure_kind"] == "missing_test_dependency"
    codes = {finding["code"] for finding in report["findings"]}
    assert "real_repo_missing_test_dependency" in codes
    assert "real_repo_regression_detected" not in codes


def test_real_repo_runner_classifies_runner_config_mismatch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    failure_text = "ERROR: pyproject.toml: 'minversion' requires pytest-2.0, actual pytest-0.1.dev1"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "runner-config-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", f"import sys; sys.stderr.write({failure_text!r}); raise SystemExit(4)"],
            "timeout_ms": 5000,
        }],
    }), encoding="utf-8")

    run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-runner-config-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["failure_kind"] == "runner_config_mismatch"
    assert "real_repo_runner_config_mismatch" in {finding["code"] for finding in report["findings"]}


def test_real_repo_runner_classifies_test_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    failure_text = "================================== FAILURES ==================================\nFAILED tests/test_app.py::test_example"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "failing-tests-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", f"import sys; sys.stdout.write({failure_text!r}); raise SystemExit(1)"],
            "timeout_ms": 5000,
        }],
    }), encoding="utf-8")

    run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-failing-tests-repo.json").read_text(encoding="utf-8"))
    assert report["current"]["failure_kind"] == "test_failure"
    assert "real_repo_test_failure" in {finding["code"] for finding in report["findings"]}


def test_real_repo_runner_executes_declared_bootstrap_before_suite(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    marker = repo / "bootstrapped.txt"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "bootstrap-repo",
            "path": str(repo),
            "ownership_scope": "external",
            "bootstrap_command": [sys.executable, "-c", "from pathlib import Path; Path('bootstrapped.txt').write_text('ok')"],
            "command": [sys.executable, "-c", "from pathlib import Path; assert Path('bootstrapped.txt').exists(); print('1 passed')"],
            "timeout_ms": 5000,
        }],
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-bootstrap-repo.json").read_text(encoding="utf-8"))
    assert marker.read_text(encoding="utf-8") == "ok"
    assert manifest["overall_status"] == "pass"
    assert report["current"]["bootstrap"]["status"] == "pass"
    assert report["summary"]["bootstrap_status"] == "pass"


def test_real_repo_runner_holds_when_declared_bootstrap_fails(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "bootstrap-fail-repo",
            "path": str(repo),
            "ownership_scope": "external",
            "bootstrap": {"command": [sys.executable, "-c", "raise SystemExit(7)"], "timeout_ms": 5000},
            "command": [sys.executable, "-c", "print('should not run')"],
            "timeout_ms": 5000,
        }],
    }), encoding="utf-8")

    run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-bootstrap-fail-repo.json").read_text(encoding="utf-8"))
    assert report["overall_status"] == "hold"
    assert report["current"]["failure_kind"] == "bootstrap_failed"
    assert report["current"]["bootstrap"]["exit_code"] == 7
    assert "real_repo_bootstrap_failed" in {finding["code"] for finding in report["findings"]}


def test_real_repo_runner_executes_split_commands_and_aggregates_records(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "split-repo",
            "path": str(repo),
            "ownership_scope": "external",
            "command": [sys.executable, "-c", "raise SystemExit(124)"],
            "split_commands": [
                [sys.executable, "-c", "print('2 passed')"],
                [sys.executable, "-c", "print('3 passed')"],
            ],
            "timeout_ms": 5000,
        }],
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-split-repo.json").read_text(encoding="utf-8"))
    assert manifest["overall_status"] == "pass"
    assert report["current"]["record_count"] == 5
    assert report["current"]["split_execution"]["status"] == "pass"
    assert report["current"]["split_execution"]["completed_count"] == 2
    assert report["summary"]["split_status"] == "pass"


def test_real_repo_runner_requires_resume_token_when_split_skips_completed_shards(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "resume-repo",
            "path": str(repo),
            "ownership_scope": "external",
            "command": [sys.executable, "-c", "raise SystemExit(124)"],
            "split_execution": {
                "completed_splits": ["1"],
                "commands": [
                    [sys.executable, "-c", "print('1 passed')"],
                    [sys.executable, "-c", "print('2 passed')"],
                ],
            },
            "timeout_ms": 5000,
        }],
    }), encoding="utf-8")

    run_real_repo_roster(roster, tmp_path / "out")

    report = json.loads((tmp_path / "out" / "real-repo-resume-repo.json").read_text(encoding="utf-8"))
    assert report["overall_status"] == "hold"
    assert report["current"]["split_execution"]["skipped_count"] == 1
    assert report["current"]["split_execution"]["resume_required"] is True
    assert "real_repo_resume_token_missing" in {finding["code"] for finding in report["findings"]}
