# lambdapi-agents

AI-agent tooling for the [Lambdapi](https://github.com/Deducteam/lambdapi)
proof assistant — an MCP server, an agent skill, and a benchmarking arena,
in one repo.

The goal: let an LLM agent write, check, and repair Lambdapi (`.lp`) proofs,
and measure how well it does under different tool configurations.

## Components

| Dir                | What                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------- |
| [`mcp/`](mcp)      | MCP server exposing `lambdapi lsp` to agents — `check`, `goals`, `query`, `try`, `symbols`, `axioms` |
| [`skill/`](skill)  | Agent skill teaching Lambdapi syntax, tactics, and the tool surface — MCP and CLI variants   |
| [`arena/`](arena)  | Benchmarking harness + proof corpora for evaluating agents across configurations             |

These are the two ends of the **"MCP vs skill"** question the project is
exploring: the MCP gives the agent a rigid, structured tool interface; the
skill gives it prose guidance and lets it drive the `lambdapi` CLI itself.
The arena exists to measure which wins, and where.

## Quickstart

### MCP server

```bash
cd mcp
pip install -e ".[dev]"
pytest                    # Stdlib-dependent tests skip if the Stdlib is absent
lambdapi-mcp --help       # the server; wire it into your MCP client
```

See [`mcp/README.md`](mcp/README.md) for client config and flags.

### Skill

Pick a variant and drop it into your agent's skills directory:

```bash
mkdir -p ~/.claude/skills/lambdapi
cp skill/SKILL.mcp.md ~/.claude/skills/lambdapi/SKILL.md   # MCP-first
# or: cp skill/SKILL.md ~/.claude/skills/lambdapi/SKILL.md # CLI-only
```

See [`skill/README.md`](skill/README.md) for the difference.

### Arena

Proof corpora live in [`arena/corpora/`](arena/corpora); the evaluation
harness is under construction. See [`arena/README.md`](arena/README.md).

## Requirements

- A `lambdapi` binary on `PATH` (`opam install lambdapi`)
- Python 3.10+ for the MCP server
- The Lambdapi Stdlib for proof-exercising tools (the opam install already
  provides it under `lambdapi`'s `lib_root`)

## Provenance

Folded together from two prototypes — `lambdapi-mcp` (server + MCP skill) and
`lambdapi-skill` (CLI skill + mirrored upstream docs) — into a single repo.
History restarts here; the originals keep theirs.

## License

[Apache-2.0](LICENSE).
