"""MCP tool implementations.

Each tool is a plain function that takes an ``LSPClient`` and returns
a JSON-serialisable dict. Tools never talk to the LSP server directly —
they compose requests via the client, which keeps the MCP layer a thin
shell over standard LSP.

The one exception is ``tool_debug`` which shells out to ``lambdapi
check --debug=FLAGS`` directly: the LSP doesn't surface unification /
metavariable trace output, only diagnostics. We reuse the client's
``binary`` / ``lib_root`` / ``map_dirs`` config to keep behaviour
consistent across the two paths.
"""

from __future__ import annotations

import os
import re
import subprocess

from .lsp import LSPClient, file_uri


# --- Small helpers ----------------------------------------------------


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


# --- lambdapi_check ---------------------------------------------------


def _check_single(
    client: LSPClient, file: str, all_errors: bool
) -> dict:
    """Type-check one .lp file. Same shape as the single-file
    ``tool_check`` return value — factored out so the batch path can
    reuse it without recursion."""
    text, err = _require_position(file)
    if err:
        return err
    uri = file_uri(file)
    with client.open_doc(uri, text) as session:
        diags = session.diagnostics
    errs = _errors(diags)
    if not errs:
        return {"ok": True, "file": file}
    errs.sort(key=lambda d: (
        d["range"]["start"]["line"], d["range"]["start"]["character"]
    ))
    formatted = [_format_err(d) for d in errs]
    if not all_errors:
        formatted = formatted[:1]
    return {"ok": False, "file": file, "errors": formatted}


def tool_check(
    client: LSPClient,
    file: str | list[str],
    all_errors: bool = False,
    stop_on_first_failure: bool = True,
) -> dict:
    """Type-check one or more .lp files.

    - **Single file** (``file`` is a string): returns
      ``{ok: true, file}`` on success, or
      ``{ok: false, file, errors: [...]}`` on failure. By default only
      the first error is reported (matching the CLI); pass
      ``all_errors=True`` for the full sorted list.
    - **Batch** (``file`` is a list of strings): reuses the persistent
      LSP session to check each file in turn. Returns
      ``{ok, passed, failed, read_errors, summary}`` where ``ok`` is
      true iff every file passed, ``passed`` is a list of
      ``{file}`` entries, ``failed`` is ``{file, errors}`` entries
      (with the same ``all_errors`` knob applied per file),
      ``read_errors`` holds files that couldn't be opened (missing,
      unreadable), and ``summary`` has the four counts. By default we
      short-circuit on the first failing file (matching the CLI's
      behaviour on multiple-file input); pass
      ``stop_on_first_failure=False`` to visit every file regardless.

    Errors within a single file are sorted by (line, character)."""
    if isinstance(file, str):
        return _check_single(client, file, all_errors)
    if not isinstance(file, list) or any(not isinstance(f, str) for f in file):
        return {
            "ok": False,
            "error": "file: expected a string or a list of strings",
        }
    passed: list[dict] = []
    failed: list[dict] = []
    read_errors: list[dict] = []
    for f in file:
        r = _check_single(client, f, all_errors)
        if r.get("ok") is True:
            passed.append({"file": f})
            continue
        # `_require_position` returns a dict with `error` but no
        # `errors` on IO failures; `_check_single` on type-error returns
        # `errors` (list). That's the distinguishing field.
        if "errors" not in r:
            read_errors.append({"file": f, "error": r.get("error", "unknown")})
            continue
        failed.append({"file": f, "errors": r["errors"]})
        if stop_on_first_failure:
            break
    return {
        "ok": not failed and not read_errors,
        "passed": passed,
        "failed": failed,
        "read_errors": read_errors,
        "summary": {
            "total": len(file),
            "passed": len(passed),
            "failed": len(failed),
            "read_errors": len(read_errors),
        },
    }


# --- lambdapi_goals ---------------------------------------------------


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


# --- lambdapi_query ---------------------------------------------------


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


# --- lambdapi_try -----------------------------------------------------


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


# --- lambdapi_symbols -------------------------------------------------


