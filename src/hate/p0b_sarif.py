"""SARIF, contract, and mutation helpers for P0b QEG export."""

from __future__ import annotations

import hashlib
from typing import Any


def _sarif_findings(sarif: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for run_index, run in enumerate(sarif.get("runs", [])):
        if not isinstance(run, dict):
            continue
        rules = {
            str(rule.get("id", "")): rule
            for tool in [run.get("tool", {})]
            for driver in [tool.get("driver", {})] if isinstance(driver, dict)
            for rule in driver.get("rules", []) if isinstance(rule, dict)
        }
        for result_index, result in enumerate(run.get("results", [])):
            if not isinstance(result, dict):
                continue
            rule_id = str(result.get("ruleId", "unknown-rule"))
            rule = rules.get(rule_id, {})
            location = _first_sarif_location(result)
            path = location.get("path", "")
            start_line = location.get("start_line", 0)
            end_line = location.get("end_line", start_line)
            message = result.get("message", {})
            message_text = str(message.get("text", "")) if isinstance(message, dict) else str(message)
            properties = result.get("properties", {}) if isinstance(result.get("properties"), dict) else {}
            fingerprints = result.get("fingerprints", {}) if isinstance(result.get("fingerprints"), dict) else {}
            partial_fingerprints = result.get("partialFingerprints", {}) if isinstance(result.get("partialFingerprints"), dict) else {}
            merged_fingerprints = {**partial_fingerprints, **fingerprints}
            findings.append({
                "finding_id": hashlib.sha256(f"{run_index}:{result_index}:{rule_id}:{path}:{start_line}".encode("utf-8")).hexdigest()[:16],
                "rule_id": rule_id,
                "rule_name": str(rule.get("name") or rule_id),
                "rule_short_description": _sarif_multiformat_text(rule.get("shortDescription")),
                "rule_full_description": _sarif_multiformat_text(rule.get("fullDescription")),
                "help_uri": str(rule.get("helpUri", "")),
                "title": str(rule.get("name") or rule_id),
                "level": str(result.get("level", "warning")),
                "severity": str(properties.get("security-severity") or properties.get("severity") or result.get("level", "warning")),
                "path": path.replace("\\", "/"),
                "start_line": start_line,
                "end_line": end_line,
                "start_column": location.get("start_column", 0),
                "end_column": location.get("end_column", 0),
                "location": location,
                "fingerprints": merged_fingerprints,
                "message": message_text,
            })
    return findings


def _contract_status(payload: dict[str, Any]) -> str:
    raw = str(payload.get("status") or payload.get("result") or payload.get("verification_status") or "").strip().lower()
    aliases = {
        "pass": "passed",
        "passed": "passed",
        "success": "passed",
        "verified": "passed",
        "ok": "passed",
        "fail": "failed",
        "failed": "failed",
        "failure": "failed",
        "error": "failed",
    }
    return aliases.get(raw, raw or "unknown")


def _mutation_status(payload: dict[str, Any]) -> str:
    raw = str(payload.get("status") or payload.get("result") or payload.get("mutant_status") or "").strip().lower()
    normalized = raw.replace(" ", "_").replace("-", "_")
    aliases = {
        "killed": "killed",
        "killed_by_timeout": "timeout",
        "timeout": "timeout",
        "survived": "survived",
        "no_coverage": "no_coverage",
        "nocoverage": "no_coverage",
        "not_covered": "no_coverage",
        "covered": "covered",
        "ignored": "ignored",
    }
    return aliases.get(normalized, normalized or "unknown")


def _line_ranges_overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    if left_start <= 0 or right_start <= 0:
        return True
    left_end = left_end or left_start
    right_end = right_end or right_start
    return left_start <= right_end and right_start <= left_end


def _first_sarif_location(result: dict[str, Any]) -> dict[str, Any]:
    locations = result.get("locations", [])
    if not locations or not isinstance(locations, list) or not isinstance(locations[0], dict):
        return {"path": "", "start_line": 0}
    physical = locations[0].get("physicalLocation", {})
    if not isinstance(physical, dict):
        return {"path": "", "start_line": 0}
    artifact = physical.get("artifactLocation", {})
    region = physical.get("region", {})
    path = str(artifact.get("uri", "")) if isinstance(artifact, dict) else ""
    start_line = int(region.get("startLine", 0)) if isinstance(region, dict) else 0
    end_line = int(region.get("endLine", start_line)) if isinstance(region, dict) else start_line
    start_column = int(region.get("startColumn", 0)) if isinstance(region, dict) else 0
    end_column = int(region.get("endColumn", 0)) if isinstance(region, dict) else 0
    return {
        "path": path.replace("\\", "/"),
        "start_line": start_line,
        "end_line": end_line,
        "start_column": start_column,
        "end_column": end_column,
        "uri_base_id": str(artifact.get("uriBaseId", "")) if isinstance(artifact, dict) else "",
    }


def _sarif_multiformat_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("markdown") or "")
    return ""
