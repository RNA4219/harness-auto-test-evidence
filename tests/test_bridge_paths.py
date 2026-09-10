from __future__ import annotations

import json
import os

from hate.bridge.router import dispatch_bridge
from hate.cli import build_parser


def _dispatch(argv: list[str]) -> int:
    parser = build_parser()
    return dispatch_bridge(parser.parse_args([*argv, "--bridge-provider", "handoff"]), parser)


def test_directory_output_with_dots_keeps_request_inside_directory(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    out = tmp_path / "reports.v1"
    assert _dispatch(["product", "grade-reports", "--docs-root", str(docs), "--out", str(out)]) == 0
    assert (out / "bridge-request.json").is_file()
    assert not (tmp_path / "bridge-request.json").exists()


def test_file_output_without_extension_keeps_request_next_to_file(tmp_path):
    policy = tmp_path / "policy.json"
    policy.write_text("{}", encoding="utf-8")
    out = tmp_path / "report"
    assert _dispatch(["platform", "policy", "explain", "--policy", str(policy), "--out", str(out)]) == 0
    assert (tmp_path / "bridge-request.json").is_file()
    assert not out.exists()


def test_source_references_are_encoded_file_uris(tmp_path):
    source = tmp_path / "policy with spaces #1.json"
    source.write_text("{}", encoding="utf-8")
    assert _dispatch(["platform", "policy", "explain", "--policy", str(source), "--out", str(tmp_path / "out.json")]) == 0
    request = json.loads((tmp_path / "bridge-request.json").read_text(encoding="utf-8"))
    assert request["sourceRefs"] == [source.resolve().as_uri()]


def test_same_file_in_multiple_arguments_preserves_bindings_with_unique_uris(tmp_path):
    source = tmp_path / "evidence.json"
    source.write_text("{}", encoding="utf-8")
    trust = tmp_path / "trust"
    trust.mkdir()
    out = tmp_path / "out"
    assert _dispatch(["workflow", "map", "--bundle", str(source), "--report", str(source), "--trust", str(trust), "--out", str(out)]) == 0
    request = json.loads((out / "bridge-request.json").read_text(encoding="utf-8"))
    assert [ref["argument"] for ref in request["input_refs"]] == ["bundle", "report", "trust"]
    assert request["sourceRefs"] == [source.resolve().as_uri(), trust.resolve().as_uri()]


def test_handoff_does_not_hash_its_own_request_inside_input_tree(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "evidence.json").write_text("{}", encoding="utf-8")
    out = inputs / "handoff"
    argv = ["product", "grade-reports", "--docs-root", str(inputs), "--out", str(out)]
    assert _dispatch(argv) == 0
    first = json.loads((out / "bridge-request.json").read_text(encoding="utf-8"))
    assert _dispatch(argv) == 0
    second = json.loads((out / "bridge-request.json").read_text(encoding="utf-8"))
    assert second == first
    assert first["input_refs"][0]["excluded_paths"] == [
        {"path": "handoff/bridge-request.json", "kind": "file"},
        {"path": "handoff", "kind": "temporary-files"},
    ]
    (inputs / "evidence.json").write_text('{"changed": true}', encoding="utf-8")
    assert _dispatch(argv) == 0
    changed = json.loads((out / "bridge-request.json").read_text(encoding="utf-8"))
    assert changed["bridge_id"] != first["bridge_id"]


def test_default_handoff_directory_is_excluded_from_store_fingerprint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    argv = ["platform", "history", "--store", str(tmp_path)]
    assert _dispatch(argv) == 0
    requests = list((tmp_path / ".hate" / "bridge").glob("*/bridge-request.json"))
    assert len(requests) == 1
    first = json.loads(requests[0].read_text(encoding="utf-8"))
    assert first["input_refs"][0]["excluded_paths"] == [{"path": ".hate/bridge", "kind": "directory"}]
    assert _dispatch(argv) == 0
    assert list((tmp_path / ".hate" / "bridge").glob("*/bridge-request.json")) == requests
    assert json.loads(requests[0].read_text(encoding="utf-8")) == first


def test_failed_request_replace_preserves_previous_request_and_cleans_temporary(tmp_path, monkeypatch):
    source = tmp_path / "policy.json"
    source.write_text("{}", encoding="utf-8")
    argv = ["platform", "policy", "explain", "--policy", str(source), "--out", str(tmp_path / "out.json")]
    assert _dispatch(argv) == 0
    request = tmp_path / "bridge-request.json"
    previous = request.read_bytes()

    def unavailable_destination(*args, **kwargs):
        raise OSError("simulated busy destination")

    monkeypatch.setattr(os, "replace", unavailable_destination)
    assert _dispatch([*argv, "--profile", "strict"]) == 2
    assert request.read_bytes() == previous
    assert not list(tmp_path.glob(".hate-bridge-*.tmp"))
