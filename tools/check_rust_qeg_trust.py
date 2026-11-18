"""QEG / AETE の Rust バイナリを Python 参照実装と比較する。"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from hate.cli import main

ROOT = Path(__file__).resolve().parents[1]


def snapshot(out):
    results = {}
    for path in out.iterdir() if out.is_dir() else []:
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".jsonl":
            value = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        else:
            value = path.read_text(encoding="utf-8")
        results[path.name] = value
    return results


def difference(left, right, key="$"):
    if left == right:
        return None
    if isinstance(left, dict) and isinstance(right, dict):
        for name in sorted(set(left) | set(right)):
            if name not in left or name not in right:
                return key, name, "field absent"
            if result := difference(left[name], right[name], f"{key}.{name}"):
                return result
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        for i, (a, b) in enumerate(zip(left, right, strict=True)):
            if result := difference(a, b, f"{key}[{i}]"):
                return result
    return key, str(left)[:280], str(right)[:280]


def check(binary, args, dest, expected=0):
    native_dir = dest / "rust"
    reference_dir = dest / "reference"
    opts = [*map(str, args), "--out"]
    with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
        exit_code = main([*opts, str(reference_dir)])
    assert exit_code == expected, (args[:2], stderr.getvalue()[:300])
    env = {**os.environ, "PATH": ""}
    native = subprocess.run([binary, *opts, str(native_dir)], text=True, encoding="utf-8", capture_output=True, env=env)
    assert native.returncode == exit_code, (args[:2], native.returncode, native.stderr[:500])
    if exit_code == 0:
        response = json.loads(stdout.getvalue())
        if "out_dir" in response:
            response["out_dir"] = str(native_dir)
        actual = json.loads(native.stdout)
        assert actual == response, (args[:2], difference(response, actual))
    else:
        diagnostic = stderr.getvalue().strip()
        assert bool(native.stderr) and not native.stdout
        if diagnostic.startswith("{"):
            assert json.loads(native.stderr) == json.loads(diagnostic)
        else:
            assert native.stderr.split(":", 1)[0] == diagnostic.split(":", 1)[0]
    diff = difference(snapshot(reference_dir), snapshot(native_dir))
    assert diff is None, (args[:2], diff)
    return reference_dir


def verify_export(binary, tmp, source):
    short = shutil.copytree(source, tmp / "partial-input")
    test_rows = short / "p0a/HATE-test-results.ndjson"
    row = json.loads(test_rows.read_text(encoding="utf-8").splitlines()[0])
    retry = {**row, "record_id": "retry-1", "payload": {**row["payload"], "attempt_index": 1}}
    row["payload"].update(status="failed", retry_index=0)
    test_rows.write_text("".join(json.dumps(r) + "\n" for r in [row, retry]), encoding="utf-8")
    (short / "risk-debt-lifecycle.json").write_text(
        '{"items":[{"debt_id":"historical","age_days":9007199254740993.0,"status":"stale"}]}',
        encoding="utf-8",
    )
    (short / "escaped-defects.csv").write_text(
        "id,release,severity,requirements\nincident-1,qeg:v1,critical,rand:auth\n", encoding="utf-8"
    )
    contracts = {"contract_id": "pact-1", "consumer": "app", "provider": "backend", "status": "failed"}
    mutation = {"mutation_id": "mutant-1", "status": "survived", "covered_by_tests": ["test-login"]}
    strength = {"test_id": row["payload"]["canonical_test_id"], "flake_score": 0.125, "sample_size": 8}
    for name, payload in [("contract", contracts), ("mutation", mutation), ("evidence-strength", strength)]:
        (short / f"p0a/HATE-{name}.ndjson").write_text(json.dumps({**row, "payload": payload}) + "\n", encoding="utf-8")
    diff_path = short / "diff-risk-test.json"
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    obligation = diff["test_obligations"][0]
    obligation["required_evidence_kinds"] += ["contract", "mutation"]
    obligation.update(required_contract_refs=["pact-1"], required_mutation_refs=["mutant-1"])
    diff_path.write_text(json.dumps(diff), encoding="utf-8")
    sarif_result = {
        "ruleId": "no-empty",
        "level": "warning",
        "message": {"text": "Empty block"},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/auth.py"}, "region": {"startLine": 12}}}],
    }
    (short / "p0a/HATE-static.sarif").write_text(json.dumps({"runs": [{"results": [sarif_result]}]}), encoding="utf-8")
    ref = check(binary, ["export", "qeg", "--fixture", short], tmp / "partial")
    check(
        binary,
        ["trust", "evaluate", "--bundle", ref / "qeg-bundle.json", "--report", ref / "qeg-export-report.json"],
        tmp / "partial-trust",
    )
    check(
        binary,
        [
            "explain",
            "--mode",
            "why-soft-gap",
            "--bundle",
            ref / "qeg-bundle.json",
            "--report",
            ref / "qeg-export-report.json",
        ],
        tmp / "partial-explain",
    )
    check(
        binary,
        ["recommend", "--gap", "all", "--bundle", ref / "qeg-bundle.json", "--report", ref / "qeg-export-report.json"],
        tmp / "partial-recommend",
    )
    pre = short / "p0a/precheck-decision.json"
    record = json.loads(pre.read_text(encoding="utf-8"))
    record["payload"].update(decision="hard_dq", qeg_export_allowed=False, exit_code=2)
    pre.write_text(json.dumps(record), encoding="utf-8")
    check(binary, ["export", "qeg", "--fixture", short], tmp / "denied", 2)
    pre.write_text(json.dumps(record).replace('"exit_code": 2', '"exit_code": 2.00000000000000001'), encoding="utf-8")
    check(binary, ["export", "qeg", "--fixture", short], tmp / "precision", 1)


def verify_large_counts(binary, tmp, source):
    fixture = shutil.copytree(source, tmp / "large-count-input")
    # Include the first unsigned-only 64-bit value, then values beyond both 64 and 128 bits.
    run_attempt = 2**64 + 1
    retry_index = 2**63
    shard_index = 2**130 + 4
    shard_total = shard_index + 3
    age = 10**350 + 7
    for path in (fixture / "p0a").iterdir():
        if path.suffix == ".ndjson":
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            if path.name == "HATE-test-results.ndjson":
                records = records[:1]
                records[0]["payload"].update(
                    attempt_index=retry_index,
                    retry_count=retry_index + 1,
                    shard_count=shard_total,
                    shard_index=shard_index,
                )
            for record in records:
                record["run_attempt"] = run_attempt
            path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        elif path.suffix == ".json":
            record = json.loads(path.read_text(encoding="utf-8"))
            if "run_attempt" in record:
                record["run_attempt"] = run_attempt
            ci = record.get("payload", {}).get("ci", {})
            if "run_attempt" in ci:
                ci["run_attempt"] = run_attempt
            content = json.dumps(record).replace(f'"run_attempt": {run_attempt}', f'"run_attempt": {run_attempt}.00')
            path.write_text(content, encoding="utf-8")
    (fixture / "risk-debt-lifecycle.json").write_text(
        json.dumps({"items": [{"debt_id": "older", "age_days": age}]}), encoding="utf-8"
    )
    diff_path = fixture / "diff-risk-test.json"
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    changed = diff["changed_entities"][0]
    changed["ranges"] = [{"start_line": shard_index, "end_line": shard_index + 4}]
    diff_path.write_text(json.dumps(diff), encoding="utf-8")
    location = {
        "physicalLocation": {"artifactLocation": {"uri": changed["path"]}, "region": {"startLine": shard_index + 1}}
    }
    (fixture / "p0a/HATE-static.sarif").write_text(
        json.dumps({"runs": [{"results": [{"ruleId": "example", "locations": [location]}]}]}), encoding="utf-8"
    )
    reference = check(binary, ["export", "qeg", "--fixture", fixture], tmp / "large-export")
    report = check(
        binary,
        ["replay", "--bundle", reference / "qeg-bundle.json", "--report", reference / "qeg-export-report.json"],
        tmp / "large-replay",
    )
    rows = json.loads((report / "retry-aggregation.json").read_text(encoding="utf-8"))["aggregates"]
    assert rows[0]["shards"]["expected_count"] == shard_total
    changed_report = shutil.copytree(report, tmp / "large-compare-head")
    for filename, key in [("doctor-report.json", "finding_count"), ("retry-aggregation.json", "aggregate_count")]:
        path = changed_report / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        data["summary"][key] = shard_total
        path.write_text(json.dumps(data), encoding="utf-8")
    check(binary, ["compare", "--base", report, "--head", changed_report], tmp / "large-compare")
    assert (
        next(item["missing_count"] for item in rows[0]["issues"] if item["issue"] == "missing_shards")
        == shard_total - 1
    )


def verify(binary, tmp, trust_only):
    bundle = ROOT / "fixtures/golden/p0b-qeg-minimal/expected"
    pair = ["--bundle", bundle / "qeg-bundle.json", "--report", bundle / "qeg-export-report.json"]
    source = ROOT / "fixtures/golden/p0b-qeg-minimal/input"
    if not trust_only:
        check(binary, ["export", "qeg", "--fixture", source], tmp / "export")
        check(binary, ["export", "qeg", "--fixture", tmp / "missing"], tmp / "invalid-export", 2)
        verify_export(binary, tmp, source)
        verify_large_counts(binary, tmp, source)
    trust = check(binary, ["trust", "evaluate", *pair], tmp / "eval")
    check(binary, ["replay", *pair], tmp / "replay")
    check(binary, ["compare", "--base", trust, "--head", trust], tmp / "compare")
    score_path = trust / "aete-score.json"
    score = json.loads(score_path.read_text(encoding="utf-8"))
    corrupted = tmp / "corrupt-score"
    corrupted.mkdir()
    raw = json.dumps({**score, "weighted_score": "TOKEN"})
    (corrupted / score_path.name).write_text(
        raw.replace('"TOKEN"', f"{score['weighted_score']}00000000000000001"), encoding="utf-8"
    )
    check(binary, ["compare", "--base", trust, "--head", corrupted], tmp / "invalid-compare", 1)
    check(binary, ["doctor", *pair], tmp / "doctor")
    for mode in ["why-soft-gap", "why-excluded", "why-score-changed"]:
        check(binary, ["explain", *pair, "--mode", mode], tmp / mode)
    check(binary, ["recommend", *pair, "--gap", "all"], tmp / "recommend")
    altered = json.loads((bundle / "qeg-bundle.json").read_text(encoding="utf-8"))
    altered["metadata"]["debugOnly"] = True
    node = next(node for node in altered["nodes"] if node["kind"] == "gate_verdict")
    node["data"].update(
        decision="conditional", qeg_export_allowed=False, exit_code=2, soft_gaps=[{"message": "baseline missing"}]
    )
    altered_path = tmp / "restricted-bundle.json"
    altered_path.write_text(json.dumps(altered), encoding="utf-8")
    restricted = ["--bundle", altered_path, *pair[2:]]
    for command in [["doctor"], ["explain", "--mode", "why-excluded"], ["recommend", "--gap", "all"]]:
        check(binary, [*command, *restricted], tmp / f"restricted-{command[0]}")
    mismatch = json.loads((bundle / "qeg-export-report.json").read_text(encoding="utf-8"))
    mismatch["run_id"] = "different-run"
    invalid = tmp / "different.json"
    invalid.write_text(json.dumps(mismatch), encoding="utf-8")
    check(binary, ["recommend", *pair[:2], "--report", invalid], tmp / "invalid", 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--trust-only", action="store_true")
    options = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        verify(options.binary.resolve(strict=True), Path(temporary), options.trust_only)
    print("QEG / AETE parity checks passed")
