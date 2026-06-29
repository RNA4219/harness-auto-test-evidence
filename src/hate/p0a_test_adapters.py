from __future__ import annotations

import hashlib
import json
import mimetypes
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .p0a_constants import REDACTION_STATUS, SCHEMA_VERSION, SOURCE_TOOL
from .p0a_io import (
    _artifact_kind,
    _dq,
    _file_sha256,
    _read_optional_json,
    _slug,
    _stable_sha256,
    _stable_source_ref,
    _to_posix,
)
from .p0a_records import _envelope


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
    seen: set[str] = set()
    for suite in suites:
        suite_name = suite.attrib.get("name", "junit")
        for index, case in enumerate(suite.findall("testcase"), start=1):
            name = case.attrib.get("name", f"case_{index}")
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
            if canonical_id in seen:
                diagnostics["duplicate_ids"].append(canonical_id)
            seen.add(canonical_id)
            test = {
                "suite": suite_name,
                "classname": classname,
                "file": file_path,
                "name": name,
                "status": status,
                "duration": _safe_float(case.attrib.get("time")),
                "duration_ms": int(round(_safe_float(case.attrib.get("time")) * 1000)),
                "canonical_test_id": canonical_id,
                "sourceRef": f"junit.xml#/testsuite/{suite_name}/testcase/{index}",
            }
            if message:
                test["message"] = message
                test["failure_text_hash"] = _stable_sha256(message)[:16]
            for marker in ("xfail", "todo", "only"):
                if _truthy(props.get(marker)) or marker in text_blob or _truthy(case.attrib.get(marker)):
                    test[marker] = True
            retry_index = case.attrib.get("retry_index") or case.attrib.get("retry") or props.get("retry_index")
            if retry_index is not None:
                test["retry_index"] = int(_safe_float(str(retry_index)))
            if _truthy(case.attrib.get("flaky")) or _truthy(props.get("flaky")) or int(test.get("retry_index", 0)) > 0:
                test["flaky"] = True
            if status == "skipped" and not message:
                test["parser_diagnostics"] = [{"code": "skipped_without_reason", "severity": "warning"}]
            tests.append(test)
    return {"tests": tests, "parser_diagnostics": diagnostics}


