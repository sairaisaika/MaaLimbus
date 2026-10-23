"""Where do the runs that end without a stop actually stop?

`tools/audit_runs.py` counts them (32 of 107).  This names them.  A run is "silent"
when it has no `mirror_loop_stopped` / `mirror_loop_error`: the process died
natively, so the last thing written is whatever it was doing -- which is the only
evidence of the cause.  Runs from before 2026-10-23 have no `loop_heartbeat`, so the
last business event and the last heartbeat are reported separately rather than
being conflated.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os

STOPS = {'mirror_loop_stopped', 'mirror_loop_error'}


def load(path):
    records = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    return records


def summarise(root):
    runs = collections.Counter()
    last_events = collections.Counter()
    last_pages = collections.Counter()
    builds = collections.Counter()
    heartbeats = 0
    for path in sorted(glob.glob(os.path.join(root, 'packaged-mirror-*', 'events.jsonl'))):
        records = load(path)
        if not records:
            runs['empty'] += 1
            continue
        if any(r.get('event') in STOPS for r in records):
            runs['stopped'] += 1
            continue
        runs['silent'] += 1
        business = [r for r in records if r.get('event') != 'loop_heartbeat']
        beats = [r for r in records if r.get('event') == 'loop_heartbeat']
        if business:
            last_events[business[-1].get('event')] += 1
        if beats:
            heartbeats += 1
            last_pages[beats[-1].get('page') or '(none)'] += 1
            builds[str(beats[-1].get('build'))[:8]] += 1
    return {'runs': dict(runs), 'silent_last_event': last_events.most_common(),
            'silent_last_page': last_pages.most_common(),
            'silent_last_build': builds.most_common(), 'silent_with_heartbeat': heartbeats}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='evidence/runtime')
    args = parser.parse_args(argv)
    report = summarise(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
