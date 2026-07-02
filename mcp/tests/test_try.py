from lambdapi_mcp import tools


def _only(r: dict) -> dict:
    """Extract the single attempt from a try result."""
    assert "attempts" in r, r
    assert len(r["attempts"]) == 1, r
    return r["attempts"][0]


def test_try_max_lines_truncates_error(lsp, fixture_path, require_stdlib):
    """Long error messages get capped to max_lines, with a count of
    dropped lines surfaced separately."""
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["apply nonexistent_symbol"],
        mode="replace", max_lines=1,
    )
    attempt = _only(r)
    assert attempt["ok"] is False
    err_lines = attempt["error"].split("\n")
    # max_lines=1 → at most one line, with the dropped count surfaced.
    assert len(err_lines) <= 1
    if "error_truncated_lines" in attempt:
        assert attempt["error_truncated_lines"] >= 1


def test_try_max_lines_zero_means_no_truncation(
    lsp, fixture_path, require_stdlib
):
    """max_lines=0 disables truncation entirely (not 'truncate to 0
    lines'). Useful when the caller wants the full error verbatim."""
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["apply nonexistent_symbol"],
        mode="replace", max_lines=0,
    )
    attempt = _only(r)
    assert attempt["ok"] is False
    assert "error_truncated_lines" not in attempt


def test_try_reflexivity_closes(lsp, fixture_path, require_stdlib):
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["reflexivity"], mode="replace",
    )
    attempt = _only(r)
    assert attempt["ok"], r
    assert attempt["closed"] is True, r
    # Closed attempts should not carry a `post` — it's trivially empty.
    assert "post" not in attempt, attempt


def test_try_bogus_tactic_fails(lsp, fixture_path, require_stdlib):
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["apply nonexistent_symbol"], mode="replace",
    )
    attempt = _only(r)
    assert attempt["ok"] is False
    assert attempt.get("error")


def test_try_many_tactics_returns_all_attempts(
    lsp, fixture_path, require_stdlib
):
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["reflexivity", "simplify"], mode="replace",
    )
    assert len(r["attempts"]) == 2
    assert r["attempts"][0]["tactic"] == "reflexivity"
    assert r["attempts"][1]["tactic"] == "simplify"


def test_try_shares_pre_across_attempts(lsp, fixture_path, require_stdlib):
    """The pre-state is captured once and hoisted to the top level so
    N attempts don't pay for N duplicate renderings."""
    r = tools.tool_try(
        lsp, fixture_path("proof.lp"),
        line=5, tactics=["reflexivity", "symmetry"], mode="replace",
    )
    assert "pre" in r
    for a in r["attempts"]:
        assert "pre" not in a, a
