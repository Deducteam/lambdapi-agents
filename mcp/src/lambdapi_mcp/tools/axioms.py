"""``lambdapi_axioms`` — scan for assumptions, rewrite rules, admits."""
from __future__ import annotations

import os
import re

from ..lsp import LSPClient
from ._common import (
    _read,
    _check_file,
    _split_lines,
    _strip_comments,
    _LINE_COMMENT_RE,
    _BLOCK_COMMENT_RE,
)


# Parser-like regexes for shape classification. Run line-by-line; good
# enough for the common cases (axioms + postulates + admits).
# Binders look like `[x y : τ a]` or `(x : τ a)`; zero or more may sit
# between the symbol name and its `:` type annotation.
_BINDERS = r"(?:\s*\[[^\]]*\]|\s*\([^)]*\))*"

# Any ``symbol`` / ``constant symbol`` declaration, captured on one line.
# Groups: 1=constant?, 2=name, 3=type (up to `;` / EOL, excluding any body).
_SYMBOL_DECL_RE = re.compile(
    r"^\s*(?:private\s+|protected\s+|sequential\s+|injective\s+|opaque\s+)*"
    r"(constant\s+)?symbol\s+([^\s:\[\(]+)" + _BINDERS +
    r"\s*:\s*(.+?)\s*;?\s*$",
)
# `admit` is a tactic inside `begin…end`. The trailing `;` is optional
# (the outer `end;` terminates the statement), and `admit` can appear
# inline inside a `{ … }` subgoal block. Match the bare word anywhere on
# a line; the ``\b`` boundary keeps us from matching the unrelated
# `admitted` end-of-proof keyword.
_ADMIT_RE = re.compile(r"\badmit\b")


_REQUIRE_RE = re.compile(
    r"\brequire\b(?:\s+open\b)?\s+(.+?);",
    re.DOTALL,
)
_MODULE_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


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
        for tok in _MODULE_TOKEN_RE.findall(m.group(1)):
            modules.append(tok)
    return modules




def _split_statements(text: str) -> list[tuple[int, str]]:
    """Split [text] (with comments already stripped) into statements
    terminated by a top-level ``;``. Returns (start_line_1based, body)
    pairs with the original line of each statement's first character."""
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


_RULE_STMT_RE = re.compile(r"^\s*rule\b(.+)$", re.DOTALL)
_RULE_HEAD_RE = re.compile(r"^\s*([^\s\(\[]+)")


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


def _scan_assumptions(
    f: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify declarations in a single file.

    Returns ``(assumptions, rewrite_rules, admits)``."""
    assumptions: list[dict] = []
    rewrite_rules: list[dict] = []
    admits: list[dict] = []
    raw = _read(f)
    text = _strip_comments(raw)
    for start_line, stmt in _split_statements(text):
        m = _RULE_STMT_RE.match(stmt)
        if m:
            for head, lhs, rhs in _parse_rewrite_rules(m.group(1)):
                rewrite_rules.append({
                    "file": f,
                    "line": start_line,
                    "symbol": head,
                    "lhs": " ".join(lhs.split()),
                    "rhs": " ".join(rhs.split()),
                })
            continue
        if "≔" in stmt or ":=" in stmt:
            continue  # has a definition body → not an assumption
        single = " ".join(stmt.split())
        dm = _SYMBOL_DECL_RE.match(single)
        if not dm:
            continue
        is_constant = bool(dm.group(1))
        name = dm.group(2)
        type_str = dm.group(3).strip()
        assumptions.append({
            "file": f,
            "line": start_line,
            "name": name,
            "type": type_str,
            "propositional": _is_propositional(type_str),
            "constant": is_constant,
        })
    # Scan the comment-stripped text so a commented-out `admit` isn't
    # counted. `_strip_comments` preserves newlines, so line numbers
    # still align with the raw source.
    for i, line in enumerate(_split_lines(text), 1):
        if _ADMIT_RE.search(line):
            admits.append({"file": f, "line": i})
    return assumptions, rewrite_rules, admits


_AXIOMS_SCOPES = ("file", "project", "all")


def tool_axioms(
    client: LSPClient, files: list[str], scope: str = "project"
) -> dict:
    """Scan [files] for unproved assumptions.

    ``scope`` controls how much is scanned:

    - ``"file"``: only the files passed in; ``require`` is not followed.
    - ``"project"`` (default): follow ``require`` transitively, but skip
      anything under the configured ``lib_root`` (the opam Stdlib tree).
      This is usually what agents want — the project's own axioms, not
      a re-dump of ``Set``/``Prop``/``eq_refl``/… every scan.
    - ``"all"``: full transitive scan, including Stdlib.

    Four buckets come back:

    - **assumptions**: any ``symbol`` / ``constant symbol`` declared
      without a ``≔`` body AND without any rewrite rule in scope keyed
      on it (a pure postulate).
    - **defined_by_rules**: data-typed (non-propositional) symbols that
      *are* the head of at least one rewrite rule in scope — i.e.
      recursive function definitions like ``+``, ``*``, ``!``. These
      behave like assumptions to the kernel but aren't propositional
      axioms; split out so the "no new axioms" contract is easy to
      check.
    - **rewrite_rules**: every ``rule LHS ↪ RHS;`` (including each
      sub-rule in a ``rule … with … with …;`` block).
    - **admits**: every ``admit`` tactic inside a proof (a hole) —
      trailing ``;`` optional; ``{ admit }`` inline forms are also
      counted. Does not match the unrelated ``admitted`` end-of-proof
      keyword.

    Also returns ``scanned_files`` (everything visited) and
    ``unresolved_imports`` (deduped: ``{module, imported_by: [...]}``).
    """
    if scope not in _AXIOMS_SCOPES:
        return {
            "ok": False,
            "error": f"scope: expected one of {list(_AXIOMS_SCOPES)}, "
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

    assumptions: list[dict] = []
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
        a, rr, ad = _scan_assumptions(path)
        assumptions.extend(a)
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

    rule_heads = {
        rr["symbol"] for rr in rewrite_rules if rr.get("symbol")
    }
    defined_by_rules: list[dict] = []
    pure_assumptions: list[dict] = []
    for a in assumptions:
        if a["name"] in rule_heads and not a.get("propositional"):
            defined_by_rules.append(a)
        else:
            pure_assumptions.append(a)

    result = {
        "files": files,
        "scope": scope,
        "scanned_files": scan_order,
        "assumptions": pure_assumptions,
        "defined_by_rules": defined_by_rules,
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
