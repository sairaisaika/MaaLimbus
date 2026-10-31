"""把一帧上的四个“我方读数”并排打印，看谁在抢答。

存在的理由：`party_point` 是四档读数的仲裁结果，而某一档在两个相邻帧之间会换答案
（实跑 `-141847/frame-0001` 火苗 (864,543) 答得出，`frame-0003` 起火苗为 None、只剩
格子辉光 (575,335)）。并排看四个读数，才知道换的是哪一档、换得对不对。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import cv2  # noqa: E402

from maalimbus import map_vision as mv  # noqa: E402


def readings(image):
    """Every reader's own answer for this frame, in the order party_point consults them."""
    return {
        'party_point': mv.party_point(image),
        'flame_point': mv.flame_point(image),
        'glow_point': mv.glow_point(image),
        'player_marker': mv.player_marker(image),
    }


def survey(directory, *, limit=8):
    rows = []
    for path in sorted(pathlib.Path(directory).glob('frame-*.png'))[:limit]:
        image = cv2.imread(str(path))
        if image is None:
            continue
        rows.append({'frame': path.stem, 'readings': readings(image)})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description='四个我方读数并排')
    parser.add_argument('directory')
    parser.add_argument('--limit', type=int, default=8)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    rows = survey(args.directory, limit=args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    for row in rows:
        values = row['readings']
        print('%s  party=%s  flame=%s  glow=%s  marker=%s' % (
            row['frame'], values['party_point'], values['flame_point'],
            values['glow_point'], values['player_marker']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
