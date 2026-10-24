"""Where the seconds inside a floor went (D122).

    python tools/audit_floor_time.py                 # the retained corpus, one run each
    python tools/audit_floor_time.py --root DIR      # one run
    python tools/audit_floor_time.py --json

A floor's dwell says how long it was on screen; this says whether the loop was fighting,
walking, shopping, taking a gift, or doing something the groups do not name -- and which
events inside that group cost the time.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import run_metrics  # noqa: E402


def report(directories=None, *, root=None):
    directories = [pathlib.Path(root)] if root else (directories or run_metrics._archives())
    rows = []
    for directory in directories:
        rows.extend(run_metrics._rows_of(pathlib.Path(directory)))
    return {'runs': len(directories), 'floors': run_metrics.floor_time(rows)}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = argv[argv.index('--root') + 1] if '--root' in argv else None
    data = report(root=root)
    if '--json' in argv:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if data['floors'] else 2
    if not data['floors']:
        print('nothing to read: no run named a floor')
        return 2
    print(f"runs read: {data['runs']}")
    for floor, entry in data['floors'].items():
        print(f'floor {floor}: {entry["seconds"]} s')
        for group, bucket in sorted(entry['groups'].items(), key=lambda pair: -pair[1]['seconds']):
            print(f"  {group:7s} {bucket['seconds']:7.1f}s  {bucket['share'] * 100:5.1f}%  n={bucket['n']}")
        for event, spent in entry['events'].items():
            print(f"    {event:28s} {spent['seconds']:7.1f}s n={spent['n']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
