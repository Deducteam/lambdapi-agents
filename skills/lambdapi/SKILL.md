---
name: lambdapi
description: >
  Write, debug, and check Lambdapi (.lp) proof-assistant code.
  TRIGGER when: editing .lp files, debugging lambdapi errors, writing
  proofs / rewrite rules / inductive types, or when the user mentions
  lambdapi or Lambdapi.
  DO NOT TRIGGER when: editing OCaml, Python, or other non-.lp code,
  even if it generates .lp output.
allowed-tools: Read, Grep, Glob, Bash(lambdapi *), mcp__lambdapi__*
license: Apache-2.0
---

# Lambdapi

Lambdapi is a proof assistant based on the λΠ-calculus modulo rewriting:
dependent types + user-declared rewrite rules. Proofs are tactic scripts
that elaborate to terms; rewrite rules extend the kernel's reduction.

## MCP tools — use these first

When the `mcp__lambdapi__*` tools are available, prefer them over `lambdapi check` in a shell — they share an LSP session and return structured output.

- `lambdapi_check file [all_errors=false] [stop_on_first_failure=true]` — type-check one or more files. Pass a string for a single file (`{ok: true, file}` on success; `{ok: false, file, errors}` on failure); pass a **list of strings** for batch-checking reusing one LSP session (`{ok, passed, failed, read_errors, summary}`). First error only per file by default (matches the CLI); pass `all_errors=true` for the full sorted list. Batch mode short-circuits on the first failing file by default (again matching the CLI on multi-file input); pass `stop_on_first_failure=false` to visit every file.
- `lambdapi_goals file line` — proof state at a 1-based line as a flush-left `pretty` string: one hypothesis per line, then `⊢ target`. Multiple goals are labelled `[i]` and indented. `no goals` when the state is empty.
- `lambdapi_try file line tactics [mode='insert']` — probe one or more tactics without touching disk. `tactics` is a **list of strings**; `mode='insert'` inserts each tactic before `line`, `mode='replace'` overwrites `line`. Returns `pre` (shared by all attempts) and `attempts: [{tactic, ok, closed, progress, post?}]`. `ok` = no error diagnostic on the probe line; `closed` = `pre` had ≥1 goal and `post` has 0; `progress` = goal state changed. `ok` alone ≠ useful — always check `closed` / `progress`.
- `lambdapi_query file line query` — run a lambdapi query at `line`. `line` is a lower bound: the query snaps forward to the next top-level statement boundary, so any line inside a `begin…end` block (or past EOF) works and the reply reports `effective_line` when the snap moved the insertion point. `query` is the verb plus payload as one string: `"type X"`, `"print X"` (shows declaration + body — subsumes hover / go-to-def), `"compute t"`, `"search \"...\""`.
- `lambdapi_symbols file` — symbols declared in a file: top-level `symbol`/`inductive`, each inductive's constructors, and its auto-generated `ind_<Type>` induction principle. Filtered against a local parse to drop transitively-imported noise.
- `lambdapi_axioms files [scope='project']` — audit unproved assumptions. `scope='file'` = just the inputs; `'project'` = follow `require` but skip files under lib-root (Stdlib); `'all'` = full transitive scan including Stdlib. Returns `assumptions` (bodyless symbols, flagged `propositional` iff type is `π …`), `defined_by_rules` (bodyless symbols later given rewrite rules — fine), `rewrite_rules`, `admits`, plus `scanned_files` and `unresolved_imports`.

**Workflow:** edit → `lambdapi_check` → on error, `lambdapi_goals` at the failing line → `lambdapi_try` (pass a list so you can race a few candidates) to converge on a fix → write the fix in. Then re-`check` and `axioms` before declaring done.

## Surface syntax

