"""Tests for JUnit dialect parser - HATE-PG-001B."""

from pathlib import Path

from hate.adapters.junit import parse_junit_xml


ROOT = Path(__file__).resolve().parents[1]
JUNIT_FIXTURES = ROOT / "fixtures" / "adapters" / "junit"


def make_xml(root_tag="testsuite", **attrs):
    """Helper to build minimal JUnit XML strings."""
    attrs_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    if root_tag == "testsuites":
        return f'<testsuites><testsuite name="s1" {attrs_str}><testcase name="t1"/></testsuite></testsuites>'
    return f'<{root_tag} name="s1" {attrs_str}><testcase name="t1"/></{root_tag}>'


def test_parse_testsuite_root():
    xml = '<testsuite name="suite1"><testcase name="test1" classname="pkg.Mod" time="1.5"/></testsuite>'
    result = parse_junit_xml(xml)
    assert result["parser_diagnostics"]["dialect"] == "testsuite"
    assert len(result["tests"]) == 1
    t = result["tests"][0]
    assert t["name"] == "test1"
    assert t["classname"] == "pkg.Mod"
    assert t["duration"] == 1.5
    assert t["status"] == "passed"


def test_parse_testsuites_root():
    xml = '<testsuites><testsuite name="s1"><testcase name="t1"/></testsuite><testsuite name="s2"><testcase name="t2"/></testsuite></testsuites>'
    result = parse_junit_xml(xml)
    assert result["parser_diagnostics"]["dialect"] == "testsuites"
    assert len(result["tests"]) == 2


def test_malformed_xml():
    result = parse_junit_xml("<invalid>")
    assert "error" in result["parser_diagnostics"]


def test_missing_testsuite():
    result = parse_junit_xml("<other><testcase name=\"t1\"/></other>")
    assert "error" in result["parser_diagnostics"]


def test_failure_detection():
    xml = '<testsuite><testcase name="t1"><failure message="assert failed"/></testcase></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0]["status"] == "failed"
    assert "assert failed" in result["tests"][0]["message"]


def test_error_detection():
    xml = '<testsuite><testcase name="t1"><error message="runtime error"/></testcase></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0]["status"] == "error"


def test_skipped_without_reason():
    xml = '<testsuite><testcase name="t1"><skipped/></testcase></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0]["status"] == "skipped"


def test_file_path_normalization():
    xml = '<testsuite><testcase name="t1" file="src\\pkg\\mod.py"/></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0]["file"] == "src/pkg/mod.py"


def test_duplicate_canonical_id():
    xml = '<testsuite><testcase name="t1" classname="Mod"/><testcase name="t1" classname="Mod"/></testsuite>'
    result = parse_junit_xml(xml)
    assert "junit:Mod.py::t1" in result["parser_diagnostics"]["duplicate_ids"]


def test_xfail_marker_property():
    xml = '<testsuite><testcase name="t1"><properties><property name="xfail" value="true"/></properties></testcase></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0].get("xfail") == True


def test_only_marker_leak():
    xml = '<testsuite><testcase name="t1"><properties><property name="only" value="true"/></properties></testcase></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0].get("only") == True


def test_flaky_retry_index():
    xml = '<testsuite><testcase name="t1" retry_index="2"/></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0].get("retry_index") == 2


def test_surefire_shape():
    xml = '<testsuite name="pkg.ModTest" tests="3" failures="1" errors="0" skipped="1"><testcase name="testA" classname="pkg.ModTest" time="0.1"/><testcase name="testB" classname="pkg.ModTest" time="0.2"><failure/></testcase><testcase name="testC" classname="pkg.ModTest" time="0"><skipped/></testcase></testsuite>'
    result = parse_junit_xml(xml)
    assert len(result["tests"]) == 3
    statuses = [t["status"] for t in result["tests"]]
    assert "passed" in statuses
    assert "failed" in statuses
    assert "skipped" in statuses


