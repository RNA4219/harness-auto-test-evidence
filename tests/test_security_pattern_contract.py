"""Contract tests for shared artifact-safety matching rules."""

from __future__ import annotations

import pytest

from hate.security import artifact_safety, patterns, redaction

SHARED_RULE_NAMES = (
    "SECRET_PATTERNS",
    "PRIVATE_KEY_PATTERNS",
    "PII_PATTERNS",
    "PATH_PATTERNS",
    "URL_PATTERN",
)


def test_scanner_and_redactor_reexport_the_canonical_rules() -> None:
    for name in SHARED_RULE_NAMES:
        canonical_rule = getattr(patterns, name)
        assert getattr(artifact_safety, name) is canonical_rule
        assert getattr(redaction, name) is canonical_rule
    assert artifact_safety.classify_url is patterns.classify_url
    assert redaction.classify_url is patterns.classify_url


@pytest.mark.parametrize(
    ("content", "finding_type", "marker"),
    [
        pytest.param('api_key = "ABCDEFGHIJKLMNOPQRSTUVWX"', "secret_detected", "[REDACTED_SECRET]", id="api-key"),
        pytest.param("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "secret_detected", "[REDACTED_SECRET]", id="github-token"),
        pytest.param("AKIAABCDEFGHIJKLMNOP", "secret_detected", "[REDACTED_SECRET]", id="aws-key"),
        pytest.param(f"sk-{'A' * 40}", "secret_detected", "[REDACTED_SECRET]", id="openai-key"),
        pytest.param('password="DUMMYCREDENTIAL12345"', "secret_detected", "[REDACTED_SECRET]", id="password"),
        pytest.param(
            "-----BEGIN PRIVATE KEY-----\nopaque-key-material\n-----END PRIVATE KEY-----",
            "secret_detected",
            "[REDACTED_SECRET]",
            id="private-key",
        ),
        pytest.param("email=person@example.com", "pii_detected", "[REDACTED_PII]", id="email"),
        pytest.param("phone=555-010-9999", "pii_detected", "[REDACTED_PII]", id="phone"),
        pytest.param('user_id="customer-123"', "pii_detected", "[REDACTED_PII]", id="user-id"),
        pytest.param('name="Ada Lovelace"', "pii_detected", "[REDACTED_PII]", id="name"),
        pytest.param(r"opened C:\Users\alice\AppData\trace.zip", "unsafe_path_detected", "[REDACTED_PATH]", id="windows-path"),
        pytest.param("opened /home/alice/.ssh/config", "unsafe_path_detected", "[REDACTED_PATH]", id="unix-home"),
        pytest.param("opened /etc/shadow", "unsafe_path_detected", "[REDACTED_PATH]", id="private-absolute-path"),
        pytest.param("opened ../secrets/token.txt", "unsafe_path_detected", "[REDACTED_PATH]", id="unix-traversal"),
        pytest.param(r"opened ..\secrets\token.txt", "unsafe_path_detected", "[REDACTED_PATH]", id="windows-traversal"),
        pytest.param(
            "https://github.com/example/repo?token=credential",
            "external_url_detected",
            "[REDACTED_URL]",
            id="suspicious-allowlisted-url",
        ),
    ],
)
def test_sensitive_matches_have_shared_detection_and_redaction(content: str, finding_type: str, marker: str) -> None:
    fixture = {
        "artifact_id": "security-pattern-contract",
        "artifact_path": "logs/security-contract.log",
        "profile": "release",
        "content": content,
    }

    safety_report = artifact_safety.scan_artifact_safety(fixture)
    redaction_report = redaction.redact_artifact(fixture)

    assert any(finding["finding_type"] == finding_type for finding in safety_report["findings"])
    assert safety_report["redaction_required"] is True
    assert redaction_report["redaction_status"] == "redacted"
    assert marker in redaction_report["redacted_content"]
