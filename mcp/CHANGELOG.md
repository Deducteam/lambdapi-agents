# Changelog

Notable changes to `lambdapi-mcp`. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is
[SemVer](https://semver.org/).

## [Unreleased]

### Changed
- Moved into the `Deducteam/lambdapi-agents` monorepo under `mcp/`; project
  URLs now point there.
- Constrained the `mcp` dependency to `<2` ahead of the SDK 2.0 API rename
  (`FastMCP` → `MCPServer`).

## [0.1.0]

- Initial MCP server layered on `lambdapi lsp`: `lambdapi_check`,
  `lambdapi_goals`, `lambdapi_query`, `lambdapi_try`, `lambdapi_symbols`,
  `lambdapi_axioms`.
