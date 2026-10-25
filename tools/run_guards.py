"""Run the guard suites in one pytest process and say where the seconds go.

Measured 2026-10-25 while auditing the development loop: 188 files under `tests/`, and a
round that touches the runner spent most of its wall clock on interpreter start-up --
each `python tools/run_tests.py tests/test_x.py` pays ~1.5 s of import before a single
test runs, and a round that checks six guards pays it six times.  This runs them in one
process instead, prints the slowest suites, and returns **pytest's own exit code** (the
AGENTS.md contract: the exit code must come from the test process, never from a pipe).

Usage:
    python tools/run_guards.py            # every guard suite, one process
    python tools/run_guards.py --list     # what it would run
    python tools/run_guards.py a.py b.py  # a subset
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
GUARD_PREFIXES = (
    "test_pages",
    "test_page_contracts",
    "test_step_rows",
    "test_plan_",
    "test_map_",
    "test_battle_",
    "test_read_",
    "test_settle_",
    "test_stall_watch",
    "test_native_",
    "test_agent_loop",
    "test_runner",
    "test_run_",
    "test_unknown_",
    "test_transition_",
    "test_recovery_",
    "test_anchor",
    "test_stop_kinds",
    "test_reason_provenance",
    "test_refuse_vocabulary",
    "test_evidence_audit",
    "test_transaction_",
    "test_floor_",
    "test_exempt_",
    "test_gesture_",
    "test_budget_tail",
    "test_assign_per_turn",
)


def guard_files(directory=None):
    """The guard suites, by the prefixes that have earned their place."""
    root = pathlib.Path(directory or TESTS)
    if not root.is_dir():
        return []
    picked = [p for p in sorted(root.glob("test_*.py")) if p.name.startswith(GUARD_PREFIXES)]
    return picked


def command(files):
    return [sys.executable, "-m", "pytest", "-q", "--durations=10", *[str(p) for p in files]]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    files = guard_files()
    if "--list" in argv:
        for p in files:
            print(p.name)
        print("guards: %d" % len(files))
        return 0
    if not files:
        print("no guard suites found under %s" % TESTS)
        return 2
    chosen = [p for p in files if not argv or p.name in argv]
    if not chosen:
        print("none of the requested suites are guards: %s" % ", ".join(argv))
        return 2
    return int(subprocess.call(command(chosen), cwd=str(ROOT)))


if __name__ == "__main__":
    raise SystemExit(main())
