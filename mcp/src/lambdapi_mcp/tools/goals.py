"""``lambdapi_goals`` — proof state at a line."""
from __future__ import annotations

from ..lsp import LSPClient, file_uri
from ._common import _require_position, _format_goals_compact


def tool_goals(client: LSPClient, file: str, line: int) -> dict:
    """Return the proof state (hyps + goals) at 1-based [line], formatted
    compactly. Output is ``{file, line, pretty}`` where ``pretty`` is a
    flush-left hypothesis-per-line rendering, or ``"no goals"`` when the
    state is empty."""
    text, err = _require_position(file, line)
    if err:
        return err
    uri = file_uri(file)
    with client.open_doc(uri, text):
        result = client.goals(uri, line=line - 1, character=0)
    goals = (result or {}).get("goals") or []
    return {
        "file": file, "line": line,
        "pretty": _format_goals_compact(goals),
    }
