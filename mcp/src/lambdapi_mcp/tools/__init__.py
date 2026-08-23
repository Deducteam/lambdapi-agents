"""MCP tool implementations, split by concern.

Each tool is a plain function taking an ``LSPClient`` and returning a
JSON-serialisable dict. This package preserves the flat import surface of
the former ``tools.py``: ``from lambdapi_mcp import tools`` then
``tools.tool_check(...)``.
"""
from __future__ import annotations

from .check import tool_check
from .goals import tool_goals
from .query import (
    _safe_query_line,  # noqa: F401
    tool_query,
)

# Private helpers re-exported at the package level for the test suite, which
# exercises them directly (kept working across the tools.py -> tools/ split).
from .signature import (
    _discover_pkg_roots,  # noqa: F401
    tool_signature,
)
from .try_ import tool_try

__all__ = [
    "tool_check",
    "tool_goals",
    "tool_query",
    "tool_signature",
    "tool_try",
]
