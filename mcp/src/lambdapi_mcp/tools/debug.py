"""``lambdapi_debug`` — run `lambdapi check --debug=FLAGS`."""
from __future__ import annotations

import os
import re
import subprocess

from ..lsp import LSPClient
from ._common import _check_file


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
        lines = [ln for ln in lines if pat.search(ln)]
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
