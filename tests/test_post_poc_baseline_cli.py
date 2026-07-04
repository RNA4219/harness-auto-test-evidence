from __future__ import annotations

import json
from pathlib import Path

from hate.cli import main


def _write_input(path: Path, reviewer: str = "bob") -> None:
    payload = {
        "baseline": {
            "baseline_id": "base-cli",
            "repo_id": "repo-main",
            "suite_id": "pytest",
            "actor": "alice",
            "policy_hash": "policy-sha256-cli",
        },
        "events": [
            {
                "event_type": "proposed",
                "candidate_run_id": "run-cli",
                "evidence_refs": ["artifact://runs/run-cli/product-readiness.json"],
                "reason": "promote stable run",
            },
            {"event_type": "approved", "reviewer": reviewer, "reason": "reviewed"},
            {
                "event_type": "frozen",
                "frozen_at": "2026-07-03T00:00:00Z",
                "immutability_hash": "sha256:cli-frozen",
            },
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_platform_baseline_promote_cli_writes_report(tmp_path: Path) -> None:
    input_path = tmp_path / "baseline-input.json"
    out_path = tmp_path / "baseline-report.json"
    _write_input(input_path)

    exit_code = main(["platform", "baseline", "promote", "--input", str(input_path), "--out", str(out_path)])

    assert exit_code == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["record_type"] == "baseline-promotion-report"
    assert report["overall_status"] == "pass"
    assert report["summary"]["final_state"] == "frozen"
    assert report["sourceRefs"] == [str(input_path)]


def test_platform_baseline_promote_cli_preserves_denial(tmp_path: Path) -> None:
    input_path = tmp_path / "baseline-self-approval.json"
    out_path = tmp_path / "baseline-denied-report.json"
    _write_input(input_path, reviewer="alice")

    exit_code = main(["platform", "baseline", "promote", "--input", str(input_path), "--out", str(out_path)])

    assert exit_code == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["overall_status"] == "hold"
    assert report["findings"][0]["code"] == "baseline_self_approval_denied"
