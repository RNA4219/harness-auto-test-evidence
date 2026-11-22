"""Bridge provider protocol and route metadata."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Literal, Protocol

PathRole = Literal["input", "optional-input", "destination"]


@dataclass(frozen=True)
class BridgeRoute:
    command_path: str
    canonical_owner: str
    canonical_contract: str
    expected_output_types: tuple[str, ...]
    deprecated_since: str = "0.3.0"
    remove_after: str = "1.0.0"
    directory_output: bool = False
    path_arguments: tuple[tuple[str, PathRole], ...] = ()


class BridgeProvider(Protocol):
    name: str

    def execute(
        self,
        args: argparse.Namespace,
        parser: argparse.ArgumentParser,
        route: BridgeRoute,
    ) -> int: ...
