"""``lambdapi_try`` — probe tactics without touching disk."""
from __future__ import annotations

from ..lsp import LSPClient, file_uri
from ._common import (
    _require_position,
    _ensure_semicolon,
    _insert_at,
    _replace_line,
    _errors,
    _goal_target,
    _format_goals_compact,
    _split_lines,
)


def _goals_key(goals: list[dict]) -> list[tuple]:
    """A gid-free, hashable summary of a goal list, for progress checks.

    The LSP assigns fresh goal ids on every didOpen, so `gid` differs
    between our pre- and post- probes even when the tactic made no
    change. Compare on (typeofgoal, type, normalised hyps) instead."""
    return [
        (
            g.get("typeofgoal", ""),
            _goal_target(g),
            tuple(
                (h.get("hname", ""), h.get("htype", ""))
                for h in g.get("hyps", []) or []
            ),
        )
        for g in goals
    ]


_TRY_DEFAULT_MAX_LINES = 12


def _truncate_lines(text: str, max_lines: int) -> tuple[str, int]:
    """Cap [text] to its first [max_lines] lines, returning the
    truncated text and the count of dropped lines (0 when nothing was
    cut)."""
    if max_lines <= 0:
        return text, 0
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text, 0
    kept = lines[:max_lines]
    dropped = len(lines) - max_lines
    return "\n".join(kept), dropped


def _probe_one(
    client: LSPClient,
    uri: str,
    text: str,
    line: int,
    tactic: str,
    mode: str,
    pre_goals: list[dict],
    max_lines: int,
) -> dict:
    """Probe a single tactic against an unchanged pre-state; return the
    per-attempt outcome dict."""
    probe = _ensure_semicolon(tactic)
    if mode == "insert":
        modified = _insert_at(text, line, probe)
    else:
        modified, _ = _replace_line(text, line, probe)
    probe_line_0 = line - 1
    with client.open_doc(uri, modified) as session:
        post = client.goals(uri, line=probe_line_0 + 1, character=0) or {}
    errs_at_probe = [
        d for d in _errors(session.diagnostics)
        if d["range"]["start"]["line"] == probe_line_0
    ]
    post_goals = post.get("goals", []) or []
    out: dict = {"tactic": tactic}
    if errs_at_probe:
        out["ok"] = False
        msg = errs_at_probe[0]["message"]
        truncated, dropped = _truncate_lines(msg, max_lines)
        out["error"] = truncated
        if dropped:
            out["error_truncated_lines"] = dropped
        return out
    closed = bool(pre_goals) and not post_goals
    progress = _goals_key(pre_goals) != _goals_key(post_goals)
    out["ok"] = True
    out["closed"] = closed
    out["progress"] = progress
    # Post-state is only worth returning when the tactic left more work.
    # If it closed the proof, post is trivially empty. If it made no
    # progress, post == pre. Skip both cases.
    if progress and not closed:
        post_str = _format_goals_compact(post_goals)
        truncated, dropped = _truncate_lines(post_str, max_lines)
        out["post"] = truncated
        if dropped:
            out["post_truncated_lines"] = dropped
    return out


def tool_try(
    client: LSPClient,
    file: str,
    line: int,
    tactics: list[str],
    mode: str = "insert",
    max_lines: int | None = None,
) -> dict:
    """Try one or more tactics at [line] without modifying the file.

    ``mode='insert'`` inserts the tactic before [line]; ``mode='replace'``
    overwrites [line] (useful when probing an already-bound name).

    The pre-state is captured once and shared across all attempts. Each
    attempt in the returned list carries the tactic and booleans:

    - ``ok``: no error diagnostic on the probe line.
    - ``closed``: the pre-state had ≥1 goal and the post-state has 0 —
      the tactic finished the proof obligation.
    - ``progress``: the goal state changed.

    ``post`` (compact goal rendering) is included only when the tactic
    made progress but didn't close the goal — the one case where the
    caller needs to see what's left.

    Both ``error`` (on failed attempts) and ``post`` (on progressed
    attempts) are truncated to [max_lines] lines (default 12) to keep
    multi-tactic probes readable. When truncation kicks in, the per-
    attempt dict gains ``error_truncated_lines`` / ``post_truncated_lines``
    so the caller knows how much was dropped. Pass ``max_lines=0`` for
    no truncation.
    """
    if mode not in ("insert", "replace"):
        return {"ok": False, "error": f"bad mode {mode!r}"}
    if not isinstance(tactics, list) or not tactics:
        return {
            "ok": False, "file": file, "line": line,
            "error": "tactics: expected a non-empty list of tactic strings",
        }
    for t in tactics:
        if not isinstance(t, str) or not t.strip():
            return {
                "ok": False, "file": file, "line": line,
                "error": "tactics: each tactic must be a non-empty string",
            }
    if max_lines is not None and (
        not isinstance(max_lines, int) or max_lines < 0
    ):
        return {
            "ok": False, "file": file, "line": line,
            "error": "max_lines: expected non-negative int",
        }
    cap = _TRY_DEFAULT_MAX_LINES if max_lines is None else max_lines
    text, err = _require_position(file, line)
    if err:
        return err
    uri = file_uri(file)
    # Capture pre-state from the UNMODIFIED document. The LSP's reply at
    # (probe_line_0, 0) would otherwise depend on whether the probed
    # tactic closed the proof (e.g. inserting `reflexivity` on a closed-
    # goal row returns an empty pre-state). Querying the unmodified text
    # sidesteps that.
    with client.open_doc(uri, text):
        pre = client.goals(uri, line=line - 1, character=0) or {}
    pre_goals = pre.get("goals", []) or []
    pre_str = _format_goals_compact(pre_goals)
    pre_truncated, pre_dropped = _truncate_lines(pre_str, cap)
    result: dict = {
        "file": file, "line": line, "mode": mode,
        "pre": pre_truncated,
        "attempts": [
            _probe_one(client, uri, text, line, t, mode, pre_goals, cap)
            for t in tactics
        ],
    }
    if pre_dropped:
        result["pre_truncated_lines"] = pre_dropped
    if mode == "replace":
        result["replaced_line"] = _split_lines(text)[line - 1].strip()
    return result
