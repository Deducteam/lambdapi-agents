# arena

Benchmarking harness for evaluating AI agents on Lambdapi proof tasks.

**Status: scaffolding.** The corpora are seeded; the evaluation runner is
under construction.

## Corpora

Self-contained Lambdapi packages (each has its own `lambdapi.pkg`), used as
proof tasks and for exercising the tooling end-to-end:

- `corpora/fermat/` — elementary number theory: divisibility, modular
  arithmetic, binomials, primes, up to Fermat's little theorem.
- `corpora/lambda/` — untyped λ-calculus metatheory: terms, β-reduction,
  parallel reduction.

`.lpo` files are derived caches and are git-ignored.

## Evaluation matrix (planned)

The arena compares agent performance across configurations. The axes:

- **MCP** — with / without the [`mcp/`](../mcp) server.
- **Skill** — without / with the [`skills/lambdapi/`](../skills/lambdapi) skill.
  With the skill on, MCP-first vs CLI-only prompting is a further sub-axis, both
  derived from the one canonical skill.
- **Agent** — Claude / Codex / Gemini.
- **Effort** — low / medium / high / xhigh / max.
- **Theory** — single corpora and *combinations* of theories: how many distinct
  ones can an agent handle, and which combinations break it?

Per task, a run should record: whether the proof type-checks, any leftover
`admit`s or axioms (via `lambdapi_axioms`), token/effort cost, and wall-clock.

## Adding a corpus

Drop a directory under `corpora/` with a `lambdapi.pkg` at its root and one or
more `.lp` files. Keep tasks self-contained (only `Stdlib.*` plus in-package
imports) so they check anywhere the Stdlib is installed.
