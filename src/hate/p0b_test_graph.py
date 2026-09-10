"""logical testと各観測recordを分け、実行履歴を失わないnodeを作る。"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from .execution_metadata import EXECUTION_FIELDS
from .execution_status import effective_status, outcome_declarations
from .p0b_support import _hash_test_id
from .p0b_types import ExportError

IDENTITY_FIELDS = ("framework", "file", "name", "classname", "class_name", "package", "parameters", "params", "identity_components")


def test_execution_groups(
    records: list[dict[str, Any]], run_id: str, run_attempt: int, source: str,
) -> list[tuple[dict[str, Any], list[tuple[dict[str, Any], dict[str, Any]]]]]:
    """同じ正規化recordは一度だけ、異なるrecordは別executionとして残す。"""
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        grouped[record["payload"]["canonical_test_id"]][encoded] = record
    result = []
    for canonical, observations in sorted(grouped.items()):
        ordered = sorted(observations.items())
        payloads = [record["payload"] for _, record in ordered]
        identity: dict[str, Any] = {}
        for field in IDENTITY_FIELDS:
            values = [payload[field] for payload in payloads if field in payload]
            if values and any(value != values[0] for value in values[1:]):
                raise ExportError(f"{source}: conflicting payload.{field} for canonical test {canonical}", exit_code=1)
            if values:
                identity[field] = values[0]
        test_hash = _hash_test_id(canonical)
        statuses = {effective_status(payload) for payload in payloads}
        test_data = {
            "canonical_test_id": canonical,
            "framework": "unknown",
            "file": "",
            **identity,
            "status": next(iter(statuses)) if len(statuses) == 1 else "inconclusive",
        }
        if len(ordered) == 1:
            test_data["duration_ms"] = payloads[0].get("duration_ms", 0)
            test_data.update(outcome_declarations(payloads[0]))
            if "parser_diagnostics" in payloads[0]:
                test_data["parser_diagnostics"] = payloads[0]["parser_diagnostics"]
        test_node = {
            "id": f"test:{test_hash}", "kind": "test",
            "label": identity.get("name", canonical), "data": test_data, "sourceRefs": [source],
        }
        executions = []
        for encoded, record in ordered:
            payload = record["payload"]
            digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            execution_id = f"execution:{run_id}:{test_hash}"
            if len(ordered) > 1:
                execution_id += f":{digest}"
            execution_data = {
                "run_id": run_id, "run_attempt": run_attempt,
                **({"commit_sha": record["commit_sha"]} if "commit_sha" in record else {}),
                "status": effective_status(payload), "duration_ms": payload.get("duration_ms", 0),
                **outcome_declarations(payload),
                "source_record_sha256": digest,
                **{field: payload[field] for field in EXECUTION_FIELDS if field in payload},
                **({"parser_diagnostics": payload["parser_diagnostics"]} if "parser_diagnostics" in payload else {}),
            }
            if "record_id" in record:
                execution_data["source_record_id"] = record["record_id"]
            executions.append((record, {
                "id": execution_id, "kind": "execution_evidence", "label": f"Execution: {canonical}",
                "data": execution_data, "sourceRefs": [source],
            }))
        result.append((test_node, executions))
    return result
