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
license: Apache-2.0
---

# Lambdapi

Lambdapi is a proof assistant based on the λΠ-calculus modulo rewriting:
dependent types + user-declared rewrite rules.

## CLI

The following is the contents of `lambdapi check --help`:
```
NAME
       lambdapi-check - Type-checks the given files.

SYNOPSIS
       lambdapi check [OPTION]… [FILE]…

ARGUMENTS
       FILE
           Source  file  with the [.lp] extension (or with the [.dk] extension
           when using the Dedukti syntax).

OPTIONS
       -c, --gen-obj
           Produce object files with the [.lpo] extension. These object  files
           can  then be read during subsequent calls to avoid re-type-checking
           fo the corresponding source file. Note that an object file is  only
           used  when it is up to date (i.e., more recent than the source). If
           that is not the case then the outdated file is overwritten.

       --confluence=CMD
           Use the command CMD for checking confluence. The command CMD should
           accept HRS-formatted text on its standard input (For more info  see
           http://project-coco.uibk.ac.at/problems/hrs.php) and the first line
           of its standard output should be either "YES", "NO" or "MAYBE".

       --debug=FLAGS
           Enables  the debugging flags specified in FLAGS. Every character of
           FLAGS correspond to  a  flag.  The  available  values  are:  a  for
           metavariables,  b  for  one  lookahead  cell  buffer  lexing, c for
           conversion, d for compilation of decision trees, e for snf,  g  for
           generation  of induction principles, i for type inference/checking,
           k for local confluence, l for library files, m for term building, n
           for parsing, o for scoping, p for pretty-printing, q for rewriting,
           r for rewrite tactic, s for subject-reduction, t for tactics, u for
           unification, v for inverse, w for whnf, x for export,  y  for  why3
           tactic, z for external tools.

       --lib-root=DIR
           Set the library root to be the directory DIR. The library root is a
           common  path  under  which  every module is placed. It has the same
           purpose as the root directory "/" of Unix systems. In  fact  it  is
           possible  to  "mount"  directories  under the library root with the
           "--map-dir" option. Lambdapi uses DIR as  library  root  if  it  is
           provided, otherwise it uses $LAMBDAPI_LIB_ROOT/lib/lambdapi/lib_root
           if the environment variable LAMBDAPI_LIB_ROOT is set, then
           $OPAM_SWITCH_PREFIX/lib/lambdapi/lib_root if OPAM_SWITCH_PREFIX 
           is set or it uses /usr/local/lib/lambdapi/lib_root.

       --map-dir=MOD:DIR
           Map  all the modules having MOD as a prefix of their module path to
           files under the directory DIR. The corresponding modules under  the
           library  root are then rendered inaccessible. This option is useful
           during the development of a library, before it can be installed  in
           the expected folder under the library root.

       --no-colors
           Disable  the use of colors when printing to the terminal. Note that
           the default behaviour is to rely on ANSI escape sequences in  order
           to make the debugging logs more readable.

       --no-sr-check
           Disable the verification that rewrite rules preserve typing.
           UNSOUND: use only for debugging.

       --record-time
           Print  statistics  on  the  time spent in different tasks (parsing,
           typing, etc.). Note that it slows down the program.

       --termination=CMD
           Use the command CMD  for  checking  termination.  The  command  CMD
           should  accept  XTC-formatted  text on its standard input (for more
           info see https://tinyurl.com/XTC-format), and the first line of its
           standard output should be either "YES", "NO" or "MAYBE".

       --timeout=NUM
           Timeout after NUM seconds. The program is interrupted with an error
           as soon as the specified number of seconds is elapsed.

       --too-long=FLOAT (absent=inf)
           Print a warning every time that a command requires more than  FLOAT
           seconds to execute. The command is not interrupted.

       -v NUM, --verbose=NUM
           Set  the verbosity level to NUM. A value smaller or equal to 0 will
           disable all printing (on standard output). Greater numbers lead  to
           more  and more informations being written to standard output.In the
           case of the websearch  command,  a  value  larger  or  equal  to  2
           willprint  the requests received by the server. A value larger than
           3 will also print the responses sent by the server.

       -w, --no-warnings
           Disable the printing of all warnings.

COMMON OPTIONS
       --help[=FMT] (default=auto)
           Show this help in format FMT. The value FMT must be  one  of  auto,
           pager,  groff  or  plain.  With  auto, the format is pager or plain
           whenever the TERM env var is dumb or undefined.

       --version
           Show version information.

EXIT STATUS
       lambdapi check exits with:

       0   on success.

       123 on indiscriminate errors reported on standard error.

       124 on command line parsing errors.

       125 on unexpected internal errors (bugs).

FILES
       A package configuration files lambdapi.pkg can be placed at the root of
       a source tree, so that Lambdapi can determine under  what  module  path
       the  underlying  modules  should be registered (relative to the library
       root). If several candidate package configuration files  are  found  in
       the  parent  folders  of  a  source file, the one in the closest parent
       directory is used.

       The syntax of package configuration files is line-based. Each line  can
       either  be  a  comment  (i.e.,  it  starts  with  a '#') or a key-value
       association of the form "key = value". Two such entries should be given
       for a configuration file to be valid: a package_name entry whose  value
       is an identifier and a root_path entry whose value is a module path.

       An example of package configuration file is given bellow.

            # Lines whose first non-whitespace charater is # are comments
            # The end of a non-comment line cannot be commented.
            # The following two fields must be defined:
            package_name = my_package_name
            root_path = a.b.c
            # Unknown fields like the following are ignored.
            unknown = this is useless

SEE ALSO
       lambdapi(1)
```