_DECL_RE = re.compile(
    r"^\s*"
    # zero or more modifiers (in any order) before `symbol` / `inductive`
    r"(?:(?:opaque|private|protected|sequential|injective|constant)\s+)*"
    r"(?:symbol|inductive)\s+"
    # symbol name: anything up to whitespace or `:` or `[`
    r"([^\s:\[]+)"
)

# A `with NAME : …` line introducing another member of a mutual inductive
# block. Only recognised AFTER we've seen an `inductive …` earlier in the
# file; scoping is enforced in `_local_decl_names`.
_WITH_TYPE_RE = re.compile(r"^\s*with\s+([^\s:\[]+)")

# A constructor line inside an `inductive` block: `  | NAME : …`.
_CTOR_RE = re.compile(r"^\s*\|\s*([^\s:\[\(]+)")


def _local_decl_names(text: str) -> set[str]:
    """Parse [text] line-by-line for locally-declared symbol names.

    Recognises:
    - ``symbol NAME`` / ``constant symbol NAME`` / ``opaque symbol NAME``
    - ``inductive NAME`` and, for mutual inductives, ``with NAME``
    - each inductive's auto-generated induction principle ``ind_NAME``
    - each constructor ``| cname`` inside an inductive block
    Used to filter documentSymbol output, since the upstream lambdapi
    LSP leaks transitively-imported symbols into the reply.
    """
    names: set[str] = set()
    in_inductive = False
    for line in _split_lines(text):
        m = _DECL_RE.match(line)
        if m:
            name = m.group(1)
            names.add(name)
            if re.match(r"^\s*(?:(?:private|protected|sequential|injective"
                        r"|constant|opaque)\s+)*inductive\b", line):
                names.add(f"ind_{name}")
                in_inductive = True
            else:
                in_inductive = False
            continue
        if in_inductive:
            wm = _WITH_TYPE_RE.match(line)
            if wm:
                names.add(wm.group(1))
                names.add(f"ind_{wm.group(1)}")
                continue
            cm = _CTOR_RE.match(line)
            if cm:
                names.add(cm.group(1))
                continue
    return names


def tool_symbols(client: LSPClient, file: str) -> dict:
    """List the symbols declared in [file] via textDocument/documentSymbol.

    The upstream lambdapi LSP replies with transitively-imported symbols
    attributed to the queried URI. We cross-check each reported symbol's
    name against a local declaration parse of [file] and drop anything
    that isn't actually declared in this file."""
    text, err = _require_position(file)
    if err:
        return err
    uri = file_uri(file)
    local_names = _local_decl_names(text)
    with client.open_doc(uri, text):
        result = client.document_symbol(uri) or []
    symbols = []
    for s in result:
        name = s.get("name", "")
        if name not in local_names:
            continue
        rng = s.get("location", {}).get("range", {}).get("start", {})
        symbols.append({
            "name": name,
            "kind": s.get("kind"),
            "line": rng.get("line", 0) + 1,
            "character": rng.get("character", 0),
        })
    return {"file": file, "symbols": symbols}


# --- lambdapi_axioms --------------------------------------------------


# Parser-like regexes for shape classification. Run line-by-line; good
# enough for the common cases (axioms + postulates + admits).
# Binders look like `[x y : τ a]` or `(x : τ a)`; zero or more may sit
# between the symbol name and its `:` type annotation.
_BINDERS = r"(?:\s*\[[^\]]*\]|\s*\([^)]*\))*"

# Any ``symbol`` / ``constant symbol`` declaration, captured on one line.
# Groups: 1=constant?, 2=name, 3=type (up to `;` / EOL, excluding any body).
_SYMBOL_DECL_RE = re.compile(
    r"^\s*(?:private\s+|protected\s+|sequential\s+|injective\s+|opaque\s+)*"
    r"(constant\s+)?symbol\s+([^\s:\[\(]+)" + _BINDERS +
    r"\s*:\s*(.+?)\s*;?\s*$",
)
# `admit` is a tactic inside `begin…end`. The trailing `;` is optional
# (the outer `end;` terminates the statement), and `admit` can appear
# inline inside a `{ … }` subgoal block. Match the bare word anywhere on
# a line; the ``\b`` boundary keeps us from matching the unrelated
# `admitted` end-of-proof keyword.
_ADMIT_RE = re.compile(r"\badmit\b")

