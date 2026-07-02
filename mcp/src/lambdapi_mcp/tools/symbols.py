"""``lambdapi_symbols`` — locally-declared symbols in a file."""
from __future__ import annotations

import re

from ..lsp import LSPClient, file_uri
from ._common import _require_position, _split_lines


_DECL_RE = re.compile(
    r"^\s*"
    # zero or more modifiers (in any order) before `symbol` / `inductive`
    r"(?:(?:opaque|private|protected|sequential|injective|constant)\s+)*"
    r"(?:symbol|inductive)\s+"
    # symbol name: anything up to whitespace or `:` or `[`
    r"([^\s:\[]+)"
)

# A `with NAME : …` line introducing another member of a mutual inductive
# block. Only recognised AFTER we've seen an `inductive …` earlier in the
# file; scoping is enforced in `_local_decl_names`.
_WITH_TYPE_RE = re.compile(r"^\s*with\s+([^\s:\[]+)")

# A constructor line inside an `inductive` block: `  | NAME : …`.
_CTOR_RE = re.compile(r"^\s*\|\s*([^\s:\[\(]+)")


def _local_decl_names(text: str) -> set[str]:
    """Parse [text] line-by-line for locally-declared symbol names.

    Recognises:
    - ``symbol NAME`` / ``constant symbol NAME`` / ``opaque symbol NAME``
    - ``inductive NAME`` and, for mutual inductives, ``with NAME``
    - each inductive's auto-generated induction principle ``ind_NAME``
    - each constructor ``| cname`` inside an inductive block
    Used to filter documentSymbol output, since the upstream lambdapi
    LSP leaks transitively-imported symbols into the reply.
    """
    names: set[str] = set()
    in_inductive = False
    for line in _split_lines(text):
        m = _DECL_RE.match(line)
        if m:
            name = m.group(1)
            names.add(name)
            if re.match(r"^\s*(?:(?:private|protected|sequential|injective"
                        r"|constant|opaque)\s+)*inductive\b", line):
                names.add(f"ind_{name}")
                in_inductive = True
            else:
                in_inductive = False
            continue
        if in_inductive:
            wm = _WITH_TYPE_RE.match(line)
            if wm:
                names.add(wm.group(1))
                names.add(f"ind_{wm.group(1)}")
                continue
            cm = _CTOR_RE.match(line)
            if cm:
                names.add(cm.group(1))
                continue
    return names


def tool_symbols(client: LSPClient, file: str) -> dict:
    """List the symbols declared in [file] via textDocument/documentSymbol.

    The upstream lambdapi LSP replies with transitively-imported symbols
    attributed to the queried URI. We cross-check each reported symbol's
    name against a local declaration parse of [file] and drop anything
    that isn't actually declared in this file."""
    text, err = _require_position(file)
    if err:
        return err
    uri = file_uri(file)
    local_names = _local_decl_names(text)
    with client.open_doc(uri, text):
        result = client.document_symbol(uri) or []
    symbols = []
    for s in result:
        name = s.get("name", "")
        if name not in local_names:
            continue
        rng = s.get("location", {}).get("range", {}).get("start", {})
        symbols.append({
            "name": name,
            "kind": s.get("kind"),
            "line": rng.get("line", 0) + 1,
            "character": rng.get("character", 0),
        })
    return {"file": file, "symbols": symbols}
