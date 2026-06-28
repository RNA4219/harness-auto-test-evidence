from __future__ import annotations
import hashlib
import json
import mimetypes
import posixpath
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
SCHEMA_VERSION = "HATE/v1"
SOURCE_TOOL = "harness-auto-test-evidence"
REDACTION_STATUS = "not_required"
from .p0a_io import (
    _artifact_kind,
    _dq,
    _file_sha256,
    _read_optional_json,
    _slug,
    _stable_sha256,
    _stable_source_ref,
    _to_posix,
    _write_json,
    _write_ndjson,
)
@dataclass
class PrecheckError(Exception):
    message: str
    exit_code: int = 1
    decision: dict[str, Any] | None = None
    out_dir: Path | None = None
    def __str__(self) -> str:
        return self.message
def _read_context(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PrecheckError(f"missing required input: {path}", exit_code=1)
    with path.open("r", encoding="utf-8") as handle:
        context = json.load(handle)
    if not isinstance(context, dict):
        raise PrecheckError(f"{path.name} must be a JSON object", exit_code=1)
    required = ["repository", "workflow", "job", "run_id", "run_attempt", "started_at"]
    missing = [field for field in required if field not in context]
    if missing:
        raise PrecheckError(f"{path.name} missing fields: {', '.join(missing)}", exit_code=1)
    provider = _normalize_ci_provider(str(context.get("provider") or context.get("ci_provider") or ""))
    if not provider:
        provider = "github-actions" if path.name == "github-context.json" else "generic-ci"
    context["_context_source_name"] = path.name
    context["_ci_provider"] = provider
    return context

def _normalize_ci_provider(provider: str) -> str:
    normalized = provider.strip().lower().replace("_", "-")
    aliases = {
        "github": "github-actions",
        "github-action": "github-actions",
        "github-actions": "github-actions",
        "generic": "generic-ci",
        "generic-ci": "generic-ci",
        "genericci": "generic-ci",
    }
    return aliases.get(normalized, normalized)

def _run_record(context: dict[str, Any], created_at: str, source_version: str) -> dict[str, Any]:
    payload = {
        "repository": context["repository"],
        "workflow": context["workflow"],
        "job": context["job"],
        "event_name": context.get("event_name", "unknown"),
        "started_at": context["started_at"],
        "finished_at": context.get("finished_at"),
        "ci": {
            "provider": context.get("_ci_provider", "github-actions"),
            "run_id": str(context["run_id"]),
            "run_attempt": int(context["run_attempt"]),
            "actor": context.get("actor"),
            "ref": context.get("ref"),
        },
    }
    base_sha = str(context.get("base_sha") or "")
    if re.match(r"^[A-Fa-f0-9]{7,64}$", base_sha):
        payload["base_sha"] = base_sha
    return _envelope(context, "run", f"run-{context['run_id']}-attempt-{context['run_attempt']}", created_at, source_version, payload)
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
def _parse_lcov(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    test_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    current_file: str | None = None
    line_hits: dict[str, int] = {}
    branch_hits: list[dict[str, int]] = []
    contexts = [{"test_id": record["payload"]["canonical_test_id"]} for record in test_records]
    def flush() -> None:
        nonlocal current_file, line_hits, branch_hits
        if current_file is None:
            return
        record_suffix = Path(current_file).stem
        payload = {
            "format": "lcov",
            "file": _to_posix(current_file),
            "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
            "branch_hits": branch_hits,
            "contexts": contexts,
        }
        records.append(
            _envelope(
                context,
                "coverage_slice",
                f"coverage-slice-{context['run_id']}-{context['run_attempt']}-{_slug(record_suffix)}",
                created_at,
                source_version,
                payload,
            )
        )
        current_file = None
        line_hits = {}
        branch_hits = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("SF:"):
            flush()
            current_file = line[3:]
        elif line.startswith("DA:"):
            line_no, hits = line[3:].split(",", 1)
            line_hits[str(int(line_no))] = int(hits)
        elif line.startswith("BRDA:"):
            line_no, block, branch, hits = line[5:].split(",", 3)
            branch_hits.append(
                {
                    "line": int(line_no),
                    "block": int(block),
                    "branch": int(branch),
                    "hits": 0 if hits == "-" else int(hits),
                }
            )
        elif line == "end_of_record":
            flush()
    flush()
    return records

def _parse_cobertura(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    test_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    records: list[dict[str, Any]] = []
    contexts = [{"test_id": record["payload"]["canonical_test_id"]} for record in test_records]
    class_index = 0
    for package_node in root.findall(".//package"):
        package_name = package_node.attrib.get("name", "")
        for class_node in package_node.findall(".//class"):
            class_index += 1
            filename = _cobertura_class_path(class_node, package_name, class_index)
            line_hits = _cobertura_line_hits(class_node)
            if not line_hits:
                continue
            payload = {
                "format": "cobertura",
                "file": _normalize_coverage_path(filename, package_name),
                "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
                "branch_hits": [],
                "contexts": contexts,
            }
            records.append(
                _envelope(
                    context,
                    "coverage_slice",
                    f"coverage-slice-{context['run_id']}-{context['run_attempt']}-cobertura-{_slug(payload['file'])}",
                    created_at,
                    source_version,
                    payload,
                )
            )
    if class_index == 0:
        for class_index, class_node in enumerate(root.findall(".//class"), start=1):
            filename = _cobertura_class_path(class_node, "", class_index)
            line_hits = _cobertura_line_hits(class_node)
            if not line_hits:
                continue
            payload = {
                "format": "cobertura",
                "file": _normalize_coverage_path(filename),
                "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
                "branch_hits": [],
                "contexts": contexts,
            }
            records.append(
                _envelope(
                    context,
                    "coverage_slice",
                    f"coverage-slice-{context['run_id']}-{context['run_attempt']}-cobertura-{_slug(payload['file'])}",
                    created_at,
                    source_version,
                    payload,
                )
            )
    return records

def _cobertura_class_path(class_node: ET.Element, package_name: str, class_index: int) -> str:
    filename = class_node.attrib.get("filename")
    if filename:
        return filename
    class_name = class_node.attrib.get("name") or f"cobertura-{class_index}"
    class_path = class_name.replace(".", "/")
    if package_name and not class_path.startswith(package_name.replace(".", "/")):
        return posixpath.join(package_name.replace(".", "/"), class_path)
    return class_path

def _cobertura_line_hits(class_node: ET.Element) -> dict[str, int]:
    line_hits: dict[str, int] = {}
    for line in class_node.findall(".//line"):
        number = line.attrib.get("number")
        if not number:
            continue
        line_hits[str(int(number))] = int(line.attrib.get("hits", "0"))
    return line_hits

def _normalize_coverage_path(raw_path: str, package_name: str = "") -> str:
    normalized = _to_posix(raw_path).strip()
    if not normalized:
        return package_name.replace(".", "/") or "unknown"
    normalized = re.sub(r"^[A-Za-z]:/+", "", normalized)
    normalized = re.sub(r"^/+", "", normalized)
    normalized = re.sub(r"/+", "/", normalized)
    for marker in ("src/", "tests/", "test/", "packages/", "pkg/", "app/", "lib/"):
        index = normalized.find(marker)
        if index >= 0:
            return posixpath.normpath(normalized[index:])
    if package_name and "/" not in normalized:
        normalized = posixpath.join(package_name.replace(".", "/"), normalized)
    return posixpath.normpath(normalized)

def _parse_jacoco(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    test_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    records: list[dict[str, Any]] = []
    contexts = [{"test_id": record["payload"]["canonical_test_id"]} for record in test_records]
    for package in root.findall(".//package"):
        package_name = package.attrib.get("name", "")
        for source_file in package.findall("sourcefile"):
            filename = source_file.attrib.get("name", "")
            if not filename:
                continue
            file_path = _normalize_coverage_path(filename, package_name)
            line_hits = {
                str(int(line.attrib["nr"])): int(line.attrib.get("ci", "0"))
                for line in source_file.findall("line")
                if line.attrib.get("nr")
            }
            if not line_hits:
                continue
            branch_hits = [
                {
                    "line": int(line.attrib["nr"]),
                    "block": 0,
                    "branch": index,
                    "hits": int(line.attrib.get("cb", "0")),
                }
                for index, line in enumerate(source_file.findall("line"))
                if int(line.attrib.get("mb", "0")) + int(line.attrib.get("cb", "0")) > 0
            ]
            payload = {
                "format": "jacoco",
                "file": file_path,
                "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
                "branch_hits": branch_hits,
                "contexts": contexts,
            }
            records.append(
                _envelope(
                    context,
                    "coverage_slice",
                    f"coverage-slice-{context['run_id']}-{context['run_attempt']}-jacoco-{_slug(file_path)}",
                    created_at,
                    source_version,
                    payload,
                )
            )
    return records

def _read_sarif(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("SARIF root must be an object")
    if data.get("version") is None or not isinstance(data.get("runs"), list):
        raise ValueError("SARIF requires version and runs")
    return data

def _sarif_dq_hits(sarif: dict[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for run in sarif.get("runs", []):
        if not isinstance(run, dict):
            continue
        for result in run.get("results", []):
            if not isinstance(result, dict):
                continue
            level = str(result.get("level", "")).lower()
            properties = result.get("properties", {}) if isinstance(result.get("properties"), dict) else {}
            severity = str(properties.get("security-severity") or properties.get("severity") or "").lower()
            if level in {"error"} or severity in {"high", "critical"}:
                hits.append(_dq("HATE-DQ-010", "unresolved high or critical SARIF finding", "results.sarif"))
    return hits
def _artifact_manifest(
    context: dict[str, Any],
    created_at: str,
    artifacts_dir: Path,
    artifact_refs_path: Path,
    fixture_path_prefix: str | None,
) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    if artifacts_dir.exists():
        for path in sorted(p for p in artifacts_dir.rglob("*") if p.is_file()):
            rel_from_artifacts = path.relative_to(artifacts_dir)
            manifest_path = _to_posix(str(rel_from_artifacts))
            if fixture_path_prefix:
                manifest_path = posixpath.join(fixture_path_prefix.strip("/"), "artifacts", manifest_path)
            artifact_id = f"artifact-{_slug(path.stem)}"
            security_checks = _artifact_security_checks(path, rel_from_artifacts)
            artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "kind": _artifact_kind(path),
                    "path": manifest_path,
                    "sha256": f"sha256:{_file_sha256(path)}",
                    "size_bytes": path.stat().st_size,
                    "classification": "public",
                    "redaction_status": REDACTION_STATUS,
                    "redaction_rule_version": "none",
                    "safe_for_summary": not _has_failed_check(security_checks),
                    "public_exposure": "none" if _has_failed_check(security_checks) else "summary",
                    "retention": {
                        "policy": "fixture",
                        "delete_after_days": None,
                    },
                    "security_checks": security_checks,
                }
            )
    if artifact_refs_path.exists():
        data = _read_optional_json(artifact_refs_path)
        refs = data.get("artifacts", [])
        if not isinstance(refs, list):
            raise ValueError("artifact-refs.json artifacts must be a list")
        for ref in refs:
            if not isinstance(ref, dict):
                raise ValueError("artifact-refs.json artifact entries must be objects")
            raw_path = str(ref.get("path", ""))
            if not raw_path:
                raise ValueError("artifact-refs.json artifact path is required")
            external_url = _is_external_url(raw_path)
            traversal = _is_path_traversal(raw_path)
            local_path = artifact_refs_path.parent / raw_path if not external_url else artifact_refs_path.parent / "__external_url__"
            exists = not external_url and local_path.exists() and local_path.is_file()
            manifest_path = _manifest_ref_path(raw_path, ref, fixture_path_prefix)
            if fixture_path_prefix:
                manifest_path = posixpath.join(fixture_path_prefix.strip("/"), manifest_path)
            if exists:
                security_checks = _artifact_security_checks(local_path, Path(raw_path))
            else:
                security_checks = {
                "path_exists": "blocked" if external_url or traversal else "fail",
                "secret_scan": "not_run",
                "pii_scan": "not_run",
                "mime_extension_scan": "not_run",
                "archive_scan": "fail" if _is_archive_path(raw_path) else "not_applicable",
                "path_traversal_scan": "fail" if traversal else "pass",
                "symlink_scan": "fail" if ref.get("symlink") is True else "not_run",
                "external_url_scan": "fail" if external_url else "pass",
                }
            if ref.get("symlink") is True:
                security_checks["symlink_scan"] = "fail"
            artifacts.append(
                {
                    "artifact_id": str(ref.get("artifact_id") or f"artifact-{_slug(Path(raw_path).stem)}"),
                    "kind": str(ref.get("kind") or _artifact_kind(local_path)),
                    "path": manifest_path,
                    "sha256": f"sha256:{_file_sha256(local_path)}" if exists else "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                    "size_bytes": local_path.stat().st_size if exists else 0,
                    "classification": str(ref.get("classification") or "public"),
                    "redaction_status": REDACTION_STATUS,
                    "redaction_rule_version": "none",
                    "safe_for_summary": _safe_for_summary(ref, exists, security_checks),
                    "public_exposure": _public_exposure(ref, security_checks),
                    "retention": {
                        "policy": "fixture",
                        "delete_after_days": None,
                    },
                    "security_checks": security_checks,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(context["run_id"]),
        "run_attempt": int(context["run_attempt"]),
        "commit_sha": str(context.get("commit_sha", "")),
        "created_at": created_at,
        "artifacts": artifacts,
    }

def _artifact_security_checks(path: Path, relative_path: Path) -> dict[str, str]:
    suffix = path.suffix.lower()
    text = ""
    if path.exists() and path.stat().st_size <= 1024 * 1024:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
    secret_patterns = [
        r"AKIA[0-9A-Z]{16}",
        r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}",
        r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
    has_secret = any(re.search(pattern, text) for pattern in secret_patterns)
    has_external_url = bool(re.search(r"https?://", text))
    mime_known = mimetypes.guess_type(path.name)[0] is not None or suffix in {".txt", ".trace", ".sarif", ".json", ".xml", ".info"}
    archive_status = "not_applicable"
    if _is_archive_path(path.name):
        archive_status = "fail"
    return {
        "path_exists": "pass" if path.exists() and path.is_file() else "fail",
        "secret_scan": "fail" if has_secret else "pass",
        "pii_scan": "not_run",
        "mime_extension_scan": "pass" if mime_known else "unknown",
        "archive_scan": archive_status,
        "path_traversal_scan": "fail" if ".." in relative_path.parts or path.is_symlink() else "pass",
        "symlink_scan": "fail" if path.is_symlink() else "pass",
        "external_url_scan": "fail" if has_external_url else "pass",
    }

def _has_failed_check(security_checks: dict[str, str]) -> bool:
    return any(value == "fail" for value in security_checks.values())

def _safe_for_summary(ref: dict[str, Any], exists: bool, security_checks: dict[str, str]) -> bool:
    if "safe_for_summary" in ref:
        return bool(ref["safe_for_summary"]) and not _has_failed_check(security_checks)
    return exists and not _has_failed_check(security_checks)

def _public_exposure(ref: dict[str, Any], security_checks: dict[str, str]) -> str:
    if _has_failed_check(security_checks):
        return "none"
    return str(ref.get("public_exposure") or "summary")

def _manifest_ref_path(raw_path: str, ref: dict[str, Any], fixture_path_prefix: str | None) -> str:
    if _is_external_url(raw_path):
        return f"redacted/external-url/{_slug(str(ref.get('artifact_id') or 'artifact'))}"
    if _is_path_traversal(raw_path):
        return f"redacted/path-traversal/{_slug(str(ref.get('artifact_id') or Path(raw_path).stem or 'artifact'))}"
    manifest_path = _to_posix(raw_path)
    if ref.get("symlink") is True:
        return f"redacted/symlink/{_slug(str(ref.get('artifact_id') or Path(raw_path).stem or 'artifact'))}"
    return manifest_path

def _is_external_url(raw_path: str) -> bool:
    return bool(re.match(r"(?i)^https?://", raw_path))

def _is_path_traversal(raw_path: str) -> bool:
    if _is_external_url(raw_path):
        return False
    normalized = _to_posix(raw_path)
    if re.match(r"^[A-Za-z]:/", normalized) or normalized.startswith("/"):
        return True
    return ".." in Path(raw_path).parts or "../" in normalized or normalized.startswith("..")

def _is_archive_path(raw_path: str) -> bool:
    suffixes = [suffix.lower() for suffix in Path(raw_path).suffixes]
    return any(suffix in {".zip", ".tar", ".tgz", ".gz", ".7z"} for suffix in suffixes)

def _quarantine_report(
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    artifact_manifest: dict[str, Any],
) -> dict[str, Any]:
    quarantined = []
    for artifact in artifact_manifest.get("artifacts", []):
        reasons = _quarantine_reasons(artifact.get("security_checks", {}))
        if artifact.get("classification") in {"secret", "pii", "restricted"} and "restricted_classification" not in reasons:
            reasons.append("restricted_classification")
        if artifact.get("safe_for_summary") is False and not reasons:
            reasons.append("unsafe_for_summary")
        if not reasons:
            continue
        quarantined.append({
            "artifact_id": artifact.get("artifact_id", ""),
            "kind": artifact.get("kind", "other"),
            "path": artifact.get("path", "redacted/unknown"),
            "reasons": reasons,
            "safe_for_summary": False,
            "public_exposure": "none",
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(context["run_id"]),
        "run_attempt": int(context["run_attempt"]),
        "commit_sha": str(context.get("commit_sha", "")),
        "created_at": created_at,
        "source_tool": SOURCE_TOOL,
        "source_version": source_version,
        "quarantined_artifacts": quarantined,
    }

def _quarantine_reasons(security_checks: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    reason_by_check = {
        "path_exists": "missing",
        "secret_scan": "secret",
        "archive_scan": "unsafe_archive",
        "path_traversal_scan": "path_traversal",
        "symlink_scan": "symlink",
        "external_url_scan": "external_url",
    }
    for check, reason in reason_by_check.items():
        if security_checks.get(check) == "fail":
            reasons.append(reason)
    return reasons
def _precheck_decision(
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    dq_hits: list[dict[str, str]],
    soft_gaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    soft_gaps = soft_gaps or []
    decision = "hard_dq" if dq_hits else "conditional" if soft_gaps else "eligible"
    exit_code = 2 if decision == "hard_dq" else 0
    reasons = [
        "Minimal P0a inputs satisfy HATE/v1 schema bootstrap contracts.",
        "QEG export is allowed as optional evidence and scheduled for P0b bundling.",
    ] if not dq_hits and not soft_gaps else [hit["message"] for hit in dq_hits] + [gap.get("message", "profile soft gap") for gap in soft_gaps]
    payload = {
        "decision": decision,
        "exit_code": exit_code,
        "dq_hits": dq_hits,
        "soft_gaps": soft_gaps,
        "reasons": reasons,
        "qeg_export_allowed": not dq_hits,
        "qeg_export_ref": None,
        "qeg_export_phase": "P0b",
    }
    return _envelope(context, "precheck_decision", f"precheck-{context['run_id']}-attempt-{context['run_attempt']}", created_at, source_version, payload)
def _audit_record(
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    outputs: dict[str, Any],
    input_dir: Path,
) -> dict[str, Any]:
    payload = {
        "validated_artifacts": [name for name, value in outputs.items() if value is not None],
        "validation_result": "pass",
        "source_refs": [
            _stable_source_ref(input_dir / str(context.get("_context_source_name", "github-context.json"))),
            _stable_source_ref(input_dir / "junit.xml"),
            _stable_source_ref(input_dir / "lcov.info"),
        ],
        "notes": [
            "This record is generated from local P0a inputs and does not contain a release Gate verdict.",
        ],
    }
    return _envelope(context, "audit_record", f"audit-{context['run_id']}-attempt-{context['run_attempt']}", created_at, source_version, payload)
def _summary(
    context: dict[str, Any],
    test_records: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
    artifact_manifest: dict[str, Any],
    decision_record: dict[str, Any],
) -> str:
    passed = sum(1 for record in test_records if record["payload"]["status"] == "passed")
    failed = sum(1 for record in test_records if record["payload"]["status"] in {"failed", "error"})
    covered = 0
    uncovered = 0
    coverage_files: list[str] = []
    for record in coverage_records:
        coverage_files.append(record["payload"]["file"])
        for hits in record["payload"]["line_hits"].values():
            if hits > 0:
                covered += 1
            else:
                uncovered += 1
    decision = decision_record["payload"]["decision"]
    artifact_names = ", ".join(artifact["artifact_id"] for artifact in artifact_manifest["artifacts"]) or "none"
    coverage_line = "No coverage records generated"
    if coverage_files:
        coverage_line = f"Coverage sample: `{coverage_files[0]}` has {covered} covered lines and {uncovered} uncovered line"
        if uncovered != 1:
            coverage_line += "s"
    return "\n".join(
        [
            "# P0a Minimal Evidence Summary",
            "",
            f"- Run: `{context['run_id']}` attempt `{context['run_attempt']}`",
            f"- Repository: `{context['repository']}`",
            f"- Commit: `{context.get('commit_sha', '')[:40]}`",
            f"- Test result: {passed} passed, {failed} failed",
            f"- {coverage_line}",
            f"- Precheck: {decision} for optional QEG evidence export in P0b",
            f"- Generated artifacts: {artifact_names}",
            "",
            "This summary is public-safe and generated from local P0a inputs.",
            "",
        ]
    )
def _envelope(
    context: dict[str, Any],
    record_type: str,
    record_id: str,
    created_at: str,
    source_version: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "run_id": str(context["run_id"]),
        "run_attempt": int(context["run_attempt"]),
        "commit_sha": str(context.get("commit_sha", "")),
        "created_at": created_at,
        "source_tool": SOURCE_TOOL,
        "source_version": source_version,
        "sha256": "",
        "redaction_status": REDACTION_STATUS,
        "payload": payload,
    }
    record["sha256"] = f"sha256:{_stable_sha256({**record, 'sha256': ''})}"
    return record
def _dq_hits_from_control(control: dict[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if control.get("unresolved_flaky_over_threshold") is True:
        hits.append(_dq("HATE-DQ-005", "unresolved flakiness is over threshold", "dq-control.json"))
    if control.get("high_risk_without_execution") is True:
        hits.append(_dq("HATE-DQ-007", "high-risk changed path has no execution evidence", "dq-control.json"))
    if control.get("unresolved_high_critical_sarif") is True:
        hits.append(_dq("HATE-DQ-010", "unresolved high or critical SARIF finding on changed path", "dq-control.json"))
    return hits
def _schema_validation_hits(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    flattened: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, list):
            flattened.extend(item for item in record if isinstance(item, dict))
        elif isinstance(record, dict) and "record_type" in record:
            flattened.append(record)
        elif not isinstance(record, dict):
            hits.append(_dq("HATE-DQ-015", "schema validation failed: generated record is not an object", "generated-record"))
    for record in flattened:
        schema_name = _schema_name_for_generated_record(record)
        if not schema_name:
            continue
        schema = _load_hate_schema(schema_name)
        for error in _validate_schema_value(record, schema, "$"):
            hits.append(_dq("HATE-DQ-015", f"schema validation failed: {error}", _schema_source_ref(record, schema_name)))
    return hits

def _schema_name_for_generated_record(record: dict[str, Any]) -> str | None:
    record_type = record.get("record_type")
    if record_type == "run":
        return "run.schema.json"
    if record_type == "test_result":
        return "test-result.schema.json"
    if record_type == "coverage_slice":
        return "coverage-slice.schema.json"
    if record_type == "precheck_decision":
        return "precheck-decision.schema.json"
    if record_type == "audit_record":
        return "audit-record.schema.json"
    if "artifacts" in record and record.get("schema_version") == SCHEMA_VERSION:
        return "artifact-manifest.schema.json"
    return None

def _schema_source_ref(record: dict[str, Any], schema_name: str) -> str:
    if schema_name == "artifact-manifest.schema.json":
        return "artifact-manifest.json"
    record_type = str(record.get("record_type") or "generated-record")
    return {
        "run": "HATE-run.json",
        "test_result": "HATE-test-results.ndjson",
        "coverage_slice": "HATE-coverage.ndjson",
        "precheck_decision": "precheck-decision.json",
        "audit_record": "record.json",
    }.get(record_type, "generated-record")

def _load_hate_schema(name: str) -> dict[str, Any]:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "HATE" / "v1" / name
    with schema_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a JSON object")
    return data

def _validate_schema_value(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    if "allOf" in schema:
        for item in schema["allOf"]:
            if not isinstance(item, dict):
                continue
            if "$ref" in item:
                item = _load_hate_schema(str(item["$ref"]))
            errors.extend(_validate_schema_value(value, item, path))
        return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']!r}")
    expected_type = schema.get("type")
    if expected_type and not _schema_type_matches(value, str(expected_type)):
        errors.append(f"{path} must be {expected_type}")
        return errors
    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path} length must be at least {min_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and not re.match(pattern, value):
            errors.append(f"{path} must match {pattern}")
    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, int | float) and value < minimum:
            errors.append(f"{path} must be >= {minimum}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for field in required:
                if isinstance(field, str) and field not in value:
                    errors.append(f"{path}.{field} is required")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for field, subschema in properties.items():
                if field in value and isinstance(subschema, dict):
                    errors.extend(_validate_schema_value(value[field], subschema, f"{path}.{field}"))
        additional = schema.get("additionalProperties", True)
        if isinstance(additional, dict):
            known = set(properties) if isinstance(properties, dict) else set()
            for field, item in value.items():
                if field not in known:
                    errors.extend(_validate_schema_value(item, additional, f"{path}.{field}"))
        elif additional is False and isinstance(properties, dict):
            unknown = sorted(set(value).difference(properties))
            if unknown:
                errors.append(f"{path} has unknown fields: {', '.join(unknown)}")
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_validate_schema_value(item, item_schema, f"{path}[{index}]"))
    return errors

def _schema_type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int | float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _parse_coveragepy_json(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
) -> list[dict[str, Any]]:
    """Parse coverage.py JSON export with context data into coverage_slice records."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("coverage.py JSON must be an object")
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        raise ValueError("coverage.py meta must be an object")
    show_contexts = bool(meta.get("show_contexts", False))
    if not show_contexts:
        raise ValueError("coverage.py JSON must have show_contexts: true for context extraction")
    files = data.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("coverage.py files must be an object")
    records: list[dict[str, Any]] = []
    for file_path, file_data in files.items():
        if not isinstance(file_data, dict):
            continue
        executed_lines = file_data.get("executed_lines", [])
        if not isinstance(executed_lines, list):
            continue
        # Build line_hits from executed_lines
        line_hits: dict[str, int] = {}
        for line_no in executed_lines:
            if isinstance(line_no, int):
                line_hits[str(line_no)] = 1
        # Extract contexts from file_data.contexts
        contexts_data = file_data.get("contexts", {})
        if not isinstance(contexts_data, dict):
            contexts_data = {}
        # Build unique context objects from all line contexts
        seen_test_ids: set[str] = set()
        contexts: list[dict[str, Any]] = []
        for line_key, test_contexts in contexts_data.items():
            if test_contexts is None:
                continue
            if not isinstance(test_contexts, list):
                continue
            for test_id in test_contexts:
                if isinstance(test_id, str) and test_id and test_id not in seen_test_ids:
                    seen_test_ids.add(test_id)
                    contexts.append({"test_id": test_id, "line": int(line_key)})
        payload = {
            "format": "coverage.py",
            "file": _to_posix(file_path),
            "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
            "branch_hits": [],
            "contexts": contexts,
        }
        record_suffix = Path(file_path).stem
        records.append(
            _envelope(
                context,
                "coverage_slice",
                f"coverage-slice-{context['run_id']}-{context['run_attempt']}-{_slug(record_suffix)}",
                created_at,
                source_version,
                payload,
            )
        )
    return records
