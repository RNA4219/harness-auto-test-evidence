from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install a wheel outside the repository and run core smoke checks.")
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    args = parser.parse_args(argv)

    wheel = args.wheel.resolve()
    fixture = args.fixture.resolve()
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable is required for wheel smoke")

    with tempfile.TemporaryDirectory(prefix="hate-wheel-smoke-") as raw:
        root = Path(raw)
        venv = root / "venv"
        _run([uv, "venv", str(venv)])
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        _run([uv, "pip", "install", "--python", str(python), str(wheel)])
        _run([str(python), "-m", "hate", "--help"], cwd=root)
        _run(
            [
                str(python),
                "-m",
                "hate",
                "p0a",
                "--input",
                str(fixture),
                "--out",
                str(root / "p0a-output"),
                "--source-version",
                "wheel-smoke",
            ],
            cwd=root,
        )
        _run(
            [
                str(python),
                "-c",
                "from hate.p0a_schema import _load_hate_schema; "
                "assert _load_hate_schema('run.schema.json')['title']",
            ],
            cwd=root,
        )
    return 0


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
