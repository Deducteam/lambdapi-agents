# Changelog

Notable changes to `lambdapi-mcp`. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is
[SemVer](https://semver.org/).

## [Unreleased]

### Added
- GitHub Actions CI: ruff + an import smoke on Python 3.10 and 3.13, plus the
  full pytest suite against `lambdapi` installed via opam.

### Changed
- Trimmed the tool surface from 8 to 5: `lambdapi_check`, `lambdapi_goals`,
  `lambdapi_query`, `lambdapi_try`, `lambdapi_signature`.
- Split `tools.py` into a `tools/` subpackage (one module per tool plus a
  shared `_common.py`); the public import surface (`tools.tool_*`) is unchanged.

### Removed
- `lambdapi_proofterm` and `lambdapi_debug`.

### Merged
- `lambdapi_symbols` + `lambdapi_axioms` → `lambdapi_signature(files, scope)`,
  which describes the theory a scope presents: a flat `symbols` list, each
  entry classified `status` (definitional / axiomatic) and `via`
  (body / rules / inductive / constructor / axiom / postulate), plus
  `rewrite_rules`, `admits`, `scanned_files`, and `unresolved_imports`. Axioms
  are the axiomatic portion of the signature; it also now surfaces definitions
  and inductive constructors that the old `axioms` scan discarded.
- Moved into the `Deducteam/lambdapi-agents` monorepo under `mcp/`; project
  URLs now point there.
- Constrained the `mcp` dependency to `<2` ahead of the SDK 2.0 API rename
  (`FastMCP` → `MCPServer`).

## [0.1.0]

- Initial MCP server layered on `lambdapi lsp`: `lambdapi_check`,
  `lambdapi_goals`, `lambdapi_query`, `lambdapi_try`, `lambdapi_symbols`,
  `lambdapi_axioms`.
