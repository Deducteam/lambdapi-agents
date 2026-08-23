"""tool_signature resolves imports against a project-local lambdapi.pkg
discovered by walking upward from the input files, and buckets
rule-defined symbols separately from postulates."""

from __future__ import annotations

import pathlib

from lambdapi_mcp import tools


def _write_project(root: pathlib.Path) -> tuple[str, str]:
    """A mini two-file project under [root]/proj with root_path=Proj.
    Returns (base_path, leaf_path)."""
    pkg = root / "proj"
    pkg.mkdir()
    (pkg / "lambdapi.pkg").write_text("package_name = proj\nroot_path = Proj\n")
    base = pkg / "Base.lp"
    base.write_text("constant symbol T : TYPE;\nsymbol ax : T;\n")
    leaf = pkg / "Leaf.lp"
    leaf.write_text("require open Proj.Base;\nsymbol f : T ≔ ax;\n")
    return str(base), str(leaf)


def test_discovers_upward_pkg(lsp, tmp_path):
    """Leaf.lp lives under a nested lambdapi.pkg the LSPClient's lib_root
    doesn't know about; the upward walk must resolve `Proj.Base`."""
    base_path, leaf_path = _write_project(tmp_path)
    r = tools.tool_signature(lsp, [leaf_path])
    assert base_path in r["scanned_files"], (
        r["scanned_files"], r.get("unresolved_imports"),
    )
    assert not r.get("unresolved_imports"), r.get("unresolved_imports")
    names = {s["name"] for s in r["symbols"]}
    assert {"T", "ax", "f"} <= names


def test_unresolved_when_no_upward_pkg(lsp, tmp_path):
    leaf = tmp_path / "orphan.lp"
    leaf.write_text("require open Proj.Base;\nsymbol g : τ ι;\n")
    r = tools.tool_signature(lsp, [str(leaf)])
    mods = [u["module"] for u in r.get("unresolved_imports", [])]
    assert "Proj.Base" in mods, r.get("unresolved_imports")


def test_defined_by_rules_vs_postulates(lsp, fixture_path):
    """`double` (two rewrite rules) is definitional-via-rules; the
    primitive constants stay axiomatic postulates. No name is both."""
    r = tools.tool_signature(lsp, [fixture_path("simple.lp")], scope="file")
    by = {s["name"]: s for s in r["symbols"]}
    assert by["double"]["via"] == "rules"
    assert by["double"]["status"] == "definitional"
    for prim in ("Nat", "zero", "succ"):
        assert by[prim]["status"] == "axiomatic"


def test_pkg_discover_closest_wins(tmp_path):
    """Two pkgs with the same root_path in the walk-up chain: the closer
    one wins (setdefault, innermost first)."""
    inner = tmp_path / "outer" / "inner"
    inner.mkdir(parents=True)
    (tmp_path / "outer" / "lambdapi.pkg").write_text(
        "package_name = shared\nroot_path = Shared\n"
    )
    (inner / "lambdapi.pkg").write_text(
        "package_name = shared\nroot_path = Shared\n"
    )
    anchor = inner / "leaf.lp"
    anchor.write_text("")
    roots = tools._discover_pkg_roots(
        lib_root=None, map_dirs=[], anchor_files=[str(anchor)],
    )
    assert roots.get("Shared") == str(inner), roots.get("Shared")


def test_pkg_discover_map_dirs_take_priority(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "lambdapi.pkg").write_text("package_name = x\nroot_path = X\n")
    anchor = pkg / "a.lp"
    anchor.write_text("")
    override = tmp_path / "override"
    override.mkdir()
    roots = tools._discover_pkg_roots(
        lib_root=None,
        map_dirs=[f"X:{override}"],
        anchor_files=[str(anchor)],
    )
    assert roots["X"] == str(override), roots
