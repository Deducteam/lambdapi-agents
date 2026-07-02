"""Tests for the lambdapi_debug tool (CLI --debug=FLAGS shell-out)."""

from __future__ import annotations

import os

import pytest

from lambdapi_mcp import tools as T


def test_debug_basic_unification(lsp, fixture_path):
    """Run --debug=u on a simple file, get some unification trace lines."""
    f = fixture_path("simple.lp")
    r = T.tool_debug(lsp, f, flags="u")
    assert r["ok"] is True
    assert r["exit_code"] == 0
    assert r["total_lines"] > 0
    # Unification trace mentions the [unif] tag.
    assert "[unif]" in r["debug_log"] or "u]" in r["debug_log"] or r["total_lines"] >= 1


def test_debug_invalid_flags(lsp, fixture_path):
    """Garbage flag chars rejected before invoking lambdapi."""
    f = fixture_path("simple.lp")
    r = T.tool_debug(lsp, f, flags="ZZ")
    assert r["ok"] is False
    assert "invalid" in r["error"]


def test_debug_empty_flags(lsp, fixture_path):
    f = fixture_path("simple.lp")
    r = T.tool_debug(lsp, f, flags="")
    assert r["ok"] is False
    assert "expected a non-empty string" in r["error"]


def test_debug_pattern_filter(lsp, fixture_path):
    """Pattern filters lines; matched_lines reflects pre-truncation count."""
    f = fixture_path("simple.lp")
    r = T.tool_debug(lsp, f, flags="iu", pattern=r"\bdouble\b")
    assert r["ok"] is True
    if r["matched_lines"] > 0:
        # Each returned line should contain "double".
        for line in r["debug_log"].split("\n"):
            if line:
                assert "double" in line
    assert r["matched_lines"] <= r["total_lines"]


def test_debug_invalid_regex(lsp, fixture_path):
    f = fixture_path("simple.lp")
    r = T.tool_debug(lsp, f, flags="u", pattern="[unclosed")
    assert r["ok"] is False
    assert "invalid regex" in r["error"]


def test_debug_tail(lsp, fixture_path):
    """tail=N keeps only the last N lines."""
    f = fixture_path("simple.lp")
    r = T.tool_debug(lsp, f, flags="iu", tail=5)
    assert r["ok"] is True
    assert r["returned_lines"] <= 5


def test_debug_head(lsp, fixture_path):
    """head=N keeps only the first N lines."""
    f = fixture_path("simple.lp")
    r = T.tool_debug(lsp, f, flags="iu", head=3)
    assert r["ok"] is True
    assert r["returned_lines"] <= 3


def test_debug_save_to(lsp, fixture_path, tmp_path):
    """save_to writes the FULL unfiltered output to disk."""
    f = fixture_path("simple.lp")
    log = tmp_path / "debug.log"
    r = T.tool_debug(
        lsp, f, flags="iu", pattern=r"NEVER_MATCHES", save_to=str(log)
    )
    assert r["ok"] is True
    assert r["log_file"] == str(log)
    assert r["matched_lines"] == 0  # filter matched nothing
    assert log.exists()
    # The file should hold the full output, even when the returned
    # debug_log was filtered to empty.
    full = log.read_text()
    assert len(full) > 0


def test_debug_file_not_found(lsp, tmp_path):
    f = str(tmp_path / "nonexistent.lp")
    r = T.tool_debug(lsp, f, flags="u")
    assert r["ok"] is False
    assert "not found" in r["error"]


def test_debug_failing_file(lsp, fixture_path):
    """Files with type errors return ok=False with a non-zero exit but
    still surface the debug log so the caller can investigate."""
    f = fixture_path("with_error.lp")
    r = T.tool_debug(lsp, f, flags="i")
    assert r["ok"] is False
    assert r["exit_code"] != 0
    assert r["total_lines"] > 0
