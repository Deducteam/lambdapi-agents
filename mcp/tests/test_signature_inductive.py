"""tool_signature must surface inductive types and their constructors
as definitional entries (kind `inductive` / `constructor`), each on its
own source line."""

from lambdapi_mcp import tools


def test_inductive_and_constructors(lsp, fixture_path):
    r = tools.tool_signature(lsp, [fixture_path("inductive.lp")], scope="file")
    by = {s["name"]: s for s in r["symbols"]}
    assert by["Foo"]["kind"] == "inductive"
    assert by["Foo"]["status"] == "definitional"
    assert by["Foo"]["via"] == "inductive"
    for ctor in ("foo_a", "foo_b"):
        assert by[ctor]["kind"] == "constructor"
        assert by[ctor]["status"] == "definitional"
    # Constructor types are captured.
    assert by["foo_b"]["type"] == "Foo → Foo"


def test_inductive_line_numbers(lsp, fixture_path):
    """Foo is on line 6, its constructors on 7 and 8."""
    r = tools.tool_signature(lsp, [fixture_path("inductive.lp")], scope="file")
    by = {s["name"]: s for s in r["symbols"]}
    assert by["Foo"]["line"] == 6
    assert by["foo_a"]["line"] == 7
    assert by["foo_b"]["line"] == 8


def test_induction_principle_not_listed(lsp, fixture_path):
    """Generated `ind_<Type>` eliminators are not part of the source
    listing."""
    r = tools.tool_signature(lsp, [fixture_path("inductive.lp")], scope="file")
    names = {s["name"] for s in r["symbols"]}
    assert "ind_Foo" not in names


def test_single_line_inductive(lsp, tmp_path):
    """Constructors written on the `≔` line are recovered too."""
    f = tmp_path / "oneline.lp"
    f.write_text("inductive B : TYPE ≔ | t : B | f : B;\n")
    r = tools.tool_signature(lsp, [str(f)], scope="file")
    by = {s["name"]: s for s in r["symbols"]}
    assert by["B"]["kind"] == "inductive"
    assert by["t"]["kind"] == "constructor"
    assert by["f"]["kind"] == "constructor"