def test_pytest_shape():
    xml = '<testsuite name="pytest" tests="1"><testcase name="test_x" classname="test_mod" file="test_mod.py" time="0.05"/></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0]["file"] == "test_mod.py"


def test_jest_vitest_shape():
    xml = '<testsuite name="example.test.js" tests="1"><testcase name="should pass" classname="example.test.js" time="0.01"/></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0]["name"] == "should pass"


def test_go_shape():
    xml = '<testsuite name="TestPackage" tests="1"><testcase name="TestFunction" classname="TestPackage" time="0.001"/></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0]["name"] == "TestFunction"


def test_xfailed_pass():
    xml = '<testsuite><testcase name="t1"><system-out>xfail marker</system-out></testcase></testsuite>'
    result = parse_junit_xml(xml)
    assert result["tests"][0].get("xfail") == True


def test_backward_compat_generate_p0a():
    """Ensure existing generate_p0a tests still work."""
    xml = '<testsuite name="suite"><testcase name="test1" classname="Mod" time="1.0"/></testsuite>'
    result = parse_junit_xml(xml)
    assert "tests" in result
    assert len(result["tests"]) == 1


def test_junit_fixture_corpus_covers_required_dialects_and_negatives():
    expected = {
        "surefire",
        "gradle",
        "pytest-junitxml",
        "jest-junit",
        "vitest-junit",
        "playwright",
        "go-junit-report",
        "parameterized",
        "windows-paths",
        "container-paths",
        "malformed-xml",
        "missing-testsuite",
        "skipped-without-reason",
        "duplicate-testcase-id",
        "focused-only-leak",
        "xfailed-as-pass",
    }

    assert expected <= {path.name for path in JUNIT_FIXTURES.iterdir() if path.is_dir()}


def test_junit_fixture_corpus_positive_files_parse():
    positive = [
        "surefire",
        "gradle",
        "pytest-junitxml",
        "jest-junit",
        "vitest-junit",
        "playwright",
        "go-junit-report",
        "parameterized",
        "windows-paths",
        "container-paths",
    ]

    parsed = {
        name: parse_junit_xml((JUNIT_FIXTURES / name / "junit.xml").read_text(encoding="utf-8"))
        for name in positive
    }

    assert all(result["tests"] for result in parsed.values())
    assert parsed["windows-paths"]["tests"][0]["file"] == "tests/test_path.py"
    assert parsed["vitest-junit"]["tests"][0]["flaky"] is True
    assert parsed["jest-junit"]["tests"][1]["todo"] is True


def test_junit_fixture_corpus_negative_files_emit_diagnostics():
    malformed = parse_junit_xml((JUNIT_FIXTURES / "malformed-xml" / "junit.xml").read_text(encoding="utf-8"))
    missing = parse_junit_xml((JUNIT_FIXTURES / "missing-testsuite" / "junit.xml").read_text(encoding="utf-8"))
    duplicate = parse_junit_xml((JUNIT_FIXTURES / "duplicate-testcase-id" / "junit.xml").read_text(encoding="utf-8"))
    skipped = parse_junit_xml((JUNIT_FIXTURES / "skipped-without-reason" / "junit.xml").read_text(encoding="utf-8"))
    focused = parse_junit_xml((JUNIT_FIXTURES / "focused-only-leak" / "junit.xml").read_text(encoding="utf-8"))
    xfailed = parse_junit_xml((JUNIT_FIXTURES / "xfailed-as-pass" / "junit.xml").read_text(encoding="utf-8"))

    assert "malformed_xml" in malformed["parser_diagnostics"]["error"]
    assert "missing_testsuite_root" in missing["parser_diagnostics"]["error"]
    assert duplicate["parser_diagnostics"]["duplicate_ids"] == ["junit:tests/test_dup.py::test_same"]
    assert skipped["tests"][0]["parser_diagnostics"][0]["code"] == "skipped_without_reason"
    assert focused["tests"][0]["only"] is True
    assert xfailed["tests"][0]["xfail"] is True
