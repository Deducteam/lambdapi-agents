"""admit detection: trailing `;` is optional, inline `{ admit }` counts,
commented-out admits don't, and the unrelated `admitted` keyword
doesn't."""

from lambdapi_mcp import tools


def test_admits_count_all_forms(lsp, fixture_path):
    r = tools.tool_axioms(
        lsp, [fixture_path("admits.lp")], scope="file",
    )
    lines = sorted(a["line"] for a in r["admits"])
    # Expected: the three real admits at lines 6, 12, 17 (with-`;`,
    # without-`;`, and inline inside a `{ … }` subgoal). The commented
    # admits on lines 4/8/15/19/20/24 and the `admitted` keyword on
    # line 26 must be excluded.
    assert lines == [6, 12, 17], (
        f"expected admits at lines [6, 12, 17], got {lines}"
    )
