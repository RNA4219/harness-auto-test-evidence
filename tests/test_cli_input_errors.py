"""入力不備とI/O失敗を、CLIの診断・終了コードへ変換する回帰テスト。"""

from __future__ import annotations

import errno
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hate import cli
from hate.p0a import PrecheckError, generate_p0a
from hate.p1a import TrustError, evaluate_trust, explain_trust, replay_trust

P0A_INPUT = Path("fixtures/golden/p0a-minimal/input")
TRUST_INPUT = Path("fixtures/golden/p0b-qeg-minimal/expected")
INVALID_INPUTS = [b"{", b"\xff", b"[]", None]


def _bad_input(path: Path, content: bytes | None) -> None:
    if content is None:
        path.unlink(missing_ok=True)
        path.mkdir()
    else:
        path.write_bytes(content)


@pytest.mark.parametrize("operation", [evaluate_trust, replay_trust])
@pytest.mark.parametrize("missing", ["bundle", "report"])
def test_trust_missing_required_input_keeps_domain_error(operation, missing: str, tmp_path: Path) -> None:
    bundle = TRUST_INPUT / "qeg-bundle.json"
    report = TRUST_INPUT / "qeg-export-report.json"
    absent = tmp_path / f"missing-{missing}.json"
    with pytest.raises(TrustError) as caught:
        operation(absent if missing == "bundle" else bundle,
                  absent if missing == "report" else report, tmp_path / "out")
    assert caught.value.exit_code == 2
    assert str(absent) in str(caught.value)
    assert not (tmp_path / "out").exists()


def test_unsupported_explain_mode_returns_trust_error(tmp_path: Path) -> None:
    with pytest.raises(TrustError, match="unsupported explain mode") as caught:
        explain_trust(TRUST_INPUT / "qeg-bundle.json", TRUST_INPUT / "qeg-export-report.json",
                      tmp_path / "out", mode="invalid-mode")
    assert caught.value.exit_code == 1


