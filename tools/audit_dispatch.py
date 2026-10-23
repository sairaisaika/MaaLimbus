"""What may happen on each page, derived from the chain -- and what has drifted.

``pages.CONTRACTS`` answered this in prose and nothing read it.  This tool prints
the machine answer (``window.dispatch_facts``) next to the recorded copy
(``pages.DISPATCH_FACTS``) and flags the four things a reader wants to know:

* pages whose record no longer matches the chain it is derived from (drift),
* pages that can refuse but never act (fine on a page that clears itself, a trap
  anywhere else),
* names the chain chooses at runtime, which no static reader can classify,
* declared wait pages whose refusal would map to a stopping action -- the
  ``路径失败后容易直接停止`` failure, which must stay empty.

Exit code: 0 when the record matches the chain, 1 when it has drifted.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import pages, window  # noqa: E402


def report(derived=None):
    derived = window.dispatch_facts() if derived is None else derived
    drift = pages.fact_drift(derived)
    unchanged = {page: row for page, row in derived.items() if page not in drift}
    unreadable = sorted({name for row in derived.values()
                         for name in row['expects'] + row['refusals']
                         if name.startswith('<')})
    return {
        'pages': len(derived),
        'rows': sorted(window.STEP_ROWS),
        'branches': _branch_pages(),
        'drift': sorted(drift),
        'silent': sorted(page for page, row in unchanged.items() if not row['actions']),
        'unreadable': unreadable,
        'unsafe_wait_branches': pages.unsafe_wait_branches(derived),
        'widest': sorted(((len(row['expects']), page) for page, row in unchanged.items()),
                         reverse=True)[:5],
        'facts': unchanged,
    }


def _branch_pages():
    """Pages still written out as their own branch of ``_plan_step``."""
    import ast

    tree = ast.parse((ROOT / 'src' / 'maalimbus' / 'window.py').read_text(encoding='utf-8'))
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == '_plan_step')
    found = set()
    for node in ast.walk(function):
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)):
            continue
        test = node.test
        if getattr(test.left, 'id', None) != 'page' or len(test.comparators) != 1:
            continue
        value = test.comparators[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            found.add(value.value)
    return sorted(found)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--json', action='store_true', help='print the whole report')
    parser.add_argument('--page', help='print one page only')
    args = parser.parse_args(argv)

    found = report()
    if args.page:
        row = found['facts'].get(args.page)
        if row is None:
            print('%s: the chain plans nothing for this page' % args.page)
            return 1
        print(json.dumps({'page': args.page, **row}, indent=1))
        return 0
    if args.json:
        print(json.dumps(found, indent=1))
        return 0 if not found['drift'] else 1

    print('pages the chain plans: %d (rows %d, branches %d)'
          % (found['pages'], len(found['rows']), len(found['branches'])))
    print('pages that never act: %s' % (', '.join(found['silent']) or 'none'))
    print('names chosen at runtime: %s' % (', '.join(found['unreadable']) or 'none'))
    print('wait pages whose refusal would stop the run: %s'
          % (', '.join('%s (%s -> %s)' % row for row in found['unsafe_wait_branches'])
             or 'none'))
    print('widest successor sets: %s'
          % ', '.join('%s %d' % (page, count) for count, page in found['widest']))
    if found['drift']:
        print('drifted from the chain: %s -- regenerate pages.DISPATCH_FACTS'
              % ', '.join(found['drift']))
        return 1
    print('recorded facts match the chain')
    return 0


if __name__ == '__main__':
    sys.exit(main())
