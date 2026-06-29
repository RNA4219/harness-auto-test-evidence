"""Shared classifications and patterns for mock/assertion integrity checks."""

from __future__ import annotations

from enum import Enum


EXTERNAL_BOUNDARY_PATTERNS = {
    "network": [
        r"mock\s*\(\s*['\"].*http.*['\"]",
        r"mock\s*\(\s*['\"].*api.*['\"]",
        r"mock\s*\(\s*['\"].*request.*['\"]",
        r"MockHttp",
        r"MockResponse",
        r"requests\.mock",
        r"aiohttp\.mock",
        r"httpx\.mock",
        r"@mock.*network",
    ],
    "filesystem": [
        r"mock\s*\(\s*['\"].*fs.*['\"]",
        r"mock\s*\(\s*['\"].*file.*['\"]",
        r"mock\s*\(\s*['\"].*path.*['\"]",
        r"MockFilesystem",
        r"MockFile",
        r"pyfakefs",
        r"@mock.*file",
    ],
    "clock": [
        r"mock\s*\(\s*['\"].*time.*['\"]",
        r"mock\s*\(\s*['\"].*clock.*['\"]",
        r"MockClock",
        r"freezegun",
        r"@mock.*time",
        r"@mock.*datetime",
        r"datetime\.mock",
    ],
    "random": [
        r"mock\s*\(\s*['\"].*random.*['\"]",
        r"MockRandom",
        r"@mock.*random",
    ],
    "secrets": [
        r"mock\s*\(\s*['\"].*secret.*['\"]",
        r"mock\s*\(\s*['\"].*credential.*['\"]",
        r"mock\s*\(\s*['\"].*token.*['\"]",
        r"MockSecrets",
        r"@mock.*secret",
    ],
    "third_party": [
        r"mock\s*\(\s*['\"].*third_party.*['\"]",
        r"mock\s*\(\s*['\"].*external.*['\"]",
        r"@mock\.patch\s*\(['\"].*thirdparty",
    ],
    "platform": [
        r"mock\s*\(\s*['\"].*platform.*['\"]",
        r"MockPlatform",
        r"@mock\.patch\s*\(['\"].*platform",
    ],
}

INTERNAL_DOMAIN_PATTERNS = [
    r"mock\s*\(\s*['\"].*service.*['\"]",
    r"mock\s*\(\s*['\"].*handler.*['\"]",
    r"mock\s*\(\s*['\"].*controller.*['\"]",
    r"mock\s*\(\s*['\"].*repository.*['\"]",
    r"mock\s*\(\s*['\"].*domain.*['\"]",
    r"mock\s*\(\s*['\"].*logic.*['\"]",
    r"mock\s*\(\s*['\"].*calculator.*['\"]",
    r"mock\s*\(\s*['\"].*validator.*['\"]",
    r"mock\s*\(\s*['\"].*processor.*['\"]",
]

EMPTY_STUB_PATTERNS = [
    r"def\s+\w+\s*\([^)]*\)\s*:\s*pass",
    r"def\s+\w+\s*\([^)]*\)\s*:\s*\.\.\.",
    r"lambda\s*[^:]*:\s*None",
    r"lambda\s*[^:]*:\s*pass",
    r"Mock\s*\(\s*\)\s*$",
    r"MagicMock\s*\(\s*\)\s*$",
    r"return_value\s*=\s*None",
    r"side_effect\s*=\s*None",
]

TRIVIAL_ASSERTION_PATTERNS = [
    r"assert\s+True",
    r"assert\s+\(?\s*True\s*\)?",
    r"assert\s+not\s+False",
    r"assert\s+\w+\s+is\s+not\s+None",
    r"assert\s+1",
    r"assert\s+\d+\s*==\s*\d+",
    r"assert\s+len\s*\(\s*\w+\s*\)\s*>=\s*0",
    r"assert\s+type\s*\(\s*\w+\s*\)\s*==\s*type",
]

NO_EXCEPTION_ONLY_PATTERNS = [
    r"try\s*:\s*\w+\.\w+\s*\([^)]*\)\s*except\s*:\s*assert\s+False",
    r"with\s+pytest\.raises\s*\(\s*\)\s*:",
    r"#\s*no\s*exception",
    r"#\s*just\s*check\s*it\s*runs",
    r"#\s*smoke\s*test",
]

SNAPSHOT_ONLY_PATTERNS = [
    r"assert\s+\w+\s*==\s*snapshot",
    r"snapshot\.match",
    r"expect\s*\(\s*\w+\s*\)\.toMatchSnapshot",
    r"snapshot\(\s*\w+\s*\)",
]


class MockClassification(Enum):
    """Classification of mock usage."""

    EXTERNAL_BOUNDARY = "external_boundary"
    INTERNAL_DOMAIN = "internal_domain"
    EMPTY_STUB = "empty_stub"
    FIXTURE_NAME_COUPLING = "fixture_name_coupling"
    UNKNOWN = "unknown"


class AssertionClassification(Enum):
    """Classification of assertion quality."""

    MEANINGFUL = "meaningful"
    TRIVIAL = "trivial"
    NO_EXCEPTION_ONLY = "no_exception_only"
    SNAPSHOT_ONLY = "snapshot_only"
    MISSING = "missing"
    CONSTANT = "constant"
