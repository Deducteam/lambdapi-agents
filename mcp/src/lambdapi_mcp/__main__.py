"""CLI entry point: ``lambdapi-mcp``.

Starts the MCP server on stdio. The client (typically Claude Desktop or
another MCP-aware tool) spawns this process and speaks MCP over stdio.
"""

from __future__ import annotations

import argparse
import sys

from .server import build_server


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="lambdapi-mcp",
        description="MCP server for the Lambdapi proof assistant.",
    )
    p.add_argument(
        "--lib-root",
        help="Path for --lib-root passed to `lambdapi lsp`. "
             "Defaults to $LAMBDAPI_LIB_ROOT or the opam install.",
    )
    p.add_argument(
        "--stdlib",
        help="Override where `Stdlib.*` resolves to (adds "
             "`--map-dir Stdlib:DIR`). Only needed when your Stdlib "
             "source lives outside `--lib-root`; otherwise the "
             "package's own lambdapi.pkg already resolves it.",
    )
    p.add_argument(
        "--binary",
        help="Override the path to the `lambdapi` binary.",
    )
    p.add_argument(
        "--log-file",
        help="Forward `--log-file PATH` to `lambdapi lsp` for debugging.",
    )
    args = p.parse_args(argv)

    server = build_server(
        lib_root=args.lib_root,
        stdlib=args.stdlib,
        binary=args.binary,
        log_file=args.log_file,
    )
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
