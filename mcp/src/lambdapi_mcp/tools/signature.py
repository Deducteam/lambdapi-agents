"""``lambdapi_signature`` — the theory a scope presents.

Describes the theory declared by one or more ``.lp`` files: every
top-level symbol, definition, inductive, and rewrite rule, each symbol
classified as **definitional** (has a ``≔`` body, is defined by rewrite
rules, or is an inductive type / constructor) or **axiomatic** (a
bodyless postulate — an ``axiom`` when its type is propositional, a
``postulate`` otherwise). ``admit`` proof-holes are axiomatic gaps and
are reported alongside.

This folds together the former ``symbols`` (what is declared) and
``axioms`` (what is assumed) tools: axioms are just the axiomatic
portion of the signature. The scan is text-based (statement-level) and
follows ``require`` transitively per the ``scope`` argument, resolving
modules against every ``lambdapi.pkg`` it can find.

Generated induction principles (``ind_<Type>``) are *not* listed: they
aren't written in the source and every inductive has one.
"""
from __future__ import annotations

import os
import re

from ..lsp import LSPClient
from ._common import (
    _BLOCK_COMMENT_RE,
    _LINE_COMMENT_RE,
    _check_file,
    _read,
    _split_lines,
    _strip_comments,
)

# --- Package / import resolution (shared with the require-walk) -----------

_REQUIRE_RE = re.compile(r"\brequire\b(?:\s+open\b)?\s+(.+?);", re.DOTALL)
_MODULE_TOKEN_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
)


