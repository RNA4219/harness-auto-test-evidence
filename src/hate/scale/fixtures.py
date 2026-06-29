"""Deterministic scale fixture manifests.

Large HATE scale fixtures are represented by compact generator inputs and
manifest summaries. This avoids committing giant generated files while keeping
500k-class graph/cardinality claims reproducible and hash-backed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


MAX_SOURCE_REF_SAMPLES = 12


@dataclass(frozen=True)
class ScaleFixtureSpec:
    """Compact generator input for a large fixture profile."""

    fixture_id: str
    seed: str
    target_tests: int
    target_coverage_records: int
    target_artifact_metadata: int
    target_risks: int
    target_graph_nodes: int
    target_graph_edges: int
    adapter_count: int = 1
    shard_count: int = 1
    max_edge_fanout: int = 8
    max_artifact_size_bytes: int = 10_000_000
    generation_profile: str = "manifest_only"
    force_source_ref_collision: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScaleFixtureSpec":
        return cls(
            fixture_id=data["fixture_id"],
            seed=data["seed"],
            target_tests=int(data.get("target_tests", 0)),
            target_coverage_records=int(data.get("target_coverage_records", 0)),
            target_artifact_metadata=int(data.get("target_artifact_metadata", 0)),
            target_risks=int(data.get("target_risks", 0)),
            target_graph_nodes=int(data.get("target_graph_nodes", 0)),
            target_graph_edges=int(data.get("target_graph_edges", 0)),
            adapter_count=int(data.get("adapter_count", 1)),
            shard_count=int(data.get("shard_count", 1)),
            max_edge_fanout=int(data.get("max_edge_fanout", 8)),
            max_artifact_size_bytes=int(data.get("max_artifact_size_bytes", 10_000_000)),
            generation_profile=data.get("generation_profile", "manifest_only"),
            force_source_ref_collision=bool(data.get("force_source_ref_collision", False)),
        )


@dataclass
class ScaleFixtureManifest:
    """Generated compact manifest for a scale fixture."""

    fixture_id: str
    seed: str
    generation_profile: str
    target_counts: dict[str, int]
    generated_counts: dict[str, int]
    shard_count: int
    adapter_count: int
    graph_cardinality: dict[str, int]
    source_ref_summary: dict[str, Any]
    artifact_summary: dict[str, Any]
    expected_hashes: dict[str, str]
    sourceRefs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "scale_fixture_manifest",
            "fixture_id": self.fixture_id,
            "seed": self.seed,
            "generation_profile": self.generation_profile,
            "target_counts": self.target_counts,
            "generated_counts": self.generated_counts,
            "shard_count": self.shard_count,
            "adapter_count": self.adapter_count,
            "graph_cardinality": self.graph_cardinality,
            "source_ref_summary": self.source_ref_summary,
            "artifact_summary": self.artifact_summary,
            "expected_hashes": self.expected_hashes,
            "sourceRefs": self.sourceRefs,
        }


@dataclass
class ScaleValidationResult:
    """Validation outcome for a scale fixture manifest."""

    fixture_id: str
    status: str
    findings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "scale_validation_result",
            "fixture_id": self.fixture_id,
            "status": self.status,
            "findings": self.findings,
        }


def generate_scale_fixture_manifest(spec: ScaleFixtureSpec) -> ScaleFixtureManifest:
    """Generate a deterministic compact manifest from a scale fixture spec."""
    _validate_non_negative(spec)
    source_ref_count = (
        spec.target_tests
        + spec.target_coverage_records
        + spec.target_artifact_metadata
        + spec.target_risks
    )
    unique_source_ref_count = source_ref_count - 1 if spec.force_source_ref_collision and source_ref_count else source_ref_count
    samples = _sample_source_refs(spec, min(MAX_SOURCE_REF_SAMPLES, source_ref_count))
    if spec.force_source_ref_collision and samples:
        samples[-1] = samples[0]

    generated_counts = {
        "tests": spec.target_tests,
        "coverage_records": spec.target_coverage_records,
        "artifact_metadata": spec.target_artifact_metadata,
        "risks": spec.target_risks,
        "graph_nodes": spec.target_graph_nodes,
        "graph_edges": spec.target_graph_edges,
    }
    manifest_without_hash = {
        "fixture_id": spec.fixture_id,
        "seed": spec.seed,
        "generation_profile": spec.generation_profile,
        "generated_counts": generated_counts,
        "shard_count": spec.shard_count,
        "adapter_count": spec.adapter_count,
        "graph_cardinality": {
            "nodes": spec.target_graph_nodes,
            "edges": spec.target_graph_edges,
            "max_edge_fanout": spec.max_edge_fanout,
        },
        "source_ref_summary": {
            "count": source_ref_count,
            "unique_count": unique_source_ref_count,
            "sample": samples,
        },
        "artifact_summary": {
            "metadata_count": spec.target_artifact_metadata,
            "max_artifact_size_bytes": spec.max_artifact_size_bytes,
            "raw_artifact_content_committed": False,
        },
    }
    manifest_hash = _stable_hash(manifest_without_hash)
    return ScaleFixtureManifest(
        fixture_id=spec.fixture_id,
        seed=spec.seed,
        generation_profile=spec.generation_profile,
        target_counts={
            "tests": spec.target_tests,
            "coverage_records": spec.target_coverage_records,
            "artifact_metadata": spec.target_artifact_metadata,
            "risks": spec.target_risks,
            "graph_nodes": spec.target_graph_nodes,
            "graph_edges": spec.target_graph_edges,
        },
        generated_counts=generated_counts,
        shard_count=spec.shard_count,
        adapter_count=spec.adapter_count,
        graph_cardinality=manifest_without_hash["graph_cardinality"],
        source_ref_summary=manifest_without_hash["source_ref_summary"],
        artifact_summary=manifest_without_hash["artifact_summary"],
        expected_hashes={"manifest": manifest_hash},
        sourceRefs=[f"fixtures/scale/{spec.fixture_id}/fixture.json"],
    )


def validate_scale_fixture_manifest(manifest: ScaleFixtureManifest | dict[str, Any]) -> ScaleValidationResult:
    """Validate deterministic counts, sourceRef cardinality, and graph fanout."""
    data = manifest.to_dict() if isinstance(manifest, ScaleFixtureManifest) else manifest
    fixture_id = data.get("fixture_id", "")
    findings: list[dict[str, Any]] = []

    target_counts = data.get("target_counts", {})
    generated_counts = data.get("generated_counts", {})
    for key, expected in target_counts.items():
        if generated_counts.get(key) != expected:
            findings.append({
                "code": "scale_count_mismatch",
                "severity": "hold",
                "message": f"{key} generated count does not match target",
                "sourceRef": f"scale:{fixture_id}:{key}",
            })

    source_summary = data.get("source_ref_summary", {})
    if source_summary.get("count") != source_summary.get("unique_count"):
        findings.append({
            "code": "source_ref_collision",
            "severity": "blocked",
            "message": "sourceRef collision detected in generated profile",
            "sourceRef": f"scale:{fixture_id}:sourceRefs",
        })

    graph = data.get("graph_cardinality", {})
    max_edges = int(graph.get("nodes", 0)) * int(graph.get("max_edge_fanout", 0))
    if int(graph.get("edges", 0)) > max_edges:
        findings.append({
            "code": "unbounded_edge_fanout",
            "severity": "blocked",
            "message": "graph edge count exceeds max_edge_fanout budget",
            "sourceRef": f"scale:{fixture_id}:graph",
        })

    artifact_summary = data.get("artifact_summary", {})
    if artifact_summary.get("raw_artifact_content_committed") is True:
        findings.append({
            "code": "raw_large_artifact_committed",
            "severity": "blocked",
            "message": "scale fixture committed raw artifact content",
            "sourceRef": f"scale:{fixture_id}:artifacts",
        })

    status = "pass" if not findings else "blocked"
    if findings and all(item["severity"] == "hold" for item in findings):
        status = "hold"
    return ScaleValidationResult(fixture_id=fixture_id, status=status, findings=findings)


def build_scale_performance_report(manifests: list[ScaleFixtureManifest | dict[str, Any]]) -> dict[str, Any]:
    """Build scale-performance-report shape from fixture manifests."""
    manifest_dicts = [item.to_dict() if isinstance(item, ScaleFixtureManifest) else item for item in manifests]
    validations = [validate_scale_fixture_manifest(item).to_dict() for item in manifest_dicts]
    aggregate = {
        "tests": sum(item["generated_counts"].get("tests", 0) for item in manifest_dicts),
        "coverage_records": sum(item["generated_counts"].get("coverage_records", 0) for item in manifest_dicts),
        "artifact_metadata": sum(item["generated_counts"].get("artifact_metadata", 0) for item in manifest_dicts),
        "graph_nodes": max((item["generated_counts"].get("graph_nodes", 0) for item in manifest_dicts), default=0),
        "graph_edges": max((item["generated_counts"].get("graph_edges", 0) for item in manifest_dicts), default=0),
    }
    findings = [finding for result in validations for finding in result["findings"]]
    return {
        "schema_version": "HATE/v1",
        "record_type": "scale-performance-report",
        "scale_targets": aggregate,
        "budgets": [
            {"operation": "fixture_generation", "target_ms": 1000, "observed_ms": None, "status": "not_run"}
        ],
        "resource_limits": {
            "max_memory_mb": 512,
            "max_input_bytes": 10_000_000,
            "max_archive_entries": 1000,
        },
        "pagination": {"required": True, "tested": True},
        "staleness": {"cache_invalidation_tested": False},
        "fixture_manifests": manifest_dicts,
        "validation_results": validations,
        "findings": findings,
        "overall_status": "pass" if not findings else "blocked",
    }


def _validate_non_negative(spec: ScaleFixtureSpec) -> None:
    for name in (
        "target_tests",
        "target_coverage_records",
        "target_artifact_metadata",
        "target_risks",
        "target_graph_nodes",
        "target_graph_edges",
        "adapter_count",
        "shard_count",
        "max_edge_fanout",
    ):
        if getattr(spec, name) < 0:
            raise ValueError(f"{name} must be non-negative")


def _sample_source_refs(spec: ScaleFixtureSpec, count: int) -> list[str]:
    return [
        f"scale://{spec.fixture_id}/{index}/{_stable_hash({'seed': spec.seed, 'index': index})[:12]}"
        for index in range(count)
    ]


def _stable_hash(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
