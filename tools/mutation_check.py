"""Prove a test guards its invariant by breaking the implementation under it.

A test that passes with the implementation deleted is documentation, not a guard.
This tool applies one textual mutation to a source file, runs one pytest node, and
restores the file byte-for-byte; the guard is *proven* only when the test fails with
the mutation in place and the restore is exact.

Usage:
    python tools/mutation_check.py --file src/maalimbus/pages.py \
        --find "if action in WAIT_ONLY_ACTIONS:" --replace "if False:" \
        --test tests/test_recovery_ladder.py::test_a_text_refusal_never_drags_the_page

Exit codes: 0 proven, 1 not proven (test passed under mutation), 2 the mutation or
the test could not be applied as asked (a stale anchor is a failure, never a pass).
"""
import argparse
import pathlib
import subprocess
import sys


def run(pytest_args):
    return subprocess.run([sys.executable, '-m', 'pytest', '-q', *pytest_args],
                          capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--find', required=True)
    parser.add_argument('--replace', required=True)
    parser.add_argument('--test', required=True)
    args = parser.parse_args()

    path = pathlib.Path(args.file)
    original = path.read_text(encoding='utf-8')
    if original.count(args.find) != 1:
        print(f'anchor appears {original.count(args.find)} times, need exactly 1')
        return 2
    mutated = original.replace(args.find, args.replace, 1)
    if mutated == original:
        print('mutation changed nothing')
        return 2

    baseline = run([args.test])
    if baseline.returncode != 0:
        print('the test already fails without a mutation: fix that first')
        print(baseline.stdout[-800:])
        return 2

    try:
        path.write_text(mutated, encoding='utf-8')
        result = run([args.test])
    finally:
        path.write_text(original, encoding='utf-8')

    if path.read_text(encoding='utf-8') != original:
        print('restore was not exact')
        return 2
    if result.returncode == 0:
        print('NOT PROVEN: the test passes with the implementation mutated')
        return 1
    print('proven: the test fails with the implementation mutated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
