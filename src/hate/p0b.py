"""Compatibility facade for P0b QEG export.

The implementation lives in ``hate.p0b_exporter`` so the public
``hate.p0b.export_qeg`` import remains stable while export phases can be
refactored independently.
"""

from __future__ import annotations

from .p0b_exporter import export_qeg
from .p0b_types import ExportError

__all__ = ["ExportError", "export_qeg"]
