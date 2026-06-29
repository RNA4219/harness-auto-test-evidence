"""Workflow evidence record assembly for P1b mapping."""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "HATE/v1"
TASK_ID = "HATE-MVP-007-P1B-WORKFLOW-MAPPING"


def _build_workflow_evidence(
    run_id: str,
    source_refs: list[str],
    alignment: dict[str, Any],
    aete: dict[str, Any],
    doctor: dict[str, Any],
    shipyard: dict[str, Any],
    rand_audit: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records = [
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "workflow_evidence",
            "evidence_id": "evidence:p1b:qeg",
            "task_id": TASK_ID,
            "run_id": run_id,
            "artifact_ref": "qeg-bundle.json",
            "summary": "QEG bundle and export report provide graph evidence for P1b alignment.",
            "source_refs": source_refs[:2],
        },
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "workflow_evidence",
            "evidence_id": "evidence:p1b:aete",
            "task_id": TASK_ID,
            "run_id": run_id,
            "artifact_ref": "aete-score.json",
            "summary": f"AETE weighted score {aete.get('weighted_score')} with confidence {aete.get('score_confidence')}.",
            "source_refs": ["aete-score.json"],
        },
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "workflow_evidence",
            "evidence_id": "evidence:p1b:alignment",
            "task_id": TASK_ID,
            "run_id": run_id,
            "artifact_ref": "requirement-evidence-alignment.json",
            "summary": f"Alignment verdict {alignment['summary']['gate_verdict']} preserves upstream gate authority.",
            "source_refs": ["requirement-evidence-alignment.json"],
        },
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "workflow_evidence",
            "evidence_id": "evidence:p1b:shipyard",
            "task_id": TASK_ID,
            "run_id": run_id,
            "artifact_ref": "shipyard-run-evidence.json",
            "summary": f"Shipyard advisory packet attached with {doctor.get('summary', {}).get('finding_count', 0)} doctor findings.",
            "source_refs": ["shipyard-run-evidence.json"],
            "publish_gate_override": shipyard["publish_gate_override"],
            "shipyard_refs_preserved": shipyard["shipyard_inputs"]["refs_preserved"],
            "shipyard_state_override": shipyard["shipyard_state_override"],
        },
    ]
    if isinstance(rand_audit, dict):
        records.append({
            "schema_version": SCHEMA_VERSION,
            "record_type": "workflow_evidence",
            "evidence_id": "evidence:p1b:rand-audit",
            "task_id": TASK_ID,
            "run_id": run_id,
            "artifact_ref": "rand-audit-packet.json",
            "summary": f"RanD audit overall {alignment['rand_audit']['overall_assessment']} preserved without override.",
            "source_refs": ["requirement-evidence-alignment.json"],
            "rand_audit_overwrite": False,
        })
    return records
