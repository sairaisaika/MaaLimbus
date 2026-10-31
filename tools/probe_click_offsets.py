"""每次地图点击相对我方的偏移，以及它是不是“一格”内的目标。

为什么需要：一局里的点击不全走同一条路径（候选列表、重试、盲点分支各发各的），
只看 accepted 率看不出“有几发是按一格内规则发的”。实跑 `-142243` 的 21 次点击里
dx 同时出现 96（半格，合法斜向）与 ±287/±480（1.5–2.5 格，不该发）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys


def offset(party, point, *, step):
    """(dx, dy, in_one_step) for one click, in the frame's own space."""
    if not party or not point:
        return None
    dx = int(point[0]) - int(party[0])
    dy = int(point[1]) - int(party[1])
    reach = 1.25 * float(step)
    return {'dx': dx, 'dy': dy, 'in_one_step': abs(dx) <= reach and abs(dy) <= reach}


def rows_from(events, *, step=190):
    """One row per map click that names both where the party was and where the click went."""
    rows = []
    for event in events:
        if event.get('event') != 'map_click_result':
            continue
        point = event.get('point')
        if not point and event.get('target'):
            box = list(event['target']) + [0, 0, 0, 0]
            point = [box[0] + box[2] // 2, box[1] + box[3] // 2 - int(round(0.18 * box[3]))]
        row = offset(event.get('party'), point, step=step)
        if row is None:
            continue
        row.update({'outcome': event.get('outcome'), 'frame': event.get('frame')})
        rows.append(row)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description='点击相对我方的偏移')
    parser.add_argument('directory')
    parser.add_argument('--step', type=float, default=190.0)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    path = pathlib.Path(args.directory) / 'events.jsonl'
    events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    rows = rows_from(events, step=args.step)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    for row in rows:
        print('%-11s dx=%4d dy=%4d one_step=%s  %s' % (
            row['outcome'], row['dx'], row['dy'], row['in_one_step'], row['frame']))
    far = [row for row in rows if not row['in_one_step']]
    print('\nclicks %d   over one step %d' % (len(rows), len(far)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
