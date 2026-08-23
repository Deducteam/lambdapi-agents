"""tool_signature: rewrite rules and admit proof-holes."""

from lambdapi_mcp import tools


def test_rewrite_rules_both_subrules(lsp, fixture_path):
    """simple.lp's `rule … with …` block yields two rules, both keyed
    on `double`."""
    r = tools.tool_signature(lsp, [fixture_path("simple.lp")], scope="file")
    rr = r["rewrite_rules"]
    assert len(rr) == 2, rr
    assert all(x["symbol"] == "double" for x in rr)
    lhs_rhs = {(x["lhs"], x["rhs"]) for x in rr}
    assert ("double zero", "zero") in lhs_rhs
    assert any(lhs == "double (succ $n)" for lhs, _ in lhs_rhs)


def test_rewrite_rules_empty_when_none(lsp, fixture_path):
    r = tools.tool_signature(lsp, [fixture_path("proof.lp")], scope="file")
    assert r["rewrite_rules"] == []


def test_admits_all_forms(lsp, fixture_path):
    """admits.lp: real admits at 6/12/17 (trailing-`;`, bare, and inline
    `{ admit }`); commented admits and the `admitted` keyword excluded."""
    r = tools.tool_signature(lsp, [fixture_path("admits.lp")], scope="file")
    lines = sorted(a["line"] for a in r["admits"])
    assert lines == [6, 12, 17], lines
