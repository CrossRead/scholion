"""A consented PGS operation outlives a host that exits after each tool call."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from typing import Any

from . import container, core, recompute


def start(since=None):
    """Reserve one job and hand its claim to a standalone installed worker."""
    claim = recompute._claim()
    if claim is None:
        return {"started": False, "reason": "busy", "job": recompute.status()}
    process = None
    try:
        container.ensure()
        context = container.capture()
        log = core.profile_dir() / ".prs-worker.log"
        kwargs: dict[str, Any] = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
                  if os.name == "nt" else {"start_new_session": True})
        env = dict(os.environ)
        env.pop("SCHOLION_MANAGED_BY", None)
        with log.open("ab") as errors:
            process = subprocess.Popen([sys.executable, "-m", "scholion.prs_worker"],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=errors, env=env, **kwargs)
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(json.dumps({"context": context, "claim": str(claim),
                                       "owner": os.getpid(), "since": since}).encode() + b"\n")
        process.stdin.close()
        output = process.stdout
        lines: queue.Queue[bytes] = queue.Queue()
        def read_ack():
            lines.put(output.readline())
        threading.Thread(target=read_ack, daemon=True).start()
        ack = json.loads(lines.get(timeout=10))
        process.stdout.close()
        if not ack.get("started"):
            raise RuntimeError(ack.get("error") or "PGS worker could not start")
        return ack
    except (OSError, ValueError, RuntimeError, queue.Empty) as exc:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        recompute._release(claim)
        return {"started": False, "reason": "worker_failed", "error": str(exc)}
    finally:
        if process is not None:
            for pipe in (process.stdin, process.stdout):
                if pipe is not None:
                    pipe.close()


def main():
    """Private stdio handshake; captured identity is gated before every write."""
    payload = json.loads(sys.stdin.buffer.readline())
    with container.pinned(payload["context"]):
        container.gate()
        claim = Path(payload["claim"])
        if claim != core.profile_dir() / recompute.CLAIM or claim.read_text(encoding="utf-8").strip() != str(payload["owner"]):
            raise RuntimeError("PGS worker claim does not match the selected profile")
        claim.write_text(str(os.getpid()), encoding="utf-8")
        recompute._write({"status": "running", "pid": os.getpid(), "started": recompute._now(),
                          "current": 0, "steps": []}, force=True)
        print(json.dumps({"started": True, "steps": 1, "worker_pid": os.getpid()}), flush=True)
        recompute._run_bound(payload.get("since"), claim, prs_only=True, force_prs=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