## Syntax

The BNF grammar for Lambdapi is as follows:
```
<qid> ::= [<uid> "."]+ <uid>

<id> ::= <uid> | <qid>

<command> ::= "opaque" <qid> ";"
            | "require" <qid>+ ";"
            | "require" [["private"] "open"] <qid>+ ";"
            | "require" <qid> "as" <uid> ";"
            | ["private"] "open" <qid>+ ";"
            | [<exposition>] <modifier>* "symbol" <uid> <param_list>* ":" <term> [<proof> | "≔" <term_proof>] ";"
            | [<exposition>] <modifier>* "symbol" <uid> <param_list>* "≔" <term> [<proof>] ";"
            | [<exposition>] <param_list>* "inductive" <inductive> ("with" <inductive>)* ";"
            | "rule" <rule> ("with" <rule>)* ";"
            | "builtin" <string> "≔" <id> ";"
            | "coerce_rule" <rule> ";"
            | "unif_rule" <unif_rule> ";"
            | "notation" <id> <notation> ";"
            | <query> ";"

<exposition> ::= "private" | "protected"

<side> ::= "left" | "right"

<modifier> ::= [<side>] "associative"
             | "commutative"
             | "constant"
             | "injective"
             | "opaque"
             | "sequential"

<inductive> ::= <uid> <param_list>* ":" <term> "≔" ["|"] [<constructor> ("|" <constructor>)*]

<constructor> ::= <uid> <param_list>* ":" <term>

<rule> ::= <term> "↪" <term>

<unif_rule> ::= <equation> "↪" "[" <equation> (";" <equation>)* "]"

<equation> ::= <term> "≡" <term>

<notation> ::= "infix" [<side>] <float_or_int>
             | "postfix" <float_or_int>
             | "prefix" <float_or_int>
             | "quantifier"

<float_or_int> ::= <float> | <integer>

<param_list> ::= <param>
               | "(" <param>+ ":" <term> ")"
               | "[" <param>+ [":" <term>] "]"

<param> ::= <uid> | "_"

<term> ::= <application> ["→" <term>]
         | [<application>] <bterm>

<application> ::= <head> <arg>*

<bterm> ::= <binder> <abstraction>
          | "let" <uid> <param_list>* [":" <term>] "≔" <term> "in" <term>

<binder> ::= "λ" | "Π" | "`" ["@"] <id>

