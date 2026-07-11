"""Bridge provider protocol and route metadata."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BridgeRoute:
    command_path: str
    canonical_owner: str
    canonical_contract: str
    expected_output_types: tuple[str, ...]
    deprecated_since: str = "0.3.0"
    remove_after: str = "1.0.0"


class BridgeProvider(Protocol):
    name: str

    def execute(
        self,
        args: argparse.Namespace,
        parser: argparse.ArgumentParser,
        route: BridgeRoute,
    ) -> int: ...
