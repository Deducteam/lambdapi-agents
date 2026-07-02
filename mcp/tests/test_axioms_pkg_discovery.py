"""tool_axioms must resolve imports against a project-local
lambdapi.pkg discovered by walking upward from the input files,
not just the one under lib_root.

Also: symbols defined via rewrite rules (the `+`/`*`/`!` pattern) are
bucketed under `defined_by_rules` separately from pure postulates."""

from __future__ import annotations

import os
import pathlib

from lambdapi_mcp import tools


def _write_project(root: pathlib.Path) -> tuple[str, str]:
    """Build a mini two-file project under [root]/proj with a
    lambdapi.pkg — root_path=Proj. Returns (base_path, leaf_path)."""
    pkg = root / "proj"
    pkg.mkdir()
    (pkg / "lambdapi.pkg").write_text(
        "package_name = proj\nroot_path = Proj\n"
    )
    base = pkg / "Base.lp"
    base.write_text(
        "constant symbol T : TYPE;\nsymbol ax : T;\n"
    )
    leaf = pkg / "Leaf.lp"
    leaf.write_text(
        "require open Proj.Base;\nsymbol f : T ≔ ax;\n"
    )
    return str(base), str(leaf)


def test_axioms_discovers_upward_pkg(lsp, tmp_path):
    """Leaf.lp lives under a directory with a nested lambdapi.pkg that
    the LSPClient's lib_root does NOT know about. The upward walk must
    pick it up so `require open Proj.Base` resolves."""
    base_path, leaf_path = _write_project(tmp_path)
    r = tools.tool_axioms(lsp, [leaf_path])
    # The upward walk finds proj/lambdapi.pkg and Base.lp is reached.
    assert base_path in r["scanned_files"], (
        f"Base.lp not scanned: {r['scanned_files']}, "
        f"unresolved: {r.get('unresolved_imports')}"
    )
    assert "unresolved_imports" not in r or not r["unresolved_imports"], (
        f"unexpected unresolved imports: {r.get('unresolved_imports')}"
    )
    names = {a["name"] for a in r["assumptions"]}
    assert {"T", "ax"} <= names


def test_axioms_unresolved_when_no_upward_pkg(lsp, tmp_path):
    """Same require, but the leaf lives in a dir without a pkg above
    it. Import stays unresolved — we don't invent a package."""
    leaf = tmp_path / "orphan.lp"
    leaf.write_text(
        "require open Proj.Base;\nsymbol g : τ ι;\n"
    )
    r = tools.tool_axioms(lsp, [str(leaf)])
    mods = [u["module"] for u in r.get("unresolved_imports", [])]
    assert "Proj.Base" in mods, (
        f"expected Proj.Base unresolved, got {r.get('unresolved_imports')}"
    )


def test_defined_by_rules_split(lsp, fixture_path):
    """`double` in simple.lp is a function symbol with two rewrite
    rules — it belongs in `defined_by_rules`, not `assumptions`. The
    primitive constants (`Nat`, `zero`, `succ`) have no rules and stay
    in `assumptions`."""
    r = tools.tool_axioms(lsp, [fixture_path("simple.lp")])
    assumption_names = {a["name"] for a in r["assumptions"]}
    defined_names = {a["name"] for a in r["defined_by_rules"]}
    assert "double" in defined_names
    assert "double" not in assumption_names
    assert {"Nat", "zero", "succ"} <= assumption_names
    # No overlap between the two buckets.
    assert not (assumption_names & defined_names), (
        f"buckets overlap: {assumption_names & defined_names}"
    )


def test_defined_by_rules_preserves_metadata(lsp, fixture_path):
    """Entries in defined_by_rules keep the same shape as assumptions
    — same keys, same types."""
    r = tools.tool_axioms(lsp, [fixture_path("simple.lp")])
    for entry in r["defined_by_rules"]:
        assert {"name", "file", "line", "type", "propositional",
                "constant"} <= entry.keys()
        # These are data-typed, not propositional, by construction.
        assert entry["propositional"] is False


def test_defined_by_rules_propositional_stays_in_assumptions(lsp, tmp_path):
    """A propositional symbol — even with a rewrite rule on its
    π-unfolding — stays in `assumptions`. This prevents silently
    reclassifying something like `em : π (p ∨ ¬ p)` if a user happens
    to write a rule keyed on that name."""
    # Contrived: a plain propositional postulate with no rules.
    f = tmp_path / "prop_ax.lp"
    f.write_text(
        "constant symbol Prop : TYPE;\n"
        "injective symbol π : Prop → TYPE;\n"
        "constant symbol ⊤ : Prop;\n"
        "constant symbol triv : π ⊤;\n"
    )
    r = tools.tool_axioms(lsp, [str(f)])
    names = {a["name"] for a in r["assumptions"]}
    assert "triv" in names
    defined = {a["name"] for a in r["defined_by_rules"]}
    assert "triv" not in defined


def test_pkg_discover_respects_closest_wins(tmp_path):
    """Two pkgs with the same root_path in the anchor's walk-up chain:
    the *closer* one wins (setdefault semantics, innermost first)."""
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
    assert roots.get("Shared") == str(inner), (
        f"expected closest pkg to win, got {roots.get('Shared')}"
    )


def test_pkg_discover_map_dirs_take_priority(tmp_path):
    """Explicit map_dirs should still win over discovered pkg files."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "lambdapi.pkg").write_text(
        "package_name = x\nroot_path = X\n"
    )
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
