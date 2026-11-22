"""JSON reportの状態を、未実行・期待失敗の宣言を失わずに正規化する。"""

from __future__ import annotations

from typing import Any

from .p0a_test_values import assertion_duration, identity_text, pytest_duration


def json_result_fields(item: dict[str, Any], framework: str, location: str) -> dict[str, Any]:
    field = "outcome" if framework == "pytest" else "status"
    declared = identity_text(item.get(field, "unknown"), f"{location}.{field}")
    status_map = {"passed": "passed", "failed": "failed", "skipped": "skipped", "error": "error"}
    if framework == "pytest":
        status_map.update(xfail="skipped", xfailed="skipped", xpass="passed", xpassed="passed")
    else:
        status_map.update(pending="skipped", todo="skipped", disabled="skipped", focused="inconclusive")
    status = status_map.get(declared, "inconclusive")
    fields: dict[str, Any] = {"source_status": declared, "status": status}
    diagnostics = []
    if declared not in status_map:
        diagnostics.append({"code": "unsupported_test_status", "severity": "warning", "sourceRef": f"{location}.{field}",
                            "message": f"Reported status {declared!r} does not establish pass or failure."})
    if framework == "pytest" and declared in {"xfail", "xfailed", "xpass", "xpassed"}:
        fields["xfail"] = True
        if declared in {"xpass", "xpassed"}:
            fields["xpass"] = True
    if declared == "todo":
        fields["todo"] = True
    if declared == "focused":
        fields["only"] = True
    if "wouldRun" in item:
        if type(item["wouldRun"]) is not bool:
            raise ValueError(f"{location}.wouldRun must be a boolean")
        fields["wouldRun"] = item["wouldRun"]
        if item["wouldRun"]:
            fields["status"] = "inconclusive"
            diagnostics.append({"code": "test_not_executed", "severity": "warning", "sourceRef": f"{location}.wouldRun",
                                "message": "Test was collected as runnable but was not executed."})
    duration: dict[str, Any] = {"duration_ms": pytest_duration(item, location)} if framework == "pytest" else assertion_duration(item, location)
    fields.update(duration)
    diagnostics.extend(duration.get("parser_diagnostics", []))
    if diagnostics:
        fields["parser_diagnostics"] = diagnostics
    return fields
