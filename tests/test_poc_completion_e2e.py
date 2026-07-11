from __future__ import annotations

import json
import sys

import pytest
from pathlib import Path

from hate.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.e2e
def test_poc_completion_platform_blackbox_loop(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    roster = tmp_path / "roster.json"
    run_dir = tmp_path / "run"
    schedule_path = tmp_path / "schedule.json"
    compare_path = tmp_path / "compare.json"
    assign_path = tmp_path / "assign.json"
    score_path = tmp_path / "score.json"
    plugin_path = tmp_path / "plugin.json"
    plugin_out = tmp_path / "plugin-out.json"
    html_path = tmp_path / "daily.html"
    grade_dir = tmp_path / "grade"

    _write_json(
        roster,
        {
            "repositories": [
                {
                    "repo_id": "pass-repo",
                    "path": str(repo),
                    "command": [sys.executable, "-c", "print('2 passed in 0.1s')"],
                    "timeout_ms": 5000,
                },
                {
                    "repo_id": "hold-repo",
                    "path": str(repo),
                    "command": [sys.executable, "-c", "raise SystemExit(2)"],
                    "timeout_ms": 5000,
                },
            ]
        },
    )

    assert main(["platform", "run", "--roster", str(roster), "--out", str(run_dir), "--source-version", "poc-e2e"]) == 0
    assert main([
        "platform",
        "schedule",
        "--roster",
        str(roster),
        "--history-store",
        str(run_dir / "real-repo-run-history.jsonl"),
        "--out",
        str(schedule_path),
        "--retry-limit",
        "2",
    ]) == 0
    assert main([
        "platform",
        "compare",
        "--base",
        str(run_dir / "real-repo-pass-repo.json"),
        "--head",
        str(run_dir / "real-repo-hold-repo.json"),
        "--out",
        str(compare_path),
    ]) == 0
    assert main(["platform", "assign", "--input", str(run_dir), "--out", str(assign_path)]) == 0
    assert main(["platform", "score", "--input", str(run_dir), "--out", str(score_path)]) == 0
    assert main(["platform", "report", "html", "--input", str(run_dir), "--out", str(html_path)]) == 0

    _write_json(
        plugin_path,
        {
            "profile": "default",
            "plugin": {
                "plugin_id": "poc-plugin",
                "detector_id": "poc-detector",
                "execution_mode": "subprocess_local",
                "signed": True,
                "trusted": True,
            },
            "limits": {"timeout_ms": 5000, "max_output_bytes": 2000, "max_input_bytes": 2000},
            "execution": {
                "command": [
                    sys.executable,
                    "-c",
                    "import json; print(json.dumps({'schema_version':'HATE/v1','detector_id':'poc-detector','sourceRefs':['poc']}))",
                ]
            },
        },
    )
    assert main(["platform", "plugin", "run", "--manifest", str(plugin_path), "--out", str(plugin_out), "--allow-local-exec"]) == 0
    assert main([
        "product",
        "grade-reports",
        "--docs-root",
        str(ROOT / "docs" / "process"),
        "--out",
        str(grade_dir),
        "--source-version",
        "poc-e2e",
    ]) == 0

    manifest = json.loads((run_dir / "real-repo-evaluation-run-report.json").read_text(encoding="utf-8"))
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    compare = json.loads(compare_path.read_text(encoding="utf-8"))
    assign = json.loads(assign_path.read_text(encoding="utf-8"))
    score = json.loads(score_path.read_text(encoding="utf-8"))
    plugin = json.loads(plugin_out.read_text(encoding="utf-8"))
    grade = json.loads((grade_dir / "product-grade-evidence-summary.json").read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    assert manifest["overall_status"] == "hold"
    assert manifest["repo_count"] == 2
    assert schedule["summary"]["cache_hit_count"] == 1
    assert schedule["summary"]["retry_count"] == 1
    assert compare["record_type"] == "platform-comparison-report"
    assert assign["record_type"] == "platform-assignment-report"
    assert score["record_type"] == "platform-score-report"
    assert plugin["overall_status"] == "pass"
    assert "HATE Platform Daily Report" in html
    assert "Operator Queue" in html
    assert grade["product_grade_implementation_status"] == "poc_complete"
    assert grade["poc_ready"] is True
    assert grade["poc_completion_percent"] == 100
    assert grade["product_ready"] is False
