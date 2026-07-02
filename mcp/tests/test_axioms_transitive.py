"""Transitive `require` closure: tool_axioms follows imports and reports
everything in scope, not just declarations in the input files."""

from lambdapi_mcp import tools


def test_axioms_follows_direct_imports(lsp, fixture_path, require_stdlib):
    """proof.lp imports Stdlib.{Set,Prop,Eq,Nat}. With scope='all',
    scanning it should pick up Stdlib declarations — not just proof.lp."""
    r = tools.tool_axioms(
        lsp, [fixture_path("proof.lp")], scope="all",
    )
    assert r["scanned_files"][0].endswith("proof.lp")
    assert any(p.endswith("/Stdlib/Eq.lp") for p in r["scanned_files"]), (
        f"Stdlib/Eq.lp not in scanned files: {r['scanned_files']}"
    )
    by_name = {a["name"]: a for a in r["assumptions"]}
    assert "eq_refl" in by_name, (
        f"eq_refl not found; got {sorted(by_name)[:15]}…"
    )
    assert by_name["eq_refl"]["propositional"] is True
    assert by_name["eq_refl"]["constant"] is True
    assert by_name["eq_refl"]["file"].endswith("/Stdlib/Eq.lp")


def test_axioms_project_scope_excludes_stdlib(
    lsp, fixture_path, require_stdlib
):
    """Default scope='project' resolves Stdlib imports but does not walk
    them — the scan contains no Stdlib files and no Stdlib axioms."""
    r = tools.tool_axioms(lsp, [fixture_path("proof.lp")])
    assert r["scope"] == "project"
    for p in r["scanned_files"]:
        assert "/Stdlib/" not in p, f"Stdlib file leaked into project scope: {p}"
    names = {a["name"] for a in r["assumptions"]}
    # Stdlib propositional axioms must NOT be in project scope.
    for stdlib_axiom in ("eq_refl", "ind_eq", "⊤ᵢ", "⊥ₑ"):
        assert stdlib_axiom not in names, (
            f"{stdlib_axiom!r} leaked from Stdlib under scope='project'"
        )
    # The scan must still succeed (no unresolved, since Stdlib resolves).
    assert "unresolved_imports" not in r, r


def test_axioms_file_scope_no_recursion(
    lsp, fixture_path, require_stdlib
):
    """scope='file' ignores `require` entirely — only the input files
    are scanned."""
    r = tools.tool_axioms(
        lsp, [fixture_path("proof.lp")], scope="file",
    )
    assert r["scanned_files"] == [fixture_path("proof.lp")]


def test_axioms_transitive_scanned_files_are_deduplicated(
    lsp, fixture_path, require_stdlib
):
    path = fixture_path("proof.lp")
    r = tools.tool_axioms(lsp, [path, path], scope="all")
    n_self = sum(1 for p in r["scanned_files"] if p.endswith("proof.lp"))
    assert n_self == 1, f"duplicate scan of proof.lp: {r['scanned_files']}"


def test_axioms_records_unresolved_imports(lsp, tmp_path):
    """Unresolved imports come back deduplicated — one entry per module
    with `imported_by` aggregating every file that tried to require it."""
    a = tmp_path / "a.lp"
    b = tmp_path / "b.lp"
    a.write_text(
        "require open NoSuchPackage.DoesNotExist;\nsymbol X : τ ι;\n"
    )
    b.write_text(
        "require open NoSuchPackage.DoesNotExist;\nsymbol Y : τ ι;\n"
    )
    r = tools.tool_axioms(lsp, [str(a), str(b)])
    ui = r.get("unresolved_imports") or []
    hits = [u for u in ui if u["module"] == "NoSuchPackage.DoesNotExist"]
    assert len(hits) == 1, f"expected one dedup'd entry, got {ui}"
    assert sorted(hits[0]["imported_by"]) == sorted([str(a), str(b)])


def test_axioms_no_imports_only_self(lsp, fixture_path):
    """simple.lp has no `require`: the scan visits only simple.lp.
    `double` has rewrite rules → `defined_by_rules`; the primitives
    stay in `assumptions`."""
    path = fixture_path("simple.lp")
    r = tools.tool_axioms(lsp, [path])
    assert r["scanned_files"] == [path]
    assumption_names = {a["name"] for a in r["assumptions"]}
    defined_names = {a["name"] for a in r["defined_by_rules"]}
    assert {"Nat", "zero", "succ"} <= assumption_names
    assert "double" in defined_names, (
        f"double should be in defined_by_rules: {defined_names}"
    )
    assert "double" not in assumption_names, (
        f"double should not be in assumptions: {assumption_names}"
    )
    props = [a for a in r["assumptions"] if a["propositional"]]
    assert props == [], f"unexpected propositional assumptions: {props}"


def test_axioms_distinguishes_propositional(
    lsp, fixture_path, require_stdlib
):
    r = tools.tool_axioms(
        lsp, [fixture_path("proof.lp")], scope="all",
    )
    by_name = {a["name"]: a for a in r["assumptions"]}
    if "⊤ᵢ" in by_name:
        assert by_name["⊤ᵢ"]["propositional"] is True
    if "Set" in by_name:
        assert by_name["Set"]["propositional"] is False
