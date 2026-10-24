"""What each recovery rung actually did to the view, from the retained journals.

The ladder is the engine's answer to a stop: one viewport gesture per stop, and the run
ends only once the ladder is spent.  Phase 6 asked for the recovery rate, and the honest
number was 1 of 274 -- but that counts whether the *page* moved, which a viewport gesture
is not supposed to do.  This prints the question the ladder can answer: did spending this
rung change what the reader could see, on the page it was spent on?

Read-only: it opens `evidence/runtime/*/events.jsonl` and nothing else.  Exit 1 only when
the classes this reports and `pages.LADDER_VIEW_EVIDENCE` disagree, i.e. when the declared
evidence has fallen behind the archive.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import pages, run_metrics  # noqa: E402


def report(directories=None):
    rows = run_metrics.ladder_effect(directories)
    verdicts = []
    problems = []
    for row in rows:
        measured = row['measured']
        changed = row['changed']
        if measured == 0:
            continue
        key = (row['gesture'], row['page'])
        observed = pages.ladder_view_class(changed, measured)
        declared = pages.LADDER_VIEW_EVIDENCE.get(key)
        verdict = {'gesture': row['gesture'], 'page': row['page'], 'seen': row['seen'],
                   'measured': measured, 'changed': changed,
                   'change_rate': row['change_rate'], 'declared': declared,
                   'observed': observed,
                   'by_design': key in pages.LADDER_STATIC_BY_DESIGN}
        verdicts.append(verdict)
        if verdict['by_design'] or observed == 'unmeasured':
            continue
        if declared is None:
            problems.append(dict(verdict, problem='undeclared'))
        elif declared != observed:
            problems.append(dict(verdict, problem='contradicted'))
    for key in sorted(pages.LADDER_VIEW_EVIDENCE):
        if not any(verdict['gesture'] == key[0] and verdict['page'] == key[1]
                   for verdict in verdicts):
            problems.append({'gesture': key[0], 'page': key[1], 'declared':
                             pages.LADDER_VIEW_EVIDENCE[key], 'observed': 'not in the archive',
                             'problem': 'stale'})
    return {'rows': rows, 'verdicts': verdicts, 'problems': problems}


def main(argv=None):
    import json
    argv = sys.argv[1:] if argv is None else argv
    found = report()
    if '--json' in argv:
        print(json.dumps(found, indent=1, ensure_ascii=False, default=str))
        return 1 if found['problems'] else 0
    if not found['verdicts']:
        print('no recovery in the retained journals')
        return 2
    seen = sum(verdict['measured'] for verdict in found['verdicts'])
    print('recoveries measured: %d' % seen)
    print('%-12s %-8s %5s %8s %8s %7s  %-14s %s'
          % ('gesture', 'page', 'seen', 'measured', 'changed', 'rate', 'observed', 'declared'))
    for verdict in found['verdicts']:
        print('%-12s %-8s %5d %8d %8d %7s  %-14s %s%s'
              % (verdict['gesture'], verdict['page'], verdict['seen'], verdict['measured'],
                 verdict['changed'], verdict['change_rate'], verdict['observed'],
                 verdict['declared'] or '-',
                 '  (moves nothing by design)' if verdict['by_design'] else ''))
    print('declared evidence the archive disagrees with: %d' % len(found['problems']))
    for problem in found['problems']:
        print('  %s on %s: %s (declared %s, archive %s, %s of %s)'
              % (problem['gesture'], problem['page'], problem['problem'],
                 problem['declared'], problem['observed'],
                 problem.get('changed', '-'), problem.get('measured', '-')))
    return 1 if found['problems'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
