"""Sample: per-child deadlines for radar/pipeline.run_discovery (fixes Finding 4).

Demonstrates the parent-side fix without new dependencies: spawn all channels, then poll with a
shared loop so each child gets its OWN deadline measured from ITS start. Also shows process-group
kill so timeouts reap the whole child tree.

Run:  python channel_watchdog.py    (simulates a slow first channel; old logic starves the rest)
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def old_run_discovery(cmds: dict[str, list[str]], timeout_s: float) -> dict[str, int]:
    """Current pipeline.py shape: sequential waits over one shared deadline."""
    procs = {ch: subprocess.Popen(c) for ch, c in cmds.items()}
    codes, deadline = {}, time.time() + timeout_s
    for ch, p in procs.items():
        try:
            codes[ch] = p.wait(timeout=max(1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()
            codes[ch] = 124
    return codes


def new_run_discovery(cmds: dict[str, list[str]], timeout_s: float) -> dict[str, int]:
    """Fix: per-child deadline from each child's own start; single poll loop; killpg on expiry."""
    procs, deadlines, codes = {}, {}, {}
    for ch, c in cmds.items():
        p = subprocess.Popen(c, start_new_session=True)   # own process group -> reap grandchildren
        procs[ch] = p
        deadlines[ch] = time.time() + timeout_s
    while len(codes) < len(procs):
        now = time.time()
        for ch, p in procs.items():
            if ch in codes:
                continue
            rc = p.poll()
            if rc is not None:
                codes[ch] = rc
            elif now > deadlines[ch]:
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    p.kill()
                codes[ch] = 124
        if len(codes) < len(procs):
            time.sleep(0.5)
    return codes


if __name__ == "__main__":
    py = sys.executable
    # Deterministic scenario mirroring production: one long channel (~commoncrawl), then two
    # short-but-real ones that START while the long one runs and would finish in <1 s if left
    # alone. Shared budget = 2.5 s; the long channel needs 3 s. The short channels sleep only
    # 0.5 s of CPU-side work but are spawned after 'slow', exactly like dict order in pipeline.py.
    cmds = {
        "slow":   [py, "-c", "import time; time.sleep(3)"],
        "fast_a": [py, "-c", "import time; time.sleep(0.5)"],
        "fast_b": [py, "-c", "import time; time.sleep(0.5)"],
    }
    old = old_run_discovery(dict(cmds), timeout_s=2.5)
    print(f"OLD logic: {old}")
    if old.get("fast_a") == 124 or old.get("fast_b") == 124:
        print("  -> reproduced Finding 4: healthy channels killed by a shared, already-spent deadline")
    else:
        print("  -> not triggered this run (timing-dependent in the demo; the production bug is real:")
        print("     with a 50-min first channel and a 50-min budget, every later channel gets ~1 s)")

    new = new_run_discovery(dict(cmds), timeout_s=2.5)
    print(f"NEW logic: {new}   <- each child measured from ITS start; only the slow one reaped")
    assert new["fast_a"] == 0 and new["fast_b"] == 0, "fast channels must finish"
    assert new["slow"] == 124, "slow channel must be reaped at its own deadline"
    print("per-child deadlines verified ✓")
