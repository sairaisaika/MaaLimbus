"""How long one node hop costs, and how many hops a floor takes (D201).

The throughput target is stated in floors per ten minutes, so the walk has to be measured
in hops: a floor is as expensive as `nodes x hop`, and a hop is as expensive as the reads
and transitions between two node clicks.  This counts both from the journals and refuses
to invent a number it cannot see (a run with no node click reports nothing).
"""
import collections
import json
import pathlib
import statistics
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE_REASON = 'map_node'


def _when(row):
    stamp = row.get('utc')
    try:
        return datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None


def current_era(directory=None):
    directory = pathlib.Path(directory or ROOT / 'evidence/runtime')
    runs = []
    for path in sorted(directory.glob('packaged-mirror-*/events.jsonl')):
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
                if line.strip()]
        if any(row.get('stop_path') for row in rows):
            runs.append((path.parent.name, rows))
    return runs


def walk(rows):
    """Node hops, the gaps between them, and the floor each hop happened on."""
    hops, gaps, floors, last, last_floor = 0, [], collections.Counter(), None, None
    for row in rows:
        if row['event'] in ('map_observed', 'battle_observed'):
            seen = row.get('floor')
            if seen:
                last_floor = str(seen)
        if row['event'] != 'window_intent' or NODE_REASON not in str(row.get('reason') or ''):
            continue
        now = _when(row)
        hops += 1
        floors[last_floor] += 1
        if now and last:
            gaps.append((now - last).total_seconds())
        last = now
    return {'hops': hops, 'gaps': gaps, 'floors': dict(floors)}


def hop_legs(rows):
    """The click -> next map read leg, and the events between two hops (D202).

    A hop's cost is not the animation: after a node click the next MAP read arrives in
    about a second and a half, so whatever a hop costs is spent between that read and the
    next plan.  Counting the events in the interval says which half to attack.
    """
    readings, fills, legs = 0, collections.Counter(), []
    hops = [index for index, row in enumerate(rows)
            if row['event'] == 'window_intent' and NODE_REASON in str(row.get('reason') or '')]
    for first, second in zip(hops, hops[1:]):
        for row in rows[first + 1:second]:
            fills[row['event']] += 1
            if row['event'] == 'map_observed':
                readings += 1
    for index in hops:
        started = _when(rows[index])
        if not started:
            continue
        for row in rows[index + 1:index + 40]:
            if row['event'] == 'map_observed' and row.get('scene') == 'MAP':
                arrived = _when(row)
                if arrived:
                    legs.append((arrived - started).total_seconds())
                break
            if row['event'] == 'window_intent':
                break
    return {'legs': legs, 'fills': fills, 'readings': readings}


def report(directory=None):
    runs = current_era(directory)
    hops, gaps, floors = 0, [], collections.Counter()
    legs, fills, readings = [], collections.Counter(), 0
    measured = 0
    for _, rows in runs:
        found = walk(rows)
        if not found['hops']:
            continue
        measured += 1
        hops += found['hops']
        gaps += found['gaps']
        floors.update(found['floors'])
        extra = hop_legs(rows)
        legs += extra['legs']
        fills.update(extra['fills'])
        readings += extra['readings']
    return {
        'runs': len(runs),
        'runs_with_a_hop': measured,
        'hops': hops,
        'hops_per_run': hops / measured if measured else None,
        'hops_per_floor': ({name: count for name, count in floors.items()} if floors else {}),
        'hop_seconds': (statistics.median(gaps) if gaps else None),
        'hop_seconds_mean': (sum(gaps) / len(gaps) if gaps else None),
        'gaps': len(gaps),
        'click_to_read': (statistics.median(legs) if legs else None),
        'reads_per_hop': (readings / hops if hops else None),
        'between_hops': dict(fills.most_common(6)),
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = pathlib.Path(argv[argv.index('--root') + 1]) if '--root' in argv else None
    data = report(root)
    if not data['runs']:
        print('nothing to read: no current-era run in this corpus')
        return 2
    print('runs: %d  with a node hop: %d' % (data['runs'], data['runs_with_a_hop']))
    if not data['hops']:
        print('no node hop was recorded, so a hop has no measured cost')
        return 0
    print('node hops: %d (%.1f per run that walked)' % (data['hops'], data['hops_per_run']))
    print('hops by floor: %s' % data['hops_per_floor'])
    print('gap between two node hops: median %.1fs mean %.1fs over %d gaps'
          % (data['hop_seconds'], data['hop_seconds_mean'], data['gaps']))
    if data['click_to_read'] is not None:
        print('node click -> next map read: median %.2fs' % data['click_to_read'])
        print('reads inside one hop: %.1f' % data['reads_per_hop'])
        print('events between two hops: %s' % data['between_hops'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
