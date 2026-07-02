"""Query line-snapping: `lambdapi_query` accepts a line that lands inside
a begin…end block (or past EOF) and snaps forward to a top-level
statement boundary before inserting."""

from lambdapi_mcp import tools
from lambdapi_mcp.tools import _safe_query_line


# `safe[1]` is always True (start of file). Use a file that exercises:
#  - top-level statement boundaries
#  - lines inside a begin…end proof body
#  - EOF snap
DOC = """\
require open Stdlib.Set Stdlib.Prop Stdlib.Eq Stdlib.Nat;

opaque symbol z : π (0 = 0) ≔
begin
  reflexivity;
end;

opaque symbol s (x : ℕ) : π (x = x) ≔
begin
  reflexivity;
end;
"""
# Line layout:
#   1 require open …;
#   2 (blank)
#   3 opaque symbol z …           ← start of stmt 2
#   4 begin
#   5   reflexivity;              ← inside proof
#   6 end;                        ← statement 2 ends on this line
#   7 (blank)
#   8 opaque symbol s (x : ℕ) …   ← start of stmt 3
#   9 begin
#  10   reflexivity;              ← inside proof
#  11 end;                        ← statement 3 ends on this line


def test_safe_query_line_start_of_file():
    assert _safe_query_line(DOC, 1) == 1


def test_safe_query_line_at_statement_start():
    # Line 3 is the first non-whitespace char after stmt 1's `;` — boundary.
    assert _safe_query_line(DOC, 3) == 3


def test_safe_query_line_inside_proof_snaps_past_end():
    # Line 5 (`reflexivity;` inside the first proof) must snap to line 7
    # (the first line after `end;` on line 6).
    assert _safe_query_line(DOC, 5) == 7


def test_safe_query_line_on_end_line_snaps_past_it():
    # Line 6 is `end;` — still inside the statement until the `;`; snap to 7.
    assert _safe_query_line(DOC, 6) == 7


def test_safe_query_line_inside_second_proof():
    # Line 10 is in stmt 3's proof; snap to 12 (past `end;` on line 11).
    assert _safe_query_line(DOC, 10) == 12


def test_safe_query_line_past_eof():
    # 1000 > 13 → falls back to EOF.
    n = DOC.count("\n") + 1
    assert _safe_query_line(DOC, 1000) in (n, n + 1)


def test_safe_query_line_ignores_semicolons_in_parens():
    # `;` inside parens must not count as a top-level boundary.
    doc = "symbol f : (Π x, π (x = x; x = x)) → TYPE;\nsymbol g : TYPE;\n"
    # line 2 is a valid statement start (after real top-level `;` on line 1)
    assert _safe_query_line(doc, 2) == 2


# ----- integration: query at a line inside begin…end now succeeds --------


def test_tool_query_inside_proof_snaps_and_succeeds(lsp, lib_root):
    path = lib_root / "query_snap.lp"
    path.write_text(DOC)
    # Requesting a query at line 5 (inside the first proof) previously
    # returned "Expected: abort, admitted, end." Now it should succeed
    # and report effective_line >= 7.
    r = tools.tool_query(lsp, str(path), line=5, query="type z")
    assert r["ok"] is True, r
    assert "z" in r.get("output", "") or "=" in r.get("output", "")
    assert r.get("effective_line", 0) >= 7


def test_tool_query_past_eof_snaps_to_eof(lsp, lib_root):
    path = lib_root / "query_eof.lp"
    path.write_text(DOC)
    # Pass a line well beyond the file — _check_line caps at n+1, so use n.
    n = DOC.count("\n") + 1
    r = tools.tool_query(lsp, str(path), line=n, query="print z")
    assert r["ok"] is True, r
