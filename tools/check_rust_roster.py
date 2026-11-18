"""Python版とRust版で同じロスターを実行し、実行時間と環境情報以外の証跡を比較する。"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from check_rust_p0a import difference

from hate.cli import main


def command(message, exit_code=0):
    if os.name == "nt":
        return [os.environ["COMSPEC"], "/D", "/C", f"echo {message} & exit /b {exit_code}"]
    return ["/bin/sh", "-c", 'printf "%s\\n" "$1"; exit "$2"', "suite", message, str(exit_code)]


def stable(data):
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in {"started_at", "finished_at", "runtime_ms", "duration_ms", "python", "rust_binary_version"}:
                continue
            if key == "cleanup_method" and data.get("cleanup_attempted") and value != "per_split":
                result[key] = "process-tree"
            else:
                result[key] = stable(value)
        return result
    if isinstance(data, list):
        return [stable(item) for item in data]
    return data


def artifacts(path):
    values = {}
    for p in path.iterdir():
        text = p.read_text(encoding="utf8")
        if p.suffix == ".jsonl":
            values[p.name] = [json.loads(line) for line in text.splitlines()]
        else:
            values[p.name] = json.loads(text)
    return stable(values)


def check(binary, root, name, roster, command_name):
    path = root / f"{name}.json"
    path.write_text(json.dumps(roster, ensure_ascii=False), encoding="utf-8")
    out = root / f"{name}-out"
    args = [*command_name.split(), "--roster", str(path), "--out", str(out), "--source-version", "acceptance"]
    with contextlib.redirect_stdout(io.StringIO()) as captured, contextlib.redirect_stderr(io.StringIO()):
        code = main(args)
    reference = out.with_name(out.name + "-python")
    if out.exists():
        out.rename(reference)
    native = subprocess.run([binary, *args], env={**os.environ, "PATH": "", "HATE_BRIDGE_PROVIDER": "compat-v0.2"},
                            capture_output=True, encoding="utf8", timeout=60)
    assert native.returncode == code, (name, code, native.returncode, native.stderr)
    if code:
        assert not out.exists()
        return
    before = stable(json.loads(captured.getvalue()))
    after = stable(json.loads(native.stdout))
    assert before == after, (name, difference(before, after))
    expected = artifacts(reference)
    actual = artifacts(out)
    assert expected.keys() == actual.keys(), (name, expected.keys(), actual.keys())
    for filename, value in expected.items():
        assert value == actual[filename], (name, filename, difference(value, actual[filename]))


if __name__ == "__main__":
    binary = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        yes = command("3 passed in 0.1s")
        no = command("1 failed, 2 passed in 0.1s", 1)
        prefix = {"repo_id": "alpha", "path": ".", "ownership_scope": "owned", "repo_class": "small"}
        case = {"name": "suite", "command": yes}
        check(binary, root, "legacy", {"repositories": [case, {**case, "name": "failing", "command": no},
                                                       {"name": "absent-cmd"}]}, "real-repo run")
        check(binary, root, "v2", {"record_type": "real-repo-roster-v2", "repositories": [{**prefix, "suites": [
            {"suite_id": "smoke", "suite_kind": "smoke", "command": yes, "bootstrap_command": yes},
            {"suite_id": "blocked", "suite_kind": "lint", "command": yes, "bootstrap_command": no},
            {"suite_id": "split", "suite_kind": "package-split", "command": yes, "split_commands": [yes, yes, no],
             "completed_splits": ["1"], "resume_token": "previous"},
        ]}]}, "platform run")
        check(binary, root, "bad", {"record_type": "real-repo-roster-v2", "repositories": [{**prefix, "suites": []}]}, "real-repo run")
        if os.name == "nt":
            ping = Path(os.environ["SystemRoot"]) / "System32/ping.exe"
            sleeper = [os.environ["COMSPEC"], "/D", "/C", f"{ping} -n 5 127.0.0.1 >nul"]
        else:
            sleeper = [shutil.which("sleep") or "/bin/sleep", "5"]
        check(binary, root, "timeout", {"repositories": [{"name": "slow", "command": sleeper, "timeout_ms": 150,
                                                           "runtime_budget_ms": 20000}]}, "real-repo run")
    print("4 roster comparisons passed (legacy, v2, invalid, timeout)")
