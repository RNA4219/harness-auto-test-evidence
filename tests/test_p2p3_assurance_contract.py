"""P2/P3 assurance record registry and schema contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from hate.p2p3 import generate_product_readiness


def test_p2p3_assurance_records_are_registered_and_schema_compatible(tmp_path: Path) -> None:
    bundle = Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    workflow_dir = Path("fixtures/golden/p1b-workflow-minimal/expected")
    out_dir = tmp_path / "product-output"
    generate_product_readiness(
        bundle_path=bundle,
        trust_dir=trust_dir,
        workflow_dir=workflow_dir,
        out_dir=out_dir,
    )

    registry = json.loads(Path("schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))
    by_record_type = {record["record_type"]: record for record in registry["records"]}
    reports = [
        json.loads((out_dir / "artifact-budget-report.json").read_text(encoding="utf-8")),
        json.loads((out_dir / "attestation-report.json").read_text(encoding="utf-8")),
        json.loads((out_dir / "audit-event-log.json").read_text(encoding="utf-8")),
        json.loads((out_dir / "commercial-contract-report.json").read_text(encoding="utf-8")),
        json.loads((out_dir / "audit-assurance-pack.json").read_text(encoding="utf-8")),
    ]
    reports.append(reports[-1]["audit_fixture_manifest"])

    for report in reports:
        assert report["record_type"] in by_record_type
        schema_path = Path(by_record_type[report["record_type"]]["schema"])
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert set(schema["required"]) <= set(report)
        assert report["record_type"] in schema["properties"]["record_type"]["enum"]
