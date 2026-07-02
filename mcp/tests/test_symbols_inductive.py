"""tool_symbols must include inductive constructors and the
auto-generated induction principle (`ind_<Type>`), not just the type
name."""

from lambdapi_mcp import tools


def test_symbols_includes_constructors_and_induction_principle(
    lsp, fixture_path, require_stdlib
):
    r = tools.tool_symbols(lsp, fixture_path("inductive.lp"))
    names = {s["name"] for s in r["symbols"]}
    for expected in ("Foo", "foo_a", "foo_b", "ind_Foo"):
        assert expected in names, f"{expected!r} missing from {sorted(names)}"
