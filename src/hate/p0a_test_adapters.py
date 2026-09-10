from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .execution_metadata import EXECUTION_FIELDS
from .p0a_execution import (
    execution_record_id,
    json_execution_metadata,
    mark_duplicate_observations,
    merge_execution_metadata,
    read_test_report,
    xml_execution_metadata,
)
from .p0a_io import (
    _slug,
    _stable_sha256,
    _to_posix,
)
from .p0a_outcomes import json_result_fields
from .p0a_records import _envelope
from .p0a_test_values import assertion_identity, identity_text, junit_duration


def parse_junit_xml(content: str) -> dict[str, Any]:
    """Parse JUnit XML text into dialect-neutral test dictionaries.

    This helper intentionally does not inspect fixture directory names. Dialect and
    markers are inferred from XML shape, testcase attributes, properties, and text.
    """
    diagnostics: dict[str, Any] = {"parser": "junit", "duplicate_ids": []}
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        return {"tests": [], "parser_diagnostics": {**diagnostics, "error": f"malformed_xml: {exc}"}}

    if root.tag == "testsuite":
        suites = [root]
        diagnostics["dialect"] = "testsuite"
    elif root.tag == "testsuites":
        suites = [suite for suite in root.findall(".//testsuite")]
        diagnostics["dialect"] = "testsuites"
    else:
        return {"tests": [], "parser_diagnostics": {**diagnostics, "error": f"missing_testsuite_root: {root.tag}"}}
    if not suites:
        return {"tests": [], "parser_diagnostics": {**diagnostics, "error": "missing_testsuite"}}

    tests: list[dict[str, Any]] = []
    for suite in suites:
        suite_name = suite.attrib.get("name", "junit")
        for index, case in enumerate(suite.findall("testcase"), start=1):
            location = f"junit.xml#/testsuite/{suite_name}/testcase/{index}"
            try:
                name = identity_text(case.attrib.get("name"), f"{location}.name")
                duration, duration_ms = junit_duration(case.attrib.get("time"), f"{location}.time")
            except ValueError as exc:
                return {"tests": [], "parser_diagnostics": {**diagnostics, "error": str(exc)}}
            classname = case.attrib.get("classname", "")
            file_path = _to_posix(case.attrib.get("file") or _file_from_classname(classname, suite_name))
            status, message = _junit_status_and_message(case)
            props = _junit_properties(case)
            text_blob = " ".join(
                item
                for item in [
                    message,
                    case.attrib.get("name", ""),
                    case.attrib.get("classname", ""),
                    _child_text(case, "system-out"),
                    _child_text(case, "system-err"),
                ]
                if item
            ).lower()
            canonical_id = f"junit:{file_path}::{name}"
            test: dict[str, Any] = {
                "suite": suite_name,
                "classname": classname,
                "file": file_path,
                "name": name,
                "status": status,
                "duration": duration,
                "duration_ms": duration_ms,
                "canonical_test_id": canonical_id,
                "sourceRef": f"junit.xml#/testsuite/{suite_name}/testcase/{index}",
            }
            if message:
                test["message"] = message
                test["failure_text_hash"] = _stable_sha256(message)[:16]
            for marker in ("xfail", "todo", "only"):
                if _truthy(props.get(marker)) or marker in text_blob or _truthy(case.attrib.get(marker)):
                    test[marker] = True
            try:
                test.update(xml_execution_metadata(case.attrib, props, test["sourceRef"]))
            except ValueError as exc:
                return {"tests": [], "parser_diagnostics": {**diagnostics, "error": str(exc)}}
            if status == "skipped" and not message:
                test["parser_diagnostics"] = [{"code": "skipped_without_reason", "severity": "warning"}]
            tests.append(test)
    diagnostics["duplicate_ids"] = mark_duplicate_observations(tests)
    return {"tests": tests, "parser_diagnostics": diagnostics}


