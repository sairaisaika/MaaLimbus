"""Print the grey profile of the line from the party to each nearby tile.

Measured on `evidence/runtime/packaged-mirror-20261025-160619/frame-0005.png`: the frame's
grey median is 4 and its p90 is 22, while a tile that a line connects reads p50 32-54 and
carries lit pixels (>30) on 54-85% of the segment; a tile with no line reads p50 3-8 and
9-16%.  So "a lit line" cannot be `grey > 90` -- nothing on that frame reaches 90 except the
badges.  This tool exists so the threshold is read off a distribution instead of inherited.
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from maalimbus import map_vision  # noqa: E402


def profile(image, start, end, *, lit, samples=240, skip=0.2):
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    xs = np.linspace(start[0], end[0], samples)
    ys = np.linspace(start[1], end[1], samples)
    row = np.array([grey[int(round(y)), int(round(x))] for x, y in zip(xs, ys)], float)
    core = row[int(len(row) * skip):int(len(row) * (1 - skip))]
    return {'percentiles': [round(float(v), 1) for v in np.percentile(core, [0, 25, 50, 75, 90, 100])],
            'share': round(float((core > lit).mean()), 3)}


def report(image, party=None, *, lit=None, reach=None):
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    if party is None:
        party = map_vision.party_point(image)
    if party is None:
        return {'party': None, 'lit': lit, 'rows': []}
    lit = max(26.0, float(np.percentile(grey, 90)) + 8.0) if lit is None else float(lit)
    reach = (image.shape[1] * 0.30) if reach is None else float(reach)
    rows = []
    for item in map_vision.map_clicks(image, player=party):
        box = list(item['box'])
        centre = (box[0] + box[2] / 2.0, box[1] + box[3] / 2.0)
        distance = ((centre[0] - party[0]) ** 2 + (centre[1] - party[1]) ** 2) ** 0.5
        if distance > reach:
            continue
        row = profile(image, party, centre, lit=lit)
        rows.append({'box': [int(v) for v in box[:4]], 'kind': item.get('kind'),
                     'distance': round(distance, 1), **row})
    rows.sort(key=lambda r: -r['share'])
    return {'party': [int(party[0]), int(party[1])], 'lit': round(lit, 1),
            'reach': round(reach, 1), 'rows': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description='grey profile of the party-to-tile lines')
    parser.add_argument('frame')
    parser.add_argument('--party', default=None, help='x,y (default: the reader)')
    parser.add_argument('--lit', type=float, default=None)
    args = parser.parse_args(argv)
    image = cv2.imread(str(args.frame))
    if image is None:
        print('cannot read %s' % args.frame, file=sys.stderr)
        return 1
    party = None
    if args.party:
        party = tuple(int(v) for v in args.party.split(','))
    data = report(image, party, lit=args.lit)
    print('party %s  lit %s  reach %s' % (data['party'], data['lit'], data['reach']))
    for row in data['rows']:
        print('  %-22s %-18s dist %5.0f  pct %s  share %.3f'
              % (row['box'], row['kind'], row['distance'], row['percentiles'], row['share']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
