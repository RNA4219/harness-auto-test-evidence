"""QEG bundle内のHATE precheckの許可情報とsoft gapを各P1a出力へ接続する。"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

from .input_values import ParsedFloat
from .p1a_io import TrustError


def _precheck_nodes(bundle: dict[str, Any]) -> Iterator[tuple[int, dict[str, Any]]]:
    for index, node in enumerate(bundle.get("nodes", [])):
        if node.get("kind") == "gate_verdict" and str(node.get("id", "")).startswith("hate_precheck:"):
            yield index, node


def validate_precheck_inputs(bundle: dict[str, Any], path: Path) -> None:
    """旧bundleの省略項目を補わず、宣言済みの解釈対象を出力前に検証する。"""
    for index, node in _precheck_nodes(bundle):
        data = node["data"]
        location = f"{path}: nodes[{index}].data"
        if "decision" in data and not isinstance(data["decision"], str):
            raise TrustError(f"{location}.decision: must be a string", exit_code=1)
        if "qeg_export_allowed" in data and type(data["qeg_export_allowed"]) is not bool:
            raise TrustError(f"{location}.qeg_export_allowed: must be a boolean", exit_code=1)
        if "exit_code" in data:
            try:
                _integer_exit_code(data["exit_code"])
            except ValueError as exc:
                raise TrustError(f"{location}.exit_code: {exc}", exit_code=1) from exc
        for field, item_type in (("soft_gaps", dict), ("dq_hits", dict), ("reasons", str)):
            if field not in data:
                continue
            values = data[field]
            if not isinstance(values, list):
                raise TrustError(f"{location}.{field}: must be an array", exit_code=1)
            for item_index, value in enumerate(values):
                if not isinstance(value, item_type):
                    expected = "an object" if item_type is dict else "a string"
                    raise TrustError(f"{location}.{field}[{item_index}]: must be {expected}", exit_code=1)


def _integer_exit_code(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a JSON integer")
    exact = Decimal(value.lexeme) if isinstance(value, ParsedFloat) else value
    try:
        normalized = int(exact)
    except (ValueError, OverflowError) as exc:
        raise ValueError("must be a finite JSON integer") from exc
    if exact != normalized:
        raise ValueError("must be a JSON integer; fractional values are invalid")
    return normalized


def _permission_violations(data: dict[str, Any], index: int) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    def add(field: str, issue: str, message: str) -> None:
        violations.append({
            "field": field, "issue": issue, "message": message,
            "validation_path": ["nodes", index, "data", field],
        })

    for field in ("decision", "exit_code", "qeg_export_allowed"):
        if field not in data:
            add(field, "precheck_permission_missing", f"{field} is missing")
    decision = data.get("decision")
    if decision in {"ineligible", "hard_dq"}:
        add("decision", "precheck_export_denied", f"decision is {decision}")
    elif "decision" in data and decision not in {"eligible", "conditional"}:
        add("decision", "invalid_precheck_decision", "decision is not recognized")
    if "exit_code" in data:
        exit_code = _integer_exit_code(data["exit_code"])
        if exit_code == 2:
            add("exit_code", "precheck_export_denied", "exit_code is 2")
        elif exit_code != 0:
            add("exit_code", "invalid_precheck_exit_code", "exit_code is neither 0 nor 2")
    if data.get("qeg_export_allowed") is False:
        add("qeg_export_allowed", "precheck_export_denied", "qeg_export_allowed is false")
    if data.get("dq_hits"):
        add("dq_hits", "precheck_export_denied", "dq_hits is not empty")
    return violations


def precheck_permission_issues(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """処理可能な許可不備を1 nodeあたり1所見へ集約し、原因ごとの位置を残す。"""
    issues: list[dict[str, Any]] = []
    for index, node in _precheck_nodes(bundle):
        data = node["data"]
        violations = _permission_violations(data, index)
        if violations:
            denied = any(item["issue"] == "precheck_export_denied" for item in violations)
            issues.append({
                "issue": "precheck_export_not_allowed" if denied else "precheck_permission_invalid",
                "message": "HATE precheck does not establish QEG export permission: "
                           + "; ".join(item["message"] for item in violations),
                "violations": violations,
                "precheck_node_id": node["id"], "precheck_payload": data,
                "precheck_reasons": data.get("reasons", []),
                "validation_path": ["nodes", index, "data"],
                "source_refs": sorted({"qeg-bundle.json", *node.get("sourceRefs", [])}),
            })
    return issues


def precheck_gaps(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """gap内容を保持し、詳細のない旧conditionalにも根拠不足を明記する。"""
    gaps: list[dict[str, Any]] = []
    for index, node in _precheck_nodes(bundle):
        data = node["data"]
        declared = data.get("soft_gaps", [])
        context = {
            "precheck_node_id": node["id"],
            "precheck_reasons": data.get("reasons", []),
            "source_refs": sorted({"qeg-bundle.json", *node.get("sourceRefs", [])}),
        }
        for gap_index, gap in enumerate(declared):
            message = gap.get("message")
            gaps.append({
                **context,
                "issue": "precheck_soft_gap",
                "message": message if isinstance(message, str) and message.strip() else "Precheck declares a soft gap.",
                "gap": gap,
                "validation_path": ["nodes", index, "data", "soft_gaps", gap_index],
            })
        if data.get("decision") == "conditional" and not declared:
            gaps.append({
                **context,
                "issue": "precheck_soft_gap_details_missing",
                "message": "Precheck is conditional, but soft-gap details are missing from the bundle.",
                "gap": None,
                "validation_path": ["nodes", index, "data", "soft_gaps"],
            })
    return gaps
