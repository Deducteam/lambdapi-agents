"""``lambdapi_proofterm`` — partial proof term at a line."""
from __future__ import annotations

from ..lsp import LSPClient, file_uri
from ._common import _require_position, _insert_at, _errors


def tool_proofterm(client: LSPClient, file: str, line: int) -> dict:
    """Show the partial proof term at 1-based [line] inside a `begin…end`
    block. Inserts `proofterm;` as a one-shot probe (the file on disk
    is not modified) and captures the resulting term.

    Useful for diagnosing higher-order unification failures: the term
    shows where in the partial proof the metavariables live, which
    often reveals scope / binder issues that ``lambdapi_try`` only
    surfaces as `?XXX ≡ y` constraints.

    Returns ``{file, line, term, raw_lines?}``. ``term`` is the printed
    partial term (e.g. ``λ P0 Q0 hP0 hQ0, ?6``); ``raw_lines`` includes
    everything Lambdapi printed in case the term was wrapped over
    multiple lines."""
    text, err = _require_position(file, line)
    if err:
        return err
    probe = "proofterm;"
    modified = _insert_at(text, line, probe)
    uri = file_uri(file)
    probe_line_0 = line - 1
    with client.open_doc(uri, modified) as session:
        pass
    diags = session.diagnostics
    errs_at_probe = [
        d for d in _errors(diags)
        if d["range"]["start"]["line"] == probe_line_0
    ]
    if errs_at_probe:
        return {
            "ok": False, "file": file, "line": line,
            "error": errs_at_probe[0]["message"],
        }
    # `proofterm` output arrives as a severity=4 (info / OK-hint)
    # diagnostic attached to the probe line — same channel as
    # `compute` / `print` queries. Pick those.
    hints = [
        d["message"] for d in diags
        if d.get("severity") == 4
        and d["range"]["start"]["line"] == probe_line_0
    ]
    candidates = [h for h in hints if h.strip()]
    term = candidates[-1] if candidates else ""
    out: dict = {"ok": True, "file": file, "line": line, "term": term}
    if len(candidates) > 1:
        out["raw_lines"] = candidates
    return out