<head> ::= ["@"] <id>
          | "_"
          | "TYPE"
          | "?" <uid> [<env>]
          | "$" <uid> [<env>]
          | "(" <term> ")"
          | <integer>
          | <string>

<arg> ::= <head> | "[" <term> "]"

<env> ::= "." "[" [<term> (";" <term>)*] "]"

<abstraction> ::= <param_list>+ "," <term>
                | <param> ":" <term> "," <term>

<term_proof> ::= <term>
               | <proof>
               | <term> <proof>

<proof> ::= "begin" <subproof>+ <proof_end>
          | "begin" [<proof_steps>] <proof_end>

<subproof> ::= "{" [<proof_steps>] "}"

<proof_steps> ::= <proof_step> [";"]
                | <proof_step> ";" <proof_steps>

<proof_step> ::= <tactic> <subproof>*

<proof_end> ::= "end" | "abort" | "admitted"

<tactic> ::= <query>
           | "admit"
           | "all_hyps" <term>
           | "apply" <term>
           | "assume" <param>+
           | "assumption"
           | "change" <term>
           | "eval" <term>
           | "fail"
           | "first_hyp" <term>
           | "focus" <integer>
           | "generalize" <uid>
           | "have" <uid> ":" <term>
           | "induction"
           | "orelse" <tactic> <tactic>
           | "refine" <term>
           | "reflexivity"
           | "remove" <uid>+
           | "repeat" <tactic>
           | "rewrite" [<side>] ["." "[" <rwpatt> "]"] <term>
           | "set" <uid> "≔" <term>
           | "simplify"
           | "simplify" <id>
           | "simplify" "rule" "off"
           | "solve"
           | "symmetry"
           | "try" <tactic>
           | "why3" [<string>]

<rwpatt> ::= <term>
            | "in" <term>
            | "in" <uid> "in" <term>
            | <term> "in" <term> ["in" <term>]
            | <term> "as" <uid> "in" <term>

<assert> ::= "assert" | "assertnot"

<test> ::= ":" | "≡"

<switch> ::= "on" | "off"

<query> ::= <assert> <param_list>* "⊢" <term> <test> <term>
          | "compute" <term>
          | "print" [<id> | "unif_rule" | "coerce_rule"]
          | "proofterm"
          | "debug" [("+"|"-") <char>+]
          | "flag" [string> <switch>]
          | "prover" <string>
          | "prover_timeout" <integer>
          | "verbose" <integer>
          | "type" <term>
          | "search" <search>

<relation> ::= "=" | ">" | ">=" | "≥"

<where> ::= "concl" | "hyp" | "spine" | "rule" | "lhs" | "rhs"

<base> ::= "name" "=" <uid>
         | ("type"|"anywhere") ("≥"|">=") ["generalize"] <term>
         | <where> <relation> ["generalize"] <term>
         | "(" <search_query> ")"

<conjunction> ::= <base> ("with" <base>)*

<disjunction> ::= <conjunction> ("|" <conjunction>)*

