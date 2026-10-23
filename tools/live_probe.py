"""One command for one live question: refreeze, run, read the answer.

WHY: driving a live attempt by hand ("refreeze, then run, then read") failed twice in a
row for the same reason -- a foreground wait outlived the shell timeout and killed the
job it was waiting for.  The sequence belongs in one process that owns its own steps.

The question it answers is chosen by `--question`, so the same script serves the next
one instead of growing a new shell incantation each time.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "evidence" / "runtime"
STEP = (190, 176)          # the two lattice pitches measured on live maps (x, y)
TOLERANCE = 24


def _run(cmd: list[str], *, timeout: float | None = None) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=ROOT, timeout=timeout)


def _clean() -> None:
    subprocess.call(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name 'MaaLimbusAgent' -ErrorAction SilentlyContinue | "
         "Stop-Process -Force; 'cleared'"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    lease = Path(os.path.expanduser("~")) / "AppData" / "Local" / "MaaLimbus" / "controller.lock"
    if lease.exists():
        try:
            lease.unlink()
        except PermissionError:
            # A live holder keeps it: say so and let the guard downstream decide, instead of
            # dying here before the question is even asked (measured 2026-10-23).
            print("lease is held by a live process; continuing", flush=True)


def _newest() -> Path | None:
    runs = sorted(glob.glob(str(EVIDENCE / "packaged-mirror-*")))
    return Path(runs[-1]) if runs else None


def _steps(run: Path) -> dict:
    """Every recorded party reading; how many moved by one lattice pitch."""
    seen: list[list[int]] = []
    for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("event") != "map_observed":
            continue
        where = event.get("map_player")
        if where:
            seen.append(list(where))
    moves = 0
    for before, after in zip(seen, seen[1:]):
        dx = abs(after[0] - before[0])
        dy = abs(after[1] - before[1])
        if any(abs(dx - pitch) <= TOLERANCE for pitch in STEP) or \
                any(abs(dy - pitch) <= TOLERANCE for pitch in STEP):
            moves += 1
    return {"readings": len(seen), "one_step_moves": moves, "first": seen[:3]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--question", default="party-steps",
                        choices=("party-steps",))
    parser.add_argument("--seconds", type=float, default=400.0)
    args = parser.parse_args(argv)

    _clean()
    if _run([sys.executable, str(ROOT / "build" / "refreeze_agent.py")]) != 0:
        print("RESULT " + json.dumps({"ok": False, "why": "refreeze failed"}))
        return 1
    if _run([sys.executable, str(ROOT / "tools" / "check_freeze.py")]) != 0:
        print("RESULT " + json.dumps({"ok": False, "why": "frozen app is stale"}))
        return 1

    _run([sys.executable, str(ROOT / "tools" / "selfrun_mirror.py"),
          "--attempts", "1", "--seconds", str(int(args.seconds))], timeout=args.seconds + 420)

    run = _newest()
    if run is None:
        print("RESULT " + json.dumps({"ok": False, "why": "no evidence directory"}))
        return 1
    answer = _steps(run)
    # A directory with no map readings means the run did not run; reporting ok would hide
    # exactly the failure this script exists to surface (measured 2026-10-23: argparse
    # rejected a float seconds value, and the empty result still printed ok=true).
    if not answer["readings"]:
        answer.update(ok=False, why="no map frames were recorded", run=run.name)
        print("RESULT " + json.dumps(answer, ensure_ascii=False))
        return 1
    answer.update(ok=True, run=run.name)
    print("RESULT " + json.dumps(answer, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
