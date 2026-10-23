"""Run pytest and exit with pytest's own status.

Why this exists: `pytest ... | tail -2 && git commit` commits a red suite, because
a pipeline's exit status is the *last* command's (`tail`), not pytest's.  That
happened twice in this project; the second time a failing guard test was
committed and only caught by re-running.

Usage: ``python tools/run_tests.py tests/test_x.py -q``
"""

import subprocess
import sys


def main(argv=None):
    """Run pytest in-process-free (a real child) and return its exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    done = subprocess.run([sys.executable, '-m', 'pytest', *args])
    return int(done.returncode)


if __name__ == '__main__':
    raise SystemExit(main())
