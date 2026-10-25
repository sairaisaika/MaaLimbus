"""Measure whether a page's picture separates a map from its node panel.

The map's identity is text (the floor header plus a theme pack line, D231), and the pack
line is missing on some pages, so the only remaining discriminator is the picture.  This
tool measures two structural features -- the share of bright pixels in the lattice band and
the number of bright connected components -- over every archived frame whose scene is
already named, and prints the two distributions.  It decides nothing: a threshold is only
honest once the ranges do not overlap with margin.

Measured 2026-10-25 (25 recent runs, 10 frames each): MAP n=69 bright 0.001-0.004, panels
n=3 bright 0.006-0.017 -- separated by 0.005 with a one-bit margin, which is why no reader
was wired.
"""
import argparse
import json
import pathlib
import statistics
import sys

import cv2
import numpy as np

SCENES = ('MAP', 'NODE_PANEL')


def features(path):
    image = cv2.imread(str(path))
    if image is None:
        return None
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = grey.shape
    band = grey[int(.22 * height):int(.78 * height), int(.10 * width):int(.90 * width)]
    bright = band > 150
    components, _labels = cv2.connectedComponents(bright.astype(np.uint8))
    return float(bright.mean()), int(components)


def survey(directory=None, *, limit=25, frames=10):
    root = pathlib.Path(directory or 'evidence/runtime')
    runs = sorted(root.glob('packaged-mirror-*'), key=lambda p: p.stat().st_mtime)[-limit:]
    groups = {scene: [] for scene in SCENES}
    for run in runs:
        for meta in sorted(run.glob('frame-*.json'))[:frames]:
            try:
                record = json.loads(meta.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            scene = record.get('scene')
            picture = meta.with_suffix('.png')
            if scene not in groups or not picture.exists():
                continue
            measured = features(picture)
            if measured is not None:
                groups[scene].append(measured)
    return {'runs': len(runs), 'groups': groups}


def _range(values):
    return (round(min(values), 3), round(statistics.median(values), 3), round(max(values), 3))


def report(data):
    lines = [f"runs read: {data['runs']}"]
    for scene, rows in data['groups'].items():
        if not rows:
            lines.append(f'{scene}: no frame whose picture was kept')
            continue
        bright = _range([row[0] for row in rows])
        components = [row[1] for row in rows]
        lines.append(f'{scene}: n={len(rows)} bright {bright} components '
                     f'({min(components)}-{max(components)})')
    maps = [row[0] for row in data['groups']['MAP']]
    panels = [row[0] for row in data['groups']['NODE_PANEL']]
    if maps and panels:
        gap = round(min(panels) - max(maps), 3)
        lines.append(f'brightest gap between a map and a panel: {gap}'
                     + (' (no overlap, but check the margin)' if gap > 0 else ' (overlap: not separable)'))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description='Measure the map/panel structural split.')
    parser.add_argument('--root', default=None, help='evidence root (default evidence/runtime)')
    parser.add_argument('--limit', type=int, default=25, help='how many recent runs to read')
    parser.add_argument('--json', action='store_true', help='print the raw survey')
    args = parser.parse_args(argv)
    data = survey(args.root, limit=args.limit)
    if args.json:
        print(json.dumps(data, indent=1))
    else:
        for line in report(data):
            print(line)
    return 0 if any(rows for rows in data['groups'].values()) else 2


if __name__ == '__main__':
    sys.exit(main())
