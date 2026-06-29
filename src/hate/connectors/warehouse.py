"""Warehouse dry-run connector wrapper."""

from __future__ import annotations

from typing import Any

from hate.connectors.ops import OpsConnectorResult, build_ops_connector


def build_warehouse_dry_run(
    enterprise_control_report: dict[str, Any],
    connector_config: dict[str, Any] | None = None,
) -> OpsConnectorResult:
    return build_ops_connector(enterprise_control_report, "warehouse", connector_config)
