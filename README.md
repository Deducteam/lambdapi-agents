# lambdapi-agents

[![CI](https://github.com/Deducteam/lambdapi-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/Deducteam/lambdapi-agents/actions/workflows/ci.yml)

AI-agent tooling for the [Lambdapi](https://github.com/Deducteam/lambdapi)
proof assistant — an MCP server, an agent skill, and a benchmarking arena,
in one repo.

The goal: let an LLM agent write, check, and repair Lambdapi (`.lp`) proofs,
and measure how well it does under different tool configurations.

## Components

| Dir                  | What                                                                                        |
| -------------------- | ------------------------------------------------------------------------------------------- |
| [`mcp/`](mcp)        | Standalone MCP server exposing `lambdapi lsp` to any client — `check`, `goals`, `query`, `try`, `symbols`, `axioms` |
| [`skills/`](skills)  | Agent skill (`skills/lambdapi/`) teaching Lambdapi syntax, tactics, and the tool surface      |
| [`arena/`](arena)    | Benchmarking harness + proof corpora for evaluating agents across configurations             |

The MCP and the skill are the two ends of the **"MCP vs skill"** question the
project explores: the MCP gives the agent a rigid, structured tool interface;
the skill gives it prose guidance and lets it drive the `lambdapi` CLI itself.
The arena measures which wins, and where.

## Quickstart

### As a Claude Code plugin (skill + server together)

```
/plugin marketplace add Deducteam/lambdapi-agents
/plugin install lambdapi-agents@deducteam
```

Installs the skill and wires up the MCP server in one step. The pieces also
work on their own:

### MCP server (any MCP client)

```bash
cd mcp
pip install -e ".[dev]"
pytest                    # Stdlib-dependent tests skip if the Stdlib is absent
lambdapi-mcp --help       # the server
```

Point a client at `uv run --directory mcp lambdapi-mcp` from a checkout (or
`uvx lambdapi-mcp` once published). See [`mcp/README.md`](mcp/README.md) for
per-client config.

### Skill (standalone)

```bash
cp -r skills/lambdapi ~/.claude/skills/lambdapi
```

It prefers the `mcp__lambdapi__*` tools when present and falls back to the
`lambdapi` CLI. See [`skills/README.md`](skills/README.md).

### Arena

Proof corpora live in [`arena/corpora/`](arena/corpora); the evaluation harness
is under construction. See [`arena/README.md`](arena/README.md).

## Requirements

- A `lambdapi` binary on `PATH` (`opam install lambdapi`)
- Python 3.10+ for the MCP server
- The Lambdapi Stdlib for proof-exercising tools (the opam install already
  provides it under `lambdapi`'s `lib_root`)

## Layout

```
mcp/              standalone Python MCP server (PyPI-publishable)
skills/lambdapi/  the agent skill (SKILL.md + references/)
arena/            benchmarking harness + proof corpora
.claude-plugin/   Claude Code plugin + marketplace manifests (thin glue)
.mcp.json         dev: auto-wire the server when using Claude Code in this repo
```

## Provenance

Folded together from two prototypes — `lambdapi-mcp` (server + skill) and
`lambdapi-skill` (CLI skill + mirrored upstream docs) — into a single repo.
History restarts here; the originals keep theirs.

## License

[Apache-2.0](LICENSE).
