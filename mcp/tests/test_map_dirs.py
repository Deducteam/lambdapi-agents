"""Regression tests for the `Stdlib` map-dir resolution.

Auto-injecting `--map-dir=Stdlib:<opam>/Stdlib` on top of a `--lib-root`
that already contains `Stdlib/` crashes `lambdapi lsp` with "Root state
is missing" when a file inside that Stdlib is opened. The server must
only add the mapping when the user explicitly supplies `--stdlib=DIR`.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from lambdapi_mcp.lsp import LSPClient, default_lib_root
from lambdapi_mcp.server import resolve_map_dirs


def test_no_stdlib_no_mapping():
    assert resolve_map_dirs(None) == []


def test_missing_stdlib_path_no_mapping(tmp_path: pathlib.Path):
    assert resolve_map_dirs(str(tmp_path / "nope")) == []


def test_explicit_stdlib_maps(tmp_path: pathlib.Path):
    assert resolve_map_dirs(str(tmp_path)) == [f"Stdlib:{tmp_path}"]


def test_opens_stdlib_file_under_lib_root():
    """With `--lib-root=<opam>/lib_root` and NO map-dir, files inside
    `<opam>/lib_root/Stdlib/` must open cleanly. With the redundant
    `Stdlib:<opam>/Stdlib` mapping, lambdapi lsp crashes."""
    opam_lib_root = default_lib_root()
    stdlib_file = os.path.join(opam_lib_root, "Stdlib", "Prop.lp")
    if not os.path.isfile(stdlib_file):
        pytest.skip("opam Stdlib not installed")

    client = LSPClient(lib_root=opam_lib_root, map_dirs=[])
    client.start()
    try:
        uri = f"file://{stdlib_file}"
        text = pathlib.Path(stdlib_file).read_text()
        with client.open_doc(uri, text) as session:
            diags = session.diagnostics
    finally:
        client.stop()

    crash = [
        d for d in diags
        if "Root state is missing" in d.get("message", "")
    ]
    assert not crash, f"LSP crashed on Stdlib file: {crash}"
