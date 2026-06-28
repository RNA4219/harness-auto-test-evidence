from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .p2p3_io import SCHEMA_VERSION, _stable_hash, _stable_ref


@dataclass
class StoreError(Exception):
    message: str
    exit_code: int = 1

    def __str__(self) -> str:
        return self.message


def ingest_local_store(
    store_dir: Path,
    bundle_path: Path,
    readiness_dir: Path,
    source_version: str | None = None,
) -> dict[str, Any]:
    """Persist canonical bundle, readiness, and risk debt into a local history store."""
    if not bundle_path.exists():
        raise StoreError(f"QEG bundle not found: {bundle_path}", exit_code=2)
    if not readiness_dir.exists():
        raise StoreError(f"product readiness directory not found: {readiness_dir}", exit_code=2)

    bundle = _read_json(bundle_path)
    readiness = _read_json(readiness_dir / "product-readiness-report.json")
    risk_debt = _read_json(readiness_dir / "enterprise-risk-debt-register.json")
    run_id = str(bundle.get("metadata", {}).get("runId") or readiness.get("run_id") or "")
    if not run_id:
        raise StoreError("cannot ingest store without run id", exit_code=1)

    run_dir = store_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    version = source_version or __version__
    manifest = _build_store_manifest(run_id, bundle_path, readiness_dir, bundle, readiness, risk_debt, version)

    _write_json(run_dir / "qeg-bundle.json", bundle)
    _write_json(run_dir / "product-readiness-report.json", readiness)
    _write_json(run_dir / "enterprise-risk-debt-register.json", risk_debt)
    _write_json(run_dir / "store-manifest.json", manifest)

    history = _update_history_index(store_dir, manifest)
    return {
        "store_status": "success",
        "exit_code": 0,
        "run_id": run_id,
        "store_dir": _store_ref(store_dir),
        "history_count": history["summary"]["run_count"],
        "generated": [
            "history-index.json",
            f"runs/{run_id}/qeg-bundle.json",
            f"runs/{run_id}/product-readiness-report.json",
            f"runs/{run_id}/enterprise-risk-debt-register.json",
            f"runs/{run_id}/store-manifest.json",
        ],
        "publish_gate_override": False,
        "release_gate_override": False,
    }


def query_local_store(store_dir: Path, resource: str, run_id: str | None = None) -> dict[str, Any]:
    """Reload a resource from the local HATE store."""
    history = _read_history(store_dir)
    selected_run = run_id or history["summary"].get("latest_run_id", "")
    if resource == "history":
        return history
    if not selected_run:
        raise StoreError("no run id supplied and history has no latest run", exit_code=2)
    artifact_map = {
        "run": "store-manifest.json",
        "bundle": "qeg-bundle.json",
        "risk-debt": "enterprise-risk-debt-register.json",
        "product-readiness": "product-readiness-report.json",
        "manifest": "store-manifest.json",
    }
    if resource not in artifact_map:
        raise StoreError(f"unknown store resource: {resource}", exit_code=2)
    path = store_dir / "runs" / selected_run / artifact_map[resource]
    data = _read_json(path)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "local_store_query",
        "resource": resource,
        "run_id": selected_run,
        "data": data,
        "source_refs": [_store_ref(path)],
        "stale_cache": False,
        "canonical_source_preserved": True,
        "publish_gate_override": False,
        "release_gate_override": False,
    }


def read_history_index(store_dir: Path) -> dict[str, Any]:
    """Read the local store history index."""
    return _read_history(store_dir)


def _build_store_manifest(
    run_id: str,
    bundle_path: Path,
    readiness_dir: Path,
    bundle: dict[str, Any],
    readiness: dict[str, Any],
    risk_debt: dict[str, Any],
    version: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "local_store_manifest",
        "run_id": run_id,
        "source_tool": "harness-auto-test-evidence",
        "source_version": version,
        "artifacts": [
            {
                "artifact_ref": "qeg-bundle.json",
                "kind": "qeg_bundle",
                "hash": _stable_hash(bundle),
                "source_ref": _stable_ref(bundle_path),
            },
            {
                "artifact_ref": "product-readiness-report.json",
                "kind": "product_readiness",
                "hash": _stable_hash(readiness),
                "source_ref": _stable_ref(readiness_dir / "product-readiness-report.json"),
            },
            {
                "artifact_ref": "enterprise-risk-debt-register.json",
                "kind": "risk_debt",
                "hash": _stable_hash(risk_debt),
                "source_ref": _stable_ref(readiness_dir / "enterprise-risk-debt-register.json"),
            },
        ],
        "summary": {
            "product_status": readiness.get("summary", {}).get("overall_status", ""),
            "risk_debt_open_count": risk_debt.get("summary", {}).get("open_count", 0),
            "bundle_node_count": len(bundle.get("nodes", [])),
            "bundle_edge_count": len(bundle.get("edges", [])),
        },
        "boundaries": {
            "canonical_source_preserved": True,
            "stale_cache": False,
            "publish_gate_override": False,
            "release_gate_override": False,
        },
    }


def _update_history_index(store_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    history_path = store_dir / "history-index.json"
    if history_path.exists():
        history = _read_json(history_path)
    else:
        history = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "local_store_history_index",
            "runs": [],
            "summary": {"run_count": 0, "latest_run_id": ""},
            "publish_gate_override": False,
            "release_gate_override": False,
        }
    runs = [run for run in history.get("runs", []) if run.get("run_id") != manifest["run_id"]]
    runs.append({
        "run_id": manifest["run_id"],
        "manifest_ref": f"runs/{manifest['run_id']}/store-manifest.json",
        "product_status": manifest["summary"]["product_status"],
        "risk_debt_open_count": manifest["summary"]["risk_debt_open_count"],
        "artifact_count": len(manifest["artifacts"]),
        "source_refs": [artifact["source_ref"] for artifact in manifest["artifacts"]],
    })
    history["runs"] = sorted(runs, key=lambda item: str(item.get("run_id", "")))
    history["summary"] = {
        "run_count": len(history["runs"]),
        "latest_run_id": manifest["run_id"],
        "resources": ["run", "bundle", "risk-debt", "product-readiness", "manifest", "history"],
    }
    history["publish_gate_override"] = False
    history["release_gate_override"] = False
    store_dir.mkdir(parents=True, exist_ok=True)
    _write_json(history_path, history)
    return history


def _read_history(store_dir: Path) -> dict[str, Any]:
    return _read_json(store_dir / "history-index.json")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise StoreError(f"required store artifact not found: {path}", exit_code=2)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise StoreError(f"{path.name} must contain a JSON object", exit_code=1)
    return data


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _store_ref(path: Path) -> str:
    try:
        return "workspace:/" + path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return "path:/" + path.name