def _parse_junit(path: Path, context: dict[str, Any], created_at: str, source_version: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    parsed = parse_junit_xml(path.read_text(encoding="utf-8"))
    diagnostics = parsed["parser_diagnostics"]
    if "error" in diagnostics:
        raise ValueError(str(diagnostics["error"]))
    records: list[dict[str, Any]] = []
    for index, test in enumerate(parsed["tests"], start=1):
        name = str(test["name"])
        canonical_test_id = str(test["canonical_test_id"])
        slug = _slug(f"{index}-{name}")
        payload = {
            "canonical_test_id": canonical_test_id,
            "framework": "junit",
            "status": test["status"],
            "duration_ms": test["duration_ms"],
            "file": test["file"],
            "identity_components": {
                "framework": "junit",
                "suite": test["suite"],
                "classname": test["classname"],
                "name": name,
            },
            "artifacts": [],
            "sourceRef": test["sourceRef"],
        }
        for optional_key in ("failure_text_hash", "message", "xfail", "todo", "only", *EXECUTION_FIELDS):
            if optional_key in test:
                payload[optional_key] = test[optional_key]
        if "parser_diagnostics" in test:
            payload["parser_diagnostics"] = payload.get("parser_diagnostics", []) + test["parser_diagnostics"]
        records.append(
            _envelope(
                context,
                "test_result",
                f"test-result-{context['run_id']}-{context['run_attempt']}-{slug}",
                created_at,
                source_version,
                payload,
            )
        )
    return records


def _parse_pytest_json(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
) -> list[dict[str, Any]]:
    """Parse pytest-json-report format into test_result records."""
    if not path.exists():
        return []
    data = read_test_report(path)
    if not isinstance(data, dict) or "tests" not in data:
        raise ValueError("pytest report requires tests array")
    tests = data.get("tests", [])
    if not isinstance(tests, list):
        raise ValueError("pytest tests must be a list")
    records: list[dict[str, Any]] = []
    occurrences: dict[str, int] = {}
    for test_index, test in enumerate(tests):
        if not isinstance(test, dict):
            raise ValueError("pytest test entry must be an object")
        location = f"{path.name}.tests[{test_index}]"
        nodeid = identity_text(test.get("nodeid"), f"{location}.nodeid")
        result_fields = json_result_fields(test, "pytest", location)
        # Extract file from nodeid (format: path/to/test.py::test_name)
        file_path = nodeid.split("::")[0] if "::" in nodeid else "unknown.py"
        name = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        payload = {
            "canonical_test_id": f"pytest:{nodeid}",
            "framework": "pytest",
            **result_fields,
            "file": _to_posix(file_path),
            "identity_components": {
                "framework": "pytest",
                "suite": file_path,
                "name": name,
            },
            "artifacts": [],
        }
        payload.update(json_execution_metadata(test, f"{path.name}.tests[{test_index}]", native_count="reruns"))
        records.append(
            _envelope(
                context,
                "test_result",
                execution_record_id(payload, context, occurrences),
                created_at,
                source_version,
                payload,
            )
        )
    return records


def _parse_vitest_json(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
) -> list[dict[str, Any]]:
    """Parse vitest JSON report format into test_result records."""
    if not path.exists():
        return []
    data = read_test_report(path)
    if not isinstance(data, dict) or "testResults" not in data:
        raise ValueError("vitest report requires testResults array")
    test_results = data.get("testResults", [])
    if not isinstance(test_results, list):
        raise ValueError("vitest testResults must be a list")
    records: list[dict[str, Any]] = []
    occurrences: dict[str, int] = {}
    for suite_index, suite in enumerate(test_results):
        if not isinstance(suite, dict):
            raise ValueError("vitest suite entry must be an object")
        assertions = suite.get("assertionResults", [])
        if not isinstance(assertions, list):
            raise ValueError("vitest assertionResults must be a list")
        suite_file = identity_text(suite.get("name"), f"{path.name}.testResults[{suite_index}].name") if assertions else ""
        for assertion_index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict):
                raise ValueError("vitest assertion entry must be an object")
            location = f"{path.name}.testResults[{suite_index}].assertionResults[{assertion_index}]"
            full_name, title, ancestors = assertion_identity(assertion, location)
            result_fields = json_result_fields(assertion, "vitest", location)
            meta = assertion.get("meta", {})
            if not isinstance(meta, dict):
                raise ValueError("vitest assertion meta must be an object")
            canonical_test_id = f"vitest:{suite_file}::{full_name}"
            payload = {
                "canonical_test_id": canonical_test_id,
                "framework": "vitest",
                **result_fields,
                "file": _to_posix(suite_file),
                "identity_components": {
                    "framework": "vitest",
                    "suite": suite_file,
                    "name": title,
                    "ancestors": ancestors,
                },
                "artifacts": [],
            }
            payload.update(merge_execution_metadata(
                json_execution_metadata(assertion, location, native_count="retryCount"),
                json_execution_metadata(meta, f"{location}.meta", native_count="retryCount"), location,
            ))
            records.append(
                _envelope(
                    context,
                    "test_result",
                    execution_record_id(payload, context, occurrences),
                    created_at,
                    source_version,
                    payload,
                )
            )
    return records


