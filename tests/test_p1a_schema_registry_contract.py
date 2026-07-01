from __future__ import annotations

import json
from pathlib import Path

from hate.p1a import evaluate_trust


ROOT = Path(__file__).resolve().parents[1]

P1A_ARTIFACTS = {
    "aete-score.json": "aete_score",
    "aete-signal-report.json": "aete_signal_report",
    "profile-report.json": "profile_report",
    "doctor-report.json": "doctor_report",
    "adapter-registry.json": "adapter_registry",
    "adapter-capability-manifest.json": "adapter_capability_manifest",
    "adapter-conformance-report.json": "adapter_conformance",
    "artifact-resolver-map.json": "artifact_resolution",
    "canonical-identity-index.json": "canonical_identity_index",
    "retry-aggregation.json": "retry_aggregation",
}


def test_p1a_generated_artifacts_have_registered_schema_contract(tmp_path: Path) -> None:
    fixture_dir = ROOT / "fixtures/golden/p0b-qeg-minimal/expected"
    out_dir = tmp_path / "trust-output"
    evaluate_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=out_dir,
    )

    registry = json.loads((ROOT / "schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))
    by_record_type = {entry["record_type"]: entry for entry in registry["records"]}

    for artifact_name, record_type in P1A_ARTIFACTS.items():
        artifact = json.loads((out_dir / artifact_name).read_text(encoding="utf-8"))
        assert artifact["schema_version"] == "HATE/v1"
        assert artifact["record_type"] == record_type
        assert record_type in by_record_type
        assert by_record_type[record_type]["phase"] == "P1a"
        assert (ROOT / by_record_type[record_type]["schema"]).exists()


def test_p1a_schema_required_fields_match_generated_artifacts(tmp_path: Path) -> None:
    fixture_dir = ROOT / "fixtures/golden/p0b-qeg-minimal/expected"
    out_dir = tmp_path / "trust-output"
    evaluate_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=out_dir,
    )

    registry = json.loads((ROOT / "schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))
    by_record_type = {entry["record_type"]: entry for entry in registry["records"]}

    for artifact_name, record_type in P1A_ARTIFACTS.items():
        artifact = json.loads((out_dir / artifact_name).read_text(encoding="utf-8"))
        schema_path = ROOT / by_record_type[record_type]["schema"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for field in schema["required"]:
            assert field in artifact, f"{artifact_name} missing {field} required by {schema_path.name}"