def _parse_junit(path: Path, context: dict[str, Any], created_at: str, source_version: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    parsed = parse_junit_xml(path.read_text(encoding="utf-8"))
    diagnostics = parsed["parser_diagnostics"]
    if "error" in diagnostics:
        raise ValueError(str(diagnostics["error"]))
    records: list[dict[str, Any]] = []
    duplicate_ids = set(diagnostics.get("duplicate_ids", []))
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
        for optional_key in ("failure_text_hash", "message", "xfail", "todo", "only", "retry_index", "flaky"):
            if optional_key in test:
                payload[optional_key] = test[optional_key]
        if canonical_test_id in duplicate_ids:
            payload["parser_diagnostics"] = [{"code": "duplicate_testcase_id", "severity": "error"}]
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
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or "tests" not in data:
        raise ValueError("pytest report requires tests array")
    tests = data.get("tests", [])
    if not isinstance(tests, list):
        raise ValueError("pytest tests must be a list")
    records: list[dict[str, Any]] = []
    for test in tests:
        if not isinstance(test, dict):
            raise ValueError("pytest test entry must be an object")
        nodeid = str(test.get("nodeid", ""))
        if not nodeid:
            raise ValueError("pytest test entry requires nodeid")
        outcome = str(test.get("outcome", "unknown"))
        # Map pytest outcomes to canonical status
        status_map = {
            "passed": "passed",
            "failed": "failed",
            "skipped": "skipped",
            "error": "error",
            "xfail": "passed",  # expected failure is still passed
            "xpassed": "passed",  # unexpected pass
        }
        status = status_map.get(outcome, "inconclusive")
        # Extract file from nodeid (format: path/to/test.py::test_name)
        file_path = nodeid.split("::")[0] if "::" in nodeid else "unknown.py"
        name = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        duration_sec = float(test.get("duration", 0))
        duration_ms = int(round(duration_sec * 1000))
        # Check for flaky marker
        flaky = bool(test.get("flaky") or test.get("reruns", 0) > 0)
        retry_index = int(test.get("retry_index", 0)) if test.get("retry_index") else None
        slug = _slug(name)
        payload = {
            "canonical_test_id": f"pytest:{nodeid}",
            "framework": "pytest",
            "status": status,
            "duration_ms": duration_ms,
            "file": _to_posix(file_path),
            "identity_components": {
                "framework": "pytest",
                "suite": file_path,
                "name": name,
            },
            "artifacts": [],
        }
        if flaky:
            payload["flaky"] = True
        if retry_index is not None:
            payload["retry_index"] = retry_index
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


def _parse_vitest_json(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
) -> list[dict[str, Any]]:
    """Parse vitest JSON report format into test_result records."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or "testResults" not in data:
        raise ValueError("vitest report requires testResults array")
    test_results = data.get("testResults", [])
    if not isinstance(test_results, list):
        raise ValueError("vitest testResults must be a list")
    records: list[dict[str, Any]] = []
    for suite in test_results:
        if not isinstance(suite, dict):
            raise ValueError("vitest suite entry must be an object")
        assertions = suite.get("assertionResults", [])
        if not isinstance(assertions, list):
            raise ValueError("vitest assertionResults must be a list")
        suite_file = str(suite.get("name", "unknown.test.ts"))
        for assertion in assertions:
            if not isinstance(assertion, dict):
                raise ValueError("vitest assertion entry must be an object")
            full_name = str(assertion.get("fullName", assertion.get("title", "")))
            title = str(assertion.get("title", full_name))
            vitest_status = str(assertion.get("status", "unknown"))
            # Map vitest status to canonical
            status_map = {
                "passed": "passed",
                "failed": "failed",
                "skipped": "skipped",
                "pending": "skipped",
                "todo": "skipped",
            }
            status = status_map.get(vitest_status, "inconclusive")
            duration_ms = int(assertion.get("duration", 0))
            # Check for flaky meta
            meta = assertion.get("meta", {})
            flaky = bool(meta.get("flaky") or meta.get("retryCount", 0) > 0)
            canonical_test_id = f"vitest:{suite_file}::{full_name}"
            slug = _slug(title)
            payload = {
                "canonical_test_id": canonical_test_id,
                "framework": "vitest",
                "status": status,
                "duration_ms": duration_ms,
                "file": _to_posix(suite_file),
                "identity_components": {
                    "framework": "vitest",
                    "suite": suite_file,
                    "name": title,
                    "ancestors": assertion.get("ancestorTitles", []),
                },
                "artifacts": [],
            }
            if flaky:
                payload["flaky"] = True
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


def _parse_jest_json(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
) -> list[dict[str, Any]]:
    """Parse jest JSON report format into test_result records."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or "testResults" not in data:
        raise ValueError("jest report requires testResults array")
    test_results = data.get("testResults", [])
    if not isinstance(test_results, list):
        raise ValueError("jest testResults must be a list")
    records: list[dict[str, Any]] = []
    for suite in test_results:
        if not isinstance(suite, dict):
            raise ValueError("jest suite entry must be an object")
        assertions = suite.get("assertionResults", [])
        if not isinstance(assertions, list):
            raise ValueError("jest assertionResults must be a list")
        suite_file = str(suite.get("name", "unknown.test.js"))
        for assertion in assertions:
            if not isinstance(assertion, dict):
                raise ValueError("jest assertion entry must be an object")
            full_name = str(assertion.get("fullName", assertion.get("title", "")))
            title = str(assertion.get("title", full_name))
            jest_status = str(assertion.get("status", "unknown"))
            # Map jest status to canonical
            status_map = {
                "passed": "passed",
                "failed": "failed",
                "skipped": "skipped",
                "pending": "skipped",
                "todo": "skipped",
                "disabled": "skipped",
            }
            status = status_map.get(jest_status, "inconclusive")
            duration_ms = int(assertion.get("duration", 0))
            # Check for snapshot failures
            failure_messages = assertion.get("failureMessages", [])
            is_snapshot_failure = any("snapshot" in str(msg).lower() for msg in failure_messages)
            canonical_test_id = f"jest:{suite_file}::{full_name}"
            slug = _slug(title)
            payload = {
                "canonical_test_id": canonical_test_id,
                "framework": "jest",
                "status": status,
                "duration_ms": duration_ms,
                "file": _to_posix(suite_file),
                "identity_components": {
                    "framework": "jest",
                    "suite": suite_file,
                    "name": title,
                    "ancestors": assertion.get("ancestorTitles", []),
                },
                "artifacts": [],
            }
            if is_snapshot_failure:
                payload["failure_type"] = "snapshot_mismatch"
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


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _nearest_suite_name(case: ET.Element, root: ET.Element) -> str:
    suite = root.find(".//testsuite")
    return suite.attrib.get("name", "junit") if suite is not None else "junit"

