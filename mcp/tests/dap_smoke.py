#!/usr/bin/env python3
"""Smoke test for `lambdapi dap`.

Drives the DAP server via stdio against `tests/fixtures/proof.lp`,
which has two `opaque symbol …` proofs with simple tactics
(`reflexivity`, `assume`, `symmetry`, `apply`).

The test prints an annotated transcript of requests/responses/events
to stdout. It is intentionally not a pytest — DAP requires careful
sequencing and event filtering that's clearer to read step-by-step.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

LAMBDAPI = os.environ.get(
    "LAMBDAPI",
    os.path.expanduser("~/.opam/default/bin/lambdapi"),
)
PROOF = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures",
    "proof.lp",
)


class DapClient:
    def __init__(self, proc):
        self.proc = proc
        self.seq = 0
        self.events = []
        self.responses = {}  # request_seq -> response
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                return
            if not line.startswith(b"Content-Length:"):
                continue
            n = int(line.split(b":", 1)[1].strip())
            sep = self.proc.stdout.readline()  # \r\n
            assert sep.strip() == b""
            body = self.proc.stdout.read(n)
            msg = json.loads(body.decode())
            with self.cv:
                t = msg.get("type")
                if t == "response":
                    self.responses[msg["request_seq"]] = msg
                elif t == "event":
                    self.events.append(msg)
                self.cv.notify_all()

    def send(self, command, arguments=None):
        self.seq += 1
        body = {
            "seq": self.seq,
            "type": "request",
            "command": command,
        }
        if arguments is not None:
            body["arguments"] = arguments
        raw = json.dumps(body).encode()
        self.proc.stdin.write(b"Content-Length: " + str(len(raw)).encode() + b"\r\n\r\n")
        self.proc.stdin.write(raw)
        self.proc.stdin.flush()
        return self.seq

    def request(self, command, arguments=None, timeout=10.0):
        seq = self.send(command, arguments)
        deadline = time.monotonic() + timeout
        with self.cv:
            while seq not in self.responses:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"no response to {command}")
                self.cv.wait(remaining)
            return self.responses.pop(seq)

    def wait_for_event(self, name, timeout=10.0):
        deadline = time.monotonic() + timeout
        with self.cv:
            while True:
                for i, ev in enumerate(self.events):
                    if ev.get("event") == name:
                        return self.events.pop(i)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"no {name} event")
                self.cv.wait(remaining)


def banner(s):
    print(f"\n=== {s} ===")


def show(label, obj):
    print(f"{label}: {json.dumps(obj, ensure_ascii=False, indent=2)}")


def main():
    if not os.path.isfile(PROOF):
        print(f"missing {PROOF}", file=sys.stderr); return 2
    if not os.access(LAMBDAPI, os.X_OK):
        print(f"missing {LAMBDAPI}", file=sys.stderr); return 2

    print(f"binary : {LAMBDAPI}")
    print(f"program: {PROOF}")

    proc = subprocess.Popen(
        [LAMBDAPI, "dap"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    cli = DapClient(proc)
    try:
        banner("initialize")
        r = cli.request("initialize", {"adapterID": "lambdapi", "linesStartAt1": True})
        show("response", r)

        # Server should immediately emit `initialized` event.
        ev = cli.wait_for_event("initialized")
        show("event", ev)

        banner("setBreakpoints (mix of tactic + non-tactic lines)")
        # Line 11 = `symmetry;` (real tactic).
        # Line 7 = blank line (no tactic at or after, before line 11
        # there's only `begin` on line 9 / `assume` on 10) — should
        # snap to 10.
        # Line 99 = past EOF — should report verified:false.
        r = cli.request("setBreakpoints", {
            "source": {"path": PROOF},
            "breakpoints": [{"line": 11}, {"line": 7}, {"line": 99}],
        })
        show("response", r)

        banner("launch (stopOnEntry=False)")
        r = cli.request("launch", {
            "program": PROOF,
            "stopOnEntry": False,
        })
        show("response", r)

        banner("configurationDone")
        r = cli.request("configurationDone")
        show("response", r)

        banner("expecting stopped@breakpoint")
        ev = cli.wait_for_event("stopped", timeout=15.0)
        show("event", ev)

        banner("threads")
        r = cli.request("threads")
        show("response", r)

        banner("stackTrace")
        r = cli.request("stackTrace", {"threadId": 1})
        show("response", r)

        banner("scopes")
        r = cli.request("scopes", {"frameId": 1})
        show("response", r)

        banner("variables (Goals scope)")
        r = cli.request("variables", {"variablesReference": 1})
        show("response", r)

        # Try expanding goal[0]'s hyps if it has any.
        gs = r["body"]["variables"]
        if gs and gs[0].get("variablesReference", 0) != 0:
            banner(f"variables (goal[0] hyps, ref={gs[0]['variablesReference']})")
            r = cli.request("variables", {
                "variablesReference": gs[0]["variablesReference"],
            })
            show("response", r)

        banner("next (step)")
        r = cli.request("next", {"threadId": 1})
        show("response", r)

        ev = cli.wait_for_event("stopped", timeout=15.0)
        show("event", ev)

        banner("variables after step")
        r = cli.request("variables", {"variablesReference": 1})
        show("response", r)

        gs = r["body"]["variables"]
        if gs and gs[0].get("variablesReference", 0) != 0:
            banner(f"variables (post-step goal[0] hyps, ref={gs[0]['variablesReference']})")
            r = cli.request("variables", {
                "variablesReference": gs[0]["variablesReference"],
            })
            show("response", r)

        banner("continue")
        r = cli.request("continue", {"threadId": 1})
        show("response", r)

        banner("waiting for terminated/exited")
        ev = cli.wait_for_event("terminated", timeout=15.0)
        show("event", ev)
        ev = cli.wait_for_event("exited", timeout=5.0)
        show("event", ev)

        banner("disconnect")
        r = cli.request("disconnect")
        show("response", r)

        return 0
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        # Print stderr tail for debugging.
        err = proc.stderr.read().decode(errors="replace")
        if err:
            print("\n--- stderr tail ---")
            print(err[-2000:])


if __name__ == "__main__":
    sys.exit(main())
