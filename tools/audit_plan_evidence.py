"""What the retained archive says happened after each plan word was sent.

Read-only: it reads ``evidence/runtime/packaged-mirror-*/events.jsonl`` and prints, per
word, how often the screen moved and where to; then which words the archive says need a
state proof and whether the code declares them.

Exit codes: 0 when the declaration matches the archive, 1 when it does not, 0 with a
message when there is no archive to read.
"""
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import plan_outcomes  # noqa: E402


if __name__ == '__main__':
    sys.exit(plan_outcomes.main(sys.argv[1:]))
