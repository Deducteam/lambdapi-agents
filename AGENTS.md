# lambdapi-agents

AI-agent tooling for the [Lambdapi](https://github.com/Deducteam/lambdapi)
proof assistant. A monorepo of an MCP server, an agent skill, an edit-time check
hook, and a benchmarking arena, plus a thin Claude Code plugin layer — work in
the component that matches your task and read its own guide first.

## Layout

- `mcp/` — standalone Python MCP server over `lambdapi lsp`. Own
  `pyproject.toml` and pytest suite; PyPI-publishable and usable by any MCP
  client. Component guide: [`mcp/AGENTS.md`](mcp/AGENTS.md).
- `skills/lambdapi/` — the agent skill: canonical `SKILL.md` (CLI-driven; it
  does not reference the MCP tools) plus `references/` mirroring the upstream
  manual for progressive disclosure.
- `hooks/` — a `PostToolUse` hook (`lp_check.py`) that type-checks a `.lp` file
  on every `Write`/`Edit` and returns the diagnostics plus the proof state at the
  failure point to the agent. Read-only: it writes no `.lpo`. Guide:
  [`hooks/README.md`](hooks/README.md).
- `arena/` — benchmarking. `corpora/` holds self-contained `.lp` packages; the
  evaluation harness is WIP. Guide: [`arena/README.md`](arena/README.md).
- `.claude-plugin/` — `plugin.json` + `marketplace.json`: the thin glue that
  ships the `skills/`, `mcp/`, and `hooks/` pieces together as one installable
  Claude Code plugin (`hooks/hooks.json` is auto-merged when it's enabled).
  `.mcp.json` at the root auto-wires the server for Claude Code used inside this
  repo.
- `docs/` — project notes.

## Conventions

- There is **one** canonical skill (`skills/lambdapi/`). The skill-on/off and
  MCP-vs-CLI distinctions are *benchmark axes* owned by `arena/`, not separate
  skills — don't fork the skill to represent a configuration.
- `mcp/` targets Python 3.10+ and pins `mcp<2` (the SDK 2.0 rename). Run its
  tests from `mcp/`: `pip install -e ".[dev]" && pytest`. Stdlib-dependent
  tests skip when the Lambdapi Stdlib isn't installed.
- `.lp` corpora each carry their own `lambdapi.pkg`; `.lpo` files are derived
  caches (git-ignored, safe to delete).
- Where a level has an `AGENTS.md` (the root and `mcp/`), that's the canonical
  agent guide and `CLAUDE.md` symlinks to it; the smaller components document
  themselves in `README.md`.

## Working on `.lp` files

With the plugin installed, the `hooks/` hook type-checks every `.lp` edit and
reports back automatically, and the `lambdapi` skill triggers on `.lp` edits.
Without it: type-check with `lambdapi check FILE.lp` (or the `lambdapi_check` MCP
tool), and inspect proof state with `lambdapi_goals` / `lambdapi_try` rather than
guessing at tactics.
