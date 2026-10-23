"""Print who writes a plan's reason and who reads one, and fail on a dead hook.

Usage:
    python tools/audit_plan_reasons.py [runner.py]

A *dead* hook is a comparison against a word no plan writer produces: the proof it
guards can never run, and nothing else in the tree notices, because a step that never
fires looks exactly like a step that was not needed.  ``maalimbus.plan_reasons`` derives
both sides from the source; this tool is the shell around it.

Exit codes: 0 the relation is complete, 1 a hook names a word nobody writes.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.plan_reasons import main as _main  # noqa: E402


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    return _main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
