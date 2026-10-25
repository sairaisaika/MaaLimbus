"""Does the candidate-kind order survive a hold-out?  (D200)

`CLICK_KIND_ORDER` is a policy: which candidate the loop tries first.  D127 set it from the
frequency with which each kind appeared, and D199 measured acceptance on the same runs that
motivated the order -- which cannot show whether the order generalises.

This tool splits the current-era corpus in half by run name (the chronological order the
directories are written in), measures acceptance per kind in each half, and reports the
disagreement.  A kind whose rate moves by more than `DRIFT` between halves is not evidence
for an order; the order has to be justified by the half it was *not* fitted on.
"""
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src')]

from maalimbus.run_metrics import settled_clicks  # noqa: E402

DRIFT = 0.20
EARLY = 'early'
LATE = 'late'


def _rows(directory):
    return [json.loads(line) for line in (directory / 'events.jsonl').read_text(
        encoding='utf-8').splitlines() if line.strip()]


def corpus(directory=None):
    """Current-era runs only: a run written before stop paths existed cannot answer."""
    directory = pathlib.Path(directory or ROOT / 'evidence/runtime')
    runs = []
    for path in sorted(directory.glob('packaged-mirror-*/events.jsonl')):
        rows = _rows(path.parent)
        if any(row.get('stop_path') for row in rows):
            runs.append((path.parent.name, rows))
    return runs


def by_kind(runs):
    accepted, total = collections.Counter(), collections.Counter()
    for _, rows in runs:
        if not any(row.get('stop_path') for row in rows):
            continue  # a run written before stop paths existed cannot answer
        last = {}
        for row in rows:
            if row['event'] == 'map_nodes_offered':
                for box, kind in zip(row.get('boxes') or [], row.get('kinds') or []):
                    last[','.join(str(int(v)) for v in box[:4])] = kind
        for click in settled_clicks(rows)['settled']:
            target = click.get('target')
            if not target:
                continue
            key = ','.join(str(int(v)) for v in target[:4])
            kind = last.get(key) or click.get('kind') or '?'
            total[kind] += 1
            if click.get('outcome') == 'accepted':
                accepted[kind] += 1
    return {kind: {'accepted': accepted[kind], 'total': total[kind],
                   'rate': accepted[kind] / total[kind]}
            for kind in total}


def split(runs):
    half = len(runs) // 2
    return {EARLY: by_kind(runs[:half]), LATE: by_kind(runs[half:])}


def drift(halves):
    """Kinds measured in both halves, sorted by how far their rates move."""
    early, late = halves[EARLY], halves[LATE]
    rows = []
    for kind in sorted(set(early) & set(late)):
        moved = abs(late[kind]['rate'] - early[kind]['rate'])
        rows.append({'kind': kind, 'early': early[kind]['rate'], 'late': late[kind]['rate'],
                     'moved': moved, 'stable': moved <= DRIFT})
    return sorted(rows, key=lambda row: -row['moved'])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = pathlib.Path(argv[argv.index('--root') + 1]) if '--root' in argv else None
    runs = corpus(root)
    if not runs:
        print('nothing to read: no current-era run in this corpus')
        return 2
    halves = split(runs)
    print('runs: %d (early %d, late %d, split by run name)'
          % (len(runs), len(runs) // 2, len(runs) - len(runs) // 2))
    for label in (EARLY, LATE):
        print('%s half:' % label)
        for kind, data in sorted(halves[label].items(), key=lambda item: -item[1]['total']):
            print('  %-22s %3d/%-3d = %.2f' % (kind, data['accepted'], data['total'],
                                               data['rate']))
    rows = drift(halves)
    print('drift above %.2f (not evidence for an order): %s'
          % (DRIFT, ', '.join(row['kind'] for row in rows if not row['stable']) or 'none'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
