"""Runner summary dialect parsers for real-repo evaluation."""

from __future__ import annotations

import re
from typing import Any


def parse_runner_summary(stdout: str, stderr: str = "") -> dict[str, Any]:
    """Parse aggregate test counts from known runner dialects."""
    text = f"{stdout}\n{stderr}".replace("\\n", "\n")
    for dialect, parser in (
        ("vitest", _parse_vitest_summary),
        ("bun", _parse_bun_test_summary),
        ("mocha", _parse_mocha_summary),
        ("lodash-test", _parse_lodash_test_summary),
        ("cargo-test", _parse_cargo_test_summary),
        ("nextjs-build", _parse_nextjs_build_summary),
        ("astro-build", _parse_astro_build_summary),
        ("typescript-typecheck", _parse_typescript_typecheck_summary),
        ("python-compileall", _parse_python_compileall_summary),
        ("pytest", _parse_pytest_summary),
    ):
        summary = parser(text)
        if summary:
            return {
                "dialect": dialect,
                "summary": summary,
                "ignored_noise": _noise_markers(text),
                "parser_status": "parsed",
            }
    partial_pytest = _parse_pytest_progress(text)
    if partial_pytest:
        return {
            "dialect": "pytest",
            "summary": partial_pytest,
            "ignored_noise": _noise_markers(text),
            "parser_status": "partial",
        }
    return {
        "dialect": "unknown",
        "summary": {},
        "ignored_noise": _noise_markers(text),
        "parser_status": "unparsed",
    }


def build_runner_dialect_coverage_report(data: dict[str, Any], report_id: str = "runner-dialect-coverage") -> dict[str, Any]:
    """Build a coverage report for runner dialect parser fixtures."""
    cases = [case for case in data.get("cases", []) if isinstance(case, dict)]
    results = []
    findings = []
    for case in cases:
        parsed = parse_runner_summary(str(case.get("stdout") or ""), str(case.get("stderr") or ""))
        expected = dict(case.get("expected") or {})
        passed = (
            parsed["dialect"] == expected.get("dialect")
            and parsed["summary"] == expected.get("summary", {})
        )
        if not passed:
            findings.append({
                "code": "runner_dialect_parser_mismatch",
                "severity": "high",
                "readiness_effect": "hold",
                "message": f"Runner dialect parser mismatch for {case.get('case_id', 'case')}.",
                "case_id": str(case.get("case_id") or ""),
            })
        results.append({
            "case_id": str(case.get("case_id") or ""),
            "expected": expected,
            "actual": parsed,
            "passed": passed,
        })
    return {
        "schema_version": "HATE/v1",
        "record_type": "runner-dialect-coverage-report",
        "report_id": report_id,
        "overall_status": "hold" if findings else "pass",
        "readiness_effect": "hold" if findings else "none",
        "runner_config": {
            "required_dialects": [
                "pytest",
                "vitest",
                "bun",
                "cargo-test",
                "nextjs-build",
                "astro-build",
                "typescript-typecheck",
                "python-compileall",
            ],
            "noise_guard": True,
        },
        "results": results,
        "findings": findings,
        "summary": {
            "case_count": len(results),
            "passed": sum(1 for result in results if result["passed"]),
            "failed": len(findings),
            "dialects": sorted({result["actual"]["dialect"] for result in results}),
        },
        "sourceRefs": list(data.get("sourceRefs") or [f"fixtures/platform/evaluation/{report_id}/fixture.json"]),
    }


def _parse_pytest_summary(text: str) -> dict[str, int]:
    counts = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "errors": 0,
    }
    for line in text.splitlines():
        normalized = line.strip("= \t\r\n")
        if re.search(r"\bTest Files\b", normalized, re.IGNORECASE):
            continue
        if not _looks_like_pytest_summary_line(normalized):
            continue
        for count, label in re.findall(
            r"(\d+)\s+(passed|failed|skipped|xfailed|xpassed|errors?)",
            normalized,
            flags=re.IGNORECASE,
        ):
            key = label.lower()
            if key == "error":
                key = "errors"
            counts[key] += int(count)
    total = sum(counts.values())
    if total == 0:
        return {}
    counts["total_tests"] = total
    return {key: value for key, value in counts.items() if value}


def _parse_pytest_progress(text: str) -> dict[str, int]:
    percentages = [
        int(value)
        for value in re.findall(r"\[\s*(\d{1,3})%\]", re.sub(r"\x1b\[[0-9;]*m", "", text))
        if 0 <= int(value) <= 100
    ]
    if not percentages:
        return {}
    return {
        "partial_progress_percent": max(percentages),
        "partial_progress_observed": 1,
    }


def _parse_vitest_summary(text: str) -> dict[str, int]:
    for line in text.splitlines():
        plain = re.sub(r"\x1b\[[0-9;]*m", "", line)
        if not re.search(r"^\s*Tests\b", plain):
            continue
        total_match = re.search(r"\((\d+)\)", plain)
        counts = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
        }
        for count, label in re.findall(
            r"(\d+)\s+(passed|failed|skipped|errors?)",
            plain,
            flags=re.IGNORECASE,
        ):
            key = label.lower()
            if key == "error":
                key = "errors"
            counts[key] += int(count)
        total = int(total_match.group(1)) if total_match else sum(counts.values())
        if total:
            counts["total_tests"] = total
            return {key: value for key, value in counts.items() if value}
    return {}


