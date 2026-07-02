# lambdapi-mcp

An [MCP](https://modelcontextprotocol.io/) server exposing
[Lambdapi](https://github.com/Deducteam/lambdapi) proof-assistant
capabilities to AI agents.

`lambdapi-mcp` is a thin layer on top of Lambdapi's standard LSP server:
each tool is implemented by composing LSP requests, so any Lambdapi
that ships `lambdapi lsp` works as a backend.

## Tools

| Tool                    | Purpose                                                        |
| ----------------------- | -------------------------------------------------------------- |
| `lambdapi_check`        | Type-check a file; first error by default, all with a flag     |
| `lambdapi_goals`        | Proof state (hyps + goals) at a 1-based line                   |
| `lambdapi_query`        | Run `compute` / `type` / `print` / `search` at a line          |
| `lambdapi_try`          | Probe one or more tactics at a line without modifying the file |
| `lambdapi_symbols`      | List symbols declared in a file                                |
| `lambdapi_axioms`       | Scan files for axioms, rewrite rules, and admits               |

Hover, go-to-definition, and completions are subsumed by `lambdapi_query`
(`print X` returns a symbol's declaration and body).

All positions exposed to tools use **1-based lines and 0-based columns**,
matching how users think about source files.

## Install

```bash
pip install lambdapi-mcp
```

Requires:

- Python 3.10+
- A `lambdapi` binary on PATH (or passed via `--binary`)
- The Lambdapi Stdlib for tools that exercise proofs. The default
  opam install already sits under `lambdapi`'s `lib_root`, so
  `Stdlib.*` imports resolve with no extra config.

## Use

### From Claude Desktop / other MCP clients

Add to your MCP config (for Claude Desktop: `~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lambdapi": {
      "command": "lambdapi-mcp"
    }
  }
}
```

Optional flags:

- `--lib-root PATH` — pass through as `--lib-root` to `lambdapi lsp`
- `--stdlib PATH` — override where `Stdlib.*` resolves to (adds
  `--map-dir Stdlib:PATH`). Only needed when your Stdlib source lives
  outside `--lib-root`; otherwise the package's own `lambdapi.pkg`
  already resolves it.
- `--binary PATH` — explicit path to the `lambdapi` binary

### Directly

```bash
lambdapi-mcp
```

Speaks MCP on stdio; typically you don't invoke it by hand.

### Lambdapi skill

The agent skill that pairs with this server lives one level up in this
monorepo, at [`../skill/`](../skill), in two variants:

- `skill/SKILL.mcp.md` — MCP-first: teaches the agent to reach for the
  `mcp__lambdapi__*` tools above.
- `skill/SKILL.md` — CLI-only: drives the `lambdapi` binary from a shell,
  with the mirrored upstream reference under `skill/doc/`.

Install one by copying it in as `SKILL.md`:

```bash
mkdir -p ~/.claude/skills/lambdapi
cp ../skill/SKILL.mcp.md ~/.claude/skills/lambdapi/SKILL.md   # MCP variant
```

The skill auto-triggers when the agent edits `.lp` files or the user
mentions Lambdapi. The MCP variant pairs with the server above — it
instructs the agent to reach for `mcp__lambdapi__*` tools first.

## Design

`lambdapi-mcp` matches the design of
[`lean-lsp-mcp`](https://github.com/oOo0oOo/lean-lsp-mcp) and
[`rocq-mcp`](https://github.com/LLM4Rocq/rocq-mcp) — all three layer on
top of the proof assistant's LSP server rather than re-implementing the
check loop, so they track upstream improvements for free.

For probing-style tools (`query`, `try`), the server modifies the
document text in-memory and re-issues `textDocument/didOpen` with the
modified content, then reads back the resulting diagnostics and goals.
The file on disk is never touched.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Fixtures live in `tests/fixtures/`. Tests that require the Lambdapi
Stdlib are skipped automatically if it isn't installed.

## License

Apache-2.0.
