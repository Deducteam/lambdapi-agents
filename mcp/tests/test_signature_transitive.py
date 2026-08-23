"""Transitive `require` closure + scope control. tool_signature follows
imports per `scope` and reports the theory across every file in scope."""

from lambdapi_mcp import tools


def _axiomatic(r):
    return {s["name"]: s for s in r["symbols"] if s["status"] == "axiomatic"}


def test_all_scope_follows_imports(lsp, fixture_path, require_stdlib):
    """scope='all' walks into Stdlib; `eq_refl` from Stdlib/Eq.lp is an
    axiom (propositional postulate)."""
    r = tools.tool_signature(
        lsp, [fixture_path("proof.lp")], scope="all",
    )
    assert r["scanned_files"][0].endswith("proof.lp")
    assert any(p.endswith("/Stdlib/Eq.lp") for p in r["scanned_files"]), (
        r["scanned_files"]
    )
    ax = _axiomatic(r)
    assert "eq_refl" in ax, sorted(ax)[:15]
    assert ax["eq_refl"]["via"] == "axiom"
    assert ax["eq_refl"]["file"].endswith("/Stdlib/Eq.lp")


def test_project_scope_excludes_stdlib(lsp, fixture_path, require_stdlib):
    """Default scope='project' resolves Stdlib imports but does not walk
    them — no Stdlib files, no Stdlib axioms."""
    r = tools.tool_signature(lsp, [fixture_path("proof.lp")])
    assert r["scope"] == "project"
    for p in r["scanned_files"]:
        assert "/Stdlib/" not in p, p
    names = {s["name"] for s in r["symbols"]}
    for stdlib_axiom in ("eq_refl", "ind_eq", "⊤ᵢ", "⊥ₑ"):
        assert stdlib_axiom not in names, stdlib_axiom
    assert "unresolved_imports" not in r, r


def test_file_scope_no_recursion(lsp, fixture_path, require_stdlib):
    r = tools.tool_signature(
        lsp, [fixture_path("proof.lp")], scope="file",
    )
    assert r["scanned_files"] == [fixture_path("proof.lp")]


def test_scanned_files_deduplicated(lsp, fixture_path, require_stdlib):
    path = fixture_path("proof.lp")
    r = tools.tool_signature(lsp, [path, path], scope="all")
    n_self = sum(1 for p in r["scanned_files"] if p.endswith("proof.lp"))
    assert n_self == 1, r["scanned_files"]


def test_local_proofs_are_definitional(lsp, fixture_path, require_stdlib):
    """proof.lp's opaque proofs are definitional (via=body), NOT axioms,
    despite having propositional types."""
    r = tools.tool_signature(lsp, [fixture_path("proof.lp")], scope="file")
    by = {s["name"]: s for s in r["symbols"]}
    for thm in ("zero_eq_zero", "eq_sym_nat"):
        assert by[thm]["status"] == "definitional"
        assert by[thm]["via"] == "body"


def test_records_unresolved_imports(lsp, tmp_path):
    a = tmp_path / "a.lp"
    b = tmp_path / "b.lp"
    a.write_text("require open NoSuchPackage.DoesNotExist;\nsymbol X : τ ι;\n")
    b.write_text("require open NoSuchPackage.DoesNotExist;\nsymbol Y : τ ι;\n")
    r = tools.tool_signature(lsp, [str(a), str(b)])
    ui = r.get("unresolved_imports") or []
    hits = [u for u in ui if u["module"] == "NoSuchPackage.DoesNotExist"]
    assert len(hits) == 1, ui
    assert sorted(hits[0]["imported_by"]) == sorted([str(a), str(b)])


def test_collects_read_errors(lsp, fixture_path, tmp_path):
    r = tools.tool_signature(
        lsp, [fixture_path("simple.lp"), str(tmp_path / "missing.lp")],
    )
    names = {s["name"] for s in r["symbols"]}
    assert "Nat" in names  # good file still scanned
    assert "read_errors" in r
    assert any("missing.lp" in e.get("file", "") for e in r["read_errors"])