- **Comments** `// line`, `/* block, nested */`. Block comments preserve line numbers in MCP output but strip text.
- **Identifiers** are arbitrary UTF-8 minus `\t\r\n :,;(){}[]".@$|?/` and bare integers. Escape weird names with `{| ... |}`.
- **Operators need surrounding whitespace.** `q*a` is one identifier (the parser will error `Unknown symbol q*a.`). Always write `q * a`, `r +1` (postfix successor), `a + b`.
- **`+1` (postfix) ≠ `+ 1` (binary +).** `n +1` is the successor constructor on ℕ; `n + 1` is addition. The kernel reduces `n + 1` to `n +1` via stdlib rules but they are syntactically different — match accordingly when writing rewrite rules.
- **Quantifier binders** use the backtick form: `` `∀ x, P x `` and `` `∃ x, P x `` (not the bare `∀ x, …`).
- **Qualified names** `Stdlib.Nat.addnC`. Optional with `open`.
- Commands end in `;`. Inside a proof, tactics also end in `;`, except a tactic followed by subgoal blocks `{ … }` takes **no** `;` between them.

## Top-level commands

```
symbol N : TYPE;                          // declared, no body → axiom
symbol z : N ≔ ...;                       // defined
opaque symbol thm : T ≔ begin ... end;    // proved, never unfolded
constant symbol c : T;                    // no rules permitted
injective symbol f : A → B;               // f a ≡ f b ⇒ a ≡ b
commutative symbol _+_ : ℕ → ℕ → ℕ;       // adds f t u ≡ f u t to conversion
associative left commutative                // AC: terms get put in canonical form
  symbol _∪_ : Set → Set → Set;
sequential symbol f : T;                  // rules tried in source order — WARNING: can break confluence/SR

inductive T : TYPE ≔                      // generates ind_T + reduction rules
  | c1 : T
  | c2 : A → T;
inductive Tree : TYPE ≔                   // mutual: link with `with`
  | node : Forest → Tree
with Forest : TYPE ≔
  | nil  : Forest
  | cons : Tree → Forest → Forest;        // generates ind_Tree AND ind_Forest

rule f (s $n) ↪ g $n;                     // $-prefixed: pattern variable
rule $x + 0 ↪ $x
with $x + s $y ↪ s ($x + $y);             // chained with `with`

notation + infix left 6;                  // priority is float (5.5 fits in)
notation ¬ prefix 35;
notation ∀ quantifier;                    // `∀ x, P x` desugaring

require open Stdlib.Nat;                  // import + open
require Stdlib.Bool as B;                 // alias only
private open Foo;                         // open only here, not for dependents

builtin "0" ≔ z;                          // map literal "0" / `0` to symbol z
```

Modifiers compose: `private opaque symbol …`, `sequential injective symbol …`, etc. `private` and `protected` are **expositions** (visibility); the rest are **modifiers** (semantics).

## Modules and packages

- File `foo/bar/baz.lp` becomes module `foo.bar.baz`, rooted at the package root.
- `lambdapi.pkg` at the package root: `package_name = mything\nroot_path = MyThing`.
- `require open A.B` makes A.B's symbols accessible unqualified. Without `open`, qualify every use.
- `require A.B as C` introduces alias `C.symbol`.
- `private open` does **not** propagate to files that `require` you.
- The MCP's `lambdapi_axioms` walks `require` transitively and resolves modules via every `lambdapi.pkg` it finds upward from the input file plus the lib root.

## Term language

```
TYPE                                      // sort of types
Π (x:A) (y:B), C                          // dependent product
λ (x:A) y, t                              // λ; later params can omit type
A → B                                     // sugar for Π _:A, B
let x ≔ t in u                            // local binding
f x y                                     // application (left-assoc)
_                                         // fresh metavariable / wildcard
?n.[x;y]                                  // explicit metavariable in env
$P.[x;y]                                  // pattern variable (rules only)
@f a b                                    // disable ALL implicits, supply by hand
f [a] b                                   // explicit value for an implicit arg
`∀ x, P x                                 // quantifier (sugar via `notation … quantifier`)
```

Implicit-arg subtleties:
- Each `_` in implicit position is a **fresh** metavariable per occurrence.
- When `refine`/`apply` can't infer an implicit, you typically see "Missing subproofs (0 subproofs for N subgoals)" with `?n: ℕ` hanging around. Cure: `@symbol explicit args` or `[type]` for individual implicits.

## Inductive types

```
inductive ℕ : TYPE ≔
  | _0  : ℕ
  | +1  : ℕ → ℕ;
