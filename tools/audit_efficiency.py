"""The six figures phase 6 asks for, computed from the journals alone.

`src/maalimbus/run_metrics.py` already owns the definitions; this tool only prints them,
so a report quotes one implementation instead of recounting by hand (the session published
two wrong numbers by recounting: D50's 81+51, D56's 28 unjudgeable words).

Exit 0 when the archive was read, 2 when there is nothing to read.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import run_metrics  # noqa: E402


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    directories = [pathlib.Path(word) for word in argv if not word.startswith('--')]
    report = run_metrics.portfolio(directories or None)
    runs = report['runs']
    if '--json' in argv:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0 if runs else 2
    print(f'runs read: {len(runs)}')
    if not runs:
        print('nothing to measure: no evidence/runtime/packaged-mirror-*/events.jsonl')
        return 2
    for name in run_metrics.MEASURES:
        row = report['measures'][name]
        value = 'not measured' if row['value'] is None else row['value']
        print(f'{name:24} {value}')
        print(f'{"":24} basis: {row["basis"]}')
        if row['note']:
            print(f'{"":24} note:  {row["note"]}')
    by_page = run_metrics.reads_by_page()
    print()
    print('reads per input, by the page the input went from (D187, current era only):')
    if not by_page:
        print('  not measured: no capable run carries enough inputs on one page')
    for name, row in sorted(by_page.items(), key=lambda item: -item[1]['median'])[:10]:
        print('  %-18s median %2d  p90 %2d  over %d input(s)'
              % (name, row['median'], row['p90'], row['inputs']))
    endings = {}
    for run in runs:
        kind = run['ending']['kind']
        endings[kind] = endings.get(kind, 0) + 1
    print(f'endings: {dict(sorted(endings.items()))}')
    floors = [run['reached_floor'] for run in runs if run['reached_floor']]
    print(f'runs with a floor: {len(floors)}  best floor: {max(floors) if floors else None}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
