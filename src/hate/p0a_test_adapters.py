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

def _parse_junit(path: Path, context: dict[str, Any], created_at: str, source_version: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    cases = root.findall(".//testcase")
    records: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", f"case_{index}")
        file_path = case.attrib.get("file") or classname.replace(".", "/") + ".py"
        suite = _nearest_suite_name(case, root)
        status = "passed"
        if case.find("failure") is not None:
            status = "failed"
        elif case.find("error") is not None:
            status = "error"
        elif case.find("skipped") is not None:
            status = "skipped"
        duration_ms = int(round(float(case.attrib.get("time", "0")) * 1000))
        canonical_test_id = f"junit:{file_path}::{name}"
        slug = _slug(name)
        payload = {
            "canonical_test_id": canonical_test_id,
            "framework": "junit",
            "status": status,
            "duration_ms": duration_ms,
            "file": _to_posix(file_path),
            "identity_components": {
                "framework": "junit",
                "suite": suite,
                "classname": classname,
                "name": name,
            },
            "artifacts": [],
        }
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
def _nearest_suite_name(case: ET.Element, root: ET.Element) -> str:
    suite = root.find(".//testsuite")
    return suite.attrib.get("name", "junit") if suite is not None else "junit"

