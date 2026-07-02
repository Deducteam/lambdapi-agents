"""``lambdapi_query`` — run compute/type/print/search at a line."""
from __future__ import annotations

import re

from ..lsp import LSPClient, file_uri
from ._common import (
    _require_position,
    _insert_at,
    _ensure_semicolon,
    _errors,
    _split_lines,
    _strip_comments,
)


_QUERY_VERBS = {"compute", "type", "print", "search"}


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _safe_query_line(text: str, requested_line: int) -> int:
    """Snap [requested_line] forward to the next top-level statement
    boundary — the smallest 1-based line at which inserting a new line
    lands immediately after a top-level ``;`` (or at start/end of file).

    Queries are top-level commands; if the user's chosen line falls
    inside a ``begin…end`` proof block (or anywhere mid-statement),
    lambdapi parses the inserted query as a tactic and reports
    ``Expected: abort, admitted, end.`` We walk the character stream
    once, tracking:

    - ``depth``: nesting of ``()`` / ``[]`` — a ``;`` inside a term
      does not terminate the statement.
    - ``proof_depth``: nesting of ``begin`` / ``end`` — tactic-internal
      ``;`` inside a proof must NOT be treated as a top-level
      terminator (the outer statement is the whole ``opaque symbol …
      begin … end;`` block).
    - ``boundary``: whether no non-whitespace char at top level has been
      seen since the last top-level ``;`` or start of file. A line is
      safe iff ``boundary`` was True and we were outside any proof when
      we crossed into that line.
    """
    stripped = _strip_comments(text)
    n = len(_split_lines(text))
    safe = [False] * (n + 2)
    safe[1] = True
    depth = 0
    proof_depth = 0
    boundary = True
    current_line = 1
    i = 0
    L = len(stripped)
    while i < L:
        ch = stripped[i]
        if ch == "\n":
            current_line += 1
            if current_line <= n + 1:
                safe[current_line] = boundary and proof_depth == 0
            i += 1
            continue
        if ch in "([":
            depth += 1
            boundary = False
            i += 1
            continue
        if ch in ")]":
            depth -= 1
            boundary = False
            i += 1
            continue
        if ch.isspace():
            i += 1
            continue
        m = _IDENT_RE.match(stripped, i) if ch.isascii() and (ch.isalpha() or ch == "_") else None
        if m:
            word = m.group()
            if word == "begin":
                proof_depth += 1
            elif word == "end" and proof_depth > 0:
                proof_depth -= 1
            boundary = False
            i = m.end()
            continue
        if ch == ";" and depth == 0 and proof_depth == 0:
            boundary = True
        else:
            boundary = False
        i += 1
    safe[n + 1] = boundary and proof_depth == 0
    lo = max(1, requested_line)
    for i in range(lo, n + 2):
        if safe[i]:
            return i
    return n + 1


def tool_query(
    client: LSPClient, file: str, line: int, query: str
) -> dict:
    """Run a query at [line]. [query] is the full query text, e.g.
    ``compute (1 + 1)`` or ``print foo``.

    [line] is a lower bound: the query is inserted at the first top-
    level statement boundary at or after [line]. When the effective
    insertion line differs from the requested one, the response
    includes an ``effective_line`` field."""
    verb = query.strip().split(None, 1)[0] if query.strip() else ""
    if verb not in _QUERY_VERBS:
        return {
            "ok": False,
            "error": f"unknown query verb {verb!r}; "
                     f"expected one of {sorted(_QUERY_VERBS)}",
        }
    text, err = _require_position(file, line)
    if err:
        return err
    effective_line = _safe_query_line(text, line)
    modified = _insert_at(text, effective_line, _ensure_semicolon(query))
    uri = file_uri(file)
    # Query output comes back through window/logMessage notifications
    # and the OK-hint (severity=4) diagnostic's message field — capture
    # both via the session.
    with client.open_doc(uri, modified) as session:
        pass
    diags = session.diagnostics
    errs = _errors(diags)
    if errs:
        out = {"ok": False, "error": errs[0]["message"]}
        if effective_line != line:
            out["effective_line"] = effective_line
        return out
    target = effective_line - 1  # 0-based probe line
    output = "\n".join(
        d["message"] for d in diags
        if d.get("severity") == 4
        and d["range"]["start"]["line"] == target
    )
    logs = [
        m["params"].get("message", "")
        for m in session.notifications
        if m.get("method") == "window/logMessage"
    ]
    out = {"ok": True, "output": output}
    if effective_line != line:
        out["effective_line"] = effective_line
    if logs:
        out["logs"] = logs
    return out