def _parse_jest_json(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
) -> list[dict[str, Any]]:
    """Parse jest JSON report format into test_result records."""
    if not path.exists():
        return []
    data = read_test_report(path)
    if not isinstance(data, dict) or "testResults" not in data:
        raise ValueError("jest report requires testResults array")
    test_results = data.get("testResults", [])
    if not isinstance(test_results, list):
        raise ValueError("jest testResults must be a list")
    records: list[dict[str, Any]] = []
    occurrences: dict[str, int] = {}
    for suite_index, suite in enumerate(test_results):
        if not isinstance(suite, dict):
            raise ValueError("jest suite entry must be an object")
        assertions = suite.get("assertionResults", [])
        if not isinstance(assertions, list):
            raise ValueError("jest assertionResults must be a list")
        suite_file = identity_text(suite.get("name"), f"{path.name}.testResults[{suite_index}].name") if assertions else ""
        for assertion_index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict):
                raise ValueError("jest assertion entry must be an object")
            location = f"{path.name}.testResults[{suite_index}].assertionResults[{assertion_index}]"
            full_name, title, ancestors = assertion_identity(assertion, location)
            result_fields = json_result_fields(assertion, "jest", location)
            # Check for snapshot failures
            failure_messages = assertion.get("failureMessages", [])
            is_snapshot_failure = any("snapshot" in str(msg).lower() for msg in failure_messages)
            canonical_test_id = f"jest:{suite_file}::{full_name}"
            payload = {
                "canonical_test_id": canonical_test_id,
                "framework": "jest",
                **result_fields,
                "file": _to_posix(suite_file),
                "identity_components": {
                    "framework": "jest",
                    "suite": suite_file,
                    "name": title,
                    "ancestors": ancestors,
                },
                "artifacts": [],
            }
            if is_snapshot_failure:
                payload["failure_type"] = "snapshot_mismatch"
            meta = assertion.get("meta", {})
            if not isinstance(meta, dict):
                raise ValueError("jest assertion meta must be an object")
            payload.update(merge_execution_metadata(
                json_execution_metadata(assertion, location, native_count="retryCount"),
                json_execution_metadata(meta, f"{location}.meta", native_count="retryCount"), location,
            ))
            records.append(
                _envelope(
                    context,
                    "test_result",
                    execution_record_id(payload, context, occurrences),
                    created_at,
                    source_version,
                    payload,
                )
            )
    return records
def _file_from_classname(classname: str, suite_name: str) -> str:
    if classname:
        suffix = ".go" if classname.startswith("Test") and "." not in classname else ".py"
        return classname.replace(".", "/").replace("\\", "/") + suffix
    if suite_name.endswith((".js", ".ts", ".py", ".go")):
        return suite_name
    return "unknown.py"


def _junit_status_and_message(case: ET.Element) -> tuple[str, str]:
    for child_name, status in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
        child = case.find(child_name)
        if child is not None:
            message = child.attrib.get("message") or (child.text or "").strip()
            return status, message
    return "passed", ""


def _junit_properties(case: ET.Element) -> dict[str, str]:
    props: dict[str, str] = {}
    for prop in case.findall("./properties/property"):
        name = prop.attrib.get("name")
        if name:
            props[name.lower()] = prop.attrib.get("value", "true")
    return props


def _child_text(case: ET.Element, child_name: str) -> str:
    child = case.find(child_name)
    return (child.text or "").strip() if child is not None else ""


def _truthy(value: Any) -> bool:
    return str(value).lower() in {"1", "true", "yes", "y", "on"}


def _nearest_suite_name(case: ET.Element, root: ET.Element) -> str:
    suite = root.find(".//testsuite")
    return suite.attrib.get("name", "junit") if suite is not None else "junit"