notation +1 postfix 100;
```

The kernel auto-generates the induction principle (e.g. `ind_ℕ : Π p, π(p _0) → (Π n, π(p n) → π(p (n +1))) → Π n, π(p n)`) plus the matching reduction rules. The `induction` tactic uses these.

Parametric: `(a:Set) inductive List : TYPE ≔ …;`.

## Rewrite rules

- Pattern variables prefix `$`. Their environment `$P.[x;y]` lists which bound variables they may depend on. Bare `$P` is shorthand for `$P.[]` and is forbidden under a binder.
- **Pattern variables cannot appear at the head of an application**: `$F.[] x ↪ …` is rejected. The flipped form `x $F.[]` is fine.
- Higher-order patterns à la Miller: `rule diff (λ x, $F.[x]) ↪ …`.
- Multiple rules per `rule … with … with …;`. The whole block is one statement.
- **Confluence and termination are your responsibility.** Lambdapi warns on critical pairs; `--confluence` plugs in an external checker.
- **Subject reduction must hold.** A rule that produces an ill-typed RHS makes the kernel unsound. `--no-sr-check` disables the check; do not use it.
- Rules can be non-linear (`rule minus $x $x ↪ 0`) and overlap; the kernel handles both, but you have to ensure confluence.
- Defined symbols are allowed in the LHS — Lambdapi is more permissive than Coq/Agda here.

## Proof mode

```
opaque symbol thm (n : ℕ) (h : π(n = 0)) : π(0 = n) ≔
begin
  assume n h;       // REQUIRED: parameters become Π-binds in the proof goal
  symmetry;
  apply h;
