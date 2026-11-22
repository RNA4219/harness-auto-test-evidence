from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from hate.bridge.router import dispatch_bridge
from hate.bridge.schemas import BridgeValidationError, validate_bridge_record
from hate.cli import build_parser


def _handoff(tmp_path: Path, argv: list[str]) -> dict:
    parser = build_parser()
    args = parser.parse_args([*argv, "--bridge-provider", "handoff"])
    # Commands without --out still write only inside this test's directory.
    args.out = tmp_path / "handoff"
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        assert dispatch_bridge(args, parser) == 0
    request_path = Path(json.loads(stdout.getvalue())["bridge_request"])
    return json.loads(request_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("command", "option", "value", "key", "expected"),
    [
        (["platform", "policy", "explain", "--policy"], "--profile", "strict", "profile", "strict"),
        (["platform", "run", "--roster"], "--source-version", "revision-2", "source_version", "revision-2"),
        (["platform", "schedule", "--roster"], "--retry-limit", "3", "retry_limit", 3),
        (["platform", "schedule", "--roster"], "--cache-ttl-hours", "48", "cache_ttl_hours", 48),
    ],
)
def test_handoff_preserves_options_and_changes_identity(tmp_path, command, option, value, key, expected):
    source = tmp_path / "input.json"
    source.write_text("{}", encoding="utf-8")
    argv = [*command, str(source)]
    if "schedule" in command:
        history = tmp_path / "history"
        history.mkdir()
        argv += ["--history-store", str(history)]
    if command == ["platform", "run", "--roster"]:
        argv += ["--out", str(tmp_path / "unused")]
    baseline = _handoff(tmp_path, argv)
    changed = _handoff(tmp_path, [*argv, option, value])
    assert changed["command_options"][key] == expected
    assert changed["input_refs"] == baseline["input_refs"]
    assert changed["bridge_id"] != baseline["bridge_id"]
    assert _handoff(tmp_path, [*argv, option, value]) == changed
    validate_bridge_record(changed, "bridge-request")


def test_handoff_preserves_false_and_explicit_default_is_equivalent(tmp_path):
    source = tmp_path / "input.json"
    source.write_text("{}", encoding="utf-8")
    history = tmp_path / "history"
    history.mkdir()
    argv = ["platform", "schedule", "--roster", str(source), "--history-store", str(history)]
    baseline = _handoff(tmp_path, argv)
    assert baseline["command_options"] == {"cache_ttl_hours": 24, "force": False, "retry_limit": 1}
    assert _handoff(tmp_path, [*argv, "--retry-limit", "1"]) == baseline
    forced = _handoff(tmp_path, [*argv, "--force"])
    assert forced["command_options"]["force"] is True
    assert forced["bridge_id"] != baseline["bridge_id"]


def test_handoff_preserves_repeated_options_and_null_defaults(tmp_path):
    source = tmp_path / "readiness.json"
    source.write_text("{}", encoding="utf-8")
    argv = ["product", "query", "--readiness", str(source), "--resource", "runs"]
    baseline = _handoff(tmp_path, argv)
    changed = _handoff(tmp_path, [*argv, "--filter", "status=open", "--filter", "owner=team"])
    assert baseline["command_options"]["filter"] == []
    assert changed["command_options"]["filter"] == ["status=open", "owner=team"]
    assert changed["command_options"]["cursor"] is None
    assert changed["bridge_id"] != baseline["bridge_id"]


def test_legacy_request_without_options_remains_readable(tmp_path):
    source = tmp_path / "policy.json"
    source.write_text("{}", encoding="utf-8")
    request = _handoff(tmp_path, ["platform", "policy", "explain", "--policy", str(source)])
    request.pop("command_options", None)
    validate_bridge_record(request, "bridge-request")


def test_handoff_identity_is_independent_of_local_output_directory(tmp_path):
    source = tmp_path / "policy.json"
    source.write_text("{}", encoding="utf-8")
    argv = ["platform", "policy", "explain", "--policy", str(source), "--profile", "strict"]
    first = _handoff(tmp_path / "first", argv)
    second = _handoff(tmp_path / "second", argv)
    assert first == second


@pytest.mark.parametrize("invalid", [{"profile": {"nested": True}}, {"filter": [["status=open"]]}])
def test_request_schema_rejects_unsupported_option_shapes(tmp_path, invalid):
    source = tmp_path / "policy.json"
    source.write_text("{}", encoding="utf-8")
    request = _handoff(tmp_path, ["platform", "policy", "explain", "--policy", str(source)])
    request["command_options"] = invalid
    with pytest.raises(BridgeValidationError):
        validate_bridge_record(request, "bridge-request")
