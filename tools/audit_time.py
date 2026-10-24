"""Where did the run's seconds go?

`tools/audit_efficiency.py` reports `mean_seconds`; this reports the budget behind it:
the seconds each event cost, read from the journal's own `utc` stamps (D66).  It answers
"which line owns the time" without touching the device, and it says how much time the
journal could not explain instead of dividing that time into the lines that were left.

    python tools/audit_time.py                 # the retained archive
    python tools/audit_time.py --json          # the same numbers, machine-readable
    python tools/audit_time.py --root evidence/runtime
"""

import json
import pathlib
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    json_out = '--json' in args
    root = None
    if '--root' in args:
        root = pathlib.Path(args[args.index('--root') + 1])

    here = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(here / 'src'))
    from maalimbus import run_metrics

    directories = None
    if root is not None:
        directories = sorted(path.parent for path in root.glob('*/events.jsonl'))
    budgets = []
    for directory in run_metrics._archives(directories):
        rows = run_metrics._rows_of(directory)
        if rows:
            budgets.append(run_metrics.time_budget(rows))
    if not budgets:
        print('no run wrote a journal under evidence/runtime')
        return 2
    report = run_metrics.time_portfolio(budgets)
    if json_out:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    value = report['value']
    print(f'runs read: {len(budgets)}')
    if value is None:
        print(f'time budget: not measured -- {report["note"]}')
        return 0
    print(f'attributed seconds: {value["attributed_seconds"]:.0f} '
          f'of {value["total_seconds"]:.0f} in total')
    print('')
    for group, entry in value['groups'].items():
        share = '  n/a' if entry['share'] is None else f'{entry["share"] * 100:4.1f}%'
        print(f'{group:<9} {entry["seconds"]:8.0f} s {share}  n={entry["n"]}')
    print('')
    print('the lines that own the time:')
    for event, entry in value['per_event'].items():
        share = '  n/a' if entry['share'] is None else f'{entry["share"] * 100:4.1f}%'
        print(f'  {event:<26} {entry["seconds"]:8.0f} s {share}  '
              f'n={entry["n"]:<6} mean={entry["mean"]:.2f} s  [{entry["group"]}]')
    print('')
    print(f'basis: {report["basis"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