end;
```

- `begin` opens proof mode, `end` closes successfully (all goals must be discharged), `abort` discards, `admitted` adds axioms for remaining goals.
- The current goal is the **focused** one; tactics act on it. Subgoals from a tactic that produces N goals must be wrapped in N `{ … }` blocks.
- **No `;` between a tactic and its `{ … }` blocks.** `induction { … } { … };` is correct; `induction; { … } { … };` is a syntax error ("Expected: abort, admitted, end").

## Tactics

| Tactic | Effect |
|---|---|
| `assume x y …` | Introduce one Π-bound variable per name |
| `apply t` | Refine goal with `t _ … _` (underscores for unknowns) |
| `refine t` | Like `apply` but `t` may contain `_` and `?n` metavariables explicitly |
| `simplify` | β-normalize + apply rewrite rules everywhere; fails if no progress |
| `simplify f` | Apply `f`'s rules only (much faster — prefer this when possible) |
| `simplify rule off` | β-only |
| `reflexivity` | Close `π (t = t)` |
| `symmetry` | Flip `π (t = u)` to `π (u = t)` |
| `rewrite h` | Rewrite L→R in goal using `h : L = R`. Syntactic — see below |
| `rewrite left h` | Rewrite R→L. **Substitutes EVERY occurrence of the RHS** — see below |
| `rewrite .[pat] h` | SSReflect-style positional rewrite — see below |
| `induction` | Apply ind-principle to the inductive head of the goal |
| `have h : T { proof }` | Local lemma; `h : T` becomes a new hypothesis |
| `change t` | Replace goal with convertible `t` |
| `generalize x` | Move `x` from context back into a Π-binding |
| `set x ≔ t` | Add a local definition |
| `remove h` | Drop a hypothesis (must not be referenced elsewhere) |
| `solve` | Discharge all pending unification goals at once |
| `why3 ["alt-ergo"]` | Punt to an SMT backend (needs the `eq`/`bot`/`top`/… builtins) |
| `admit` | Close the current goal with an axiom (do not ship) |
| `fail` | Always fails — useful as a checkpoint while developing |

### The `rewrite` tactic — semantics and footguns

**`rewrite h` is syntactic, not up-to-reduction.** Two definitionally
equal expressions may fail to match. Three common shapes:

1. *Kernel reduced past the pattern.* If a rewrite rule fires before
   you apply `rewrite h`, the LHS that `h` wants to match may no longer
   appear verbatim. Fix: state the pre-reduction form explicitly with
   `have h' : π (LHS_pre = LHS_post) { reflexivity }; rewrite h';
   rewrite h;`, or `simplify;` first to put both sides in the same
   normal form.
2. *Auto-reduction has already reshaped the goal.* Rewrite rules on
   operators (Stdlib's `+` normalises left-assoc to right-assoc) can
   make a rewrite appear to "do nothing". Always inspect the post-state
   with `lambdapi_goals` when a rewrite that "should" have moved
   something didn't.
3. *Defined numeric literals.* In Stdlib, `_1 ≔ _0 +1`, `_2 ≔ _1 +1`,
   … — so writing `1` as an argument produces the defined symbol `_1`,
   while an already-unfolded `_0 +1` in the goal is a different
   syntactic shape. Cheapest fix: `simplify;` first — it unfolds the
   numeric definitions uniformly.

**`rewrite left h` substitutes EVERY occurrence of the RHS.** With
`h : r +1 = a`, `rewrite left h` turns every `a` in the goal into
`r +1` — including the `a` inside `q * a`. To substitute only one
position, either use a positional pattern (see below) or reach for
`feq`-transport: `refine feq (λ z, q * a + z) h` rebuilds the goal
with the substitution boxed inside the lambda.

**`rewrite` only acts on the goal.** There is no Coq-style
`rewrite h in hyp`; the `in` inside SSReflect's `.[…]` pattern is a
*context qualifier on the goal* (restrict the match to a named subterm
of the goal — see below), not a hypothesis selector. To substitute
inside a named hypothesis, either `generalize h; rewrite …; assume h;`
(lift the hypothesis into the goal, rewrite, put it back) or go via
`ind_eq : π (x = y) → Π p, π (p y) → π (p x)` — note the direction is
reversed from what you'd guess. From `e : 1 = a` and `hab : π (P a)`,
`ind_eq e (λ x, P x) hab` gives `π (P 1)`; if you only have
`e : a = 1`, compose with `eq_sym e` first.

### SSReflect rewrite patterns

`rewrite` accepts an optional positional pattern in `.[ … ]` immediately
before the equation. The dot is part of the syntax — `rewrite [pat] h`
without it is a parse error. Use these to surgically rewrite one
position when blanket `rewrite h` would substitute too aggressively.

```
rewrite .[add _ b] addcomm;            // first match of `add _ b`
rewrite .[x in (add x b)] addcomm;     // bind `x`, rewrite where x appears in (add x b)
rewrite .[in x in (add x c)] eq;       // outer ctx `in (add x c)`, then x
rewrite .[(add a _) in x in (add c x)] addcomm;  // nested context
rewrite .[x as h in (add x b)] addcomm; // bind both occurrence and rewrite witness
```

Pattern grammar (from the docs):

```
<rw_patt> ::= <term>                        // pick a literal subterm
            | "in" <term>                   // rewrite inside <term>
            | "in" <ident> "in" <term>      // ident ranges over occurrences in <term>
            | <ident> "in" <term>           // bind ident to a subterm of <term>
            | <term> "in" <ident> "in" <term>  // outer context first, then ident
            | <term> "as" <ident> "in" <term>  // bind both witness and rewrite focus