def _parse_bun_test_summary(text: str) -> dict[str, int]:
    counts = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
    }
    for line in text.splitlines():
        plain = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        summary_match = re.fullmatch(
            r"(\d+)\s+(pass|fail|skip|error)s?",
            plain,
            flags=re.IGNORECASE,
        )
        if summary_match:
            count, label = summary_match.groups()
            key = {
                "pass": "passed",
                "fail": "failed",
                "skip": "skipped",
                "error": "errors",
            }[label.lower()]
            counts[key] += int(count)
            continue
        ran_match = re.search(r"Ran\s+(\d+)\s+tests?\s+across\b", plain, flags=re.IGNORECASE)
        if ran_match:
            total = int(ran_match.group(1))
            if total:
                counts["total_tests"] = total
                return {key: value for key, value in counts.items() if value}
    return {}


def _parse_mocha_summary(text: str) -> dict[str, int]:
    counts = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
    }
    matched = False
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    for count, label in re.findall(
        r"^\s*(\d+)\s+(passing|failing|pending)(?:\s|\()",
        plain,
        flags=re.IGNORECASE | re.MULTILINE,
    ):
        matched = True
        key = {
            "passing": "passed",
            "failing": "failed",
            "pending": "skipped",
        }[label.lower()]
        counts[key] += int(count)
    total = sum(counts.values())
    if not matched or total == 0:
        return {}
    counts["total_tests"] = total
    return {key: value for key, value in counts.items() if value}


def _parse_lodash_test_summary(text: str) -> dict[str, int]:
    counts = {
        "passed": 0,
        "failed": 0,
    }
    matched = False
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    for passed, failed, total in re.findall(
        r"PASS:\s*(\d+)\s+FAIL:\s*(\d+)\s+TOTAL:\s*(\d+)",
        plain,
        flags=re.IGNORECASE,
    ):
        matched = True
        counts["passed"] += int(passed)
        counts["failed"] += int(failed)
        counts["total_tests"] = int(counts.get("total_tests", 0)) + int(total)
    if not matched:
        return {}
    return {key: value for key, value in counts.items() if value}


def _parse_cargo_test_summary(text: str) -> dict[str, int]:
    counts = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
    }
    matched = False
    for line in text.splitlines():
        plain = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        if not plain.lower().startswith("test result:"):
            continue
        matched = True
        for count, label in re.findall(
            r"(\d+)\s+(passed|failed|ignored|filtered out)",
            plain,
            flags=re.IGNORECASE,
        ):
            key = label.lower()
            if key in {"ignored", "filtered out"}:
                key = "skipped"
            counts[key] += int(count)
    total = sum(counts.values())
    if not matched or total == 0:
        return {}
    counts["total_tests"] = total
    return {key: value for key, value in counts.items() if value}


def _parse_nextjs_build_summary(text: str) -> dict[str, int]:
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    if "next build" not in plain and "Next.js" not in plain:
        return {}
    if "Compiled successfully" not in plain:
        return {}
    static_pages = 0
    page_match = re.search(r"Generating static pages\s+\((\d+)/(\d+)\)", plain)
    if page_match:
        static_pages = int(page_match.group(2))
    summary = {
        "build_passed": 1,
        "typecheck_passed": 1 if "checking validity of types" in plain else 0,
        "static_pages": static_pages,
        "total_checks": 1,
    }
    return {key: value for key, value in summary.items() if value}


def _parse_astro_build_summary(text: str) -> dict[str, int]:
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    if "astro build" not in plain and "[build]" not in plain:
        return {}
    if "[build] Complete!" not in plain:
        return {}
    pages = 0
    page_match = re.search(r"\[build\]\s+(\d+)\s+page\(s\)\s+built", plain)
    if page_match:
        pages = int(page_match.group(1))
    return {
        "build_passed": 1,
        "static_pages": pages,
        "total_checks": 1,
    }


def _parse_typescript_typecheck_summary(text: str) -> dict[str, int]:
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    if "tsc --noEmit" not in plain:
        return {}
    if re.search(r"\berror TS\d+:", plain):
        return {}
    return {"typecheck_passed": 1, "total_checks": 1}


def _parse_python_compileall_summary(text: str) -> dict[str, int]:
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    listing_count = len(re.findall(r"^Listing\s+'[^']+'\.\.\.", plain, flags=re.MULTILINE))
    compiling_count = len(re.findall(r"^Compiling\s+'[^']+'\.\.\.", plain, flags=re.MULTILINE))
    if listing_count == 0 and compiling_count == 0:
        return {}
    return {
        "compiled_paths": listing_count + compiling_count,
        "total_checks": 1,
    }


def _looks_like_pytest_summary_line(line: str) -> bool:
    if not line:
        return False
    if re.search(r"\b(test|tests|passed|failed|skipped|xfailed|xpassed|errors?)\b", line, re.IGNORECASE) is None:
        return False
    if re.search(r"\bin\s+\d+(\.\d+)?s\b", line, re.IGNORECASE):
        return True
    if re.search(r"\d+\s+(passed|failed|skipped|xfailed|xpassed|errors?)", line, re.IGNORECASE):
        return "," in line or " passed" in line or " failed" in line
    return False


def _noise_markers(text: str) -> list[str]:
    markers = []
    lowered = text.lower()
    for marker in ("semantic_error", "handler emitted", "failed to fetch", "expected failure", "non-summary"):
        if marker in lowered:
            markers.append(marker)
    return markers
