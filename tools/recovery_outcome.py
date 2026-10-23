"""Which recovery actions are followed by an actual change of page?

A recovery is only useful if the page it was spent on is not the page that comes
next.  This replays every retained run and pairs each recovery with the next page
it saw, so "recover" can be scored by outcome instead of by count.
"""
from __future__ import annotations
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVENTS = ('window_recovery', 'window_reread')


INPUTS = ('window_intent', 'map_click_result')


def pairs(events):
    """Yield (recovery_event, page_seen_after_its_input).

    A recovery is written when the action is decided; the click or swipe it asks for
    lands afterwards.  Pairing it with the next page event therefore measures the frame
    that was already on screen, which biases every action towards "no change".  Skip
    ahead to the first page observed *after* the input the recovery asked for.
    """
    for i, event in enumerate(events):
        if event.get('event') not in EVENTS:
            continue
        boundary = None
        for j in range(i + 1, len(events)):
            if events[j].get('event') in INPUTS:
                boundary = j
                break
        if boundary is None:      # the recovery never asked for an input: no evidence
            yield event, None
            continue
        page = None
        for k in range(boundary + 1, len(events)):
            page = events[k].get('page') or events[k].get('scene')
            if page:
                break
        yield event, page


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
