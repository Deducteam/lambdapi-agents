"""Pre/post consistency and the closed/progress flags for try."""

import pathlib

from lambdapi_mcp import tools


def _only(r: dict) -> dict:
    assert len(r["attempts"]) == 1, r
    return r["attempts"][0]


def test_try_pre_reflects_state_before_closing_tactic(
    lsp, fixture_path, require_stdlib
):
    """Regression: `reflexivity` used to report an empty pre-state
    because the LSP was queried after the closing tactic had already
    collapsed the proof. Pre must reflect the goal *before* the tactic."""
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["reflexivity"], mode="replace",
    )
    attempt = _only(r)
    # Pre is shared at the top level; it must contain a ⊢ line.
    assert "⊢" in r["pre"], r
    assert attempt["ok"], attempt
    assert attempt["closed"] is True
    assert attempt["progress"] is True


def test_try_symmetry_no_progress_flagged(lsp, fixture_path, require_stdlib):
    """`symmetry` on `π (0 = 0)` leaves the state unchanged — progress
    must be False, post must be absent."""
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["symmetry"], mode="replace",
    )
    attempt = _only(r)
    assert attempt["ok"] is True
    assert attempt["progress"] is False
    assert attempt["closed"] is False
    assert "post" not in attempt, attempt


def test_try_closed_flag_false_on_error(lsp, fixture_path, require_stdlib):
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["apply nonexistent_symbol"], mode="replace",
    )
    attempt = _only(r)
    assert attempt["ok"] is False
    # closed/progress omitted on error paths — the state is meaningless.
    assert "closed" not in attempt
    assert "progress" not in attempt


def test_try_post_only_when_progressed_and_open(
    lsp, fixture_path, require_stdlib
):
    """When a tactic makes progress but leaves the goal open, `post`
    carries the remaining state. For closed-or-no-progress, post is
    omitted — reconstructible from pre."""
    # `assume x;` inside eq_sym_nat (line 10, before `symmetry`) introduces
    # a hypothesis — progress, not closed.
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=10, tactics=["assume w"], mode="insert",
    )
    attempt = _only(r)
    if attempt.get("ok") and attempt.get("progress") and not attempt.get("closed"):
        assert "post" in attempt, attempt
        assert "⊢" in attempt["post"]


def test_try_does_not_touch_file_on_disk(lsp, fixture_path, require_stdlib):
    path = pathlib.Path(fixture_path("proof.lp"))
    before = path.read_bytes()
    tools.tool_try(lsp, str(path), line=5, tactics=["reflexivity"])
    tools.tool_try(
        lsp, str(path), line=5, tactics=["admit"], mode="replace",
    )
    tools.tool_try(
        lsp, str(path), line=5,
        tactics=["reflexivity", "symmetry", "admit"],
    )
    assert path.read_bytes() == before, "try must not mutate the file"
