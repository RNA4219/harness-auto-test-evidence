"""Documentation lifecycle evaluation for HATE-GAP-033."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DocsLifecycleFinding:
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


def evaluate_docs_lifecycle_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_docs_lifecycle_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "docs-lifecycle-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_docs_lifecycle_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "docs-lifecycle-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["docs-lifecycle"])
    lifecycle_config = _normalize_lifecycle_config(
        input_data.get("lifecycle_config", input_data)
    )
    findings = _findings_for(lifecycle_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "docs-lifecycle-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "lifecycle_config": lifecycle_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "required_docs_defined": lifecycle_config["required_docs_defined"],
            "version_binding_enforced": lifecycle_config["version_binding_enforced"],
            "doc_claim_stale": lifecycle_config["doc_claim_stale"],
            "broken_ref_count": len(lifecycle_config["broken_refs"]),
            "doc_age_days": lifecycle_config["doc_age_days"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_lifecycle_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    required_docs = [
        str(doc) for doc in config.get("required_docs", []) if str(doc)
    ]
    broken_refs = [
        str(ref) for ref in config.get("broken_refs", []) if str(ref)
    ]
    legacy_contract = any(
        key in config
        for key in (
            "required_docs_inventory_defined",
            "version_binding_valid",
            "release_note_linkage_defined",
            "claim_checks_defined",
            "broken_ref_scan_enabled",
            "stale_claim_handling_defined",
            "broken_ref_count",
            "stale_claim_count",
            "docs_version",
            "product_version",
        )
    )
    if legacy_contract:
        broken_ref_count = int(config.get("broken_ref_count", 0) or 0)
        stale_claim_count = int(config.get("stale_claim_count", 0) or 0)
        docs_version = str(config.get("docs_version", "") or "")
        product_version = str(config.get("product_version", "") or "")
        return {
            "required_docs_defined": bool(config.get("required_docs_inventory_defined", False)),
            "required_docs_missing_code": "docs_lifecycle_inventory_missing",
            "version_binding_enforced": bool(config.get("version_binding_valid", False)),
            "broken_ref_detection_enabled": bool(config.get("broken_ref_scan_enabled", True)),
            "stale_doc_max_age_days": int(config.get("stale_doc_max_age_days", 0) or 0),
            "required_docs": required_docs,
            "doc_claim_stale": stale_claim_count > 0,
            "doc_age_days": int(config.get("doc_age_days", 0) or 0),
            "broken_refs": [f"broken-ref-{index + 1}" for index in range(broken_ref_count)],
            "version_bound": bool(
                config.get(
                    "version_bound",
                    not (docs_version and product_version and docs_version != product_version),
                )
            ),
            "docs_version": docs_version,
            "product_version": product_version,
        }
    return {
        "required_docs_defined": bool(config.get("required_docs_defined", False)),
        "required_docs_missing_code": "docs_lifecycle_required_docs_missing",
        "version_binding_enforced": bool(config.get("version_binding_enforced", False)),
        "broken_ref_detection_enabled": bool(config.get("broken_ref_detection_enabled", False)),
        "stale_doc_max_age_days": int(config.get("stale_doc_max_age_days", 0) or 0),
        "required_docs": required_docs,
        "doc_claim_stale": bool(config.get("doc_claim_stale", False)),
        "doc_age_days": int(config.get("doc_age_days", 0) or 0),
        "broken_refs": broken_refs,
        "version_bound": bool(config.get("version_bound", False)),
        "docs_version": str(config.get("docs_version", "") or ""),
        "product_version": str(config.get("product_version", "") or ""),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[DocsLifecycleFinding]:
    findings: list[DocsLifecycleFinding] = []
    if not config["required_docs_defined"]:
        findings.append(_finding(
            config["required_docs_missing_code"],
            "Documentation lifecycle requires required docs definition.",
            source_ref,
        ))
    if not config["version_binding_enforced"]:
        findings.append(_finding(
            "docs_lifecycle_version_binding_missing",
            "Documentation lifecycle requires version binding enforcement.",
            source_ref,
        ))
    if not config["broken_ref_detection_enabled"]:
        findings.append(_finding(
            "docs_lifecycle_broken_ref_detection_missing",
            "Documentation lifecycle requires broken reference detection.",
            source_ref,
        ))
    if config["doc_claim_stale"]:
        findings.append(_finding(
            "docs_lifecycle_stale_claim_denied",
            "Stale documentation claim is denied by lifecycle policy.",
            source_ref,
        ))
    if config["doc_age_days"] > config["stale_doc_max_age_days"]:
        findings.append(_finding(
            "docs_lifecycle_doc_exceeded_max_age",
            f"Documentation age {config['doc_age_days']} exceeds max {config['stale_doc_max_age_days']} days.",
            source_ref,
        ))
    if config["broken_refs"]:
        findings.append(_finding(
            "docs_lifecycle_broken_refs_found",
            f"Documentation lifecycle found {len(config['broken_refs'])} broken references.",
            source_ref,
        ))
    if not config["version_bound"]:
        code = "docs_lifecycle_version_not_bound"
        if config.get("docs_version") and config.get("product_version"):
            code = "docs_lifecycle_version_mismatch"
        findings.append(_finding(
            code,
            "Documentation must be version bound to product release.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> DocsLifecycleFinding:
    return DocsLifecycleFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