_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_REQUIRE_RE = re.compile(
    r"\brequire\b(?:\s+open\b)?\s+(.+?);",
    re.DOTALL,
)
_MODULE_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


def _read_pkg(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition("=")
                    out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def _discover_pkg_roots(
    lib_root: str | None,
    map_dirs: list[str],
    anchor_files: list[str] | None = None,
) -> dict[str, str]:
    """Return ``{root_path_name: directory}`` for every known Lambdapi
    package.

    Sources, in priority order:

    1. ``map_dirs`` (explicit ``Name:/abs/path`` pairs).
    2. ``lambdapi.pkg`` discovered by walking *upward* from each
       ``anchor_files`` entry — this is how we pick up a project's own
       package when the user hasn't pointed ``lib_root`` at it.
    3. ``lambdapi.pkg`` discovered by walking *downward* under
       ``lib_root`` (typically the opam-installed Stdlib tree)."""
    roots: dict[str, str] = {}
    for md in map_dirs or []:
        if ":" in md:
            name, path = md.split(":", 1)
            if os.path.isdir(path):
                roots.setdefault(name, path)
    for anchor in anchor_files or []:
        d = os.path.dirname(os.path.abspath(anchor))
        prev: str | None = None
        while d and d != prev:
            pkg_path = os.path.join(d, "lambdapi.pkg")
            if os.path.isfile(pkg_path):
                pkg = _read_pkg(pkg_path)
                rp = pkg.get("root_path")
                if rp:
                    roots.setdefault(rp, d)
            prev = d
            d = os.path.dirname(d)
    if lib_root and os.path.isdir(lib_root):
        for dirpath, _dirnames, filenames in os.walk(lib_root):
            if "lambdapi.pkg" in filenames:
                pkg = _read_pkg(os.path.join(dirpath, "lambdapi.pkg"))
                rp = pkg.get("root_path")
                if rp:
                    roots.setdefault(rp, dirpath)
    return roots


def _installed_dirs(
    lib_root: str | None,
    map_dirs: list[str],
    anchor_files: list[str] | None = None,
) -> set[str]:
    """Absolute directories that represent *installed* library roots,
    for the purpose of excluding them under ``scope='project'``.

    A directory is installed iff it's either:
    - an explicit ``map_dir`` target (``--stdlib …`` / ``--map-dir …``), or
    - a ``lambdapi.pkg`` directory found by walking **downward** from
      ``lib_root`` that is NOT also reachable by walking **upward** from
      ``anchor_files``.

    The upward-exclusion matters in tests (and any setup where the user
    points ``lib_root`` at their project root): the same directory
    shows up in both sources, and the upward hit wins — it's the user's
    project, not an installed library."""
    from_map: set[str] = set()
    for md in map_dirs or []:
        if ":" in md:
            _, path = md.split(":", 1)
            if os.path.isdir(path):
                from_map.add(os.path.abspath(path))
    from_upward: set[str] = set()
    for anchor in anchor_files or []:
        d = os.path.dirname(os.path.abspath(anchor))
        prev: str | None = None
        while d and d != prev:
            if os.path.isfile(os.path.join(d, "lambdapi.pkg")):
                from_upward.add(d)
            prev = d
            d = os.path.dirname(d)
    from_libroot: set[str] = set()
    if lib_root and os.path.isdir(lib_root):
        for dirpath, _dirnames, filenames in os.walk(lib_root):
            if "lambdapi.pkg" in filenames:
                from_libroot.add(os.path.abspath(dirpath))
    return from_map | (from_libroot - from_upward)


def _resolve_module(module: str, roots: dict[str, str]) -> str | None:
    """Resolve ``Stdlib.Nat`` → ``/.../Stdlib/Nat.lp``."""
    parts = module.split(".")
    if not parts:
        return None
    prefix = parts[0]
    root_dir = roots.get(prefix)
    if root_dir is None:
        return None
    rel = os.path.join(*parts[1:]) + ".lp" if len(parts) > 1 else prefix + ".lp"
    path = os.path.join(root_dir, rel)
    return path if os.path.isfile(path) else None


def _parse_requires(text: str) -> list[str]:
    """Return the module names mentioned in any ``require ... ;`` block."""
    stripped = _LINE_COMMENT_RE.sub("", text)
    stripped = _BLOCK_COMMENT_RE.sub("", stripped)
    modules: list[str] = []
    for m in _REQUIRE_RE.finditer(stripped):
        for tok in _MODULE_TOKEN_RE.findall(m.group(1)):
            modules.append(tok)
    return modules


def _strip_comments(text: str) -> str:
    """Remove `// …` and `/* … */` comments while preserving newlines
    so line numbers stay aligned."""
    out = _BLOCK_COMMENT_RE.sub(
        lambda m: re.sub(r"[^\n]", " ", m.group(0)), text
    )
    out = _LINE_COMMENT_RE.sub("", out)
    return out


def _split_statements(text: str) -> list[tuple[int, str]]:
    """Split [text] (with comments already stripped) into statements
    terminated by a top-level ``;``. Returns (start_line_1based, body)
    pairs with the original line of each statement's first character."""
    stmts: list[tuple[int, str]] = []
    buf: list[str] = []
    depth = 0
    line = 1
    stmt_start: int | None = None
    for ch in text:
        if ch not in " \t\n" and stmt_start is None:
            stmt_start = line
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == ";" and depth == 0:
            body = "".join(buf).strip()
            if body and stmt_start is not None:
                stmts.append((stmt_start, body))
            buf.clear()
            stmt_start = None
        else:
            buf.append(ch)
        if ch == "\n":
            line += 1
    # Any unterminated tail is ignored (malformed file).
    return stmts


_RULE_STMT_RE = re.compile(r"^\s*rule\b(.+)$", re.DOTALL)
_RULE_HEAD_RE = re.compile(r"^\s*([^\s\(\[]+)")


def _is_propositional(type_str: str) -> bool:
    """A type is propositional iff it eventually applies ``π`` to a Prop
    (i.e. ``π …`` somewhere at the top level after quantifiers). We
    approximate: a leading token ``π`` or ``Π …, π`` counts."""
    if type_str.lstrip().startswith("π"):
        return True
    return bool(re.search(r"(?:^|\s|,)π[\s(]", type_str))


def _parse_rewrite_rules(body: str) -> list[tuple[str, str, str]]:
    """Split a `rule …[with …]*` body into ``(head, lhs, rhs)`` triples.

    ``head`` is the leftmost identifier on the LHS — the symbol this
    rule reduces. ``lhs`` and ``rhs`` are the raw text on either side
    of ``↪``."""
    out: list[tuple[str, str, str]] = []
    # Statements are split at top-level `;`, so we never see `with` from
    # outside a rule here. Splitting on word-boundary `with` is safe.
    subs = re.split(r"\bwith\b", body)
    for sub in subs:
        if "↪" not in sub:
            continue
        lhs, _, rhs = sub.partition("↪")
        lhs = lhs.strip()
        rhs = rhs.strip()
        m = _RULE_HEAD_RE.match(lhs)
        head = m.group(1) if m else ""
        out.append((head, lhs, rhs))
    return out


def _scan_assumptions(
    f: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify declarations in a single file.

    Returns ``(assumptions, rewrite_rules, admits)``."""
    assumptions: list[dict] = []
    rewrite_rules: list[dict] = []
    admits: list[dict] = []
    raw = _read(f)
    text = _strip_comments(raw)
    for start_line, stmt in _split_statements(text):
        m = _RULE_STMT_RE.match(stmt)
        if m:
            for head, lhs, rhs in _parse_rewrite_rules(m.group(1)):
                rewrite_rules.append({
                    "file": f,
                    "line": start_line,
                    "symbol": head,
                    "lhs": " ".join(lhs.split()),
                    "rhs": " ".join(rhs.split()),
                })
            continue
        if "≔" in stmt or ":=" in stmt:
            continue  # has a definition body → not an assumption
        single = " ".join(stmt.split())
        dm = _SYMBOL_DECL_RE.match(single)
        if not dm:
            continue
        is_constant = bool(dm.group(1))
        name = dm.group(2)
        type_str = dm.group(3).strip()
        assumptions.append({
            "file": f,
            "line": start_line,
            "name": name,
            "type": type_str,
            "propositional": _is_propositional(type_str),
            "constant": is_constant,
        })
    # Scan the comment-stripped text so a commented-out `admit` isn't
    # counted. `_strip_comments` preserves newlines, so line numbers
    # still align with the raw source.
    for i, line in enumerate(_split_lines(text), 1):
        if _ADMIT_RE.search(line):
            admits.append({"file": f, "line": i})
    return assumptions, rewrite_rules, admits


_AXIOMS_SCOPES = ("file", "project", "all")


def tool_axioms(
    client: LSPClient, files: list[str], scope: str = "project"
) -> dict:
    """Scan [files] for unproved assumptions.

    ``scope`` controls how much is scanned:

    - ``"file"``: only the files passed in; ``require`` is not followed.
    - ``"project"`` (default): follow ``require`` transitively, but skip
      anything under the configured ``lib_root`` (the opam Stdlib tree).
      This is usually what agents want — the project's own axioms, not
      a re-dump of ``Set``/``Prop``/``eq_refl``/… every scan.
    - ``"all"``: full transitive scan, including Stdlib.

    Four buckets come back:

    - **assumptions**: any ``symbol`` / ``constant symbol`` declared
      without a ``≔`` body AND without any rewrite rule in scope keyed
      on it (a pure postulate).
    - **defined_by_rules**: data-typed (non-propositional) symbols that
      *are* the head of at least one rewrite rule in scope — i.e.
      recursive function definitions like ``+``, ``*``, ``!``. These
      behave like assumptions to the kernel but aren't propositional
      axioms; split out so the "no new axioms" contract is easy to
      check.
    - **rewrite_rules**: every ``rule LHS ↪ RHS;`` (including each
      sub-rule in a ``rule … with … with …;`` block).
    - **admits**: every ``admit`` tactic inside a proof (a hole) —
      trailing ``;`` optional; ``{ admit }`` inline forms are also
      counted. Does not match the unrelated ``admitted`` end-of-proof
      keyword.

    Also returns ``scanned_files`` (everything visited) and
    ``unresolved_imports`` (deduped: ``{module, imported_by: [...]}``).
    """
    if scope not in _AXIOMS_SCOPES:
        return {
            "ok": False,
            "error": f"scope: expected one of {list(_AXIOMS_SCOPES)}, "
                     f"got {scope!r}",
        }
    if not isinstance(files, list) or any(
        not isinstance(f, str) for f in files
    ):
        return {
            "ok": False,
            "error": "files: expected a list of file-path strings",
        }

    lib_root = getattr(client, "lib_root", None)
    map_dirs = getattr(client, "map_dirs", []) or []
    anchors = [f for f in files if isinstance(f, str)]
    installed_dirs = _installed_dirs(lib_root, map_dirs, anchors)

    def _is_installed(path: str) -> bool:
        p = os.path.abspath(path)
        return any(
            p == d or p.startswith(d + os.sep) for d in installed_dirs
        )

    roots = _discover_pkg_roots(lib_root, map_dirs, anchor_files=anchors)

    assumptions: list[dict] = []
    rewrite_rules: list[dict] = []
    admits: list[dict] = []
    read_errors: list[dict] = []
    unresolved: dict[str, list[str]] = {}

    scanned: set[str] = set()
    scan_order: list[str] = []
    frontier: list[tuple[str, str | None]] = []
    for f in files:
        err = _check_file(f)
        if err:
            read_errors.append(err)
            continue
        frontier.append((os.path.abspath(f), None))

    while frontier:
        path, imported_by = frontier.pop(0)
        if path in scanned:
            continue
        if not os.path.isfile(path):
            read_errors.append({
                "ok": False, "file": path, "error": "file not found",
                "imported_by": imported_by,
            })
            continue
        # In project scope, Stdlib files are resolved but not walked.
        if scope == "project" and imported_by is not None and _is_installed(path):
            scanned.add(path)
            continue
        scanned.add(path)
        scan_order.append(path)
        a, rr, ad = _scan_assumptions(path)
        assumptions.extend(a)
        rewrite_rules.extend(rr)
        admits.extend(ad)
        # No recursion in file scope — each input file is scanned once,
        # its requires are ignored.
        if scope == "file":
            continue
        text = _read(path)
        for mod in _parse_requires(text):
            resolved = _resolve_module(mod, roots)
            if resolved is None:
                unresolved.setdefault(mod, [])
                if path not in unresolved[mod]:
                    unresolved[mod].append(path)
                continue
            resolved_abs = os.path.abspath(resolved)
            if resolved_abs not in scanned:
                frontier.append((resolved_abs, path))

    rule_heads = {
        rr["symbol"] for rr in rewrite_rules if rr.get("symbol")
    }
    defined_by_rules: list[dict] = []
    pure_assumptions: list[dict] = []
    for a in assumptions:
        if a["name"] in rule_heads and not a.get("propositional"):
            defined_by_rules.append(a)
        else:
            pure_assumptions.append(a)

    result = {
        "files": files,
        "scope": scope,
        "scanned_files": scan_order,
        "assumptions": pure_assumptions,
        "defined_by_rules": defined_by_rules,
        "rewrite_rules": rewrite_rules,
        "admits": admits,
    }
    if read_errors:
        result["read_errors"] = read_errors
    if unresolved:
        result["unresolved_imports"] = [
            {"module": mod, "imported_by": sorted(set(by))}
            for mod, by in sorted(unresolved.items())
        ]
    return result


# --- lambdapi_proofterm -----------------------------------------------


def tool_proofterm(client: LSPClient, file: str, line: int) -> dict:
    """Show the partial proof term at 1-based [line] inside a `begin…end`
    block. Inserts `proofterm;` as a one-shot probe (the file on disk
    is not modified) and captures the resulting term.

    Useful for diagnosing higher-order unification failures: the term
    shows where in the partial proof the metavariables live, which
    often reveals scope / binder issues that ``lambdapi_try`` only
    surfaces as `?XXX ≡ y` constraints.

    Returns ``{file, line, term, raw_lines?}``. ``term`` is the printed
    partial term (e.g. ``λ P0 Q0 hP0 hQ0, ?6``); ``raw_lines`` includes
    everything Lambdapi printed in case the term was wrapped over
    multiple lines."""
    text, err = _require_position(file, line)
    if err:
        return err
    probe = "proofterm;"
    modified = _insert_at(text, line, probe)
    uri = file_uri(file)
    probe_line_0 = line - 1
    with client.open_doc(uri, modified) as session:
        pass
    diags = session.diagnostics
    errs_at_probe = [
        d for d in _errors(diags)
        if d["range"]["start"]["line"] == probe_line_0
    ]
    if errs_at_probe:
        return {
            "ok": False, "file": file, "line": line,
            "error": errs_at_probe[0]["message"],
        }
    # `proofterm` output arrives as a severity=4 (info / OK-hint)
    # diagnostic attached to the probe line — same channel as
    # `compute` / `print` queries. Pick those.
    hints = [
        d["message"] for d in diags
        if d.get("severity") == 4
        and d["range"]["start"]["line"] == probe_line_0
    ]
    candidates = [h for h in hints if h.strip()]
    term = candidates[-1] if candidates else ""
    out: dict = {"ok": True, "file": file, "line": line, "term": term}
    if len(candidates) > 1:
        out["raw_lines"] = candidates
    return out


# --- lambdapi_debug ---------------------------------------------------


_DEBUG_FLAGS_RE = re.compile(r"^[acdegiklmnopqrstuvwxyz]+$")
_VALID_DEBUG_FLAGS = "acdegiklmnopqrstuvwxyz"


def _run_check_debug(
    client: LSPClient,
    file: str,
    flags: str,
    timeout: float,
) -> tuple[int, str]:
    """Spawn ``lambdapi check --debug=FLAGS`` and return (exit_code, output).
    Combines stdout + stderr — debug traces go to stderr but errors go
    to stdout, and a one-stream view is what callers want."""
    cmd: list[str] = [client.binary, "check", "--debug=" + flags]
    if client.lib_root:
        cmd += ["--lib-root", client.lib_root]
    for md in client.map_dirs:
        cmd += ["--map-dir", md]
    cmd.append(file)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        partial = ""
        if e.stdout:
            partial += e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", "replace")
        if e.stderr:
            partial += e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", "replace")
        return -1, partial + f"\n[debug timed out after {timeout}s]"


def tool_debug(
    client: LSPClient,
    file: str,
    flags: str,
    pattern: str | None = None,
    tail: int | None = None,
    head: int | None = None,
    save_to: str | None = None,
    timeout: float = 60.0,
) -> dict:
    """Run ``lambdapi check --debug=FLAGS`` on [file] and return filtered
    output. Use this when LSP diagnostics aren't enough — typically for
    HOU / metavariable / unification debugging where you need to see
    the solver's actual steps.

    [flags] is a string of debug-flag characters (see lambdapi --help):
    a (metavars), c (conversion), d (decision trees), e (snf), i
    (inference), k (local confluence), m (term building), n (parsing),
    o (scoping), p (pretty), q (rewriting), r (rewrite tactic), s
    (subject reduction), t (tactics), u (unification), w (whnf), …
    Most useful for proof-debugging: ``u`` (unification), ``a``
    (metavariables), ``t`` (tactics), or combinations like ``"iut"``.

    Output management (debug traces are large — multi-MB on big proofs):
    - [pattern] (regex): keep only lines matching this pattern.
    - [head]: keep only the first N lines after filtering.
    - [tail]: keep only the last N lines after filtering.
    - [save_to]: write the FULL unfiltered output to this path (so the
      caller can re-grep without re-running). Returned as ``log_file``.

    Defaults: no filter, no truncation, no save. The caller controls.
    Returns ``{ok, file, exit_code, total_lines, returned_lines,
    debug_log, log_file?}``.
    """
    err = _check_file(file)
    if err:
        return err
    if not isinstance(flags, str) or not flags:
        return {
            "ok": False, "file": file,
            "error": "flags: expected a non-empty string of debug chars",
        }
    if not _DEBUG_FLAGS_RE.match(flags):
        return {
            "ok": False, "file": file,
            "error": (
                f"flags: contains invalid debug chars; allowed = "
                f"{_VALID_DEBUG_FLAGS!r}, got {flags!r}"
            ),
        }
    if pattern is not None:
        try:
            pat = re.compile(pattern)
        except re.error as e:
            return {
                "ok": False, "file": file,
                "error": f"pattern: invalid regex: {e}",
            }
    else:
        pat = None
    if head is not None and (not isinstance(head, int) or head < 0):
        return {"ok": False, "file": file, "error": "head: expected non-negative int"}
    if tail is not None and (not isinstance(tail, int) or tail < 0):
        return {"ok": False, "file": file, "error": "tail: expected non-negative int"}

    rc, output = _run_check_debug(client, file, flags, timeout)

    if save_to:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(save_to)) or ".", exist_ok=True)
            with open(save_to, "w", encoding="utf-8") as f:
                f.write(output)
        except OSError as e:
            return {
                "ok": False, "file": file,
                "error": f"save_to: {e}",
                "exit_code": rc,
            }

    raw_lines = output.split("\n")
    total = len(raw_lines)
    lines = raw_lines
    if pat is not None:
        lines = [l for l in lines if pat.search(l)]
    matched = len(lines)
    if head is not None:
        lines = lines[:head]
    if tail is not None:
        lines = lines[-tail:]

    out: dict = {
        "ok": rc == 0,
        "file": file,
        "exit_code": rc,
        "total_lines": total,
        "matched_lines": matched,
        "returned_lines": len(lines),
        "debug_log": "\n".join(lines),
    }
    if save_to:
        out["log_file"] = save_to
    return out
