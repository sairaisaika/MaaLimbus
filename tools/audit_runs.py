"""Count what each retained run actually did, including the ones that died.

A crashed process writes no `mirror_loop_stopped`, so a report built from stop events
silently drops it.  `run_metrics.summarise` now flags that case; this tool is the place
the flag is read, so the failure rate has a denominator that includes crashes.

The census is exhaustive by construction: every run lands in exactly one of `stop`,
`error`, `died` or `no_events`, and the four counts are checked against the number of
runs read.  Until D50 there were only two buckets and the ten retained runs that ended on
`mirror_loop_error` alone appeared in neither, so the printed totals did not add up
(81 + 51 of 142).

Exit codes: 0 every run stopped on its own, 1 at least one run ended on an error or died,
2 there was nothing to read.
"""

from __future__ import annotations

import collections
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


def census(runs):
    """Classify every run; returns (counts, paths, failed, floors).

    `failed` holds the runs that did not stop on their own -- both kinds, because the
    exit code and the printed list want the same set; `counts` still keeps them apart.

    Four buckets, one run each, so `sum(counts.values()) == len(runs)` is a property of
    the function rather than a hope about the corpus.
    """
    counts = collections.Counter()
    paths = collections.Counter()
    failed = []
    floors = 0
    for run in runs:
        report = run_metrics.summarise(read(run / 'events.jsonl'), run)
        end = report['ending']
        counts[end['kind']] += 1
        paths[end['path'] or '-'] += 1
        if end['kind'] in ('died', 'error'):
            failed.append((run.name, report['events'], report['floors'], end))
        floors += 1 if report['floors'] else 0
    return counts, paths, failed, floors


def main(argv):
    runs = sorted(p.parent for p in EVIDENCE.glob('packaged-mirror-*/events.jsonl'))
    if not runs:
        print('RESULT: no runs to read')
        return 2
    counts, paths, failed, floors = census(runs)
    total = sum(counts.values())
    print('runs: %d  stopped: %d  errored: %d  died: %d  killed at the budget: %d  '
          'no events: %d'
          % (total, counts['stop'], counts['error'], counts['died'], counts['budget'],
             counts['no_events']))
    print('runs_that_reached_a_floor: %d' % floors)
    print('endings by path: %s' % dict(paths.most_common()))
    if total != len(runs):
        # Cannot happen by construction; checked anyway, because this number was wrong
        # once and every rate divided by it was wrong too.
        print('RESULT: the census lost runs (%d of %d classified)' % (total, len(runs)))
        return 1
    for name, events, fl, end in failed[-5:]:
        print('  %s: %s  events=%d  floors=%d  path=%s  reason=%s'
              % (end['kind'], name, events, len(fl), end['path'], end['reason']))
    if failed:
        print('RESULT: %d run(s) did not stop on their own' % len(failed))
        return 1
    print('RESULT: every run ended on its own stop path')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
