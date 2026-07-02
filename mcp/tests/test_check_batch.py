"""Batch-mode `tool_check`: list input reuses the LSP session and
returns a per-file summary."""

from lambdapi_mcp import tools


def test_batch_all_pass(lsp, fixture_path):
    files = [fixture_path("simple.lp"), fixture_path("modifiers.lp")]
    r = tools.tool_check(lsp, files)
    assert r["ok"] is True, r
    assert {p["file"] for p in r["passed"]} == set(files)
    assert r["failed"] == []
    assert r["read_errors"] == []
    assert r["summary"] == {
        "total": 2, "passed": 2, "failed": 0, "read_errors": 0,
    }


def test_batch_mixed_pass_and_fail_default_short_circuits(lsp, fixture_path):
    # Default stop_on_first_failure=True matches the CLI — stop at the
    # first failing file.
    files = [
        fixture_path("simple.lp"),
        fixture_path("with_error.lp"),
        fixture_path("multiple_errors.lp"),
    ]
    r = tools.tool_check(lsp, files)
    assert r["ok"] is False, r
    assert [p["file"] for p in r["passed"]] == [fixture_path("simple.lp")]
    assert [x["file"] for x in r["failed"]] == [fixture_path("with_error.lp")]
    assert r["failed"][0]["errors"]
    # multiple_errors.lp was never visited.
    assert r["read_errors"] == []
    assert r["summary"] == {
        "total": 3, "passed": 1, "failed": 1, "read_errors": 0,
    }


def test_batch_visits_every_file_when_short_circuit_disabled(
    lsp, fixture_path
):
    files = [
        fixture_path("simple.lp"),
        fixture_path("with_error.lp"),
        fixture_path("multiple_errors.lp"),
    ]
    r = tools.tool_check(lsp, files, stop_on_first_failure=False)
    assert r["ok"] is False, r
    assert [p["file"] for p in r["passed"]] == [fixture_path("simple.lp")]
    failed_files = {x["file"] for x in r["failed"]}
    assert failed_files == {
        fixture_path("with_error.lp"),
        fixture_path("multiple_errors.lp"),
    }
    for fr in r["failed"]:
        assert len(fr["errors"]) == 1  # default: one per file
    assert r["summary"] == {
        "total": 3, "passed": 1, "failed": 2, "read_errors": 0,
    }


def test_batch_all_errors_flag_applies_per_file(lsp, fixture_path):
    r = tools.tool_check(
        lsp, [fixture_path("multiple_errors.lp")], all_errors=True,
    )
    assert len(r["failed"]) == 1
    assert len(r["failed"][0]["errors"]) >= 2


def test_batch_stop_on_first_failure_is_default(lsp, fixture_path, tmp_path):
    # Default behaviour: stop on the first failing file; a nonexistent
    # file after it is never visited.
    files = [
        fixture_path("with_error.lp"),
        str(tmp_path / "nope.lp"),
    ]
    r = tools.tool_check(lsp, files)
    assert r["ok"] is False
    assert len(r["failed"]) == 1
    assert r["failed"][0]["file"] == fixture_path("with_error.lp")
    assert r["read_errors"] == []
    assert r["summary"]["total"] == 2
    assert r["summary"]["passed"] + r["summary"]["failed"] + \
           r["summary"]["read_errors"] < r["summary"]["total"]


def test_batch_missing_file_goes_to_read_errors(lsp, fixture_path, tmp_path):
    # IO errors don't trigger the short-circuit (that's for type-errors);
    # every file is still visited so the missing one lands in read_errors.
    files = [fixture_path("simple.lp"), str(tmp_path / "nope.lp")]
    r = tools.tool_check(lsp, files)
    assert r["ok"] is False  # the missing file makes ok=false
    assert len(r["passed"]) == 1
    assert r["failed"] == []
    assert len(r["read_errors"]) == 1
    assert r["read_errors"][0]["error"] == "file not found"


def test_single_string_preserves_legacy_shape(lsp, fixture_path):
    r = tools.tool_check(lsp, fixture_path("simple.lp"))
    # Same shape as before: {ok, file}. No batch fields.
    assert r["ok"] is True
    assert "file" in r
    for k in ("passed", "failed", "read_errors", "summary"):
        assert k not in r, f"{k} leaked into single-file response"


def test_bad_argument_shape(lsp):
    r = tools.tool_check(lsp, 42)  # type: ignore[arg-type]
    assert r["ok"] is False
    assert "expected" in r["error"]
    r2 = tools.tool_check(lsp, ["a.lp", 7])  # type: ignore[list-item]
    assert r2["ok"] is False
    assert "expected" in r2["error"]
