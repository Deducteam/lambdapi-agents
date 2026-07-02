#!/usr/bin/env python3
"""M2/M3 smoke test for `lambdapi dap`.

Walks through:
- launch with stopOnEntry=False; bps on lines 10 and 12 of proof.lp.
- Step over until line 12 reached.
- evaluate `print eq_refl` (a query) — should succeed and return text.
- evaluate `compute (0 + 1)` — should compute.
- evaluate `garbage` — should fail cleanly.
- stepBack — proof rewinds; expect stopped at earlier index.
- continue — proof finishes.
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
        self.responses = {}
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
            sep = self.proc.stdout.readline()
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
        body = {"seq": self.seq, "type": "request", "command": command}
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
                rem = deadline - time.monotonic()
                if rem <= 0:
                    raise TimeoutError(f"no response to {command}")
                self.cv.wait(rem)
            return self.responses.pop(seq)

    def wait_for_event(self, name, timeout=10.0):
        deadline = time.monotonic() + timeout
        with self.cv:
            while True:
                for i, ev in enumerate(self.events):
                    if ev.get("event") == name:
                        return self.events.pop(i)
                rem = deadline - time.monotonic()
                if rem <= 0:
                    raise TimeoutError(f"no {name} event")
                self.cv.wait(rem)


def banner(s): print(f"\n=== {s} ===")
def show(label, obj): print(f"{label}: {json.dumps(obj, ensure_ascii=False, indent=2)}")


def get_first_goal(cli):
    r = cli.request("variables", {"variablesReference": 1})
    gs = r["body"]["variables"]
    return gs[0]["value"] if gs else None


def get_pause_pos(cli):
    r = cli.request("stackTrace", {"threadId": 1})
    fs = r["body"]["stackFrames"]
    if not fs: return None
    return f"{fs[0]['source']['name']}:{fs[0]['line']}"


def main():
    proc = subprocess.Popen([LAMBDAPI, "dap"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, bufsize=0)
    cli = DapClient(proc)
    try:
        cli.request("initialize", {"adapterID": "lambdapi", "linesStartAt1": True})
        cli.wait_for_event("initialized")
        cli.request("setBreakpoints", {
            "source": {"path": PROOF},
            "breakpoints": [{"line": 10}, {"line": 12}],
        })
        cli.request("launch", {
            "program": PROOF, "stopOnEntry": False, "debug": "u"})
        cli.request("configurationDone")

        banner("stop @ line 10 (assume)")
        cli.wait_for_event("stopped", timeout=15.0)
        print("goal:", get_first_goal(cli))

        banner("evaluate `print eq_refl`")
        r = cli.request("evaluate", {"expression": "print eq_refl"})
        show("response", r)

        banner("evaluate `compute (0 + 1)`")
        r = cli.request("evaluate", {"expression": "compute (0 + 1)"})
        show("response", r)

        banner("evaluate `garbage tokens`")
        r = cli.request("evaluate", {"expression": "garbage tokens"})
        show("response", r)

        banner("continue → stop @ line 12 (apply h)")
        cli.request("continue", {"threadId": 1})
        cli.wait_for_event("stopped", timeout=15.0)
        print("pos:", get_pause_pos(cli), "goal:", get_first_goal(cli))

        banner("stepBack")
        cli.request("stepBack", {"threadId": 1})
        cli.wait_for_event("stopped", timeout=15.0)
        print("pos:", get_pause_pos(cli), "goal:", get_first_goal(cli))

        banner("stepBack again")
        cli.request("stepBack", {"threadId": 1})
        cli.wait_for_event("stopped", timeout=15.0)
        print("pos:", get_pause_pos(cli), "goal:", get_first_goal(cli))

        banner("continue twice → finish")
        cli.request("continue", {"threadId": 1})
        # stepBack put us back at line 10; continue hits line 12 again, then finish.
        cli.wait_for_event("stopped", timeout=15.0)
        cli.request("continue", {"threadId": 1})
        cli.wait_for_event("terminated", timeout=15.0)
        cli.wait_for_event("exited", timeout=5.0)

        cli.request("disconnect")
        return 0
    finally:
        try: proc.stdin.close()
        except Exception: pass
        try: proc.wait(timeout=2)
        except subprocess.TimeoutExpired: proc.kill()
        err = proc.stderr.read().decode(errors="replace")
        if err:
            print("\n--- stderr tail ---")
            print(err[-2000:])


if __name__ == "__main__":
    sys.exit(main())
