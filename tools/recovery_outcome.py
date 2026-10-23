"""Which recovery actions are followed by an actual change of page?

A recovery is only useful if the page it was spent on is not the page that comes
next.  This replays every retained run and pairs each recovery with the next page
it saw, so "recover" can be scored by outcome instead of by count.
"""
from __future__ import annotations
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVENTS = ('window_recovery', 'window_reread')


def pairs(events):
    """Yield (recovery_event, next_page_or_None) in journal order."""
    current = None
    for event in events:
        name = event.get('event')
        if name in EVENTS:
            current = event
            continue
        page = event.get('page') or event.get('scene')
        if current is not None and page:
            yield current, page
            current = None


def summarise(events):
    out = {}
    for recovery, page in pairs(events):
        kind = recovery.get('recovery_kind') or recovery.get('kind') or 'unknown'
        action = recovery.get('recovery_action') or 'unknown'
        was = recovery.get('page') or 'unknown'
        key = (action, kind)
        entry = out.setdefault(key, {'total': 0, 'changed': 0})
        entry['total'] += 1
        if page != was:
            entry['changed'] += 1
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(ROOT / 'evidence' / 'runtime'))
    args = parser.parse_args(argv)
    totals = {}
    runs = 0
    for path in sorted(pathlib.Path(args.root).glob('*/events.jsonl')):
        events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        runs += 1
        for key, entry in summarise(events).items():
            slot = totals.setdefault(key, {'total': 0, 'changed': 0})
            slot['total'] += entry['total']
            slot['changed'] += entry['changed']
    print(f'runs: {runs}')
    for (action, kind), entry in sorted(totals.items(), key=lambda kv: -kv[1]['total']):
        rate = entry['changed'] / entry['total'] if entry['total'] else 0.0
        print(f'  {action:<12} {kind:<28} {entry["changed"]:>3}/{entry["total"]:<3} changed  {rate:.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
