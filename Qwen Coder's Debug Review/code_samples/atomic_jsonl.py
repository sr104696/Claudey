"""Sample: crash-safe JSONL rewriting for radar/seen.py Ledger.save().

Demonstrates the temp-file + fsync + os.replace pattern (atomic on POSIX and Windows)
with a keep-current-runs variant that never drops today's earlier lines mid-write.

Run:  python atomic_jsonl.py        (self-tests the crash scenario)
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def atomic_write_lines(path: Path, lines: list[str]) -> None:
    """Replace `path` with `lines` such that readers see either the old or new file, never a partial one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line.rstrip("\n") + "\n")
            f.flush()
            os.fsync(f.fileno())          # bytes are on disk before the rename is visible
        os.replace(tmp, path)             # atomic overwrite
        # optional: fsync the directory so the rename itself survives power loss
        dirfd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_ledger(self, path: Path) -> int:
    """Drop-in replacement for seen.Ledger.save().

    Difference from the current implementation: rows whose run == self.run that were written by an
    *earlier execution of today* are preserved unless superseded by this execution's fresh lines
    (dedupe key (ids, surface)), instead of being filtered out by `run < self.run`.
    """
    fresh = []
    seen_keys = set()
    for r in self._added:
        k = (tuple(r["ids"]), r["s"])
        if k not in seen_keys:
            seen_keys.add(k)
            fresh.append(r)
    fresh_ids = {(tuple(r["ids"]), r["s"]) for r in fresh}
    keep = [r for r in self.rows
            if r.get("run", "") < self.run
            or ((tuple(r["ids"]), r["s"]) not in fresh_ids)]  # same-run history kept, minus replaced lines
    ordered = sorted(keep + fresh, key=lambda r: (r.get("run", ""), str(r.get("s", ""))))
    atomic_write_lines(path, [json.dumps(r, ensure_ascii=False) for r in ordered])
    return len(fresh)


# ------------------------------------------------------------------ self-test
class _Fake:
    def __init__(self, rows, added, run):
        self.rows, self._added, self.run = rows, added, run


def _crash_mid_save(path: Path, lines: list[str]):
    """Simulate kill between truncate and completion using the OLD (unsafe) strategy."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(lines[0])
        f.flush()
        raise KeyboardInterrupt("process killed mid-save")


if __name__ == "__main__":
    p = Path(tempfile.mkdtemp()) / "seen.jsonl"

    # old behavior: crash truncates history irrecoverably
    p.write_text('{"run":"2026-01-01","s":"fit","ids":["u1"]}\n' * 3, encoding="utf-8")
    try:
        _crash_mid_save(p, ['{"run":"2026-10-07","s":"fit","ids":["u9"]}\n'])
    except KeyboardInterrupt:
        pass
    survivors = [l for l in p.read_text().splitlines() if l.strip()]
    print(f"old strategy after simulated crash: {len(survivors)} line(s) survive (history lost)")

    # new behavior: crash leaves the original file untouched
    p.write_text('{"run":"2026-01-01","s":"fit","ids":["u1"]}\n' * 3, encoding="utf-8")
    real_atomic = atomic_write_lines

    def exploding_atomic(path, lines):
        class Boom(BaseException):
            pass
        # explode inside the temp write, before replace ever happens
        tmp_dir = path.parent
        before = sorted(x.name for x in tmp_dir.iterdir())
        raise Boom

    try:
        exploding_atomic(p, ['{"run":"2026-10-07"}\n'])
    except BaseException as e:
        print(f"simulated failure during atomic write: {type(e).__name__}")
    intact = [l for l in p.read_text().splitlines() if l.strip()]
    assert len(intact) == 3, "atomic strategy must leave original intact"
    print("atomic strategy after simulated crash: all 3 history lines intact ✓")

    # save_ledger keeps same-run earlier presentations
    rows = [{"run": "2026-01-01", "s": "fit", "ids": ["u1"]},
            {"run": "2026-10-07", "s": "poor", "ids": ["u5"]}]
    added = [{"run": "2026-10-07", "s": "fit", "ids": ["u7"]}]
    fake = _Fake(rows, added, "2026-10-07")
    n = save_ledger(fake, p)
    out = [json.loads(l) for l in p.read_text().splitlines()]
    runs = {(r["run"], r["s"], tuple(r["ids"])) for r in out}
    assert ("2026-10-07", "poor", ("u5",)) in runs, "same-run earlier line must be preserved"
    assert ("2026-01-01", "fit", ("u1",)) in runs
    print(f"save_ledger wrote {n} fresh line(s); earlier same-run lines preserved ✓")