```

When `feq (λ z, …)` transport is too coarse, reach for `.[x in …]`. See
`tests/OK/rewrite1.lp` in the lambdapi source for ~20 worked examples.

## Tacticals

```
t1 ; t2          // sequential — t2 runs on every goal t1 produced
t1 | t2          // orelse: try t1, on failure try t2
try t            // succeed-or-no-op
repeat t         // apply t until it stops making progress
eval t           // normalise tactic expression first
```

`apply ∨ₑ X { case_1 } { case_2 }` is the canonical inline case-split idiom — the two `{ … }` slots discharge the two arrows of `∨ₑ`. Same shape works for any constructor that produces N subproofs.

## Queries

```
compute t;                 // normalise t and print
type t;                    // print the inferred type of t
print foo;                 // show foo's signature, rules, notation
print;                     // current goals (in proof mode)
search "QUERY";            // full-text search against ~/.LPSearch.db
proofterm;                 // show the in-progress proof term
flag "print_implicits" on; // toggle a printer flag
flag "eta_equality" on;    // ENABLE η-reduction in the rewrite engine
                           //   (off by default — silent failures on η-redexes)
debug +e;                  // toggle debug mode flags
assert ⊢ t : T;            // type-check assertion (passes silently)
assertnot ⊢ t : T;         // negative assertion
```

`lambdapi_query` accepts the verb plus payload as one string: `query="compute (1 + 1)"` etc.

## Hard-won patterns

These are real footguns that bite during nontrivial proofs. Internalise them.

**Missing-implicit failures are usually silent.** When `refine f x y z` returns "Missing subproofs (0 subproofs for N subgoals)" with stray `?n: T` metavariables, the inference engine couldn't solve an implicit. Switch to `@f impl_args explicit_args` — e.g. `refine @cong_add p (a^p) a 1 1 ih (cong_refl p 1)`. This nearly always fixes it.

**Strong / course-of-values induction is not built in for `ℕ`.** Derive it: define `cov_aux : Π n m, m < n → P m` by ordinary induction, then `strong_ind P h n := cov_aux P h (n +1) n (ltnSn n)`.

**Nat literals ≥1 print with an underscore.** Stdlib declares `builtin "0" ≔ _0` and `builtin "nat_succ" ≔ +1`, so the parser desugars source `3` to `_0 +1 +1 +1`, and the printer shows `_0` as `0`. But `_1`, `_2`, … are *defined symbols* (`_1 ≔ _0 +1`, …) with no `builtin "1"` / `"2"` / … reverse-mapping, so a goal containing `_0 +1` gets folded back to the defined name `_1` by the printer. Don't confuse `_1` (literal one) with `?1` (metavariable one) — different prefix. See the `rewrite` footgun section for the practical consequence.

**Re-association on `+` — pick the right lemma.** Stdlib has several similarly-named rearrangement lemmas; they are easy to confuse and the error messages don't tell you which one you needed.

| Lemma | Statement | Use when |
|---|---|---|
| `addnC m n` | `m + n = n + m` | swap two addends |
| `addnA m n p` | `(m + n) + p = m + (n + p)` | re-associate a left-assoc chunk (rarely needed — kernel auto-right-associates) |
| `addnAC m n p` | `m + (n + p) = n + (m + p)` | **most common** — commute the inner two in a right-assoc triple |
| `addnCA m n p` | `(m + n) + p = (m + p) + n` | rotate a left-assoc triple: move the middle to the end |
| `addnACA m n p q` | `(m + n) + (p + q) = (m + p) + (n + q)` | interleave two pairs |

When the goal is already in right-assoc canonical form (`x + (y + (z + w))`) and you need to bring a later term forward, the answer is almost always one or more `addnAC`. `addnCA` operates on left-assoc (`(x + y) + z`) — if you see "No subterm matches" when passing an expression that's in right-assoc form, you probably meant `addnAC`.

**`apply ⊥ₑ` often can't infer the result type.** Use `refine @⊥ₑ (TARGET_PROP) X` — explicit target prop after `@`, then the proof of `⊥`.

## Common errors

| Error | Diagnosis |
|---|---|
| `Unknown symbol q*a.` | Missing space — write `q * a` |
| `Missing subproofs (0 for N)` | Either you didn't write `{ … }` blocks, or implicit-arg inference left metavariables — use `@`-explicit |
| `Expected: abort, admitted, end.` | A stray `;` between a tactic and a `{ … }` block |
| `is not a product` | You `assume`d a parameter that you then meant to `induction` on |
| `No subterm of [X] matches [Y]` | `rewrite` is syntactic; the pattern `[Y]` isn't a literal subterm of goal `[X]`. See the `rewrite` tactic footgun section — common causes are kernel-reduction, `_1` vs `_0 +1` unfolding, and wrong associativity (`addnCA` vs `addnAC`). |
| `not in scope` | Missing `require open`, or symbol name typo, or in a private/protected section you didn't import |
| `Unification goals are unsatisfiable` | Type mismatch reduced to a constraint the kernel couldn't solve. Often the same root cause as missing implicits — try `@` |
| `Pattern variable … can be replaced by '_'` | A `$x` in a rule never appears on the RHS — replace with `_` |

## CLI cheatsheet

When the MCP isn't available (or you need something the MCP doesn't wrap), drop to the binary.

```
lambdapi check FILE.lp                # type-check
lambdapi check -c FILE.lp             # also write .lpo object cache (skipped on stale source)
lambdapi check --no-sr-check FILE.lp  # disable subject-reduction check (UNSOUND — debugging only)
lambdapi check --confluence=CMD …     # plug in an external confluence checker (HRS input)
lambdapi check --termination=CMD …    # ditto for termination (XTC input)
lambdapi check --timeout=N FILE.lp    # hard kill after N seconds
lambdapi check --too-long=F FILE.lp   # warn on commands taking > F seconds
lambdapi check --debug=FLAGS FILE.lp  # see below for FLAGS chars
lambdapi check --map-dir=MOD:DIR …    # mount DIR as module prefix MOD
lambdapi check --lib-root=DIR …       # override the library root

