"""Shared helpers for the MCP tools: file/line validation, text editing,
diagnostic extraction, goal-state formatting, and comment stripping.
"""
from __future__ import annotations

import os
import re


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _check_file(path: str) -> dict | None:
    """Return a clean error dict if [path] can't be read, else None."""
    if not isinstance(path, str) or not path:
        return {"ok": False, "error": "file: expected non-empty string"}
    if not os.path.isfile(path):
        return {"ok": False, "file": path, "error": "file not found"}
    if not os.access(path, os.R_OK):
        return {"ok": False, "file": path, "error": "file not readable"}
    return None


def _check_line(text: str, line: int) -> dict | None:
    """Return a clean error dict if 1-based [line] is out of [text]'s range."""
    if not isinstance(line, int):
        return {"ok": False, "error": "line: expected int"}
    n = len(_split_lines(text))
    if line < 1 or line > n + 1:
        return {
            "ok": False,
            "error": f"line {line} out of range: file has {n} line(s) "
                     f"(valid: 1..{n + 1})",
        }
    return None


def _require_position(
    file: str, line: int | None = None, character: int | None = None
) -> tuple[str | None, dict | None]:
    """Validate file exists + (optional) line / character arguments.

    Returns ``(text, None)`` on success, or ``(None, error_dict)`` with
    the file/line/character fields filled in for caller convenience."""
    err = _check_file(file)
    if err:
        return None, err
    text = _read(file)
    if line is not None:
        err = _check_line(text, line)
        if err:
            err["file"] = file
            err["line"] = line
            if character is not None:
                err["character"] = character
            return None, err
    if character is not None and (
        not isinstance(character, int) or character < 0
    ):
        return None, {
            "ok": False, "file": file, "line": line,
            "error": f"character {character} must be a non-negative int",
        }
    return text, None


def _split_lines(text: str) -> list[str]:
    return text.split("\n")


def _join_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def _ensure_semicolon(s: str) -> str:
    s = s.rstrip()
    return s if s.endswith(";") else s + ";"


def _insert_at(text: str, line_1based: int, content: str) -> str:
    """Insert [content] as its own line before 1-based [line_1based]."""
    lines = _split_lines(text)
    lines.insert(line_1based - 1, content)
    return _join_lines(lines)


def _replace_line(text: str, line_1based: int, content: str) -> tuple[str, str]:
    """Replace the 1-based [line_1based] with [content].
    Returns (new_text, original_line_stripped)."""
    lines = _split_lines(text)
    original = lines[line_1based - 1]
    lines[line_1based - 1] = content
    return _join_lines(lines), original.strip()


def _errors(diags: list[dict]) -> list[dict]:
    return [d for d in diags if d.get("severity") == 1]


def _format_err(d: dict) -> dict:
    r = d.get("range", {}).get("start", {})
    return {
        "line": r.get("line", 0) + 1,    # 1-based for humans
        "character": r.get("character", 0),
        "message": d.get("message", ""),
    }


def _goal_target(g: dict) -> str:
    """Return the target-line string for a goal. Typ goals have ``type``;
    Unif goals have ``constr`` (a unifier constraint)."""
    return g.get("type") or g.get("constr") or ""


def _format_hyps(hyps: list[dict] | None) -> list[str]:
    out: list[str] = []
    for h in hyps or []:
        name = h.get("hname", "_")
        htype = (h.get("htype", "") or "").lstrip(": ").strip()
        out.append(f"{name} : {htype}")
    return out


def _format_goals_compact(goals: list[dict] | None) -> str:
    """Flush-left single-goal rendering; numbered blocks when >1 goals.

    No header for a single goal (the ``⊢`` line already tells the reader
    what they're looking at). For many goals, an ``N goals:`` line plus
    per-goal ``[i]`` labels."""
    goals = goals or []
    if not goals:
        return "no goals"
    if len(goals) == 1:
        hyps = _format_hyps(goals[0].get("hyps"))
        return _join_lines(hyps + [f"⊢ {_goal_target(goals[0])}"])
    lines: list[str] = [f"{len(goals)} goals:"]
    for i, g in enumerate(goals):
        lines.append(f"[{i}]")
        for h in _format_hyps(g.get("hyps")):
            lines.append(f"  {h}")
        lines.append(f"  ⊢ {_goal_target(g)}")
    return _join_lines(lines)


_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(text: str) -> str:
    """Remove `// …` and `/* … */` comments while preserving newlines
    so line numbers stay aligned."""
    out = _BLOCK_COMMENT_RE.sub(
        lambda m: re.sub(r"[^\n]", " ", m.group(0)), text
    )
    out = _LINE_COMMENT_RE.sub("", out)
    return out
