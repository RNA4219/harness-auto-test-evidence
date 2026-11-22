from __future__ import annotations

import json

from hate.p0b_phases import append_coverage_nodes, append_sarif_finding_nodes, append_test_execution_nodes
from hate.store import LocalStore
from hate.store.replay import replay_bundle


def test_p0b_generated_test_coverage_and_finding_nodes_are_stored_as_artifacts(tmp_path):
    nodes, edges = [], []
    test_ids = append_test_execution_nodes(
        test_records=[{"payload": {"canonical_test_id": "pytest:test_alpha", "status": "passed", "artifacts": []}}],
        artifact_by_id={}, nodes=nodes, edges=edges, unsupported_claims=[], unsafe_artifacts=[], excluded_artifacts=[],
        run_id="source-run", run_attempt=1, p0a_dir=tmp_path, source_ref=lambda path: path.name,
    )
    append_coverage_nodes(
        coverage_records=[{"payload": {"file": "app.py", "line_hits": {"1": 1}, "branch_hits": [], "contexts": []}}],
        test_node_ids=test_ids, nodes=nodes, edges=edges, p0a_dir=tmp_path, source_ref=lambda path: path.name,
    )
    append_sarif_finding_nodes(
        sarif_record={"runs": [{"results": [{"ruleId": "style-rule", "level": "warning", "message": {"text": "example"}}]}]},
        nodes=nodes, edges=edges, changed_node_by_path={}, changed_node_ranges={},
        p0a_dir=tmp_path, source_ref=lambda path: path.name,
    )
    assert {"test", "coverage", "finding", "execution_evidence"} <= {node["kind"] for node in nodes}
    # この低水準のnode構築は、存在しないprovenanceを補わない。
    assert "commit_sha" not in next(node for node in nodes if node["kind"] == "execution_evidence")["data"]
    source = tmp_path / "qeg-bundle.json"
    source.write_text(json.dumps({"nodes": nodes, "edges": edges}), encoding="utf-8")
    before = source.read_bytes()
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    imported = store.import_bundle(source, "run-1", "revision-1", hold)
    assert imported.success
    manifest = store.read_manifest("run-1")
    artifacts = [json.loads((imported.manifest_path.parent / f"{identifier}.json").read_text(encoding="utf-8")) for identifier in manifest.artifact_ids]
    assert {node["kind"] for node in artifacts} == {"test", "coverage", "finding"}
    assert all(node in nodes for node in artifacts)
    replay = replay_bundle(store, imported.bundle_id)
    assert replay.integrity_ok and replay.artifacts_replayed == 3
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert source.read_bytes() == before
