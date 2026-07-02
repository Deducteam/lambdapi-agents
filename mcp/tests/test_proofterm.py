"""Tests for the lambdapi_proofterm tool."""

from __future__ import annotations

from lambdapi_mcp import tools as T


def test_proofterm_initial_state(lsp, fixture_path, require_stdlib):
    """Inside a fresh proof, proofterm prints a bare metavariable."""
    r = T.tool_proofterm(lsp, fixture_path("proof.lp"), line=5)
    assert r["ok"] is True
    # Should be a single metavariable like `?1`.
    assert "?" in r["term"]


def test_proofterm_after_assume(lsp, fixture_path, require_stdlib, tmp_path):
    """After binding parameters, the proof term shows the lambda
    skeleton plus a metavariable for the body."""
    src = tmp_path / "skel.lp"
    src.write_text((
        "require open Stdlib.Set Stdlib.Prop Stdlib.Eq Stdlib.Nat;\n"
        "\n"
        "opaque symbol skel [P Q : Prop] : π (P ⇒ Q ⇒ P) ≔\n"
        "begin\n"
        "  assume P Q hP hQ;\n"
        "  refine hP;\n"
        "end;\n"
    ))
    # lambdapi.pkg comes from the lib_root fixture.
    r = T.tool_proofterm(lsp, str(src), line=6)
    assert r["ok"] is True
    # After `assume P Q hP hQ;` the term should be a 4-arg lambda
    # capped by a metavar for the remaining goal.
    assert "λ" in r["term"]
    assert "?" in r["term"]


def test_proofterm_file_not_found(lsp, tmp_path):
    r = T.tool_proofterm(lsp, str(tmp_path / "x.lp"), line=1)
    assert r["ok"] is False
    assert "not found" in r["error"]


def test_proofterm_invalid_line(lsp, fixture_path):
    r = T.tool_proofterm(lsp, fixture_path("simple.lp"), line=10000)
    assert r["ok"] is False
    assert "out of range" in r["error"]
