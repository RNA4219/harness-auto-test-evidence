"""UAT tests for deterministic scale fixture manifests."""

from __future__ import annotations

import json
from pathlib import Path

from hate.scale import (
    ScaleFixtureSpec,
    build_scale_performance_report,
    generate_scale_fixture_manifest,
    validate_scale_fixture_manifest,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "scale"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "HATE"
    / "v1"
    / "scale-performance-report.schema.json"
)


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def manifest_from_fixture(name: str):
    fixture = load_fixture(name)
    spec = ScaleFixtureSpec.from_dict(fixture["input"])
    return generate_scale_fixture_manifest(spec), fixture["expected"]


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "small-seed",
        "multi-adapter-seed",
        "source-ref-cardinality",
        "artifact-heavy-seed",
        "risk-heavy-seed",
        "invalid-collision",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_generation_is_deterministic_by_seed() -> None:
    fixture = load_fixture("small-seed")
    spec = ScaleFixtureSpec.from_dict(fixture["input"])

    first = generate_scale_fixture_manifest(spec).to_dict()
    second = generate_scale_fixture_manifest(spec).to_dict()

    assert first == second
    assert first["expected_hashes"]["manifest"].startswith("sha256:")


def test_small_seed_smoke_counts_validate() -> None:
    manifest, expected = manifest_from_fixture("small-seed")
    result = validate_scale_fixture_manifest(manifest)

    assert result.status == expected["status"]
    assert manifest.generated_counts["tests"] == expected["tests"]
    assert manifest.generated_counts["coverage_records"] == expected["coverage_records"]
    assert manifest.generated_counts["artifact_metadata"] == expected["artifact_metadata"]
    assert manifest.generated_counts["graph_nodes"] == expected["graph_nodes"]
    assert manifest.generated_counts["graph_edges"] == expected["graph_edges"]


def test_multi_adapter_seed_preserves_index_cardinality() -> None:
    manifest, expected = manifest_from_fixture("multi-adapter-seed")
    result = validate_scale_fixture_manifest(manifest)

    assert result.status == expected["status"]
    assert manifest.adapter_count == expected["adapter_count"]
    assert manifest.shard_count == expected["shard_count"]
    assert manifest.generated_counts["tests"] == expected["tests"]
    assert manifest.graph_cardinality["edges"] <= (
        manifest.graph_cardinality["nodes"] * manifest.graph_cardinality["max_edge_fanout"]
    )


def test_source_ref_cardinality_has_no_collision() -> None:
    manifest, expected = manifest_from_fixture("source-ref-cardinality")
    result = validate_scale_fixture_manifest(manifest)

    assert result.status == expected["status"]
    assert manifest.source_ref_summary["count"] == expected["source_ref_count"]
    assert manifest.source_ref_summary["unique_count"] == expected["source_ref_unique_count"]
    assert len(set(manifest.source_ref_summary["sample"])) == len(manifest.source_ref_summary["sample"])


def test_artifact_heavy_seed_is_metadata_only() -> None:
    manifest, expected = manifest_from_fixture("artifact-heavy-seed")
    result = validate_scale_fixture_manifest(manifest)

    assert result.status == expected["status"]
    assert manifest.artifact_summary["metadata_count"] == expected["artifact_metadata"]
    assert manifest.artifact_summary["raw_artifact_content_committed"] is expected["raw_artifact_content_committed"]


def test_risk_heavy_seed_proves_500k_class_without_giant_fixture() -> None:
    manifest, expected = manifest_from_fixture("risk-heavy-seed")
    result = validate_scale_fixture_manifest(manifest)
    fixture_size = (FIXTURE_ROOT / "risk-heavy-seed" / "fixture.json").stat().st_size

    assert result.status == expected["status"]
    assert manifest.generated_counts["tests"] == expected["tests"]
    assert manifest.generated_counts["coverage_records"] == expected["coverage_records"]
    assert manifest.generated_counts["artifact_metadata"] == expected["artifact_metadata"]
    assert manifest.generated_counts["graph_nodes"] == expected["graph_nodes"]
    assert manifest.generated_counts["graph_edges"] == expected["graph_edges"]
    assert manifest.generation_profile == "large_manifest_only"
    assert fixture_size < 10_000


def test_invalid_collision_is_blocked() -> None:
    manifest, expected = manifest_from_fixture("invalid-collision")
    result = validate_scale_fixture_manifest(manifest)

    assert result.status == expected["status"]
    assert result.findings[0]["code"] == expected["finding_code"]


def test_scale_performance_report_shape() -> None:
    manifests = [
        manifest_from_fixture("small-seed")[0],
        manifest_from_fixture("risk-heavy-seed")[0],
    ]
    report = build_scale_performance_report(manifests)

    assert report["record_type"] == "scale-performance-report"
    assert report["scale_targets"]["tests"] == 101000
    assert report["scale_targets"]["coverage_records"] == 10010000
    assert report["scale_targets"]["artifact_metadata"] == 100100
    assert report["scale_targets"]["graph_nodes"] == 500000
    assert report["scale_targets"]["graph_edges"] == 2000000
    assert report["pagination"]["required"] is True
    assert report["overall_status"] == "pass"


def test_scale_performance_report_schema_contract_is_registered_shape() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "scale-performance-report"
    assert set(schema["required"]) >= {
        "schema_version",
        "record_type",
        "scale_targets",
        "budgets",
        "resource_limits",
        "pagination",
        "staleness",
        "findings",
    }
