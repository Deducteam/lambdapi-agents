from lambdapi_mcp import tools


def test_check_clean_file(lsp, fixture_path):
    r = tools.tool_check(lsp, fixture_path("simple.lp"))
    assert r["ok"], r
    assert r["file"].endswith("simple.lp")


def test_check_default_reports_first_error_only(lsp, fixture_path):
    r = tools.tool_check(lsp, fixture_path("multiple_errors.lp"))
    assert r["ok"] is False
    # Default matches the CLI: only the first sorted error is returned.
    assert len(r["errors"]) == 1, r
    assert "Undef1" in r["errors"][0]["message"]
    assert r["errors"][0]["line"] == 2


def test_check_all_errors_returns_full_sorted_list(lsp, fixture_path):
    r = tools.tool_check(
        lsp, fixture_path("multiple_errors.lp"), all_errors=True,
    )
    assert r["ok"] is False
    lines = [e["line"] for e in r["errors"]]
    assert len(lines) >= 2, r
    assert lines == sorted(lines), f"errors should be sorted by line: {lines}"


def test_check_reports_error(lsp, fixture_path):
    r = tools.tool_check(lsp, fixture_path("with_error.lp"))
    assert r["ok"] is False
    assert r["errors"]
    first = r["errors"][0]
    assert "Undefined" in first["message"]
    # 1-based line: the error is on line 3 of with_error.lp
    assert first["line"] == 3
