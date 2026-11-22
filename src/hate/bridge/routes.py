"""CLI責務台帳と実行時ルーティングで共有する橋渡し先。"""

from __future__ import annotations

from .protocol import BridgeRoute, PathRole

# v0.3.0の実行時の担当先・契約名を維持し、コマンド名からの推測を排除する。
_ROUTES = {
    "expansion run": ("workflow-cookbook", "workflow-cookbook/HATE-bridge-consumer/v1"),
    "gap closure": ("workflow-cookbook", "workflow-cookbook/HATE-bridge-consumer/v1"),
    "platform assign": ("agent-state-gate", "HumanQueueItem/v1"),
    "platform baseline promote": ("quality-evidence-graph", "QEG/v1"),
    "platform baseline review": ("quality-evidence-graph", "QEG/v1"),
    "platform compare": ("agent-gatefield", "AgentAssessment/v1"),
    "platform debt": ("agent-state-gate", "AgentAssessment/v1"),
    "platform findings": ("agent-state-gate", "AgentAssessment/v1"),
    "platform history": ("workflow-cookbook", "HATE-evidence-export/v1"),
    "platform history-analytics": ("product-ops-evidence", "POE/v1"),
    "platform history-materialize": ("workflow-cookbook", "HATE-evidence-export/v1"),
    "platform notify deliver": ("product-ops-evidence", "POE/v1"),
    "platform notify route": ("product-ops-evidence", "POE/v1"),
    "platform plugin run": ("harness-auto-test-evidence", "HATE/v1"),
    "platform policy explain": ("agent-gatefield", "GatePolicy/v1"),
    "platform report html": ("product-ops-evidence", "POE/v1"),
    "platform review": ("manual-bb-test-harness", "manual_case_set/v1"),
    "platform run": ("shipyard-cp", "RunSystemPacket"),
    "platform schedule": ("shipyard-cp", "RunSystemPacket"),
    "platform score": ("agent-gatefield", "AgentAssessment/v1"),
    "platform serve": ("product-ops-evidence", "POE/v1"),
    "platform triage": ("agent-state-gate", "HumanQueueItem/v1"),
    "platform verdict": ("quality-evidence-graph", "QEG/v1"),
    "product grade-reports": ("product-ops-evidence", "POE/v1"),
    "product query": ("product-ops-evidence", "POE/v1"),
    "product readiness": ("product-ops-evidence", "POE/v1"),
    "product serve": ("product-ops-evidence", "POE/v1"),
    "real-repo history-ingest": ("shipyard-cp", "RunSystemPacket"),
    "real-repo history-query": ("shipyard-cp", "RunSystemPacket"),
    "real-repo run": ("shipyard-cp", "RunSystemPacket"),
    "release candidate": ("quality-evidence-graph", "QEG/v1"),
    "validation cycles": ("workflow-cookbook", "five-tool-validation-manifest/v1"),
    "workflow map": ("workflow-cookbook", "agent-protocols/HATE-bridge-consumer/v1"),
}

BRIDGE_COMMANDS = frozenset(command.split()[0] for command in _ROUTES)

_DIRECTORY_OUTPUT_COMMANDS = frozenset({
    "workflow map", "product readiness", "product grade-reports", "release candidate",
    "gap closure", "expansion run", "real-repo run", "platform run", "validation cycles",
})

# ローカルのout/manifest_out以外は、未指定の任意引数も含めて列挙する。
_PATH_ARGUMENTS = {
    "expansion run": ("fixtures_root",),
    "gap closure": ("repo_root",),
    "platform assign": ("input",),
    "platform baseline promote": ("input",),
    "platform baseline review": ("input",),
    "platform compare": ("base", "head"),
    "platform debt": ("input",),
    "platform findings": ("input",),
    "platform history": ("store",),
    "platform history-analytics": ("input",),
    "platform history-materialize": ("input", "previous_manifest"),
    "platform notify deliver": ("input",),
    "platform notify route": ("input",),
    "platform plugin run": ("manifest",),
    "platform policy explain": ("policy",),
    "platform report html": ("input",),
    "platform review": ("input",),
    "platform run": ("roster",),
    "platform schedule": ("roster", "history_store"),
    "platform score": ("input",),
    "platform serve": ("readiness",),
    "platform triage": ("input",),
    "platform verdict": ("input", "corpus"),
    "product grade-reports": ("docs_root",),
    "product query": ("readiness",),
    "product readiness": ("bundle", "trust", "workflow"),
    "product serve": ("readiness",),
    "real-repo history-ingest": ("history", "store"),
    "real-repo history-query": ("store",),
    "real-repo run": ("roster",),
    "release candidate": ("readiness",),
    "validation cycles": ("fixture",),
    "workflow map": (
        "bundle", "report", "trust", "rand_requirements", "rand_audit",
        "shipyard_worker_result", "shipyard_run_system_packet",
    ),
}

# argparseのrequiredは指定の要否であり、ファイルの存在条件ではない。
_PATH_ROLE_OVERRIDES: dict[tuple[str, str], PathRole] = {
    ("real-repo history-ingest", "store"): "destination",
    ("platform schedule", "history_store"): "optional-input",
}


def route_for_command(command: str) -> BridgeRoute:
    try:
        owner, contract = _ROUTES[command]
        arguments = _PATH_ARGUMENTS[command]
    except KeyError as exc:
        raise ValueError(f"unregistered bridge command: {command}") from exc
    return BridgeRoute(
        command, owner, contract, (f"legacy:{command.replace(' ', '-')}",),
        directory_output=command in _DIRECTORY_OUTPUT_COMMANDS,
        path_arguments=tuple((name, _PATH_ROLE_OVERRIDES.get((command, name), "input")) for name in arguments),
    )