<search> ::= <disjunction> | <search> "in" <id>
```

## Standard library

The Lambdapi standard library is given by the opam package `lambdapi-stdlib`
and can be found at `$OPAM_SWITCH_PREFIX/lib/lambdapi/lib_root/Stdlib/`.
It contains the following files (use as `require open Stdlib.<name>;`):
| File | Covers |
|---|---|
| `Set.lp` | `Set` type codes, interpretation `τ : Set → TYPE` (builtin `"T"`), base code `ι`, non-emptiness `el` |
| `Prop.lp` | Propositional logic: `Prop`, `π` (builtins `"Prop"`, `"P"`), `⊤ ⊥ ⇒ ¬ ∧ ∨ ⇔` with intro/elim rules |
| `FOL.lp` | First-order quantifiers `∀`/`∃` over `τ a` (builtins `"all"`, `"ex"`), `∃ᵢ`/`∃ₑ` |
| `Eq.lp` | Polymorphic Leibniz equality `=`, `≠`, `eq_refl`, `ind_eq` (builtins `"eq"`/`"refl"`/`"eqind"` needed by `reflexivity`/`rewrite`), `feq`, `eq_sym` |
| `Impred.lp` | Impredicativity: code `o` with `τ o ↪ Prop` |
| `HOL.lp` | Higher-order arrow code `⤳` with `τ (a ⤳ b) ↪ τ a → τ b` |
| `Classic.lp` | Classical logic: excluded middle `em`, `¬¬ₑ`, `∨¬ᵢ`, `∃¬ᵢ` |
| `Epsilon.lp` | Hilbert's choice operator `ε` and its axiom `εᵢ` |
| `FunExt.lp` | Function extensionality axiom `funExt` |
| `PropExt.lp` | Propositional extensionality `propExt` + many equational simplification lemmas on `∧ ∨ ¬ ⇒ ⊤ ⊥ =` |
| `Bool.lp` | Inductive booleans `𝔹`: `not/or/and/if`, `istrue`, reflection lemmas linking to `∧`/`∨` |
| `Comp.lp` | Comparison datatype `Comp` (`Eq`/`Lt`/`Gt`), `opp`, case analysis |
| `Nat.lp` | Peano naturals `ℕ` (ssrnat-style): `+ - * ^ ! ≤ < max min`, decidable equality `eqn`, literal builtins `"0"`–`"10"`, many lemmas |
| `Pos.lp` | Positive binary numbers `ℙ` (`H`/`O`/`I`): `succ`, `add`, `compare`, `val : ℙ → ℕ` |
| `Z.lp` | Binary integers `ℤ` over `ℙ`: `+ - * —` (negation), comparison `≐`, `≤`, literal builtins |
| `Q.lp` | Rationals `ℚ` as fractions of `ℤ`: `qadd`, `qmul`, `qdiv`, normalization |
| `List.lp` | Polymorphic lists `𝕃` (seq.v-style): `++ map filter rev nth size iota all has count perm_eq …` |
| `Prod.lp` | Cartesian product `×`, pairing `‚`, projections `₁`/`₂` |
| `Option.lp` | Option type: `none`, `some` |
| `String.lp` | Builtin `String` type and its `Set` code |
| `Tactic.lp` | Reified `Tactic` type for metaprogramming: `#apply`, `#assume`, `#rewrite`, … with the `"apply"` etc. builtins |
| `Conj.lp` | Meta-theorems for n-ary conjunctions (clause lists): `∧ᵢₙ`, `∧ₑₙ`, `conj` |
| `Disj.lp` | Meta-theorems for n-ary disjunctions: `∨ᵢₙ`, `∨ₑₙ`, `permute`, `delete`, clause transforms |


## Documentation

Documentation for Lambdapi can be found in `references/`: 

| File | Covers |
|---|---|
| [about.md](references/about.md) | What Lambdapi is, design |
| [getting_started.md](references/getting_started.md) | `lambdapi init`, first package |
| [options.md](references/options.md) | Full CLI reference (this file is a summary) |
| [module.md](references/module.md) | `lambdapi.pkg`, module paths, library root |
| [terms.md](references/terms.md) | Term syntax: identifiers, `Π`, `λ`, `_`, `?n`, `$P` |
| [commands.md](references/commands.md) | `symbol`, `rule`, `inductive`, `notation`, `require`, `open`, `builtin`, `coerce_rule`, `unif_rule` |
| [proof.md](references/proof.md) | `begin`/`end`/`abort`/`admitted`, subgoal `{ … }` blocks |
| [tactics.md](references/tactics.md) | `apply`, `assume`, `refine`, `induction`, `simplify`, etc. |
| [equality.md](references/equality.md) | `reflexivity`, `symmetry`, `rewrite` (with SSReflect patterns) |
| [tacticals.md](references/tacticals.md) | `try`, `repeat`, `orelse`, `eval` |
| [queries.md](references/queries.md) | `assert`, `compute`, `print`, `type`, `flag`, `debug` |
| [query_language.md](references/query_language.md) | Syntax for `lambdapi search` queries |
| [dedukti.md](references/dedukti.md) | `.dk` interop |
| [latex.md](references/latex.md) | Embedding `.lp` in LaTeX |
