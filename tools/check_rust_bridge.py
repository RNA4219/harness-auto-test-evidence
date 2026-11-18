"""公開 Bridge CLI の依頼内容と受け取り結果を Python 版と比較する。"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from hate.bridge.routes import _ROUTES
from hate.cli import build_parser, main


def compare(binary, args, expect=0, before_native=None):
    with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
        reference_code = main(args)
    assert reference_code == expect, (args, reference_code, stderr.getvalue())
    if before_native is not None:
        before_native()
    native = subprocess.run([binary, *args], capture_output=True, encoding="utf-8", env={**os.environ, "PATH": ""})
    assert native.returncode == reference_code, (args, native.returncode, native.stderr)
    if expect == 0:
        assert json.loads(native.stdout) == json.loads(stdout.getvalue()), (args, native.stdout, stdout.getvalue())
        return json.loads(native.stdout)
    assert not native.stdout
    return None


def check(binary):
    parser = build_parser()
    Path("input").mkdir()
    Path("input/テスト!.txt").write_text("テスト", encoding="utf-8")
    Path("docs/process").mkdir(parents=True)
    Path("fixtures/expansion").mkdir(parents=True)
    for command in sorted(_ROUTES):
        child = parser
        args = command.split()
        for name in args:
            sub = next(a for a in child._actions if isinstance(a, argparse._SubParsersAction))
            child = sub.choices[name]
        args += ["--bridge-provider", "handoff"]
        for action in child._actions:
            if action.required:
                value = "out" if action.dest == "out" else (action.choices or ["input"])[0]
                args.extend([action.option_strings[0], value])
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            assert main(args) == 0, command
        path = Path(json.loads(stdout.getvalue())["bridge_request"])
        expected = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
        compare(binary, args)
        assert json.loads(path.read_text(encoding="utf-8")) == expected, command

    args = ["platform", "score", "--input", "input", "--out", "out.json", "--bridge-provider", "handoff"]
    info = compare(binary, args)
    path = Path(info["bridge_request"])
    request = json.loads(path.read_text(encoding="utf-8"))
    content = b"test artifact"
    Path("artifact.bin").write_bytes(content)
    result = {
        "schema_version": "HATE-bridge/v1", "record_type": "bridge_result",
        "bridge_id": request["bridge_id"], "owner": request["owner"], "sourceRefs": request["sourceRefs"],
        "status": "completed", "diagnostics": [],
        "output_refs": [{"record_type": request["expected_output_types"][0], "path": "artifact.bin",
                         "target_name": "restored.bin", "sha256": hashlib.sha256(content).hexdigest()}],
    }
    output = Path("result.json")
    output.write_text(json.dumps(result), encoding="utf-8")
    args = ["bridge", "materialize", "--request", str(path), "--result", str(output), "--out", "restored"]
    compare(binary, args, before_native=lambda: Path("restored/restored.bin").unlink())
    assert Path("restored/restored.bin").read_bytes() == content
    result["output_refs"][0]["sha256"] = "0" * 64
    output.write_text(json.dumps(result), encoding="utf-8")
    compare(binary, args, 2)
    assert Path("restored/restored.bin").read_bytes() == content
    result["output_refs"][0]["sha256"] = hashlib.sha256(content).hexdigest()
    result["output_refs"][0]["target_name"] = "Straße.bin"
    result["output_refs"].append({**result["output_refs"][0], "target_name": "STRASSE.bin"})
    output.write_text(json.dumps(result), encoding="utf-8")
    compare(binary, args, 2)
    assert not Path("restored/Straße.bin").exists()


if __name__ == "__main__":
    binary = str(Path(sys.argv[1]).resolve(strict=True))
    with tempfile.TemporaryDirectory() as temporary, contextlib.chdir(temporary), patch.dict(os.environ, HATE_BRIDGE_PROVIDER=""):
        check(binary)
    print(f"{len(_ROUTES)} handoff commands and bridge materialization passed")