@pytest.mark.parametrize("filename", [
    "github-context.json", "record-control.json", "dq-control.json",
    "artifact-refs.json", "evidence-strength-config.json",
])
@pytest.mark.parametrize("content", INVALID_INPUTS, ids=["syntax", "utf8", "array", "directory"])
def test_p0a_bad_json_is_a_diagnosed_input_error(
    filename: str, content: bytes | None, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "input"
    shutil.copytree(P0A_INPUT, source)
    _bad_input(source / filename, content)
    out = tmp_path / "out"
    with pytest.raises(PrecheckError) as caught:
        generate_p0a(source, out)
    assert caught.value.exit_code == 1
    assert filename in str(caught.value)
    assert cli.main(["p0a", "--input", str(source), "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HATE-E-CLI:" in captured.err and filename in captured.err
    assert not out.exists()


@pytest.mark.parametrize("filename", ["qeg-bundle.json", "qeg-export-report.json"])
@pytest.mark.parametrize("content", INVALID_INPUTS, ids=["syntax", "utf8", "array", "directory"])
def test_trust_bad_json_is_a_diagnosed_input_error(
    filename: str, content: bytes | None, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "input"
    shutil.copytree(TRUST_INPUT, source)
    _bad_input(source / filename, content)
    bundle, report, out = source / "qeg-bundle.json", source / "qeg-export-report.json", tmp_path / "out"
    with pytest.raises(TrustError) as caught:
        evaluate_trust(bundle, report, out)
    assert caught.value.exit_code == 1
    assert filename in str(caught.value)
    assert cli.main(["trust", "evaluate", "--bundle", str(bundle), "--report", str(report),
                     "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HATE-E-TRUST:" in captured.err and filename in captured.err
    assert not out.exists()


@pytest.mark.parametrize(("command", "code", "prefix"), [
    (["trust", "evaluate"], 2, "TRUST"), (["replay"], 2, "REPLAY"),
    (["doctor"], 1, "DOCTOR"), (["explain"], 1, "EXPLAIN"),
    (["recommend"], 1, "RECOMMEND"), (["compare"], 1, "COMPARE"),
])
def test_trust_cli_missing_input_preserves_command_diagnostic(
    command: list[str], code: int, prefix: str, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    absent = str(tmp_path / "missing")
    options = ["--base", absent, "--head", absent] if command == ["compare"] else [
        "--bundle", absent, "--report", absent,
    ]
    assert cli.main([*command, *options, "--out", str(tmp_path / "out")]) == code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"HATE-E-{prefix}:" in captured.err and absent in captured.err


def _command(engine: str, out: Path) -> list[str]:
    if engine == "p0a":
        return ["p0a", "--input", str(P0A_INPUT), "--out", str(out)]
    if engine == "export":
        return ["export", "qeg", "--fixture", "fixtures/golden/p0b-qeg-minimal/input", "--out", str(out)]
    return ["trust", "evaluate", "--bundle", str(TRUST_INPUT / "qeg-bundle.json"),
            "--report", str(TRUST_INPUT / "qeg-export-report.json"), "--out", str(out)]


@pytest.mark.parametrize("engine", ["p0a", "trust", "export"])
def test_output_file_is_not_replaced_when_a_directory_is_required(
    engine: str, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "existing-output"
    out.write_bytes(b"preserve existing output")
    assert cli.main(_command(engine, out)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HATE-E-CLI:" in captured.err
    assert str(out) in captured.err.replace("\\\\", "\\")
    assert out.read_bytes() == b"preserve existing output"


@pytest.mark.parametrize("engine", ["p0a", "trust", "export"])
def test_output_write_failure_returns_io_diagnostic(
    engine: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "output"
    original = Path.write_text

    def fail_output(path: Path, *args, **kwargs):
        if path.is_relative_to(out):
            raise OSError(errno.ENOSPC, "no space left on device", str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_output)
    assert cli.main(_command(engine, out)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HATE-E-CLI:" in captured.err and "no space left" in captured.err
    assert str(out) in captured.err.replace("\\\\", "\\")


@pytest.mark.parametrize("engine", ["p0a", "trust"])
def test_unreadable_json_preserves_original_cause(
    engine: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    target = (P0A_INPUT / "github-context.json" if engine == "p0a" else TRUST_INPUT / "qeg-bundle.json").resolve()
    original = Path.open

    def deny_input(path: Path, *args, **kwargs):
        if path.resolve() == target:
            raise PermissionError(errno.EACCES, "access denied", str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_input)
    error_type = PrecheckError if engine == "p0a" else TrustError
    with pytest.raises(error_type) as caught:
        if engine == "p0a":
            generate_p0a(P0A_INPUT, tmp_path / "out")
        else:
            evaluate_trust(target, TRUST_INPUT / "qeg-export-report.json", tmp_path / "out")
    assert isinstance(caught.value.__cause__, PermissionError)
    assert cli.main(_command(engine, tmp_path / "out")) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "access denied" in captured.err and target.name in captured.err


@pytest.mark.parametrize("failure", [ValueError("internal value failure"), RuntimeError("internal failure")])
def test_cli_does_not_hide_programming_errors(failure: Exception, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_dispatch(*args):
        raise failure

    monkeypatch.setattr(cli, "dispatch_cli", broken_dispatch)
    with pytest.raises(type(failure), match=str(failure)):
        cli.main(_command("p0a", Path("unused")))


def test_hard_dq_keeps_structured_decision_and_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    assert cli.main(["p0a", "--input", "fixtures/golden/p0a-minimal/dq-01-sha-missing", "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    decision = json.loads(captured.err)
    assert decision["payload"]["exit_code"] == 2
    assert "HATE-DQ-001" in {item["code"] for item in decision["payload"]["dq_hits"]}
    assert json.loads((out / "precheck-decision.json").read_text(encoding="utf-8")) == decision


@pytest.mark.subprocess
@pytest.mark.parametrize(("engine", "code", "prefix"), [("p0a", 1, "CLI"), ("trust", 2, "TRUST")])
def test_module_cli_errors_have_no_traceback(
    engine: str, code: int, prefix: str, tmp_path: Path,
) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "github-context.json").write_bytes(b"{")
    command = ["p0a", "--input", str(source)] if engine == "p0a" else [
        "trust", "evaluate", "--bundle", str(source / "missing.json"),
        "--report", str(TRUST_INPUT / "qeg-export-report.json"),
    ]
    result = subprocess.run(
        [sys.executable, "-B", "-m", "hate", *command, "--out", str(tmp_path / "out")],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        env={**os.environ, "PYTHONUTF8": "1"}, check=False,
    )
    assert result.returncode == code
    assert result.stdout == ""
    assert f"HATE-E-{prefix}:" in result.stderr
    assert "Traceback" not in result.stderr
