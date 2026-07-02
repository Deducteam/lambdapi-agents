---
name: lambdapi
description: >
  Write, debug, and check Lambdapi (.lp) proof-assistant code via the
  lambdapi CLI.
  TRIGGER when: editing .lp files, debugging lambdapi errors, writing
  proofs / rewrite rules / inductive types, or when the user mentions
  lambdapi or Lambdapi.
  DO NOT TRIGGER when: editing OCaml, Python, or other non-.lp code,
  even if it generates .lp output.
allowed-tools: Read, Grep, Glob, Bash(lambdapi *)
---

# Lambdapi

Lambdapi is a proof assistant based on the λΠ-calculus modulo rewriting:
dependent types + user-declared rewrite rules. Proofs are tactic scripts
that elaborate to terms; rewrite rules extend the kernel's reduction.

Drive it from the `lambdapi` CLI. The mirrored upstream docs in `doc/`
cover surface syntax, commands, tactics, and queries; this file
documents the CLI itself.

## Subcommands

```
lambdapi check FILE.lp [FILE.lp ...]   # type-check
lambdapi parse FILE.lp                 # syntax-only, no typing (fast smoke test)
lambdapi init MOD.PATH                 # scaffold a package (creates lambdapi.pkg + Makefile)
lambdapi index FILE.lp ...             # populate ~/.LPSearch.db
lambdapi search "QUERY"                # query that index (see doc/query_language.md)
lambdapi websearch                     # web frontend for the index (default port 8080)
lambdapi export -o FMT FILE.lp         # convert: lp, dk, raw_dk, hrs, xtc, raw_coq, stt_coq
lambdapi decision-tree MOD.symbol      # dump a symbol's pattern-match tree as graphviz
lambdapi lsp                           # LSP server (for editor integration)
lambdapi install / uninstall           # follow package config
lambdapi version
lambdapi help [SUBCOMMAND]             # `lambdapi check --help` for per-command flags
```

`check`, `parse`, `export`, `index` accept `.lp` or `.dk`; the parser
is auto-selected. Multi-file `check` is fail-fast in text mode (stops
on first failing file).

## Common flags

Apply to `check`, `decision-tree`, `export`, `parse`, `lsp`:

```
--lib-root=<DIR>          # override the library root (see resolution order below)
--map-dir=<MOD>:<DIR>     # mount DIR as module prefix MOD (alternative: lambdapi.pkg)
--debug=<FLAGS>           # concatenated single-char trace flags (see below)
--timeout=<N>             # give up after N seconds (reset per file)
-v <N>, --verbose=<N>     # 0 silent, 1 default, higher = more
--no-sr-check             # disable subject-reduction check — UNSOUND, debugging only
--json                    # NDJSON output (one object per line); see doc/options.md
```

`check`-only:

```
-c, --gen-obj             # write .lpo object cache alongside source
--too-long=<FLOAT>        # warn on commands taking > FLOAT seconds
--confluence=<CMD>        # external confluence checker, HRS on stdin
--termination=<CMD>       # external termination checker, XTC on stdin
```

**Debug-flag chars** (`--debug=iut` etc.): `a` metavariables, `c`
conversion, `d` decision trees, `e` snf, `g` ind-principle generation,
`i` type inference/checking, `k` local confluence, `l` library files,
`m` term building, `n` parsing, `o` scoping, `p` pretty-printing, `r`
rewrite tactic, `s` subject reduction, `t` tactics, `u` unification,
`v` inverse, `w` whnf, `x` export, `y` why3, `z` external tools.

**Library-root resolution** (priority order): `--lib-root` flag →
`$LAMBDAPI_LIB_ROOT/lib/lambdapi/lib_root` →
`$OPAM_SWITCH_PREFIX/lib/lambdapi/lib_root` →
`/usr/local/lib/lambdapi/lib_root`.

**Exit codes:** `0` ok, `123` errors, `124` CLI parse errors, `125`
internal bug.

## Packages and lookup

A `lambdapi.pkg` file at a directory root makes everything under it a
package:

```
package_name = mything
root_path    = MyThing.subpath
```

File `<root>/a/b.lp` then resolves as module `MyThing.subpath.a.b`. The
package file is mandatory for anything beyond toy single-file usage;
otherwise modules can't be looked up. `lambdapi init` writes a starter
one. See `doc/module.md`.

## Object cache (`.lpo`)

`-c` (or the LSP) writes `foo.lpo` next to `foo.lp`. Reused on later
runs if newer than the source. **Delete stale `.lpo` files** when
changing lambdapi versions or `root_path`; the error message
`File X.lpo is incompatible with current binary` is the usual symptom.

## Workflow

```
edit file.lp  →  lambdapi check file.lp  →  read first error  →  fix  →  re-check
```

For a sharper feedback loop:

- `lambdapi parse file.lp` — catches syntax errors without paying for
  type-checking (useful on long files).
- `lambdapi check --debug=t file.lp` — when a tactic-script fails
  mysteriously, the `t` flag traces tactic dispatch.
- `lambdapi check --json file.lp | jq` — programmatic diagnostics (each
  error has `range`, `severity`, `message`).

**Error messages carry the goal state.** An unfinished proof, a subproof
mismatch, *and an immediate tactic failure* (e.g. `rewrite` with no
matching subterm, `fail`, a bad `apply`/`refine`, `induction` on a
non-inductive goal) all report the hypotheses + remaining goal inline, in
both the human and `--json` (`message` field) output. So when a tactic
fails you already see the goal it was applied to — no need to splice a
probe to recover it.

To inspect a point that *isn't* failing, drop a query into the script and
re-check:

```
print;       // inside `begin … end`: dumps hypotheses + current goal
proofterm;   // dumps the partial proof term
type t;      // print type of t at this point
compute t;   // normalise t and print
```

These print to stdout during `check`. Wrap a region in
`debug +u;` / `debug -u;` for scoped traces (or `+a` for all flags).

## Reference

The mirrored upstream docs in `doc/` are the source of truth for
syntax and semantics:

| File | Covers |
|---|---|
| [about.md](doc/about.md) | What Lambdapi is, design |
| [getting_started.md](doc/getting_started.md) | `lambdapi init`, first package |
| [options.md](doc/options.md) | Full CLI reference (this file is a summary) |
| [module.md](doc/module.md) | `lambdapi.pkg`, module paths, library root |
| [terms.md](doc/terms.md) | Term syntax: identifiers, `Π`, `λ`, `_`, `?n`, `$P` |
| [commands.md](doc/commands.md) | `symbol`, `rule`, `inductive`, `notation`, `require`, `open`, `builtin`, `coerce_rule`, `unif_rule` |
| [proof.md](doc/proof.md) | `begin`/`end`/`abort`/`admitted`, subgoal `{ … }` blocks |
| [tactics.md](doc/tactics.md) | `apply`, `assume`, `refine`, `induction`, `simplify`, etc. |
| [equality.md](doc/equality.md) | `reflexivity`, `symmetry`, `rewrite` (with SSReflect patterns) |
| [tacticals.md](doc/tacticals.md) | `try`, `repeat`, `orelse`, `eval` |
| [queries.md](doc/queries.md) | `assert`, `compute`, `print`, `type`, `flag`, `debug` |
| [query_language.md](doc/query_language.md) | Syntax for `lambdapi search` queries |
| [dedukti.md](doc/dedukti.md) | `.dk` interop |
| [latex.md](doc/latex.md) | Embedding `.lp` in LaTeX |
| [lambdapi.bnf](doc/lambdapi.bnf) | Full BNF grammar |
