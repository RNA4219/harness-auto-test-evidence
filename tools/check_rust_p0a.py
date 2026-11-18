"""P0a の公開 CLI を既存 fixture で実行し、Python 版と Rust 版の成果物を照合する。"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from hate.cli import main


def read_artifacts(directory):
    values = {}
    for path in directory.iterdir():
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".ndjson":
            values[path.name] = [json.loads(line) for line in content.splitlines()]
        elif path.suffix in {".json", ".sarif"}:
            values[path.name] = json.loads(content)
        else:
            values[path.name] = content
    return values


def difference(before, after, loc=""):
    if isinstance(before, dict) and isinstance(after, dict):
        if set(before) != set(after):
            return loc, set(before) ^ set(after)
        for key in sorted(before, key=lambda k: (k == "sha256", k)):
            if before[key] != after[key]:
                return difference(before[key], after[key], f"{loc}/{key}")
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        for index, (left, right) in enumerate(zip(before, after, strict=True)):
            if left != right:
                return difference(left, right, f"{loc}/{index}")
    return loc, before, after


def check(binary, source, profile):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = root / "run"
        args = ["p0a", "--input", str(source), "--out", str(out), "--profile", profile, "--fixture-path-prefix", "example"]
        with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            reference = main(args)
        previous = root / "reference"
        if out.exists():
            out.rename(previous)
        result = subprocess.run([binary, *args], capture_output=True, encoding="utf-8", env={**os.environ, "PATH": ""})
        assert result.returncode == reference, (reference, result.returncode, result.stderr[:300])
        if previous.exists():
            before, after = read_artifacts(previous), read_artifacts(out)
            assert before == after, difference(before, after)
        else:
            assert not out.exists()
        if reference == 0:
            assert json.loads(stdout.getvalue()) == json.loads(result.stdout)
            assert result.stderr == stderr.getvalue()
        elif reference == 2:
            assert json.loads(stderr.getvalue()) == json.loads(result.stderr)
            assert not result.stdout
        else:
            assert not result.stdout
            assert result.stderr.startswith("HATE-E-CLI:")


def check_artifact_references(binary):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "input"
        shutil.copytree("fixtures/golden/p0a-minimal/input", root)
        (root / "nested").mkdir()
        outside = root.parent / "external.txt"
        outside.write_text("local test evidence", encoding="utf-8")
        refs = ["../external.txt", str(outside), "nested/../github-context.json", "../missing.txt"]
        if os.name != "nt":
            (root / "link.txt").symlink_to(outside)
            refs.append("link.txt")
        entries = [{"artifact_id": f"artifact-{index}", "path": ref} for index, ref in enumerate(refs)]
        (root / "artifact-refs.json").write_text(json.dumps({"artifacts": entries}), encoding="utf-8")
        check(binary, root, "default")


def check_large_integer_inputs(binary):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "input"
        shutil.copytree("fixtures/golden/p0a-minimal/input", root)
        ctx = root / "github-context.json"
        data = json.loads(ctx.read_text(encoding="utf-8"))
        data["run_id"] = 2**64 + 5
        data["run_attempt"] = "ATTEMPT"
        ctx.write_text(json.dumps(data).replace('"ATTEMPT"', "184467440737095516170e-1"), encoding="utf-8")
        (root / "pytest-report.json").write_text(
            '{"tests":[{"nodeid":"src/a.py::a","outcome":"passed","attempt_index":18446744073709551617,'
            '"duration":18446744073709551.617,"matrix":{"big":18446744073709551619,"small":1.00e-7}}]}',
            encoding="utf-8",
        )
        check(binary, root, "default")


def check_combined_input(binary):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "input"
        shutil.copytree("fixtures/golden/p0a-minimal/input", root)
        test_id = "junit:tests/test_auth.py::test_login"
        (root / "run-history.jsonl").write_text(
            "\n".join(json.dumps({"tests": [{"test_id": test_id, "status": s}]}) for s in ["pass", "fail", "pass"]),
            encoding="utf-8",
        )
        (root / "stryker-report.json").write_text(json.dumps({"mutants": [
            {"id": "1", "file": "src/auth.py", "line": 9, "status": "Killed", "killedBy": [test_id]},
            {"id": "2", "file": "src/auth.py", "line": 10, "status": "Survived", "coveredBy": [test_id]},
        ]}), encoding="utf-8")
        (root / "results.sarif").write_text(json.dumps({"version": "2.1.0", "runs": [
            {"results": [{"properties": {"severity": "critical"}}]},
        ]}), encoding="utf-8")
        check(binary, root, "strict")
        (root / "pytest-report.json").write_text(
            '{"tests":[{"nodeid":"src/a.py::a","outcome":"xpassed","attempt_index":0,'
            '"call":{"duration":0.00050000000000000001},"matrix":{"v":1e-8}}]}', encoding="utf-8",
        )
        check(binary, root, "default")


if __name__ == "__main__":
    binary = str(Path(sys.argv[1]).resolve(strict=True))
    golden = Path("fixtures/golden/p0a-minimal")
    sources = sorted({p.parent for folder in (golden, Path("fixtures/adapters"))
                      for p in folder.rglob("*context.json") if p.name in {"github-context.json", "ci-context.json", "generic-ci-context.json"}})
    cases = [(s, "default") for s in sources]
    cases.extend((Path("fixtures/adapters/artifacts/secret"), p) for p in ("strict", "release", "experimental"))
    if len(sys.argv) > 2:
        cases = [(s, p) for s, p in cases if any(k in str(s) for k in sys.argv[2:])]
    failures = []
    for source, profile in cases:
        try:
            check(binary, source, profile)
        except (AssertionError, OSError, ValueError) as exc:
            failures.append((str(source), profile, str(exc)[:750]))
    for failure in failures:
        print(*failure)
    if len(sys.argv) == 2:
        check_combined_input(binary)
        check_artifact_references(binary)
        check_large_integer_inputs(binary)
        print("History, mutation, SARIF and precise numeric input comparisons passed")
        print("Local artifact reference comparison passed")
        print("Large integer and canonical hash comparison passed")
    print(f"{len(cases) - len(failures)}/{len(cases)} P0a fixture cases passed")
    sys.exit(bool(failures))
