"""Rust CLI の運用レポート、プラグイン、履歴、ストアを Python 実装と照合する。"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from check_rust_qeg_trust import difference

from hate.cli import main

ROOT = Path(__file__).resolve().parents[1]


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def scenario(invoke):
    results = {}
    def run(label, args, files=(), clock_fields=()):
        args = list(map(str, args))
        result = invoke(args)
        observed = {"stdout": result}
        for name in files:
            path = Path(name)
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".jsonl":
                data = [json.loads(row) for row in path.read_text(encoding="utf-8").splitlines()]
            else:
                data = path.read_text(encoding="utf-8")
            observed[name] = data

        def clock(value):
            if isinstance(value, list):
                return [clock(item) for item in value]
            if isinstance(value, dict):
                checked = {}
                for key, item in value.items():
                    if key in clock_fields:
                        instant = datetime.fromisoformat(item.replace("Z", "+00:00"))
                        assert instant.tzinfo
                        if abs((datetime.now(UTC) - instant).total_seconds()) < 120:
                            item = "<timestamp>"
                    checked[key] = clock(item)
                return checked
            return value

        results[label] = clock(observed)

    fixtures = ROOT / "fixtures"
    for folder, commands in [
        ("post-poc/baseline", ["baseline promote", "baseline review"]),
        ("post-poc/notifications", ["notify route", "notify deliver"]),
        ("post-poc/history", ["history-analytics", "history-materialize"]),
        ("platform/policy", ["policy explain"]),
        ("platform/plugin-sandbox", ["plugin run"]),
    ]:
        for fixture in sorted((fixtures / folder).glob("*/fixture.json")):
            for cmd in commands:
                args = ["platform", *cmd.split()]
                files = ["result.json"]
                if cmd in {"policy explain", "plugin run"}:
                    write("input.json", json.loads(fixture.read_text(encoding="utf-8"))["input"])
                    args.extend(["--policy" if cmd == "policy explain" else "--manifest", "input.json"])
                else:
                    data = json.loads(fixture.read_text(encoding="utf-8"))
                    data["input"].setdefault("created_at", "2002-01-02T03:04:05Z")
                    write("input.json", data)
                    args.extend(["--input", "input.json"])
                args.extend(["--out", "result.json"])
                if cmd == "history-materialize":
                    args.extend(["--manifest-out", "manifest.json"])
                    files.append("manifest.json")
                label = f"{cmd}/{fixture.parent.name}"
                run(label, args, files, {"created_at"} if folder.startswith("post-poc/") else ())
                if cmd == "history-materialize":
                    shutil.copyfile("manifest.json", "previous.json")
                    run(label + "/cached", args + ["--previous-manifest", "previous.json"], files, {"created_at"})

    finding = {"code": "test_failure", "severity": "high", "sourceRefs": ["case:évidence"]}
    report = {
        "record_type": "real-repo-evaluation-report", "repo_id": "demo", "suite_id": "unit",
        "run_id": "example", "overall_status": "hold", "current": {"record_count": 4, "runtime_ms": 5},
        "findings": [finding], "risk_debt": [finding], "manual_reviews": [finding],
        "sourceRefs": ["input:demo"]
    }
    write("reports/a.json", report)
    write("base.json", {**report, "overall_status": "pass", "current": {"record_count": 6}})
    write("corpus.json", {"entries": [{"repo_id": "demo", "suite_id": "unit", "expected_status": "hold"}]})
    for cmd in ["findings", "debt", "review", "assign", "score", "verdict", "triage", "report html"]:
        args = ["platform", *cmd.split(), "--input", "reports"]
        files = []
        if cmd == "verdict":
            args.extend(["--corpus", "corpus.json"])
        if cmd not in {"findings", "debt", "review"}:
            files = ["report.html" if cmd == "report html" else "result.json"]
            args.extend(["--out", files[0]])
        run(cmd, args, files, {"generated_at"} if cmd == "assign" else ())
    run("compare", ["platform", "compare", "--base", "base.json", "--head", "reports/a.json"])
    write("roster.json", {"repositories": [{"repo_id": "demo", "suites": [{"suite_id": "unit"}]}]})
    run("schedule", ["platform", "schedule", "--roster", "roster.json", "--history-store", "history"], clock_fields={"generated_at"})
    run("large schedule budgets", ["platform", "schedule", "--roster", "roster.json", "--history-store", "history",
        "--retry-limit", str(2**87), "--cache-ttl-hours", str(2**87)], clock_fields={"generated_at"})

    sample = json.loads((fixtures / "platform/plugin-sandbox/builtin-pass/fixture.json").read_text(encoding="utf-8"))["input"]
    sample.update(profile="default")
    sample["plugin"]["execution_mode"] = "subprocess_local"
    command = [str(Path(os.environ["SYSTEMROOT"]) / "System32/cmd.exe"), "/D", "/C", "echo {}"] if os.name == "nt" else ["/bin/echo", "{}"]
    sample["execution"] = {"command": command}
    write("plugin.json", sample)
    run("local plugin", ["platform", "plugin", "run", "--manifest", "plugin.json", "--allow-local-exec"])
    assert results["local plugin"]["stdout"]["execution_attempted"]

    write("bundle.json", {"metadata": {"runId": "run-example"}, "nodes": [{"title": "証跡", "weight": 1e-9}], "edges": []})
    write("ready/product-readiness-report.json", {"summary": {"overall_status": "pass"}})
    write("ready/enterprise-risk-debt-register.json", {"summary": {"open_count": 0}})
    ingest = ["store", "ingest", "--store", "store", "--bundle", "bundle.json", "--readiness", "ready"]
    run("store ingest", ingest)
    run("store reingest", ingest)
    run("store history", ["store", "history", "--store", "store"])
    for resource in ("run", "manifest", "history", "bundle", "risk-debt", "product-readiness"):
        run("query " + resource, ["store", "query", "--store", "store", "--resource", resource])
    write("bundle.json", {})
    results["missing run id"] = invoke(ingest, expected=1)
    write("bundle.json", [])
    results["array bundle"] = invoke(ingest, expected=1)
    Path("bundle.json").unlink()
    results["missing bundle"] = invoke(ingest, expected=2)
    entry = {"record_type": "real-repo-run-history-entry", "repo_id": "demo", "suite_id": "unit",
             "status": "pass", "started_at": "2025-02-01T12:00:00Z", "source_version": "one"}
    Path("history.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
    history_clock = {"ingested_at", "updated_at"}
    for number in range(2):
        run(f"history ingest {number}", ["real-repo", "history-ingest", "--history", "history.jsonl", "--store", "history"],
            ["history/run_history.jsonl", "history/history-index.json"], history_clock)
    for group, cmd in [("real-repo", "history-query"), ("platform", "history")]:
        run(group + " history query", [group, cmd, "--store", "history", "--repo-id", "demo", "--limit", "1"], clock_fields=history_clock)
    run("unbounded history limit", ["platform", "history", "--store", "history", "--limit", str(2**87)], clock_fields=history_clock)
    return results


def reference(args, expected=0):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        status = main(args)
    assert status == expected, (args, err.getvalue())
    if expected:
        return status, err.getvalue().strip()
    return json.loads(out.getvalue())


def verify(binary):
    def native(args, expected=0):
        process = subprocess.run([binary, *args], env={**os.environ, "PATH": ""}, encoding="utf-8", capture_output=True)
        assert process.returncode == expected, (args, process.stderr)
        if expected:
            return process.returncode, process.stderr.strip()
        return json.loads(process.stdout)

    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp), patch.dict(os.environ, HATE_BRIDGE_PROVIDER="compat-v0.2"):
        sandbox = Path("case")
        sandbox.mkdir()
        with contextlib.chdir(sandbox):
            expected = scenario(reference)
        shutil.rmtree(sandbox)
        sandbox.mkdir()
        with contextlib.chdir(sandbox):
            actual = scenario(native)
    mismatches = [(label, diff) for label, value in expected.items() if (diff := difference(value, actual[label]))]
    assert not mismatches, "\n".join(map(str, mismatches))
    print(f"{len(actual)} operation cases passed")


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve(strict=True))
