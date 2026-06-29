"""Shared classifications and patterns for implementation-test coupling."""

from __future__ import annotations

from enum import Enum


DETECTOR_ID_COUPLING = "hate.pg004c.coupling_detector"
DETECTOR_ID_MANUAL_REVIEW = "hate.pg004c.manual_review_bridge"


class CouplingClassification(Enum):
    """Classification of implementation-test coupling."""

    TEST_NAME_BRANCH = "test_name_branch"
    FIXTURE_NAME_BRANCH = "fixture_name_branch"
    GOLDEN_FIXTURE_PATH_BRANCH = "golden_fixture_path_branch"
    ENV_FLAG_BRANCH = "env_flag_branch"
    CI_MARKER_BRANCH = "ci_marker_branch"
    DATA_DRIVEN_PARSER = "data_driven_parser"
    STABLE_FIXTURE_MAPPING = "stable_fixture_mapping"
    NO_COUPLING = "no_coupling"


class OracleClassification(Enum):
    """Classification of oracle presence."""

    EXPECTED_VALUE = "expected_value"
    CONTRACT_CHECK = "contract_check"
    PROPERTY_ASSERTION = "property_assertion"
    MUTATION_SCORE = "mutation_score"
    MANUAL_ORACLE = "manual_oracle"
    NO_ORACLE = "no_oracle"


class CoverageClassification(Enum):
    """Classification of coverage evidence."""

    EXECUTED_TESTS_WITH_ORACLE = "executed_tests_with_oracle"
    COVERAGE_ONLY = "coverage_only"
    COVERED_LINES_ONLY = "covered_lines_only"
    NO_COVERAGE = "no_coverage"


class ManualReviewClassification(Enum):
    """Classification of manual review requirement."""

    SUSPICIOUS_AI_AVOIDANCE = "suspicious_ai_avoidance"
    FIXTURE_NAME_COUPLING = "fixture_name_coupling"
    BROAD_MOCKS = "broad_mocks"
    MISSING_ORACLE = "missing_oracle"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    MISSING_HUMAN_RECORD = "missing_human_record"
    EXPIRED_HUMAN_RECORD = "expired_human_record"
    VALID_MANUAL_REVIEW = "valid_manual_review"


TEST_NAME_BRANCH_PATTERNS = [
    r"if\s+['\"]test_",
    r"if\s+\w+\s*==\s*['\"]test_",
    r"if\s+\w+\s*in\s*\[.*['\"]test_",
    r"if\s+__name__\s*==\s*['\"]test",
    r"getattr\s*\(\s*\w+\s*,\s*['\"]test_",
    r"hasattr\s*\(\s*\w+\s*,\s*['\"]test_",
]

FIXTURE_NAME_BRANCH_PATTERNS = [
    r"if\s+['\"]fixture_",
    r"if\s+\w+\s*==\s*['\"]fixture_",
    r"if\s+\w+\s*in\s*\[.*['\"]fixture_",
    r"getattr\s*\(\s*\w+\s*,\s*['\"]fixture_",
    r"hasattr\s*\(\s*\w+\s*,\s*['\"]fixture_",
]

GOLDEN_FIXTURE_PATH_PATTERNS = [
    r"if\s+['\"]golden/",
    r"if\s+\w+\s*==\s*['\"]golden/",
    r"if\s+\w+\s*contains\s*['\"]golden/",
    r"if\s+path\s*includes\s*['\"]golden/",
]

ENV_FLAG_PATTERNS = [
    r"if\s+os\.environ\.get\s*\(\s*['\"]TEST_",
    r"if\s+getenv\s*\(\s*['\"]TEST_",
    r"if\s+process\.env\.TEST_",
    r"if\s+System\.getenv\s*\(\s*['\"]TEST_",
]

CI_MARKER_PATTERNS = [
    r"if\s+os\.environ\.get\s*\(\s*['\"]CI['\"]",
    r"if\s+getenv\s*\(\s*['\"]CI['\"]",
    r"if\s+process\.env\.CI",
    r"if\s+isCI\s*\(",
]

DATA_DRIVEN_PARSER_PATTERNS = [
    r"def\s+parse_\w+\s*\(",
    r"def\s+load_\w+\s*\(",
    r"for\s+\w+\s+in\s+data",
    r"data\[",
    r"fixtures\[",
]

STABLE_FIXTURE_MAPPING_PATTERNS = [
    r"fixture_map\s*=",
    r"FIXTURE_MAP\s*=",
    r"fixture_registry\s*=",
    r"get_fixture\s*\(",
]
