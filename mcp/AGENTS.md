# lambdapi-mcp

MCP server exposing Lambdapi proof-assistant capabilities to AI agents. Layers on top of `lambdapi lsp`; source in `src/lambdapi_mcp/`, pytest suite in `tests/` with fixtures in `tests/fixtures/`.

## Architecture

- `lsp.py` — JSON-RPC client for `lambdapi lsp`. Handles framing, request/reply routing, diagnostics. Auto-restarts the subprocess on `BrokenPipeError` / death; `restart_count` is observable.
- `tools/` — one module per tool (`check`, `goals`, `query`, `try_`, `symbols`, `axioms`, `proofterm`, `debug`) plus `_common.py` for shared helpers (file/line validation, text editing, diagnostic + goal-state formatting, comment stripping). Each tool is a pure function taking an `LSPClient` and returning a JSON-serialisable dict; it validates its inputs (`_check_file`, `_check_line`) and returns `{ok: false, error: ...}` on bad input rather than leaking Python exceptions. `tools/__init__.py` re-exports the flat surface (`tools.tool_check`, …).
- `server.py` — `FastMCP` glue; registers one MCP tool per `tool_*` function and holds a single long-lived `LSPClient` per session.
- `__main__.py` — CLI (`lambdapi-mcp`) with `--lib-root`, `--stdlib`, `--binary`, `--log-file`.

## Tools (8)

`lambdapi_check`, `lambdapi_goals`, `lambdapi_query`, `lambdapi_symbols`, `lambdapi_try`, `lambdapi_axioms`, `lambdapi_proofterm`, `lambdapi_debug`.

Hover / go-to-definition / completions are subsumed by `lambdapi_query` (`print X` shows a symbol's declaration + body). Multi-tactic probing is built into `lambdapi_try` (takes a list).

Notable semantics worth remembering:

- **`lambdapi_check`**: returns the first error by default (matches the CLI). Pass `all_errors=true` for the full sorted list. Errors get a `hint` when the message smells like a spacing problem or a `rewrite` "No subterm matches" failure.
- **`lambdapi_try`**: probes in-memory only (file on disk is never touched). Takes `tactics: list[str]` and `mode` ∈ {`insert`, `replace`}. Returns one shared `pre` goal-state plus `attempts[i] = {ok, closed, progress, post?}`. `ok` means no error diagnostic on the probe line; `closed` means `pre` had ≥1 goal and `post` has 0 (the obligation finished); `progress` means the goal state actually changed (compared gid-free). `ok` alone does NOT mean the tactic did anything useful.
- **`lambdapi_symbols`**: the upstream LSP leaks transitively-imported symbols with the queried URI and original-file line numbers. We filter against a local declaration parse of the file — only symbols that actually appear as `symbol NAME` / `inductive NAME` / etc. in the input file are returned.
- **`lambdapi_axioms`**: takes `scope` ∈ {`file`, `project` (default), `all`}. `file` = just the inputs. `project` = follow `require` but skip files under `lib_root` (Stdlib). `all` = full transitive scan including Stdlib. Returns `assumptions` (any `symbol` without `≔` body, flagged `propositional` iff type is `π …`), `defined_by_rules` (bodyless symbols later given rewrite rules — fine), `rewrite_rules` (every `rule LHS ↪ RHS` including sub-rules of `with`-chained blocks), `admits`, `scanned_files`, and deduplicated `unresolved_imports`. Statement-level scan (splits on top-level `;`) so multi-line declarations with bodies on later lines are correctly recognised as definitions, not assumptions.
- **Stdlib resolution**: the server does NOT auto-inject a `Stdlib:…` map-dir. A file's own `lambdapi.pkg` under `--lib-root` resolves `Stdlib.*` imports. Only pass `--stdlib=DIR` when your Stdlib source lives outside lib-root — a duplicate mapping crashes `lambdapi lsp` with "Root state is missing".

## Corpora

The exercise corpora moved up to the monorepo's benchmarking arena at
[`../arena/corpora/`](../arena/corpora). Each subdirectory is its own package
(`lambdapi.pkg` at the root):

- `../arena/corpora/fermat/` — elementary number theory: `Binom.lp`, `Divides.lp`, `Euclid.lp`, `Fermat.lp`, `Mod.lp`, `Prime.lp`.
- `../arena/corpora/lambda/` — untyped λ-calculus metatheory: `Term.lp`, `Beta.lp`, `Parallel.lp`.
- **Stdlib** lives under the opam lib-root (`$OPAM_SWITCH_PREFIX/lib/lambdapi/lib_root/Stdlib/`). A file's own `lambdapi.pkg` resolves `Stdlib.*` imports with no extra config.
- The `lambdapi` binary is at `$OPAM_SWITCH_PREFIX/bin/lambdapi`. `.lpo` files next to `.lp` are derived caches — safe to `rm` when lambdapi versions skew.

Use `../arena/corpora/` when exercising the MCP tools manually. The `tests/fixtures/` dir is for the pytest suite — don't expand it for ad-hoc tool exploration.

## Running

- Tests: `source .venv/bin/activate && python -m pytest tests/ -v`.
- Python 3.13 venv at `.venv/`; deps managed via `pyproject.toml` (mcp>=1.0.0, pytest>=8.0 as dev).
- The crash-recovery test (`tests/test_crash_recovery.py`) SIGKILLs the underlying `lambdapi lsp` subprocess — harmless, but expect a brief zombie reap.