def _read_pkg(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition("=")
                    out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def _discover_pkg_roots(
    lib_root: str | None,
    map_dirs: list[str],
    anchor_files: list[str] | None = None,
) -> dict[str, str]:
    """Return ``{root_path_name: directory}`` for every known Lambdapi
    package.

    Sources, in priority order:

    1. ``map_dirs`` (explicit ``Name:/abs/path`` pairs).
    2. ``lambdapi.pkg`` discovered by walking *upward* from each
       ``anchor_files`` entry — this is how we pick up a project's own
       package when the user hasn't pointed ``lib_root`` at it.
    3. ``lambdapi.pkg`` discovered by walking *downward* under
       ``lib_root`` (typically the opam-installed Stdlib tree)."""
    roots: dict[str, str] = {}
    for md in map_dirs or []:
        if ":" in md:
            name, path = md.split(":", 1)
            if os.path.isdir(path):
                roots.setdefault(name, path)
    for anchor in anchor_files or []:
        d = os.path.dirname(os.path.abspath(anchor))
        prev: str | None = None
        while d and d != prev:
            pkg_path = os.path.join(d, "lambdapi.pkg")
            if os.path.isfile(pkg_path):
                pkg = _read_pkg(pkg_path)
                rp = pkg.get("root_path")
                if rp:
                    roots.setdefault(rp, d)
            prev = d
            d = os.path.dirname(d)
    if lib_root and os.path.isdir(lib_root):
        for dirpath, _dirnames, filenames in os.walk(lib_root):
            if "lambdapi.pkg" in filenames:
                pkg = _read_pkg(os.path.join(dirpath, "lambdapi.pkg"))
                rp = pkg.get("root_path")
                if rp:
                    roots.setdefault(rp, dirpath)
    return roots


def _installed_dirs(
    lib_root: str | None,
    map_dirs: list[str],
    anchor_files: list[str] | None = None,
) -> set[str]:
    """Absolute directories that represent *installed* library roots,
    for the purpose of excluding them under ``scope='project'``.

    A directory is installed iff it's either:
    - an explicit ``map_dir`` target (``--stdlib …`` / ``--map-dir …``), or
    - a ``lambdapi.pkg`` directory found by walking **downward** from
      ``lib_root`` that is NOT also reachable by walking **upward** from
      ``anchor_files``.

    The upward-exclusion matters in tests (and any setup where the user
    points ``lib_root`` at their project root): the same directory
    shows up in both sources, and the upward hit wins — it's the user's
    project, not an installed library."""
    from_map: set[str] = set()
    for md in map_dirs or []:
        if ":" in md:
            _, path = md.split(":", 1)
            if os.path.isdir(path):
                from_map.add(os.path.abspath(path))
    from_upward: set[str] = set()
    for anchor in anchor_files or []:
        d = os.path.dirname(os.path.abspath(anchor))
        prev: str | None = None
        while d and d != prev:
            if os.path.isfile(os.path.join(d, "lambdapi.pkg")):
                from_upward.add(d)
            prev = d
            d = os.path.dirname(d)
    from_libroot: set[str] = set()
    if lib_root and os.path.isdir(lib_root):
        for dirpath, _dirnames, filenames in os.walk(lib_root):
            if "lambdapi.pkg" in filenames:
                from_libroot.add(os.path.abspath(dirpath))
    return from_map | (from_libroot - from_upward)


def _resolve_module(module: str, roots: dict[str, str]) -> str | None:
    """Resolve ``Stdlib.Nat`` → ``/.../Stdlib/Nat.lp``."""
    parts = module.split(".")
    if not parts:
        return None
    prefix = parts[0]
    root_dir = roots.get(prefix)
    if root_dir is None:
        return None
    rel = os.path.join(*parts[1:]) + ".lp" if len(parts) > 1 else prefix + ".lp"
    path = os.path.join(root_dir, rel)
    return path if os.path.isfile(path) else None


def _parse_requires(text: str) -> list[str]:
    """Return the module names mentioned in any ``require ... ;`` block."""
    stripped = _LINE_COMMENT_RE.sub("", text)
    stripped = _BLOCK_COMMENT_RE.sub("", stripped)
    modules: list[str] = []
    for m in _REQUIRE_RE.finditer(stripped):
        modules.extend(_MODULE_TOKEN_RE.findall(m.group(1)))
    return modules


# --- Statement splitting + low-level token scanning -----------------------

_MODIFIERS = (
    "private", "protected", "sequential", "injective", "constant", "opaque",
)
_MODIFIER_PREFIX_RE = re.compile(
    r"^\s*((?:(?:" + "|".join(_MODIFIERS) + r")\s+)*)"
)


def _split_statements(text: str) -> list[tuple[int, str]]:
    """Split [text] (with comments already stripped) into statements
    terminated by a top-level ``;``. Returns (start_line_1based, body)
    pairs with the original line of each statement's first character.

    ``;`` inside ``begin…end`` proof bodies still terminates here — but
    that only truncates the proof term, which we never inspect: every
    declaration's name, type, and ``≔`` all sit before the first
    in-proof ``;``, so the truncated head classifies correctly."""
    stmts: list[tuple[int, str]] = []
    buf: list[str] = []
    depth = 0
    line = 1
    stmt_start: int | None = None
    for ch in text:
        if ch not in " \t\n" and stmt_start is None:
            stmt_start = line
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == ";" and depth == 0:
            body = "".join(buf).strip()
            if body and stmt_start is not None:
                stmts.append((stmt_start, body))
            buf.clear()
            stmt_start = None
        else:
            buf.append(ch)
        if ch == "\n":
            line += 1
    # Any unterminated tail is ignored (malformed file).
    return stmts


def _find_top_level(s: str, ch: str) -> int:
    """Index of the first [ch] at bracket-depth 0 in [s], or -1."""
    depth = 0
    for i, c in enumerate(s):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ch and depth == 0:
            return i
    return -1


def _find_top_level_str(s: str, sub: str) -> int:
    """Index of the first [sub] at bracket-depth 0 in [s], or -1."""
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and s.startswith(sub, i):
            return i
        i += 1
    return -1


def _split_body(decl: str) -> tuple[str, bool]:
    """Split a symbol declaration [decl] into (head, has_body).

    The body separator is ``≔`` (or its ASCII spelling ``:=``); [head]
    is everything before it (``symbol NAME binders : TYPE``)."""
    i = _find_top_level(decl, "≔")
    if i >= 0:
        return decl[:i], True
    i = _find_top_level_str(decl, ":=")
    if i >= 0:
        return decl[:i], True
    return decl, False


# --- Declaration classification -------------------------------------------

_RULE_STMT_RE = re.compile(r"^\s*rule\b(.+)$", re.DOTALL)
_RULE_HEAD_RE = re.compile(r"^\s*([^\s\(\[]+)")
_ADMIT_RE = re.compile(r"\badmit\b")
_SYM_NAME_RE = re.compile(r"symbol\s+([^\s:\[\(]+)\s*(.*)", re.DOTALL)

# Inductive type header: `inductive NAME : TYPE ≔ …` (and each mutual
# member introduced by `with NAME : TYPE ≔ …`).
_IND_HEAD_RE = re.compile(
    r"^\s*(?:(?:" + "|".join(_MODIFIERS) + r")\s+)*"
    r"(?:inductive|with)\s+([^\s:\[\(]+)\s*:\s*([^≔]*)"
)
# A constructor line inside an inductive block: `| NAME : TYPE`.
_IND_CTOR_LINE_RE = re.compile(r"^\s*\|\s*([^\s:\[\(]+)\s*:\s*(.+?)\s*;?\s*$")


def _is_propositional(type_str: str) -> bool:
    """A type is propositional iff it eventually applies ``π`` to a Prop
    (i.e. ``π …`` somewhere at the top level after quantifiers). We
    approximate: a leading token ``π`` or ``Π …, π`` counts."""
    if type_str.lstrip().startswith("π"):
        return True
    return bool(re.search(r"(?:^|\s|,)π[\s(]", type_str))


def _parse_rewrite_rules(body: str) -> list[tuple[str, str, str]]:
    """Split a `rule …[with …]*` body into ``(head, lhs, rhs)`` triples.

    ``head`` is the leftmost identifier on the LHS — the symbol this
    rule reduces. ``lhs`` and ``rhs`` are the raw text on either side
    of ``↪``."""
    out: list[tuple[str, str, str]] = []
    # Statements are split at top-level `;`, so we never see `with` from
    # outside a rule here. Splitting on word-boundary `with` is safe.
    subs = re.split(r"\bwith\b", body)
    for sub in subs:
        if "↪" not in sub:
            continue
        lhs, _, rhs = sub.partition("↪")
        lhs = lhs.strip()
        rhs = rhs.strip()
        m = _RULE_HEAD_RE.match(lhs)
        head = m.group(1) if m else ""
        out.append((head, lhs, rhs))
    return out


def _symbol_entry(f: str, line: int, name: str, typ: str, has_body: bool) -> dict:
    """Classify a plain ``symbol`` declaration. Rule-defined symbols are
    reclassified later once all rule heads are known."""
    if has_body:
        status, via = "definitional", "body"
    elif _is_propositional(typ):
        status, via = "axiomatic", "axiom"
    else:
        status, via = "axiomatic", "postulate"
    return {
        "file": f, "line": line, "name": name, "type": typ,
        "kind": "symbol", "status": status, "via": via,
    }


def _ctors_in_segment(segment: str, f: str, line: int) -> list[dict]:
    """Parse inline constructors from the text after a same-line ``≔``
    (single-line inductive style): ``| a : T | b : U``."""
    out: list[dict] = []
    depth = 0
    parts: list[str] = []
    buf: list[str] = []
    for c in segment:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "|" and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
    parts.append("".join(buf))
    for p in parts:
        m = re.match(r"\s*([^\s:\[\(]+)\s*:\s*(.+?)\s*;?\s*$", p)
        if m:
            out.append({
                "file": f, "line": line, "name": m.group(1),
                "type": m.group(2).strip(), "kind": "constructor",
                "status": "definitional", "via": "constructor",
            })
    return out


def _parse_inductive(body: str, start_line: int, f: str) -> list[dict]:
    """Parse an ``inductive`` statement (possibly a mutual ``with`` block)
    into its type formers and constructors — all definitional.

    Line-based so each type / constructor keeps its own source line;
    constructors written on the ``≔`` line are recovered too."""
    out: list[dict] = []
    saw_type = False
    for off, ln in enumerate(body.split("\n")):
        lineno = start_line + off
        hm = _IND_HEAD_RE.match(ln)
        if hm:
            out.append({
                "file": f, "line": lineno, "name": hm.group(1),
                "type": (hm.group(2) or "").strip(), "kind": "inductive",
                "status": "definitional", "via": "inductive",
            })
            saw_type = True
            if "≔" in ln:
                out.extend(
                    _ctors_in_segment(ln.split("≔", 1)[1], f, lineno)
                )
            continue
        cm = _IND_CTOR_LINE_RE.match(ln)
        if cm and saw_type:
            out.append({
                "file": f, "line": lineno, "name": cm.group(1),
                "type": cm.group(2).strip(), "kind": "constructor",
                "status": "definitional", "via": "constructor",
            })
    return out


def _scan_theory(f: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify a single file's declarations.

    Returns ``(symbols, rewrite_rules, admits)``."""
    symbols: list[dict] = []
    rewrite_rules: list[dict] = []
    admits: list[dict] = []
    raw = _read(f)
    text = _strip_comments(raw)
    for start_line, stmt in _split_statements(text):
        rm = _RULE_STMT_RE.match(stmt)
        if rm:
            for head, lhs, rhs in _parse_rewrite_rules(rm.group(1)):
                rewrite_rules.append({
                    "file": f,
                    "line": start_line,
                    "symbol": head,
                    "lhs": " ".join(lhs.split()),
                    "rhs": " ".join(rhs.split()),
                })
            continue
        single = " ".join(stmt.split())
        rest = _MODIFIER_PREFIX_RE.sub("", single, count=1)
        if rest.startswith("inductive "):
            symbols.extend(_parse_inductive(stmt, start_line, f))
            continue
        if rest.startswith("symbol "):
            head, has_body = _split_body(rest)
            nm = _SYM_NAME_RE.match(head)
            if not nm:
                continue
            name = nm.group(1)
            tail = nm.group(2)
            ci = _find_top_level(tail, ":")
            typ = tail[ci + 1:].strip() if ci >= 0 else ""
            symbols.append(_symbol_entry(f, start_line, name, typ, has_body))
            continue
    # Scan the comment-stripped text so a commented-out `admit` isn't
    # counted. `_strip_comments` preserves newlines, so line numbers align.
    for i, line in enumerate(_split_lines(text), 1):
        if _ADMIT_RE.search(line):
            admits.append({"file": f, "line": i})
    return symbols, rewrite_rules, admits


_SIGNATURE_SCOPES = ("file", "project", "all")


def tool_signature(
    client: LSPClient, files: list[str], scope: str = "project"
) -> dict:
    """Describe the theory presented by [files].

    ``scope`` controls how much is scanned:

    - ``"file"``: only the files passed in; ``require`` is not followed.
    - ``"project"`` (default): follow ``require`` transitively, but skip
      anything under the configured ``lib_root`` (the opam Stdlib tree).
      This is usually what agents want — the project's own theory, not a
      re-dump of ``Set``/``Prop``/``eq_refl``/… every scan.
    - ``"all"``: full transitive scan, including Stdlib.

    Returns:

    - **symbols**: every declared symbol, each with ``name``, ``line``,
      ``file``, ``type``, ``kind`` (``symbol`` / ``inductive`` /
      ``constructor``), ``status`` (``definitional`` / ``axiomatic``),
      and ``via`` — *why* it's classified so:

      - ``body`` — has a ``≔`` definition (a def / theorem / opaque proof),
      - ``rules`` — bodyless but reduced by rewrite rules (a function),
      - ``inductive`` / ``constructor`` — part of an inductive definition,
      - ``axiom`` — a bodyless propositional (``π …``) postulate,
      - ``postulate`` — a bodyless non-propositional postulate.

      Axioms are exactly the ``via == "axiom"`` entries; the whole
      axiomatic base is ``status == "axiomatic"`` plus ``admits``.

    - **rewrite_rules**: every ``rule LHS ↪ RHS;`` (including each
      sub-rule of a ``rule … with … with …;`` block).
    - **admits**: every ``admit`` proof-hole (trailing ``;`` optional;
      ``{ admit }`` inline forms counted; the ``admitted`` keyword is not).
    - **scanned_files**: everything visited, in order.
    - **unresolved_imports**: deduped ``{module, imported_by: [...]}``.
    - **read_errors**: input files that couldn't be opened (when any).

    Generated induction principles (``ind_<Type>``) are not listed.
    """
    if scope not in _SIGNATURE_SCOPES:
        return {
            "ok": False,
            "error": f"scope: expected one of {list(_SIGNATURE_SCOPES)}, "
                     f"got {scope!r}",
        }
    if not isinstance(files, list) or any(
        not isinstance(f, str) for f in files
    ):
        return {
            "ok": False,
            "error": "files: expected a list of file-path strings",
        }

    lib_root = getattr(client, "lib_root", None)
    map_dirs = getattr(client, "map_dirs", []) or []
    anchors = [f for f in files if isinstance(f, str)]
    installed_dirs = _installed_dirs(lib_root, map_dirs, anchors)

    def _is_installed(path: str) -> bool:
        p = os.path.abspath(path)
        return any(
            p == d or p.startswith(d + os.sep) for d in installed_dirs
        )

    roots = _discover_pkg_roots(lib_root, map_dirs, anchor_files=anchors)

    symbols: list[dict] = []
    rewrite_rules: list[dict] = []
    admits: list[dict] = []
    read_errors: list[dict] = []
    unresolved: dict[str, list[str]] = {}

    scanned: set[str] = set()
    scan_order: list[str] = []
    frontier: list[tuple[str, str | None]] = []
    for f in files:
        err = _check_file(f)
        if err:
            read_errors.append(err)
            continue
        frontier.append((os.path.abspath(f), None))

    while frontier:
        path, imported_by = frontier.pop(0)
        if path in scanned:
            continue
        if not os.path.isfile(path):
            read_errors.append({
                "ok": False, "file": path, "error": "file not found",
                "imported_by": imported_by,
            })
            continue
        # In project scope, Stdlib files are resolved but not walked.
        if scope == "project" and imported_by is not None and _is_installed(path):
            scanned.add(path)
            continue
        scanned.add(path)
        scan_order.append(path)
        syms, rr, ad = _scan_theory(path)
        symbols.extend(syms)
        rewrite_rules.extend(rr)
        admits.extend(ad)
        # No recursion in file scope — each input file is scanned once,
        # its requires are ignored.
        if scope == "file":
            continue
        text = _read(path)
        for mod in _parse_requires(text):
            resolved = _resolve_module(mod, roots)
            if resolved is None:
                unresolved.setdefault(mod, [])
                if path not in unresolved[mod]:
                    unresolved[mod].append(path)
                continue
            resolved_abs = os.path.abspath(resolved)
            if resolved_abs not in scanned:
                frontier.append((resolved_abs, path))

    # A bodyless, non-propositional symbol that heads a rewrite rule is a
    # function definition, not a postulate — reclassify it as definitional.
    # Propositional symbols stay axiomatic even if a rule is keyed on them.
    rule_heads = {rr["symbol"] for rr in rewrite_rules if rr.get("symbol")}
    for s in symbols:
        if s["via"] == "postulate" and s["name"] in rule_heads:
            s["status"] = "definitional"
            s["via"] = "rules"

    result: dict = {
        "ok": True,
        "scope": scope,
        "scanned_files": scan_order,
        "symbols": symbols,
        "rewrite_rules": rewrite_rules,
        "admits": admits,
    }
    if read_errors:
        result["read_errors"] = read_errors
    if unresolved:
        result["unresolved_imports"] = [
            {"module": mod, "imported_by": sorted(set(by))}
            for mod, by in sorted(unresolved.items())
        ]
    return result