lambdapi init my.package.path         # scaffold a new package (creates lambdapi.pkg)
lambdapi parse FILE.lp                # syntax-only (no typing) — fast smoke test
lambdapi lsp                          # the LSP backend the MCP server wraps
lambdapi version                      # print version
lambdapi index FILE.lp                # populate ~/.LPSearch.db for `search` queries
lambdapi search "QUERY"               # query that index
```

**`--debug=FLAGS`** chars — concatenate any subset to enable trace output:
`a` metavariables, `c` conversion, `d` decision trees, `e` snf, `g` ind-principle generation, `i` type inference/checking, `k` local confluence, `l` library files, `m` term building, `n` parsing, `o` scoping, `p` pretty-printing, `r` rewrite tactic, `s` subject reduction, `t` tactics, `u` unification, `v` inverse, `w` whnf, `x` export, `y` why3, `z` external tools. So `--debug=iut` traces type inference + unification + tactics.

**Library-root resolution** (in priority order): `--lib-root` flag → `$LAMBDAPI_LIB_ROOT/lib/lambdapi/lib_root` → `$OPAM_SWITCH_PREFIX/lib/lambdapi/lib_root` → `/usr/local/lib/lambdapi/lib_root`.

**`.lpo` object cache:** generated next to `.lp` source files when `-c` is passed (or by the LSP when checking). Used on subsequent runs if newer than the source. Delete `.lpo` files when changing lambdapi versions or when `root_path` in `lambdapi.pkg` changes — stale caches give confusing errors.

**Exit codes:** `0` ok, `123` indiscriminate errors, `124` CLI parse errors, `125` internal bug.

## Reference

- **Stdlib** (typically at `$OPAM_SWITCH_PREFIX/lib/lambdapi/lib_root/Stdlib/`): `Nat.lp`, `Bool.lp`, `Eq.lp`, `Prop.lp`, `FOL.lp`, `Set.lp`, `List.lp`, … Many useful lemmas live here — search before re-proving (`grep` the file or `lambdapi_query … "search \"...\""`).
- **Lambdapi source and docs** ([github.com/Deducteam/lambdapi](https://github.com/Deducteam/lambdapi)): `doc/tactics.rst`, `doc/terms.rst`, `doc/commands.rst`, `doc/equality.rst`, `doc/lambdapi.bnf` are the most useful single files. `tests/OK/` is a goldmine of small worked examples.
- **Online docs:** [lambdapi.readthedocs.io](https://lambdapi.readthedocs.io/).
