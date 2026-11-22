"""現在のrunへ取り込むHATE recordのrun/attempt/commitを照合する。"""

from __future__ import annotations

from typing import Any

from .input_values import commit_identifier, positive_run_attempt, run_identifier
from .p0b_types import ExportError, P0bInputBundle


def _identity(data: dict[str, Any], location: str, *, required: bool) -> dict[str, str | int]:
    result: dict[str, str | int] = {}
    for field, validator in (("run_id", run_identifier), ("run_attempt", positive_run_attempt), ("commit_sha", commit_identifier)):
        if field not in data:
            if required:
                raise ExportError(f"{location}.{field} is required", exit_code=1)
            continue
        try:
            result[field] = validator(data[field])
        except ValueError as exc:
            raise ExportError(f"{location}.{field}: {exc}", exit_code=1) from exc
    if "run_attempt" in result:
        data["run_attempt"] = result["run_attempt"]
    return result


def validate_input_run(inputs: P0bInputBundle) -> None:
    base_location = str(inputs.p0a_dir / "HATE-run.json")
    base = _identity(inputs.run_record, base_location, required=True)

    def compare(data: dict[str, Any], location: str, *, required: bool = True) -> None:
        for field, value in _identity(data, location, required=required).items():
            if value != base[field]:
                raise ExportError(f"{location}.{field} mismatch with {base_location}.{field}", exit_code=1)

    for name, record in [
        ("HATE-run.json", inputs.run_record), ("precheck-decision.json", inputs.precheck_decision),
        ("record.json", inputs.audit_record), ("artifact-manifest.json", inputs.artifact_manifest),
    ]:
        location = str(inputs.p0a_dir / name)
        compare(record, location)
        if name != "artifact-manifest.json" and not isinstance(record.get("payload"), dict):
            raise ExportError(f"{location}.payload must be a JSON object", exit_code=1)
    ci = inputs.run_record["payload"].get("ci", {})
    if not isinstance(ci, dict):
        raise ExportError(f"{base_location}.payload.ci must be a JSON object", exit_code=1)
    compare(ci, f"{base_location}.payload.ci", required=False)
    for name, records in [
        ("HATE-test-results.ndjson", inputs.test_records), ("HATE-coverage.ndjson", inputs.coverage_records),
        ("HATE-contract.ndjson", inputs.contract_records), ("HATE-mutation.ndjson", inputs.mutation_records),
        ("HATE-evidence-strength.ndjson", inputs.evidence_strength_records),
    ]:
        for index, record in enumerate(records):
            location = f"{inputs.p0a_dir / name}: records[{index}]"
            compare(record, location)
            if not isinstance(record.get("payload"), dict):
                raise ExportError(f"{location}.payload must be a JSON object", exit_code=1)
    # 変更対応表の宣言は現在runのもの。履歴資料のrisk debt/escaped defectsには適用しない。
    compare(inputs.diff_risk_test, str(inputs.diff_risk_path), required=False)
    # native SARIFにHATE識別情報が追加されている場合のみ照合する。
    compare(inputs.sarif_record, str(inputs.p0a_dir / "HATE-static.sarif"), required=False)
