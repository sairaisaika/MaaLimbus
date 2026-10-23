"""Count what each retained run actually did, including the ones that died.

A crashed process writes no `mirror_loop_stopped`, so a report built from stop events
silently drops it.  `run_metrics.summarise` now flags that case; this tool is the place
the flag is read, so the failure rate has a denominator that includes crashes.

Exit codes: 0 every run stopped on its own, 1 at least one run died without a stop,
2 there was nothing to read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import run_metrics                      # noqa: E402

EVIDENCE = ROOT / 'evidence' / 'runtime'


def read(path):
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def main(argv):
    runs = sorted(p.parent for p in EVIDENCE.glob('packaged-mirror-*/events.jsonl'))
    if not runs:
        print('RESULT: no runs to read')
        return 2
    died, stopped, floors = [], 0, 0
    for run in runs:
        report = run_metrics.summarise(read(run / 'events.jsonl'))
        if report['ended_without_a_stop']:
            died.append((run.name, report['events'], report['floors']))
        elif report['stops']:
            stopped += 1
        floors += 1 if report['floors'] else 0
    print(f'runs: {len(runs)}  stopped: {stopped}  died_without_a_stop: {len(died)}')
    print(f'runs_that_reached_a_floor: {floors}')
    for name, events, fl in died[-5:]:
        print(f'  died: {name}  events={events}  floors={fl}')
    if died:
        print('RESULT: some runs ended without a stop event — their process died')
        return 1
    print('RESULT: every run ended on its own stop path')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
