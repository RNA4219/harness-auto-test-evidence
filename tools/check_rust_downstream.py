"""後続帳票の CLI・HTTP 互換性をテストする。引数はビルド済み hate のパス。"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from hate.p2p3 import make_product_read_model_handler

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "fixtures/golden"
QEG = GOLDEN / "p0b-qeg-minimal/expected"
TRUST = GOLDEN / "p1a-trust-minimal/expected"
WORKFLOW = GOLDEN / "p1b-workflow-minimal/expected"
READY = GOLDEN / "p2p3-product-readiness-minimal/expected"
CYCLES = ROOT / "fixtures/validation-cycles/ten-cycle-go/fixture.json"


def normalize(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "generated_at" and isinstance(item, str) and item.endswith("Z"):
                instant = datetime.fromisoformat(item.replace("Z", "+00:00"))
                if abs((datetime.now(UTC) - instant).total_seconds()) < 120:
                    item = "<current UTC>"
            result[key] = normalize(item)
        return result
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            content = json.loads(content)
        elif path.suffix == ".jsonl":
            content = [json.loads(row) for row in content.splitlines()]
        result[path.relative_to(root).as_posix()] = normalize(content)
    return result


def expect_equal(label, expected, actual):
    if type(expected) is not type(actual):
        raise AssertionError(f"{label}: {type(expected).__name__} != {type(actual).__name__}")
    if isinstance(expected, dict):
        assert expected.keys() == actual.keys(), (label, expected.keys() ^ actual.keys())
        for key in expected:
            expect_equal(f"{label}/{key}", expected[key], actual[key])
    elif isinstance(expected, list):
        assert len(expected) == len(actual), (label, len(expected), len(actual))
        for i, (left, right) in enumerate(zip(expected, actual, strict=True)):
            expect_equal(f"{label}/{i}", left, right)
    else:
        assert expected == actual, (label, expected, actual)


def response_line(stream):
    if not stream.strip():
        return None
    line = stream.strip().splitlines()[-1]
    try:
        return normalize(json.loads(line))
    except json.JSONDecodeError:
        return line


def check_cli(binary, work, label, args):
    out = work / "out"
    if args[:2] != ["product", "query"]:
        args = [*args, "--out", out]
    args = list(map(str, args))
    reference = subprocess.run(
        [sys.executable, "-m", "hate", *args],
        cwd=work,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        encoding="utf-8",
        timeout=90,
    )
    expected = snapshot(out)
    if out.exists():
        shutil.rmtree(out)
    native = subprocess.run(
        [str(binary), *args],
        cwd=work,
        env={**os.environ, "PATH": ""},
        capture_output=True,
        encoding="utf-8",
        timeout=90,
    )
    assert native.returncode == reference.returncode, (label, reference.stderr, native.stderr)
    expect_equal(label, response_line(reference.stdout), response_line(native.stdout))
    expect_equal(label, response_line(reference.stderr), response_line(native.stderr))
    expect_equal(label, expected, snapshot(out))
    if out.exists():
        shutil.rmtree(out)
    print(f"{label} OK ({len(expected)} files)")


def get(port, path):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        return [response.status, response.getheader("Content-Type"), json.loads(response.read())]
    finally:
        conn.close()


def check_servers(binary, work):
    paths = [
        "/",
        "/v1/product-readiness?filter.status=hold&request_id=http-1",
        "/v1/risk-debt?role=auditor&filter.status=open&cursor=2&stale_cache=TRUE",
        "/v1/artifacts?role=viewer",
        "/v1/missing",
        "/v1/runs?role=invalid",
    ]
    with ThreadingHTTPServer(("127.0.0.1", 0), make_product_read_model_handler(READY)) as reference:
        thread = threading.Thread(target=reference.serve_forever)
        thread.start()
        try:
            expected = [get(reference.server_port, path) for path in paths]
        finally:
            reference.shutdown()
            thread.join()
    assert [r[0] for r in expected] == [200, 200, 200, 403, 404, 403]
    for alias in ("product", "platform"):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        with subprocess.Popen(
            [str(binary), alias, "serve", "--readiness", str(READY), "--host", "127.0.0.1", "--port", str(port)],
            cwd=work,
            env={**os.environ, "PATH": ""},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as server:
            try:
                deadline = time.monotonic() + 10
                while True:
                    try:
                        first = get(port, paths[0])
                        break
                    except ConnectionRefusedError:
                        if server.poll() is not None or time.monotonic() >= deadline:
                            raise
                        time.sleep(0.05)
                actual = [first, *(get(port, path) for path in paths[1:])]
                expect_equal(f"{alias} serve", expected, actual)
            finally:
                server.terminate()
                server.wait(timeout=5)
        print(f"{alias} serve OK ({len(paths)} HTTP requests)")


def check(binary):
    with tempfile.TemporaryDirectory(prefix="hate-downstream-") as temp:
        work = Path(temp).resolve()
        isolated = work / "input"
        empty_docs = isolated / "docs/process"
        empty_docs.mkdir(parents=True)
        invalid = work / "incomplete.json"
        invalid.write_text(json.dumps({"fixture_id": "日本語", "input": {"cycles": [{}]}}), encoding="utf-8")
        q = ["product", "query", "--readiness", READY]
        release = ["release", "candidate", "--readiness", READY]
        scenarios = {
            "workflow": [
                "workflow",
                "map",
                "--bundle",
                QEG / "qeg-bundle.json",
                "--report",
                QEG / "qeg-export-report.json",
                "--trust",
                TRUST,
            ],
            "readiness": [
                "product",
                "readiness",
                "--bundle",
                QEG / "qeg-bundle.json",
                "--trust",
                TRUST,
                "--workflow",
                WORKFLOW,
            ],
            "grade": ["product", "grade-reports", "--docs-root", ROOT / "docs/process"],
            "release": [*release, "--dry-run"],
            "blocked release": release,
            "validation": ["validation", "cycles", "--fixture", CYCLES],
            "blocked validation": ["validation", "cycles", "--fixture", invalid],
            "expansion": ["expansion", "run", "--fixtures-root", ROOT / "fixtures/expansion", "--case-kind", "all"],
            "gap": ["gap", "closure", "--repo-root", ROOT],
            "missing gap ledger": ["gap", "closure", "--repo-root", isolated],
            "grade empty checkout": ["product", "grade-reports", "--docs-root", empty_docs],
            "filtered query": [*q, "--resource", "risk-debt", "--filter", "status=open"],
            "forbidden query": [*q, "--resource", "artifacts", "--role", "viewer"],
        }
        original = Path.cwd()
        try:
            os.chdir(work)
            for label, args in scenarios.items():
                check_cli(binary, work, label, args)
            check_servers(binary, work)
        finally:
            os.chdir(original)


if __name__ == "__main__":
    check(Path(sys.argv[1]).resolve())
