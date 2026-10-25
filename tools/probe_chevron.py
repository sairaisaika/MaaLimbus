#!/usr/bin/env python
"""Print the shapes around the party so the step chevron can be measured, not guessed.

The path chevron is the game's own statement about which node the page will accept, and it is
not a node: on `packaged-mirror-20261025-135349/frame-0005` it is two small glyphs side by side
(~22x10 each) at (844,215)-(885,223), while every node mark is a compact 24x27 badge.  The
detector in `map_vision.marker_boxes` returns nothing on that frame, so the threshold has to
come from measurements like this one rather than from the 1080p constants that were written
for the archived captures.

Usage:
    python tools/probe_chevron.py EVIDENCE_FRAME.png [--party X,Y] [--radius 260]
"""

import argparse
import sys

import cv2
import numpy as np


def regions(image, party, radius):
    height, width = image.shape[:2]
    x0 = max(0, party[0] - radius)
    x1 = min(width, party[0] + radius)
    y0 = max(0, party[1] - radius)
    y1 = min(height, party[1] + radius)
    crop = image[y0:y1, x0:x1]
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    rows = []
    for threshold in (110, 125, 140, 155):
        mask = (grey > threshold).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 7), np.uint8))
        count, _labels, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
        found = []
        for index in range(1, count):
            area = int(stats[index][4])
            side_w, side_h = int(stats[index][2]), int(stats[index][3])
            if area < 120 or side_h == 0:
                continue
            ratio = side_w / float(side_h)
            if not (1.0 <= ratio <= 4.0):
                continue
            cx, cy = int(centres[index][0]) + x0, int(centres[index][1]) + y0
            patch = hsv[max(0, cy - y0 - side_h // 2):cy - y0 + side_h // 2 + 1,
                        max(0, cx - x0 - side_w // 2):cx - x0 + side_w // 2 + 1]
            if patch.size == 0:
                continue
            found.append({'area': area, 'w': side_w, 'h': side_h, 'ratio': round(ratio, 2),
                          'centre': [cx, cy],
                          'hsv': [int(v) for v in patch.reshape(-1, 3).mean(axis=0)]})
        rows.append((threshold, sorted(found, key=lambda item: -item['area'])[:6]))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('frame')
    parser.add_argument('--party', default='500,244')
    parser.add_argument('--radius', type=int, default=260)
    args = parser.parse_args(argv)
    image = cv2.imread(args.frame)
    if image is None:
        print('no such frame: %s' % args.frame, file=sys.stderr)
        return 2
    party = [int(v) for v in args.party.split(',')]
    print('frame %s %dx%d party %s' % (args.frame, image.shape[1], image.shape[0], party))
    for threshold, found in regions(image, party, args.radius):
        print('threshold %d: %d shape(s)' % (threshold, len(found)))
        for item in found:
            print('   area %4d %3dx%-3d ratio %.2f centre %s hsv %s'
                  % (item['area'], item['w'], item['h'], item['ratio'], item['centre'],
                     item['hsv']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
