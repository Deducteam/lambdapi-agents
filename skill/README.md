# skill

The agent skill that teaches an LLM to write, check, and debug Lambdapi
(`.lp`) code. It ships in **two variants** — the two ends of the "MCP vs
skill" question this project is exploring:

- **`SKILL.mcp.md`** — MCP-first. Assumes the [`mcp/`](../mcp) server is wired
  in and tells the agent to reach for the structured `mcp__lambdapi__*` tools
  before shelling out. More rigid, more efficient.
- **`SKILL.md`** — CLI-only. Drives the `lambdapi` binary directly and leans on
  the mirrored upstream reference in [`doc/`](doc). No server required; the
  agent has more latitude.

`doc/` mirrors the upstream Lambdapi manual — surface syntax, commands,
tactics, queries, and the grammar (`lambdapi.bnf`) — shared reference for the
CLI variant.

## Install

A skill is a directory containing a `SKILL.md`. Pick a variant and copy it in:

```bash
mkdir -p ~/.claude/skills/lambdapi
cp SKILL.mcp.md ~/.claude/skills/lambdapi/SKILL.md   # MCP variant
# or, the CLI variant (which references ./doc):
cp SKILL.md ~/.claude/skills/lambdapi/SKILL.md
cp -r doc   ~/.claude/skills/lambdapi/doc
```

Both auto-trigger when the agent edits `.lp` files or the user mentions
Lambdapi.

## Which to use?

For a wired-up MCP setup, prefer `SKILL.mcp.md`. For a plain shell with no
server, use `SKILL.md`. The [`arena/`](../arena) benchmarks both (and neither)
to quantify the difference.
