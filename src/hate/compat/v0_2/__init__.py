"""Frozen v0.2 behavior used by the v0.3 bridge router.

Only security, correctness, and schema/CLI compatibility fixes belong here.
"""

from .handlers import dispatch_compat_cli

__all__ = ["dispatch_compat_cli"]
