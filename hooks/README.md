# hooks

A Claude Code [PostToolUse hook](https://docs.claude.com/en/docs/claude-code/hooks)
that type-checks Lambdapi (`.lp`) files as the agent edits them.

## What it does

After every `Write` or `Edit` of a `.lp` file, `lp_check.py` runs
`lambdapi check --no-colors --too-long=5` on it and feeds the result back into
the transcript:

- **on failure** — every `[line:col]` diagnostic, each with the `Proof state:`
  block lambdapi prints beneath it kept **verbatim** (hypotheses, separator,
  numbered goals), so the agent can fix the error without a separate round-trip
  to inspect the goals;
- **on success** — a one-line confirmation with elapsed time, so a green edit
  is acknowledged rather than ambiguously silent.

`--too-long=5` makes lambdapi warn about any single command taking over 5s, so
a pathologically slow proof is visible rather than merely felt.

The check is **read-only**: it never passes `-c`, so it writes no `.lpo` object
cache — an edit-time check that did could shadow a later build with a stale
cache or race a separate `lambdapi check -c`. It's silent for non-`.lp` edits and
never fails the turn: if anything goes wrong (no `lambdapi` on `PATH`, a parse
error, a timeout) the edit just proceeds without extra context.

It parses lambdapi's ordinary terminal output rather than a machine-readable
format: `lambdapi check` has no `--json`, and the proof state is printed on
error by default. If a diagnostic can't be parsed, the raw output tail is
surfaced instead, so a failure is never silently swallowed.

## Using it

Installing the [plugin](../README.md) wires this hook up automatically —
`hooks/hooks.json` is merged into your Claude Code session when the plugin is
enabled, and needs `lambdapi` on `PATH`.

Standalone, point a `PostToolUse` hook at the script from your project's
`.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          { "type": "command", "command": "python3 /path/to/hooks/lp_check.py" }
        ]
      }
    ]
  }
}
```

## Imports

The hook needs no per-project configuration — no `--map-dir`. It relies on the
edited file's own `lambdapi.pkg` to resolve in-package and `Stdlib.*` imports,
the same way `lambdapi check FILE.lp` does on the command line. A file that sits
under no package (no `lambdapi.pkg` above it, not under the library root) can't
be mapped and the hook will say so; add a `lambdapi.pkg` at the package root to
fix it.
