# skills

Agent skills for the Lambdapi proof assistant, in the standard layout
(`<skill>/SKILL.md` + optional `references/`).

## `lambdapi/`

Teaches an LLM to write, check, and debug Lambdapi (`.lp`) code. The canonical
`SKILL.md` prefers the `mcp__lambdapi__*` tools from the [`mcp/`](../mcp) server
when they're available and falls back to the `lambdapi` CLI otherwise.
`references/` mirrors the upstream Lambdapi manual (syntax, commands, tactics,
queries, grammar) for progressive disclosure.

The **skill-on/off** and **MCP-vs-CLI** distinctions are benchmark axes owned by
[`arena/`](../arena), not separate skills here — the arena derives those
configurations from this one canonical skill.

## Install

Standalone:

```bash
cp -r lambdapi ~/.claude/skills/lambdapi
```

Or install it together with the MCP server via the Claude Code plugin — see the
repo [README](../README.md).
