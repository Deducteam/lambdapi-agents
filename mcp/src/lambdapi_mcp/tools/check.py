"""``lambdapi_check`` — type-check one or more .lp files."""
from __future__ import annotations

from ..lsp import LSPClient, file_uri
from ._common import _require_position, _errors, _format_err


def _check_single(
    client: LSPClient, file: str, all_errors: bool
) -> dict:
    """Type-check one .lp file. Same shape as the single-file
    ``tool_check`` return value — factored out so the batch path can
    reuse it without recursion."""
    text, err = _require_position(file)
    if err:
        return err
    uri = file_uri(file)
    with client.open_doc(uri, text) as session:
        diags = session.diagnostics
    errs = _errors(diags)
    if not errs:
        return {"ok": True, "file": file}
    errs.sort(key=lambda d: (
        d["range"]["start"]["line"], d["range"]["start"]["character"]
    ))
    formatted = [_format_err(d) for d in errs]
    if not all_errors:
        formatted = formatted[:1]
    return {"ok": False, "file": file, "errors": formatted}


def tool_check(
    client: LSPClient,
    file: str | list[str],
    all_errors: bool = False,
    stop_on_first_failure: bool = True,
) -> dict:
    """Type-check one or more .lp files.

    - **Single file** (``file`` is a string): returns
      ``{ok: true, file}`` on success, or
      ``{ok: false, file, errors: [...]}`` on failure. By default only
      the first error is reported (matching the CLI); pass
      ``all_errors=True`` for the full sorted list.
    - **Batch** (``file`` is a list of strings): reuses the persistent
      LSP session to check each file in turn. Returns
      ``{ok, passed, failed, read_errors, summary}`` where ``ok`` is
      true iff every file passed, ``passed`` is a list of
      ``{file}`` entries, ``failed`` is ``{file, errors}`` entries
      (with the same ``all_errors`` knob applied per file),
      ``read_errors`` holds files that couldn't be opened (missing,
      unreadable), and ``summary`` has the four counts. By default we
      short-circuit on the first failing file (matching the CLI's
      behaviour on multiple-file input); pass
      ``stop_on_first_failure=False`` to visit every file regardless.

    Errors within a single file are sorted by (line, character)."""
    if isinstance(file, str):
        return _check_single(client, file, all_errors)
    if not isinstance(file, list) or any(not isinstance(f, str) for f in file):
        return {
            "ok": False,
            "error": "file: expected a string or a list of strings",
        }
    passed: list[dict] = []
    failed: list[dict] = []
    read_errors: list[dict] = []
    for f in file:
        r = _check_single(client, f, all_errors)
        if r.get("ok") is True:
            passed.append({"file": f})
            continue
        # `_require_position` returns a dict with `error` but no
        # `errors` on IO failures; `_check_single` on type-error returns
        # `errors` (list). That's the distinguishing field.
        if "errors" not in r:
            read_errors.append({"file": f, "error": r.get("error", "unknown")})
            continue
        failed.append({"file": f, "errors": r["errors"]})
        if stop_on_first_failure:
            break
    return {
        "ok": not failed and not read_errors,
        "passed": passed,
        "failed": failed,
        "read_errors": read_errors,
        "summary": {
            "total": len(file),
            "passed": len(passed),
            "failed": len(failed),
            "read_errors": len(read_errors),
        },
    }
