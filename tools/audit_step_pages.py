"""把「观察到的页面」和「循环当时认为自己在哪一页」对到一起。

D361 的账错在这里：`map_observed.scene` 里确实有 UNKNOWN，但那几次都发生在 **settle 循环
内部**，而 `loop_heartbeat` 的 `page` 每次都是 MAP——step 起点从来没读到 UNKNOWN，
因此挂在起点的 `unknown_needs_reread` / `map_by_structure` 一次都不该触发。

用法：python tools/audit_step_pages.py [evidence/runtime/<run>]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def report(run) -> dict:
    run = pathlib.Path(run)
    path = run / 'events.jsonl'
    if not path.is_file():
        return {'run': run.name, 'error': 'no events'}
    events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    observed = [e.get('scene') for e in events if e.get('event') == 'map_observed']
    beats = [e.get('page') for e in events if e.get('event') == 'loop_heartbeat']
    starts = [page for page in beats if page]
    return {
        'run': run.name,
        'observed': len(observed),
        'observed_unknown': observed.count('UNKNOWN'),
        'step_starts': len(starts),
        'step_starts_unknown': starts.count('UNKNOWN'),
        'verdict': ('the unreadable frames live inside a step, not at its start'
                    if starts.count('UNKNOWN') == 0 and observed.count('UNKNOWN')
                    else 'the step itself starts on an unreadable page'),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='观察到的页面 vs 循环认为的页面')
    parser.add_argument('run', nargs='?', default=None)
    args = parser.parse_args(argv)
    if args.run:
        runs = [pathlib.Path(args.run)]
    else:
        runtime = ROOT / 'evidence' / 'runtime'
        runs = sorted((p for p in runtime.glob('*') if p.is_dir()),
                      key=lambda p: p.stat().st_mtime)[-3:]
    rows = [report(run) for run in runs]
    for row in rows:
        if 'error' in row:
            print('%-46s %s' % (row['run'], row['error']))
            continue
        print('%-46s 观察 %2d（UNKNOWN %d）  步首 %2d（UNKNOWN %d）  %s'
              % (row['run'], row['observed'], row['observed_unknown'],
                 row['step_starts'], row['step_starts_unknown'], row['verdict']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
