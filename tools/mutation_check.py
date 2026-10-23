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


def prove_one(guard):
    args = argparse.Namespace(**guard)
    path = pathlib.Path(args.file)
    original = path.read_text(encoding='utf-8')
    if original.count(args.find) != 1:
        return f'anchor count {original.count(args.find)}'
    mutated = original.replace(args.find, args.replace, 1)
    if mutated == original:
        return 'mutation changed nothing'
    baseline = run([args.test])
    if baseline.returncode != 0:
        return 'test already red'
    try:
        path.write_text(mutated, encoding='utf-8')
        result = run([args.test])
    finally:
        path.write_text(original, encoding='utf-8')
    if path.read_text(encoding='utf-8') != original:
        return 'restore not exact'
    return None if result.returncode != 0 else 'test passed under mutation'


def prove_manifest(path):
    import json
    guards = json.loads(path.read_text(encoding='utf-8'))
    failures = 0
    for guard in guards:
        problem = prove_one(guard)
        name = guard.get('name') or guard['test']
        print(f'{"PROVEN " if problem is None else "UNPROVEN"} {name}'
              + ('' if problem is None else f'  <- {problem}'))
        failures += problem is not None
    print(f'{len(guards) - failures}/{len(guards)} guards proven')
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file')
    parser.add_argument('--find')
    parser.add_argument('--replace')
    parser.add_argument('--test')
    parser.add_argument('--manifest',
                        help='a JSON list of guards to prove in one pass')
    args = parser.parse_args()
    if args.manifest:
        return prove_manifest(pathlib.Path(args.manifest))
    if not all((args.file, args.find, args.replace, args.test)):
        parser.error('either --manifest or all of --file/--find/--replace/--test')

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
