# lambdapi-agents

AI-agent tooling for the [Lambdapi](https://github.com/Deducteam/lambdapi)
proof assistant. This is a monorepo of three independent components — work in
the one that matches your task and read its own `AGENTS.md` first.

## Layout

- `mcp/` — Python MCP server over `lambdapi lsp`. Own `pyproject.toml` and
  pytest suite. Component guide: [`mcp/AGENTS.md`](mcp/AGENTS.md).
- `skill/` — the agent skill, in two deliberate variants:
  - `SKILL.mcp.md` — MCP-first (assumes the `mcp__lambdapi__*` tools).
  - `SKILL.md` — CLI-only (drives the `lambdapi` binary); `doc/` mirrors the
    upstream reference.
- `arena/` — benchmarking. `corpora/` holds self-contained `.lp` packages; the
  evaluation harness is WIP. Guide: [`arena/README.md`](arena/README.md).
- `docs/` — project notes.

## Conventions

- The two `skill/` files are alternatives (the "MCP vs skill" experiment), not
  duplicates — keep them in sync in substance but distinct in tool posture. If
  you change Lambdapi guidance in one, check whether the other needs it too.
- `mcp/` targets Python 3.10+. Run its tests from `mcp/`:
  `pip install -e ".[dev]" && pytest`. Stdlib-dependent tests skip when the
  Lambdapi Stdlib isn't installed.
- `.lp` corpora each carry their own `lambdapi.pkg`; `.lpo` files are derived
  caches (git-ignored, safe to delete).
- `AGENTS.md` is the canonical agent guide at each level; `CLAUDE.md` is a
  symlink to it.

## Working on `.lp` files

If a `lambdapi` skill is active in your harness it will trigger on `.lp` edits.
Otherwise: type-check with `lambdapi check FILE.lp` (or the `lambdapi_check`
MCP tool), and inspect proof state with `lambdapi_goals` / `lambdapi_try`
rather than guessing at tactics.
