"""Run the suite in chunks and judge each chunk by its own summary line.

Why not one pytest: in this environment a run can end with every test passing and
still return 4, because the process aborts after the last test but before the
summary is printed.  Chaining `pytest && git commit` on that exit code therefore
reports failure for a green suite, and the reverse mistake is worse -- a truncated
run looks like a pass because no failure line was seen.  The rule here is: a chunk
counts only when its output contains a `N passed` (or `N failed`) summary; a chunk
without a summary is reported as `no summary` and fails the run.
"""
from __future__ import annotations
import argparse, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / 'tests'
COUNT = re.compile(r'(\d+) (passed|failed)')


def parse(output: str) -> dict:
    """Read a pytest summary line, in either order (`N failed, M passed`)."""
    counts = {kind: int(number) for number, kind in COUNT.findall(output or '')}
    if not counts:
        return {'reported': False, 'passed': 0, 'failed': 0}
    return {'reported': True, 'passed': counts.get('passed', 0),
            'failed': counts.get('failed', 0)}


def chunks(files, size):
    for start in range(0, len(files), size):
        yield files[start:start + size]


def run_chunk(paths, python=sys.executable):
    proc = subprocess.run([python, '-m', 'pytest', *paths, '-q', '-p', 'no:cacheprovider'],
                          cwd=str(ROOT), capture_output=True, text=True)
    return parse(proc.stdout + proc.stderr), (proc.stdout or '') + (proc.stderr or '')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, default=8)
    parser.add_argument('--files', nargs='*', default=None,
                        help='explicit files; defaults to every tests/test_*.py')
    args = parser.parse_args(argv)
    files = args.files or [str(p.relative_to(ROOT)) for p in sorted(TESTS.glob('test_*.py'))]
    total = {'passed': 0, 'failed': 0, 'no_summary': 0, 'chunks': 0}
    for chunk in chunks(files, max(1, args.size)):
        seen, output = run_chunk(chunk)
        total['chunks'] += 1
        total['passed'] += seen['passed']
        total['failed'] += seen['failed']
        if seen['failed']:
            for line in output.splitlines():
                if line.startswith('FAILED '):
                    print('   ', line[:160])
        if not seen['reported']:
            total['no_summary'] += 1
            print(f'  NO SUMMARY  {len(chunk)} files: {chunk[0]} ...')
        else:
            print(f'  {seen["passed"]:>4} passed  {seen["failed"]:>2} failed  ({len(chunk)} files)')
    print(f'chunks {total["chunks"]}  passed {total["passed"]}  failed {total["failed"]}'
          f'  no-summary {total["no_summary"]}')
    return 0 if total['failed'] == 0 and total['no_summary'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
