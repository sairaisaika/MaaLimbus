#!/usr/bin/env python
"""How often does a run click a node the map has already refused?

A refused click is not an error: the page stays where it is and the verdict says so.  What it
must not be is *repeated* -- the node was refused because the game does not accept that step
from where the party stands, and clicking it again spends the page budget to learn the same
fact twice.

Measured over the last 40 retained runs: 139 rejected clicks, **76 of them (55%) were the same
target being refused again**, and the worst runs repeat a single node four times.  That is the
state-layer defect behind `unexpected_successor` stops: the reader is not the problem, the
memory is.

Usage:
    python tools/audit_refused_retries.py [--runs 40]
Exit codes: 0 measured, 2 nothing to read.
"""

import argparse
import json
import pathlib
import sys
from collections import Counter

EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / 'evidence' / 'runtime'


def runs(directory=None, limit=40):
    root = pathlib.Path(directory) if directory else EVIDENCE
    found = sorted(root.glob('packaged-mirror-*'))[-limit:]
    return [run for run in found if (run / 'events.jsonl').is_file()]


def report(directory=None, limit=40):
    totals = {'rejected': 0, 'repeated': 0}
    rows = []
    for run in runs(directory, limit):
        seq = []
        for line in (run / 'events.jsonl').read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get('event') == 'map_click_result' and event.get('outcome') == 'rejected':
                seq.append(tuple(event.get('target') or ()))
        counts = Counter(seq)
        repeated = sum(value - 1 for value in counts.values() if value > 1)
        totals['rejected'] += len(seq)
        totals['repeated'] += repeated
        if seq:
            rows.append({'run': run.name, 'rejected': len(seq), 'repeated': repeated,
                         'worst': max(counts.values()) if counts else 0})
    return totals, rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=40)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    totals, rows = report(limit=args.runs)
    if not rows:
        print('no run in the corpus recorded a rejected map click', file=sys.stderr)
        return 2
    rate = totals['repeated'] / float(max(1, totals['rejected']))
    if args.json:
        print(json.dumps({'totals': totals, 'rate': round(rate, 3), 'runs': rows}, indent=2))
    else:
        print('rejected clicks: %d  repeated after a refusal: %d  (%.0f%%)'
              % (totals['rejected'], totals['repeated'], 100 * rate))
        for row in rows[:10]:
            print('   %s rejected %d repeated %d worst %d'
                  % (row['run'][-13:], row['rejected'], row['repeated'], row['worst']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
