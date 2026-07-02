"""Tests for platform-phase real-repo evaluation packets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from hate.cli import main
from hate.evaluation import (
    build_real_repo_baseline_governance_report,
    build_real_repo_evaluation_report,
    build_real_repo_score_report,
    build_runner_dialect_coverage_report,
)
from hate.evaluation.history_store import ingest_real_repo_history, query_real_repo_history
from hate.evaluation.output_safety import safe_command_output
from hate.evaluation.real_repo import run_real_repo_roster


ROOT = Path(__file__).resolve().parents[1]
PLATFORM_EVALUATION_FIXTURE_ROOT = ROOT / "fixtures" / "platform" / "evaluation"


def test_real_repo_score_model_emits_breakdown_and_basis() -> None:
    fixture = _fixture("score-model-balanced")

    report = build_real_repo_score_report(fixture["input"], fixture["fixture_id"])

    assert report["record_type"] == fixture["expected"]["record_type"]
    assert report["score"] == fixture["expected"]["score"]
    assert report["score_band"] == fixture["expected"]["score_band"]
    assert report["release_approval"] is fixture["expected"]["release_approval"]
    assert report["score_breakdown"]["base_score"] == 85.5
    assert report["score_breakdown"]["penalty_total"] == 23
    assert len(report["decision_basis"]) >= fixture["expected"]["decision_basis_min"]


def test_real_repo_score_model_clamps_penalty_heavy_score() -> None:
    fixture = _fixture("score-model-penalty-cap")

    report = build_real_repo_score_report(fixture["input"], fixture["fixture_id"])

    assert report["score"] == fixture["expected"]["score"]
    assert report["score_band"] == fixture["expected"]["score_band"]
    assert report["score_breakdown"]["penalty_total"] == fixture["expected"]["penalty_total"]
    assert report["score_breakdown"]["score"] == report["score"]


def test_real_repo_output_safety_redacts_sensitive_excerpt() -> None:
    fixture = _fixture("redacted-deterministic-output")

    result = safe_command_output(fixture["input"]["stdout"], fixture["input"]["stderr"], limit=160)

    assert result["metadata"]["redaction_status"] == fixture["expected"]["redaction_status"]
    assert result["metadata"]["raw_access"] == fixture["expected"]["raw_access"]
    assert result["metadata"]["ansi_removed"] is fixture["expected"]["ansi_removed"]
    assert result["metadata"]["control_characters_removed"] is fixture["expected"]["control_characters_removed"]
    assert result["metadata"]["line_endings_normalized"] is fixture["expected"]["line_endings_normalized"]
    assert result["metadata"]["safe_for_read_model"] is True
    for marker in fixture["expected"]["markers"]:
        assert marker in result["excerpt"]
    for forbidden in fixture["expected"]["forbidden"]:
        assert forbidden not in result["excerpt"]


def test_real_repo_runner_persists_redacted_output_safety_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    sensitive_output = (
        "\u001b[31mFAIL\u001b[0m\\r\\n"
        "api_key=supersecretvalue1234567890 "
        "alice@example.com "
        f"{tmp_path}\\private\\file.txt"
    )
    roster.write_text(json.dumps({
        "repositories": [{
            "repo_id": "redaction-repo",
            "path": str(repo),
            "command": [sys.executable, "-c", f"print({sensitive_output!r})"],
            "timeout_ms": 5000,
        }]
    }), encoding="utf-8")

    manifest = run_real_repo_roster(roster, tmp_path / "out")
    report = json.loads((tmp_path / "out" / "real-repo-redaction-repo.json").read_text(encoding="utf-8"))

    assert manifest["overall_status"] == "pass"
    assert report["current"]["output_safety"]["redaction_status"] == "redacted"
    assert report["current"]["output_safety"]["safe_for_read_model"] is True
    assert "supersecretvalue1234567890" not in report["current"]["command_excerpt"]
    assert "alice@example.com" not in report["current"]["command_excerpt"]
    assert str(tmp_path) not in report["current"]["command_excerpt"]


def test_real_repo_timeout_cleanup_fixture_contract() -> None:
    fixture = _fixture("timeout-cleanup")

    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}
    assert report["current"]["timeout_cleanup"]["timeout_reason"] == fixture["expected"]["timeout_reason"]
    assert report["current"]["timeout_cleanup"]["cleanup_attempted"] is fixture["expected"]["cleanup_attempted"]


def test_real_repo_history_store_ingests_history_jsonl(tmp_path: Path) -> None:
    fixture = _fixture("history-store-ingest")
    history_path = tmp_path / "real-repo-run-history.jsonl"
    _write_history_jsonl(history_path, fixture["input"]["history_entries"])

    report = ingest_real_repo_history(history_path, tmp_path / "store")
    index = json.loads((tmp_path / "store" / "history-index.json").read_text(encoding="utf-8"))
    stored = (tmp_path / "store" / "run_history.jsonl").read_text(encoding="utf-8").splitlines()

    assert report["record_type"] == fixture["expected"]["record_type"]
    assert report["ingested_count"] == fixture["expected"]["ingested_count"]
    assert report["stored_count"] == fixture["expected"]["stored_count"]
    assert report["repo_count"] == fixture["expected"]["repo_count"]
    assert report["source_history_hash"].startswith("sha256:")
    assert index["record_type"] == fixture["expected"]["index_record_type"]
    assert len(stored) == 1


def test_real_repo_history_store_queries_repo_suite_source_status_and_time(tmp_path: Path) -> None:
    fixture = _fixture("history-store-query-filter")
    history_path = tmp_path / "real-repo-run-history.jsonl"
    _write_history_jsonl(history_path, fixture["input"]["history_entries"])
    ingest_real_repo_history(history_path, tmp_path / "store")

    report = query_real_repo_history(tmp_path / "store", **fixture["expected"]["filter"])

    assert report["record_type"] == fixture["expected"]["record_type"]
    assert report["matched_count"] == fixture["expected"]["matched_count"]
    assert report["returned_count"] == fixture["expected"]["matched_count"]
    assert report["entries"][0]["run_id"] == fixture["expected"]["returned_run_id"]
    assert report["entries"][0]["store_sequence"] == 2


def test_real_repo_history_cli_ingest_and_query(tmp_path: Path) -> None:
    fixture = _fixture("history-store-query-filter")
    history_path = tmp_path / "real-repo-run-history.jsonl"
    store_dir = tmp_path / "store"
    _write_history_jsonl(history_path, fixture["input"]["history_entries"])

    ingest_exit = main(["real-repo", "history-ingest", "--history", str(history_path), "--store", str(store_dir)])
    query_exit = main([
        "real-repo",
        "history-query",
        "--store",
        str(store_dir),
        "--repo-id",
        "alpha",
        "--suite-id",
        "unit",
        "--status",
        "hold",
        "--limit",
        "1",
    ])
    report = query_real_repo_history(store_dir, repo_id="alpha", suite_id="unit", status="hold", limit=1)

    assert ingest_exit == 0
    assert query_exit == 0
    assert report["matched_count"] == 1
    assert report["entries"][0]["run_id"] == "run-alpha-unit-002"


def test_runner_dialect_coverage_ignores_noisy_logs() -> None:
    fixture = _fixture("noisy-runner-log")

    report = build_runner_dialect_coverage_report(fixture["input"], fixture["fixture_id"])

    assert report["record_type"] == fixture["expected"]["record_type"]
    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["summary"]["case_count"] == fixture["expected"]["case_count"]
    assert report["summary"]["failed"] == fixture["expected"]["failed"]
    assert report["summary"]["dialects"] == fixture["expected"]["dialects"]
    assert all(result["passed"] for result in report["results"])
    assert any(result["actual"]["ignored_noise"] for result in report["results"])


def test_runner_dialect_coverage_does_not_misclassify_cargo_as_pytest() -> None:
    fixture = _fixture("noisy-runner-log")

    report = build_runner_dialect_coverage_report(fixture["input"], fixture["fixture_id"])

    cargo = next(result for result in report["results"] if result["case_id"] == "cargo-test-real-output")
    assert cargo["actual"]["dialect"] == "cargo-test"
    assert cargo["actual"]["summary"] == {"passed": 25, "total_tests": 25}


def test_runner_dialect_coverage_classifies_build_and_check_outputs() -> None:
    fixture = _fixture("noisy-runner-log")

    report = build_runner_dialect_coverage_report(fixture["input"], fixture["fixture_id"])
    actual_by_case = {result["case_id"]: result["actual"] for result in report["results"]}

    assert actual_by_case["nextjs-build-real-output"]["dialect"] == "nextjs-build"
    assert actual_by_case["astro-build-real-output"]["dialect"] == "astro-build"
    assert actual_by_case["typescript-typecheck-real-output"]["dialect"] == "typescript-typecheck"
    assert actual_by_case["python-compileall-real-output"]["dialect"] == "python-compileall"


def test_real_repo_baseline_approval_freeze_is_usable() -> None:
    fixture = _fixture("baseline-approval-freeze")

    report = build_real_repo_baseline_governance_report(fixture["input"], fixture["fixture_id"], today="2026-07-01")

    assert report["record_type"] == fixture["expected"]["record_type"]
    assert report["status"] == fixture["expected"]["status"]
    assert report["frozen"] is fixture["expected"]["frozen"]
    assert report["can_use_for_regression"] is fixture["expected"]["can_use_for_regression"]
    assert report["summary"]["finding_count"] == fixture["expected"]["finding_count"]


def test_real_repo_unapproved_baseline_cannot_hide_regression() -> None:
    fixture = _fixture("baseline-unapproved-denied")

    report = build_real_repo_baseline_governance_report(fixture["input"], fixture["fixture_id"], today="2026-07-01")

    assert report["status"] == fixture["expected"]["status"]
    assert report["can_use_for_regression"] is fixture["expected"]["can_use_for_regression"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_real_repo_expired_baseline_cannot_hide_regression() -> None:
    fixture = _fixture("baseline-expired-denied")

    report = build_real_repo_baseline_governance_report(fixture["input"], fixture["fixture_id"], today="2026-07-01")

    assert report["status"] == fixture["expected"]["status"]
    assert report["can_use_for_regression"] is fixture["expected"]["can_use_for_regression"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def _fixture(name: str) -> dict:
    return json.loads((PLATFORM_EVALUATION_FIXTURE_ROOT / name / "fixture.json").read_text(encoding="utf-8"))


def _write_history_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n" for entry in entries),
        encoding="utf-8",
    )
