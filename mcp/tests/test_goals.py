from lambdapi_mcp import tools


def test_goals_outside_proof_returns_no_goals(
    lsp, fixture_path, require_stdlib
):
    r = tools.tool_goals(lsp, fixture_path("proof.lp"), line=1)
    assert r["pretty"] == "no goals"


def test_goals_inside_proof_shows_target_and_hyps(
    lsp, fixture_path, require_stdlib
):
    # proof.lp:10 sits inside eq_sym_nat, after `assume x y h;`. The
    # pretty rendering should include at least the turnstile target.
    r = tools.tool_goals(lsp, fixture_path("proof.lp"), line=10)
    pretty = r["pretty"]
    assert "⊢" in pretty, f"no target line in pretty output: {pretty!r}"


def test_goals_single_goal_is_flush_left(lsp, fixture_path, require_stdlib):
    """Single-goal rendering has no header or `[i]` label — the ⊢ line
    already conveys what's being shown."""
    r = tools.tool_goals(lsp, fixture_path("proof.lp"), line=10)
    pretty = r["pretty"]
    # No goal-count header for the single-goal case.
    assert not pretty.startswith("1 goal"), pretty
    # No per-goal label.
    assert "[0]" not in pretty, pretty


def test_goals_returns_file_and_line(lsp, fixture_path, require_stdlib):
    r = tools.tool_goals(lsp, fixture_path("proof.lp"), line=10)
    assert r["line"] == 10
    assert r["file"].endswith("proof.lp")
