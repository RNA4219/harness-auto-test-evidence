from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from hate.bridge.router import dispatch_bridge
from hate.bridge.routes import BRIDGE_COMMANDS, route_for_command
from hate.bridge.schemas import BridgeValidationError, validate_bridge_record
from hate.cli import build_parser


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.json"
    path.write_text("{}", encoding="utf-8")
    return path


def _dispatch(argv):
    parser = build_parser()
    return dispatch_bridge(parser.parse_args([*argv, "--bridge-provider", "handoff"]), parser)


def _request(argv, capsys):
    assert _dispatch(argv) == 0
    path = Path(json.loads(capsys.readouterr().out)["bridge_request"])
    request = json.loads(path.read_text(encoding="utf-8"))
    validate_bridge_record(request, "bridge-request")
    return request


@pytest.mark.parametrize(
    ("argv", "argument"),
    [
        (["platform", "policy", "explain", "--policy", "missing.json"], "policy"),
        (["real-repo", "history-query", "--store", "missing-store"], "store"),
        (["product", "grade-reports", "--out", "out"], "docs_root"),
    ],
)
def test_missing_required_or_default_input_fails_before_writing(tmp_path, capsys, argv, argument):
    assert _dispatch(argv) == 2
    error = capsys.readouterr().err
    assert f"bridge input not found: {argument}" in error
    assert not list(tmp_path.rglob("bridge-request.json"))


def test_supplied_optional_input_must_exist(source, tmp_path, capsys):
    assert _dispatch([
        "platform", "history-materialize", "--input", str(source),
        "--previous-manifest", "missing.json", "--out", "out.json",
    ]) == 2
    assert "bridge input not found: previous_manifest" in capsys.readouterr().err
    assert not (tmp_path / "bridge-request.json").exists()


def test_new_store_destination_is_preserved_without_creating_it(source, tmp_path, capsys):
    store = tmp_path / "new store"
    argv = ["real-repo", "history-ingest", "--history", str(source), "--store", str(store)]
    request = _request(argv, capsys)
    assert request["path_arguments"]["store"] == {
        "path": str(store), "role": "destination", "exists": False,
    }
    assert request["path_arguments"]["history"] == {
        "path": str(source), "role": "input", "exists": True,
    }
    assert [ref["argument"] for ref in request["input_refs"]] == ["history"]
    assert request["sourceRefs"] == [source.as_uri()]
    assert "store" not in request["command_options"]
    assert not store.exists()
    assert _request(argv, capsys) == request
    changed = _request([*argv[:-1], str(tmp_path / "another store")], capsys)
    assert changed["bridge_id"] != request["bridge_id"]


def test_existing_store_state_is_fingerprinted(source, tmp_path, capsys):
    store = tmp_path / "store"
    argv = ["real-repo", "history-ingest", "--history", str(source), "--store", str(store)]
    missing = _request(argv, capsys)
    store.mkdir()
    empty = _request(argv, capsys)
    assert empty["path_arguments"]["store"]["exists"] is True
    assert empty["bridge_id"] != missing["bridge_id"]
    assert [ref["argument"] for ref in empty["input_refs"]] == ["history", "store"]
    (store / "run_history.jsonl").write_text('{"sequence": 1}\n', encoding="utf-8")
    populated = _request(argv, capsys)
    assert populated["bridge_id"] != empty["bridge_id"]


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_schedule_preserves_missing_history_and_fingerprints_existing_history(source, tmp_path, capsys, kind):
    history = tmp_path / "history"
    argv = ["platform", "schedule", "--roster", str(source), "--history-store", str(history)]
    missing = _request(argv, capsys)
    assert missing["path_arguments"]["history_store"] == {
        "path": str(history), "role": "optional-input", "exists": False,
    }
    assert [ref["argument"] for ref in missing["input_refs"]] == ["roster"]
    assert not history.exists()
    if kind == "directory":
        history.mkdir()
    else:
        history.write_text("", encoding="utf-8")
    existing = _request(argv, capsys)
    assert existing["path_arguments"]["history_store"]["exists"] is True
    assert existing["input_refs"][0]["kind"] == kind
    assert existing["bridge_id"] != missing["bridge_id"]


def test_file_cannot_be_used_as_store_destination(source, tmp_path, capsys):
    assert _dispatch(["real-repo", "history-ingest", "--history", str(source), "--store", str(source)]) == 2
    assert "bridge destination must be a directory: store" in capsys.readouterr().err
    assert source.read_text(encoding="utf-8") == "{}"
    assert not (tmp_path / ".hate").exists()


def test_handoff_cannot_create_missing_input_as_side_effect(source, tmp_path, capsys):
    history = tmp_path / "history"
    assert _dispatch([
        "platform", "schedule", "--roster", str(source), "--history-store", str(history),
        "--out", str(history / "schedule.json"),
    ]) == 2
    assert "handoff output would create missing path argument: history_store" in capsys.readouterr().err
    assert not history.exists()


def test_unregistered_path_argument_is_rejected(source, tmp_path, capsys):
    parser = build_parser()
    args = parser.parse_args(["platform", "policy", "explain", "--policy", str(source), "--bridge-provider", "handoff"])
    args.future_input = tmp_path / "future"
    assert dispatch_bridge(args, parser) == 2
    assert "unregistered bridge path argument: future_input" in capsys.readouterr().err
    assert not (tmp_path / ".hate").exists()


def test_all_bridge_cli_path_arguments_have_roles():
    checked = set()

    def visit(parser, parts):
        subparsers = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
        if not subparsers and parts[0] in BRIDGE_COMMANDS:
            command = " ".join(parts)
            declared = dict(route_for_command(command).path_arguments)
            actual = {action.dest for action in parser._actions if action.type is Path}
            assert set(declared) == actual - {"out", "manifest_out"}, command
            assert set(declared.values()) <= {"input", "optional-input", "destination"}
            checked.add(command)
        for action in subparsers:
            for name, child in action.choices.items():
                visit(child, [*parts, name])

    visit(build_parser(), [])
    assert len(checked) == 33


@pytest.mark.parametrize(
    "invalid",
    [
        {"path": "/source", "role": "unknown", "exists": True},
        {"path": "", "role": "input", "exists": True},
        {"path": "/source", "role": "input", "exists": False},
        {"path": "/source", "role": "input", "exists": "true"},
        {"path": "/source", "role": "input"},
        {"path": "/source", "role": "input", "exists": True, "extra": 1},
    ],
)
def test_schema_rejects_invalid_path_arguments(source, capsys, invalid):
    request = _request(["platform", "policy", "explain", "--policy", str(source)], capsys)
    request["path_arguments"] = {"policy": invalid}
    with pytest.raises(BridgeValidationError):
        validate_bridge_record(request, "bridge-request")


def test_old_request_without_path_arguments_remains_readable(source, capsys):
    request = _request(["platform", "policy", "explain", "--policy", str(source)], capsys)
    request.pop("path_arguments", None)
    validate_bridge_record(request, "bridge-request")
