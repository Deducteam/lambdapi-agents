"""MCP server: tool registration + lifecycle.

Each MCP tool maps to a function in ``tools.py`` and is registered with
FastMCP. The server holds a single ``LSPClient`` for the session so that
subsequent tool calls reuse the already-checked state where possible.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from . import tools as T
from .lsp import LSPClient, default_lib_root


def resolve_map_dirs(stdlib: str | None) -> list[str]:
    """Map-dirs to pass to `lambdapi lsp`.

    Only honors an explicit `--stdlib=DIR` override. We deliberately don't
    auto-inject a `Stdlib:…` mapping: when Stdlib already lives under
    `lib_root` (the opam default), an extra mapping duplicates the
    package registration and crashes `lambdapi lsp` with "Root state is
    missing". Users who keep Stdlib elsewhere pass `--stdlib=DIR`.
    """
    if stdlib and os.path.isdir(stdlib):
        return [f"Stdlib:{stdlib}"]
    return []


def build_server(
    lib_root: str | None = None,
    stdlib: str | None = None,
    binary: str | None = None,
    log_file: str | None = None,
) -> FastMCP:
    lib_root = lib_root or default_lib_root()
    map_dirs = resolve_map_dirs(stdlib)

    lsp = LSPClient(
        lib_root=lib_root,
        map_dirs=map_dirs,
        binary=binary,
        log_file=log_file,
    )
    lsp.start()

    mcp = FastMCP("lambdapi-mcp")

    @mcp.tool(
        description=(
            "Type-check one or more Lambdapi (.lp) files. Pass a single "
            "string for one file (returns ok=true or ok=false with "
            "errors=[{line,character,message}]) or a list of strings "
            "for batch-checking against the same LSP session (returns "
            "{ok, passed, failed, read_errors, summary}). By default "
            "only the first error per file is returned (matching the "
            "CLI); pass all_errors=true for the full sorted list. In "
            "batch mode we short-circuit on the first failing file by "
            "default (also matching the CLI on multi-file input); pass "
            "stop_on_first_failure=false to visit every file."
        )
    )
    def lambdapi_check(
        file: str | list[str],
        all_errors: bool = False,
        stop_on_first_failure: bool = True,
    ) -> dict:
        return T.tool_check(
            lsp, file,
            all_errors=all_errors,
            stop_on_first_failure=stop_on_first_failure,
        )

    @mcp.tool(
        description=(
            "Return the proof state at 1-based [line] as a compact "
            "flush-left rendering: one hypothesis per line, then a "
            "`⊢ target` line. When there are multiple goals each is "
            "labelled `[i]` and indented. Returns `no goals` if the "
            "state is empty."
        )
    )
    def lambdapi_goals(file: str, line: int) -> dict:
        return T.tool_goals(lsp, file, line)

    @mcp.tool(
        description=(
            "Run a Lambdapi query (compute/type/print/search) at a "
            "1-based line. Use `type X` to see a symbol's type; "
            "`print X` to see its declaration and definition (which "
            "subsumes hover + go-to-definition). [line] is a lower "
            "bound: the query is inserted at the first top-level "
            "statement boundary at or after [line], so lines inside a "
            "begin…end block (or past EOF) snap forward automatically. "
            "The response includes `effective_line` whenever the snap "
            "moved the insertion point. Output is the query's "
            "response text."
        )
    )
    def lambdapi_query(file: str, line: int, query: str) -> dict:
        return T.tool_query(lsp, file, line, query)

    @mcp.tool(
        description=(
            "Probe one or more tactics at [line] without modifying the "
            "file on disk. `tactics` is a list of strings. "
            "mode='insert' (default) inserts each tactic before [line]; "
            "mode='replace' overwrites [line]. "
            "Returns `pre` (the goal state shared by all attempts) and "
            "`attempts`: one entry per tactic with `ok` (no error "
            "diagnostic), `closed` (tactic finished the obligation), "
            "`progress` (goal state changed), and `post` (remaining "
            "goal state, included only when progress && !closed). "
            "Both `error` and `post` are truncated to `max_lines` "
            "(default 12) to keep multi-tactic probes readable; pass "
            "max_lines=0 for no truncation."
        )
    )
    def lambdapi_try(
        file: str,
        line: int,
        tactics: list[str],
        mode: str = "insert",
        max_lines: int | None = None,
    ) -> dict:
        return T.tool_try(
            lsp, file, line, tactics, mode=mode, max_lines=max_lines
        )

    @mcp.tool(
        description=(
            "List the top-level symbols declared in a file (via LSP "
            "documentSymbol, filtered to only locally-declared names)."
        )
    )
    def lambdapi_symbols(file: str) -> dict:
        return T.tool_symbols(lsp, file)

    @mcp.tool(
        description=(
            "Scan [files] for unproved assumptions, rewrite rules, and "
            "admits. `scope` controls recursion: 'file' = just the "
            "inputs, 'project' (default) = follow `require` but skip "
            "files under lib_root (Stdlib), 'all' = full transitive "
            "scan including Stdlib. Returns assumptions, "
            "defined_by_rules, rewrite_rules, admits, scanned_files, "
            "and deduplicated unresolved_imports."
        )
    )
    def lambdapi_axioms(
        files: list[str], scope: str = "project"
    ) -> dict:
        return T.tool_axioms(lsp, files, scope=scope)

    @mcp.tool(
        description=(
            "Show the partial proof term at 1-based [line] inside a "
            "begin…end block. Inserts `proofterm;` as a one-shot probe "
            "without touching the file on disk. Returns "
            "`{ok, file, line, term, raw_lines?}` where `term` is the "
            "printed partial term — useful for HOU debugging where you "
            "need to see where the metavariables live in the term."
        )
    )
    def lambdapi_proofterm(file: str, line: int) -> dict:
        return T.tool_proofterm(lsp, file, line)

    @mcp.tool(
        description=(
            "Run `lambdapi check --debug=FLAGS` and return filtered "
            "trace output. Use this when LSP diagnostics aren't enough — "
            "typically for HOU / metavariable / unification debugging "
            "(`flags='u'` for unification, `'a'` for metavariables, "
            "`'t'` for tactics, or combinations like `'iut'`). Trace "
            "output can be very large (multi-MB on big proofs); manage "
            "via `pattern` (regex line filter), `head` / `tail` (line "
            "caps), and `save_to` (write full log to a file so you can "
            "re-grep without re-running). Returns `{ok, exit_code, "
            "total_lines, matched_lines, returned_lines, debug_log, "
            "log_file?}`."
        )
    )
    def lambdapi_debug(
        file: str,
        flags: str,
        pattern: str | None = None,
        tail: int | None = None,
        head: int | None = None,
        save_to: str | None = None,
        timeout: float = 60.0,
    ) -> dict:
        return T.tool_debug(
            lsp, file, flags,
            pattern=pattern, tail=tail, head=head,
            save_to=save_to, timeout=timeout,
        )

    # Attach the LSP handle for tests / introspection.
    mcp._lsp_client = lsp  # type: ignore[attr-defined]
    return mcp
