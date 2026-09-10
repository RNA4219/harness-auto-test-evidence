"""保存証跡の集約レポートと、失敗状態を保持するreadiness判定。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .report_serialization import report_data, report_hash

if TYPE_CHECKING:
    from .replay import BaselineInfo, ReplayReport


def build_store_replay_report(
    replay_report: ReplayReport | dict[str, Any],
    *,
    comparison_report: Any | None = None,
    doctor_report: Any | None = None,
    migration_report: dict[str, Any] | None = None,
    baseline_info: BaselineInfo | dict[str, Any] | None = None,
    include_observation: bool = False,
) -> dict[str, Any]:
    """Build the product-grade store-replay-report envelope.

    The replay, compare, doctor, and migration modules intentionally remain
    separate. This builder creates the evidence report required by product-grade
    acceptance so release checks can prove replay determinism, diff behavior,
    corruption diagnostics, migration state, and baseline selection together.
    """

    replay = dict(replay_report) if isinstance(replay_report, dict) else replay_report.to_dict(include_observation=include_observation)
    replay = report_data(replay, observation_field="replayed_at", include_observation=include_observation)
    comparison = _to_dict_or_none(comparison_report)
    doctor = _to_dict_or_none(doctor_report)
    migration = dict(migration_report if migration_report is not None else replay.get("migration_status", {}))
    baseline = _baseline_section(baseline_info, comparison, replay)
    conflicts = _identity_conflicts(replay, comparison, doctor, baseline)
    if conflicts:
        replay["diagnostics"] = _unique_diagnostics([*replay.get("diagnostics", []), *conflicts])
        if any(item["issue"] == "baseline_identity_mismatch" for item in conflicts):
            baseline["valid"] = False
    replay["diagnostics"] = _supplemental_diagnostics(replay, comparison, doctor, migration if migration_report is not None else None)
    diff_entries = _diff_entries(comparison) if comparison is not None else replay.get("diff_entries", [])
    corruption_findings = _corruption_findings(doctor) if doctor is not None else replay.get("corruption_findings", [])
    migration_status = _migration_status(replay, migration)
    evidence = {**replay, "diff_entries": diff_entries, "corruption_findings": corruption_findings}
    readiness_effect = _store_replay_readiness(evidence, comparison, doctor, migration_status, baseline, migration)
    report = {
        **replay,
        "record_type": "store_replay_report",
        "baseline_resolution": baseline,
        "diff_entries": diff_entries,
        "corruption_findings": corruption_findings,
        "migration_status": migration_status,
        "readiness_effect": readiness_effect,
        "sourceRefs": _store_replay_source_refs(replay, comparison, doctor, migration if migration_report is not None else {}),
    }
    report["replay_hash"] = report_hash(report, hash_field="replay_hash", observation_field="replayed_at")
    return report_data(report, observation_field="replayed_at", include_observation=include_observation)


def _to_dict_or_none(value: Any | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        if not isinstance(converted, dict):
            raise TypeError("report.to_dict() must return a dictionary")
        return dict(converted)
    if isinstance(value, dict):
        return dict(value)
    raise TypeError("report must be a dictionary or provide to_dict()")


def _unique_diagnostics(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _supplemental_diagnostics(
    replay: dict[str, Any], comparison: dict[str, Any] | None, doctor: dict[str, Any] | None,
    migration: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    diagnostics = list(replay.get("diagnostics", []))
    for name, supplement in (("comparison", comparison), ("doctor", doctor), ("migration", migration)):
        if supplement is None:
            continue
        for field in (("diagnostics",) if name == "doctor" else ("diagnostics", "findings")):
            for item in supplement.get(field, []):
                entry = {"issue": "supplemental_report_diagnostic", "report": name, "field": field, "detail": item}
                if "severity" in item:
                    entry["severity"] = item["severity"]
                diagnostics.append(entry)
    return _unique_diagnostics(diagnostics)


def _identity_conflicts(
    replay: dict[str, Any], comparison: dict[str, Any] | None, doctor: dict[str, Any] | None,
    baseline: dict[str, Any],
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for name, other in (("comparison", comparison), ("doctor", doctor)):
        if other is None:
            continue
        for field in ("bundle_id", "run_id"):
            if other.get(field) and other[field] != replay.get(field):
                conflicts.append({"issue": "report_identity_mismatch", "report": name, "field": field, "severity": "hard_dq"})
    sources = [baseline, comparison or {}]
    if isinstance(replay.get("baseline_resolution"), dict):
        sources.append(replay["baseline_resolution"])
    for field in ("baseline_bundle_id", "baseline_run_id"):
        identities = {source[field] for source in sources if source.get(field)}
        if len(identities) > 1:
            conflicts.append({"issue": "baseline_identity_mismatch", "field": field, "severity": "hard_dq"})
    return conflicts


def _baseline_section(
    baseline_info: BaselineInfo | dict[str, Any] | None,
    comparison: dict[str, Any] | None,
    replay: dict[str, Any],
) -> dict[str, Any]:
    if baseline_info is None and isinstance(replay.get("baseline_resolution"), dict):
        baseline_info = replay["baseline_resolution"]
    if baseline_info is not None:
        baseline = baseline_info.to_dict() if hasattr(baseline_info, "to_dict") else dict(baseline_info)
        return {
            "baseline_bundle_id": str(baseline.get("baseline_bundle_id") or ""),
            "baseline_run_id": str(baseline.get("baseline_run_id") or ""),
            "baseline_created_at": str(baseline.get("baseline_created_at") or ""),
            "selection_method": str(baseline.get("selection_method") or "explicit_ref"),
            "is_filename_sort": bool(baseline.get("is_filename_sort", False)),
            "valid": (bool(baseline.get("baseline_bundle_id")) or (
                baseline.get("selection_method") == "none" and not baseline.get("baseline_run_id")
            ))
            and not bool(baseline.get("is_filename_sort", False)) and baseline.get("valid", True) is True,
        }
    if comparison:
        is_filename_sort = bool(comparison.get("is_filename_sort_baseline", False))
        method = str(comparison.get("baseline_selection_method") or "none")
        return {
            "baseline_bundle_id": str(comparison.get("baseline_bundle_id") or ""),
            "baseline_run_id": str(comparison.get("baseline_run_id") or ""),
            "baseline_created_at": "",
            "selection_method": method,
            "is_filename_sort": is_filename_sort,
            "valid": bool(comparison.get("baseline_bundle_id")) and not is_filename_sort,
        }
    return {
        "baseline_bundle_id": "",
        "baseline_run_id": "",
        "baseline_created_at": "",
        "selection_method": "none",
        "is_filename_sort": False,
        "valid": True,
    }


def _diff_entries(comparison: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not comparison:
        return []
    entries: list[dict[str, Any]] = []
    for item in comparison.get("artifact_diffs", []):
        entries.append(
            {
                "artifact_id": str(item.get("artifact_id") or ""),
                "baseline_hash": item.get("baseline_hash"),
                "current_hash": item.get("current_hash"),
                "result": str(item.get("result") or "incomparable"),
                "details": dict(item.get("details") or {}),
            }
        )
    return entries


def _corruption_findings(doctor: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not doctor:
        return []
    findings: list[dict[str, Any]] = []
    for item in doctor.get("findings", []):
        retained = {
            "finding_id": str(item.get("finding_id") or ""),
            "severity": str(item.get("severity") or "info"),
            "category": str(item.get("category") or "unknown"),
            "message": str(item.get("message") or ""),
            "path": item.get("path"),
            "remediation": item.get("remediation"),
        }
        for field in ("bundle_id", "artifact_id", "expected", "actual", "diagnostics", "run_id"):
            if field in item:
                retained[field] = item[field]
        if "run_id" not in retained:
            run_id = item.get("diagnostics", {}).get("run_id") or doctor.get("run_id")
            if run_id is not None:
                retained["run_id"] = run_id
        findings.append(retained)
    return findings


def _migration_status(replay: dict[str, Any], migration: dict[str, Any]) -> dict[str, Any]:
    if migration:
        compatible = migration.get("compatibility_class") == "compatible" and migration.get("schema_compatible", True) is True
        return {
            "schema_compatible": compatible and replay.get("schema_compatible") is True,
            "migration_hold": not compatible or migration.get("readiness_effect") in {"hold", "hard_dq"}
            or migration.get("migration_hold", False) is True
            or replay.get("migration_hold", False) is True or replay.get("schema_compatible") is not True,
            "compatibility_class": str(migration.get("compatibility_class") or "unknown"),
            "rollback_plan_ref": str(migration.get("rollback_plan_ref") or migration.get("rollback_ref") or ""),
            "checksum_before": str(migration.get("checksum_before") or ""),
            "checksum_after": str(migration.get("checksum_after") or ""),
        }
    return {
        "schema_compatible": bool(replay.get("schema_compatible", False)),
        "migration_hold": replay.get("migration_hold", False) is True or replay.get("schema_compatible") is not True,
        "compatibility_class": "compatible" if replay.get("schema_compatible", False) else "migration_required",
        "rollback_plan_ref": "",
        "checksum_before": "",
        "checksum_after": "",
    }


def _store_replay_readiness(
    replay: dict[str, Any],
    comparison: dict[str, Any] | None,
    doctor: dict[str, Any] | None,
    migration_status: dict[str, Any],
    baseline: dict[str, Any],
    migration: dict[str, Any],
) -> str:
    if replay.get("readiness_effect") == "hard_dq":
        return "hard_dq"
    if any(replay.get(flag, True) is not True for flag in ("legal_hold_preserved", "baseline_valid", "integrity_ok")):
        return "hard_dq"
    if _has_hard_dq(replay) or _has_hard_dq(doctor) or _has_hard_dq(comparison) or _has_hard_dq(migration):
        return "hard_dq"
    if migration.get("readiness_effect") == "hard_dq":
        return "hard_dq"
    if doctor and (doctor.get("healthy") is False or int(doctor.get("hard_dq_count", 0) or 0) > 0):
        return "hard_dq"
    if int(replay.get("hash_mismatches", 0) or 0) > 0 or int(replay.get("artifacts_missing", 0) or 0) > 0:
        return "hard_dq"
    if not baseline["valid"]:
        return "hard_dq"
    if comparison and bool(comparison.get("is_filename_sort_baseline", False)):
        return "hard_dq"
    if migration_status["migration_hold"] or replay.get("readiness_effect") == "hold":
        return "hold"
    if comparison and str(comparison.get("comparison_result")) in {"regression", "incomparable"}:
        return "hold"
    if any(item.get("result") in {"regression", "incomparable"} for item in replay.get("diff_entries", [])):
        return "hold"
    if comparison and int(comparison.get("regressions", 0) or 0) > 0:
        return "hold"
    return "pass"


def _has_hard_dq(report: dict[str, Any] | None) -> bool:
    if report is None:
        return False
    return any(
        isinstance(item, dict) and item.get("severity") in {"hard_dq", "hard_block", "critical"}
        for field in ("diagnostics", "findings", "corruption_findings") for item in report.get(field, [])
    )


def _store_replay_source_refs(
    replay: dict[str, Any],
    comparison: dict[str, Any] | None,
    doctor: dict[str, Any] | None,
    migration: dict[str, Any],
) -> list[str]:
    refs = {
        "src/hate/store/replay.py",
        "docs/process/STORE_SCHEMA_REQUIREMENTS.md",
        "docs/process/EPIC_TASK_PACKETS.md:HATE-PG-006",
    }
    refs.update(replay.get("sourceRefs", []))
    if comparison:
        refs.add("src/hate/store/compare.py")
    if doctor:
        refs.add("src/hate/store/doctor.py")
    if migration:
        refs.add("src/hate/store/migration_rebuild.py")
    return sorted(refs)
