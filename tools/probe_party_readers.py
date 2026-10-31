"""把“我方”的每个读数并列出来，并标出它是否落在某个已检出的格框上。

用来回答“该信谁”这个问题：`glow_point`、`flame_point`、`player_marker` 各自能给出一个点，
但它们在不同帧里互相矛盾（实测 `-164228`：glow (766,335) 稳定，flame 在 frame-0002/0003
跳到 (1439,189) 的右侧装饰上）。判据不该在几个读数之间投票，而该看**谁落在游戏自己画的
格子框里**。

用法：
    python tools/probe_party_readers.py                 # 最近一次 run 的前 5 帧
    python tools/probe_party_readers.py --frames 10
    python tools/probe_party_readers.py --run evidence/runtime/packaged-mirror-xxx
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

READERS = ('_bgr_party_point', 'glow_point', 'flame_point', 'player_marker')


def latest_run(root=ROOT / 'evidence/runtime'):
    runs = sorted((p for p in root.glob('packaged-mirror-*') if p.is_dir()),
                  key=lambda p: p.stat().st_mtime)
    return runs[-1] if runs else None


def describe(image, boxes):
    """每个读数 + 是否落在某个格框内。"""
    import maalimbus.map_vision as vision

    def inside(point):
        if point is None:
            return None
        px, py = point
        for box in boxes:
            x, y, w, h = [float(v) for v in box[:4]]
            if x <= px <= x + w and y <= py <= y + h:
                return [int(x), int(y)]
        return None

    rows = {}
    for name in READERS:
        function = getattr(vision, name, None)
        if function is None:
            continue
        try:
            point = function(image)
        except Exception as error:  # 只读探针，不抛
            rows[name] = {'point': None, 'error': type(error).__name__}
            continue
        rows[name] = {'point': None if point is None else [int(point[0]), int(point[1])],
                      'inside': inside(point)}
    return rows


def main(argv=None):
    import cv2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=pathlib.Path, default=None)
    parser.add_argument('--frames', type=int, default=5)
    args = parser.parse_args(argv)
    run = args.run or latest_run()
    if run is None or not run.is_dir():
        print('no run directory to look at')
        return 2
    import maalimbus.map_vision as vision
    seen = 0
    for png in sorted(run.glob('frame-*.png')):
        image = cv2.imread(str(png))
        if image is None:
            continue
        boxes = [item['box'] if isinstance(item, dict) else item
                 for item in (vision.map_clicks(image) or [])]
        print(png.name, 'boxes', len(boxes))
        for name, row in describe(image, boxes).items():
            print('   %-16s %-14s inside=%s' % (name, row.get('point'), row.get('inside')))
        seen += 1
        if seen >= args.frames:
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
