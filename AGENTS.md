# lambdapi-agents

AI-agent tooling for the [Lambdapi](https://github.com/Deducteam/lambdapi)
proof assistant. A monorepo of three components plus a thin Claude Code plugin
layer — work in the component that matches your task and read its own
`AGENTS.md` first.

## Layout

- `mcp/` — standalone Python MCP server over `lambdapi lsp`. Own
  `pyproject.toml` and pytest suite; PyPI-publishable and usable by any MCP
  client. Component guide: [`mcp/AGENTS.md`](mcp/AGENTS.md).
- `skills/lambdapi/` — the agent skill: canonical `SKILL.md` (prefers the
  `mcp__lambdapi__*` tools when available, else the `lambdapi` CLI) plus
  `references/` mirroring the upstream manual for progressive disclosure.
- `arena/` — benchmarking. `corpora/` holds self-contained `.lp` packages; the
  evaluation harness is WIP. Guide: [`arena/README.md`](arena/README.md).
- `.claude-plugin/` — `plugin.json` + `marketplace.json`: the thin glue that
  ships `skills/` + the `mcp/` server together as one installable Claude Code
  plugin. `.mcp.json` at the root auto-wires the server for Claude Code used
  inside this repo.
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
- `AGENTS.md` is the canonical agent guide at each level; `CLAUDE.md` is a
  symlink to it.

## Working on `.lp` files

If the `lambdapi` skill is active it will trigger on `.lp` edits. Otherwise:
type-check with `lambdapi check FILE.lp` (or the `lambdapi_check` MCP tool), and
inspect proof state with `lambdapi_goals` / `lambdapi_try` rather than guessing
at tactics.
