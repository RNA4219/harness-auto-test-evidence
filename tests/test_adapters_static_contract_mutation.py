"""Tests for SARIF, Pact, and Stryker adapter corpus - HATE-PG-001D."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hate.adapters.pact import parse_pact_file
from hate.adapters.sarif import parse_sarif_file
from hate.adapters.stryker import parse_stryker_file


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_sarif_fixture_preserves_location_severity_and_tool() -> None:
    result = parse_sarif_file(ROOT / "fixtures/adapters/sarif/full-mapping/HATE-static.sarif")

    assert [finding["rule_id"] for finding in result["findings"]] == ["WARN001", "WARN001"]
    assert result["findings"][0]["severity"] == "warning"
    assert result["findings"][0]["file"] == "src/db.py"
    assert result["findings"][0]["line"] == 5
    assert result["findings"][0]["tool"] == "semgrep"
    assert result["findings"][0]["sourceRef"].endswith("/locations/0")


def test_sarif_suppressed_finding_is_retained(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "suppressed.sarif",
        {
            "runs": [
                {
                    "tool": {"driver": {"name": "CodeQL"}},
                    "results": [
                        {
                            "ruleId": "SEC001",
                            "level": "error",
                            "message": {"text": "suppressed"},
                            "suppressions": [{"kind": "inSource"}],
                            "properties": {"changed_path": True},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "src/auth.py"},
                                        "region": {"startLine": 10},
                                    }
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )

    [finding] = parse_sarif_file(path)["findings"]
    assert finding["suppressed"] is True
    assert finding["changed_path"] is True
    assert finding["severity"] == "error"


def test_sarif_missing_location_and_malformed_json_are_errors(tmp_path: Path) -> None:
    missing = write_json(tmp_path / "missing.sarif", {"runs": [{"results": [{"ruleId": "R1"}]}]})
    malformed = tmp_path / "bad.sarif"
    malformed.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="physicalLocation"):
        parse_sarif_file(missing)
    with pytest.raises(ValueError, match="malformed SARIF"):
        parse_sarif_file(malformed)


def test_pact_hate_ndjson_fixture_preserves_failed_required_contract() -> None:
    result = parse_pact_file(ROOT / "fixtures/adapters/pact/contract-evidence/HATE-contract.ndjson")

    statuses = {contract["contract_id"]: contract["status"] for contract in result["contracts"]}
    failed = next(contract for contract in result["contracts"] if contract["contract_id"] == "pact-billing-provider-create-invoice")
    assert statuses == {
        "pact-auth-provider-login": "passed",
        "pact-billing-provider-create-invoice": "failed",
    }
    assert failed["provider"] == "billing-provider"
    assert failed["required"] is True
    assert failed["failure_class"] == "provider_verification_failed"
    assert failed["sourceRef"].endswith("#line=2")


def test_pact_verification_json_and_missing_interaction_id(tmp_path: Path) -> None:
    valid = write_json(
        tmp_path / "pact.json",
        {
            "provider": {"name": "auth-provider"},
            "consumer": {"name": "web-client"},
            "metadata": {"pactSpecification": {"version": "4.0.0"}},
            "interactions": [{"id": "login-success", "status": "passed"}],
        },
    )
    missing = write_json(tmp_path / "missing.json", {"interactions": [{}]})

    [contract] = parse_pact_file(valid)["contracts"]
    assert contract["interaction_id"] == "login-success"
    assert contract["pact_version"] == "4.0.0"
    with pytest.raises(ValueError, match="interaction id"):
        parse_pact_file(missing)


def test_stryker_hate_ndjson_fixture_preserves_survivors_and_no_coverage() -> None:
    result = parse_stryker_file(ROOT / "fixtures/adapters/stryker/mutation-evidence/HATE-mutation.ndjson")

    statuses = {mutation["mutation_id"]: mutation["status"] for mutation in result["mutations"]}
    survivor = next(mutation for mutation in result["mutations"] if mutation["mutation_id"] == "mut-auth-002")
    assert statuses == {
        "mut-auth-001": "killed",
        "mut-auth-002": "survived",
        "mut-db-001": "no_coverage",
    }
    assert survivor["file"] == "src/auth.py"
    assert survivor["covered_by"] == ["junit:tests/test_auth.py::test_login"]
    assert survivor["sourceRef"].endswith("#line=2")


def test_stryker_report_json_and_unknown_status(tmp_path: Path) -> None:
    valid = write_json(
        tmp_path / "mutation.json",
        {
            "mutants": [
                {
                    "id": "1",
                    "status": "Survived",
                    "sourceFilePath": "src\\calc.py",
                    "location": {"start": {"line": 7}},
                    "mutatorName": "ArithmeticOperator",
                    "coveredBy": ["test_calc"],
                }
            ]
        },
    )
    bad = write_json(tmp_path / "bad-mutation.json", {"mutants": [{"id": "1", "status": "Invented"}]})

    [mutation] = parse_stryker_file(valid)["mutations"]
    assert mutation["status"] == "survived"
    assert mutation["file"] == "src/calc.py"
    assert mutation["line"] == 7
    with pytest.raises(ValueError, match="unknown mutant status"):
        parse_stryker_file(bad)


def test_named_fixture_corpus_exists_for_static_contract_mutation() -> None:
    expected = {
        "fixtures/adapters/sarif/high-critical-changed-path/results.sarif",
        "fixtures/adapters/sarif/suppressed-finding/results.sarif",
        "fixtures/adapters/sarif/multiple-runs/results.sarif",
        "fixtures/adapters/sarif/malformed-json/results.sarif",
        "fixtures/adapters/sarif/missing-result-location/results.sarif",
        "fixtures/adapters/pact/provider-pass/verification.json",
        "fixtures/adapters/pact/provider-fail/verification.json",
        "fixtures/adapters/pact/version-mismatch/can-i-deploy.json",
        "fixtures/adapters/pact/malformed-json/verification.json",
        "fixtures/adapters/pact/missing-interaction-id/verification.json",
        "fixtures/adapters/stryker/killed-survived-timeout/mutation.json",
        "fixtures/adapters/stryker/no-coverage/mutation.json",
        "fixtures/adapters/stryker/incremental/mutation.json",
        "fixtures/adapters/stryker/malformed-json/mutation.json",
        "fixtures/adapters/stryker/unknown-mutant-status/mutation.json",
    }

    assert all((ROOT / path).exists() for path in expected)


def test_named_positive_corpus_parses() -> None:
    sarif = parse_sarif_file(ROOT / "fixtures/adapters/sarif/multiple-runs/results.sarif")
    pact_fail = parse_pact_file(ROOT / "fixtures/adapters/pact/provider-fail/verification.json")
    pact_mismatch = parse_pact_file(ROOT / "fixtures/adapters/pact/version-mismatch/can-i-deploy.json")
    stryker = parse_stryker_file(ROOT / "fixtures/adapters/stryker/killed-survived-timeout/mutation.json")
    incremental = parse_stryker_file(ROOT / "fixtures/adapters/stryker/incremental/mutation.json")

    assert [finding["tool"] for finding in sarif["findings"]] == ["semgrep", "codeql"]
    assert pact_fail["contracts"][0]["status"] == "failed"
    assert pact_mismatch["contracts"][0]["failure_class"] == "version_mismatch"
    assert {mutation["status"] for mutation in stryker["mutations"]} == {"killed", "survived", "timeout"}
    assert incremental["mutations"][0]["mutation_id"] == "m1"


def test_named_negative_corpus_errors() -> None:
    with pytest.raises(ValueError, match="malformed SARIF"):
        parse_sarif_file(ROOT / "fixtures/adapters/sarif/malformed-json/results.sarif")
    with pytest.raises(ValueError, match="physicalLocation"):
        parse_sarif_file(ROOT / "fixtures/adapters/sarif/missing-result-location/results.sarif")
    with pytest.raises(json.JSONDecodeError):
        parse_pact_file(ROOT / "fixtures/adapters/pact/malformed-json/verification.json")
    with pytest.raises(ValueError, match="interaction id"):
        parse_pact_file(ROOT / "fixtures/adapters/pact/missing-interaction-id/verification.json")
    with pytest.raises(json.JSONDecodeError):
        parse_stryker_file(ROOT / "fixtures/adapters/stryker/malformed-json/mutation.json")
    with pytest.raises(ValueError, match="unknown mutant status"):
        parse_stryker_file(ROOT / "fixtures/adapters/stryker/unknown-mutant-status/mutation.json")
