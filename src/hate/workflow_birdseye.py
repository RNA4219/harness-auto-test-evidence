"""Workflow-cookbook Birdseye freshness evaluation for HATE-GAP-024."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BirdseyeFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_birdseye_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_birdseye_freshness_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "workflow-birdseye-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_birdseye_freshness_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "workflow-birdseye-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["workflow-birdseye"])
    birdseye = _normalize_birdseye(input_data.get("birdseye", input_data))
    findings = _findings_for(birdseye, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "workflow-birdseye-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "birdseye": birdseye,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "index_exists": birdseye["index_exists"],
            "caps_missing_count": len(birdseye["caps_missing"]),
            "changed_paths_have_caps": birdseye["changed_paths_have_caps"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_birdseye(raw_birdseye: dict[str, Any]) -> dict[str, Any]:
    birdseye = dict(raw_birdseye or {})
    readme_matches = bool(birdseye.get("readme_matches_index", True))
    changed_paths_have_caps = bool(birdseye.get("changed_paths_have_caps", True))
    return {
        "index_exists": bool(birdseye.get("index_exists", True)),
        "node_count_matches_caps": bool(birdseye.get("node_count_matches_caps", True)),
        "readme_matches_index": readme_matches,
        "generated_at_matches": bool(birdseye.get("generated_at_matches", readme_matches)),
        "caps_missing": list(birdseye.get("caps_missing") or []),
        "changed_paths_have_caps": changed_paths_have_caps,
        "docs_schema_fixture_map_fresh": bool(birdseye.get("docs_schema_fixture_map_fresh", changed_paths_have_caps)),
        "product_ready_claim": bool(birdseye.get("product_ready_claim", False)),
        "explicit_exception_record": bool(birdseye.get("explicit_exception_record", False)),
        "context": str(birdseye.get("context") or "local_implementation_handoff"),
    }


def _findings_for(birdseye: dict[str, Any], source_ref: str) -> list[BirdseyeFinding]:
    findings: list[BirdseyeFinding] = []
    stale = (
        not birdseye["index_exists"]
        or not birdseye["node_count_matches_caps"]
        or not birdseye["readme_matches_index"]
        or not birdseye["generated_at_matches"]
        or bool(birdseye["caps_missing"])
        or not birdseye["changed_paths_have_caps"]
    )
    if stale:
        findings.append(_finding(
            "birdseye_stale_or_incomplete",
            "Birdseye index, README metadata, caps files, or changed-path capsules are stale or incomplete.",
            source_ref,
        ))
    if birdseye["product_ready_claim"] and not birdseye["docs_schema_fixture_map_fresh"]:
        findings.append(_finding(
            "birdseye_product_ready_claim_stale",
            "Product-ready claim must not use stale docs/schema/fixture map.",
            source_ref,
        ))
    if birdseye["context"] == "emergency_patch" and stale and not birdseye["explicit_exception_record"]:
        findings.append(_finding(
            "birdseye_emergency_exception_missing",
            "Emergency patch can tolerate stale Birdseye only with explicit exception record.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> BirdseyeFinding:
    return BirdseyeFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
