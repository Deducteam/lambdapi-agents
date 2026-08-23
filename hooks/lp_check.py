#!/usr/bin/env python3
"""PostToolUse hook: type-check an edited Lambdapi (.lp) file and surface its
diagnostics back to the agent.

The installed lambdapi (combined branch, dev-3.0.0-136+) reports the proof
state inside plain-text errors by default: a red `[file:line:col]` message,
followed by an uncolored block opened by one of

    Proof state before tactic application:
    Proof state after tactic application:
    Proof state:

listing hypotheses, a dashed separator, and the goals. This hook parses the
`[file:line:col]` diagnostics, joining message continuation lines, and keeps
any proof-state block verbatim so the goal display survives intact.

It runs read-only (no `-c`; it never writes a `.lpo`). On success it reports
a one-line confirmation with elapsed time; on failure it renders every error.
Silent for non-.lp files. Never fails the turn (exit 0 always).
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

TIMEOUT = 120       # wall-clock s
_MAX_LINE = 500     # characters per rendered line
_MAX_STATE = 60     # lines kept per proof-state block
_MAX_RAW = 1500     # characters of raw output to surface when nothing parses

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LOC_RE = re.compile(r"^\[(?P<path>[^\]]*?\.lp):(?P<line>\d+):(?P<col>[\d:-]+)\]"
                    r"\s*(?P<msg>.*)$")
STATE_RE = re.compile(r"^Proof state( (before|after) tactic application)?:$")
STRUCT_RE = re.compile(r"^(Start|End) checking |^axiom _ax\d+:")


def _emit(context):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))


def _clip(s, n=_MAX_LINE):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 1] + "…"


class _Block:
    """One `[line:col]` diagnostic: a message plus an optional verbatim
    proof-state tail."""

    def __init__(self, loc, msg):
        self.loc, self.msg, self.state = loc, msg, []

    def feed(self, ln):
        if self.state or STATE_RE.match(ln):
            self.state.append(ln.rstrip())
        elif ln.strip():
            self.msg = (self.msg + " " + ln.strip()).strip()

    def render(self):
        out = f"[{self.loc}] {_clip(self.msg)}".rstrip()
        state = self.state[:_MAX_STATE]
        if len(self.state) > _MAX_STATE:
            state.append(f"… (+{len(self.state) - _MAX_STATE} more lines)")
        if state:
            out += "\n" + "\n".join(_clip(ln) for ln in state)
        return out


def _errors_from_text(out):
    errors, cur = [], None

    def close():
        nonlocal cur
        if cur and (cur.msg or cur.state) \
                and not cur.msg.lower().startswith("warning"):
            errors.append(cur.render())
        cur = None

    for ln in ANSI.sub("", out).splitlines():
        ln = ln.rstrip()
        if STRUCT_RE.match(ln):
            close()
            continue
        m = LOC_RE.match(ln)
        if m:
            close()
            cur = _Block(f"{m['line']}:{m['col']}", m["msg"].strip())
        elif cur is not None:
            cur.feed(ln)
    close()
    return errors


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    tool_input = event.get("tool_input") or {}
    path_s = tool_input.get("TargetFile") or tool_input.get("file_path") or ""
    if not path_s.endswith(".lp"):
        return
    path = Path(path_s)
    try:
        if not path.is_file():
            return
        path = path.resolve()
    except OSError:
        return
    # No `-c`: read-only, never writes a `.lpo`. --too-long=5 surfaces any
    # single command taking >5s.
    cmd = ["lambdapi", "check", "--no-colors", "--too-long=5", str(path)]
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT)
    except FileNotFoundError:
        return
    except subprocess.TimeoutExpired:
        _emit(f"⏱ lambdapi check timed out after {TIMEOUT}s on {path.name} "
              f"— too slow to verify this edit automatically; run "
              f"`lambdapi check {path.name}` manually.")
        return
    dt = time.monotonic() - t0
    if r.returncode == 0:
        _emit(f"✓ lambdapi check passed: {path.name} ({dt:.1f}s)")
        return
    errors = _errors_from_text(r.stdout + "\n" + r.stderr)
    if not errors:
        raw = (r.stderr or r.stdout).strip()
        if not raw:
            return
        errors.append(_clip(ANSI.sub("", raw), _MAX_RAW))
    _emit("`lambdapi check` failed on the file you just edited:\n\n"
          + "\n\n".join(errors))


if __name__ == "__main__":
    main()
