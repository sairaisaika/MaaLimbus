"""Crop the brightest candidates of a map frame so a human can name the party dot.

The party marker was looked for by colour share and by bright-core-plus-warm-base
structure, and both returned nothing on red-themed maps (rounds 94-95) -- because the
thresholds were written before anyone had looked at the pixels.  This tool does the
looking: it cuts the N brightest blobs inside the board, labels each with its frame
coordinates, and writes one montage PNG.  Nothing here is a decision; it exists so the
next change is derived from a picture instead of guessed.

    python tools/probe_party_crop.py evidence/runtime/<run>/frame-0002.png
"""
import argparse
import pathlib
import sys

import cv2
import numpy as np

BOARD = (0.02, 0.03, 0.82, 0.86)


def candidates(image, count=8, side=96, value=140):
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([0, 0, value]), np.array([45, 255, 255]))
    left, top, right, bottom = BOARD
    mask[:int(height * top), :] = 0
    mask[int(height * bottom):, :] = 0
    mask[:, :int(width * left)] = 0
    mask[:, int(width * right):] = 0
    found = cv2.connectedComponentsWithStats(mask, 8)
    rows = []
    for index in range(1, found[0]):
        x, y, box_w, box_h, area = found[2][index]
        if area < 20:
            continue
        rows.append((int(area), int(x), int(y), int(box_w), int(box_h)))
    rows.sort(reverse=True)
    crops = []
    for area, x, y, box_w, box_h in rows[:count]:
        cx, cy = x + box_w // 2, y + box_h // 2
        half = side // 2
        patch = image[max(0, cy - half):cy + half, max(0, cx - half):cx + half]
        if patch.size == 0:
            continue
        patch = cv2.resize(patch, (side, side), interpolation=cv2.INTER_AREA)
        cv2.putText(patch, '%d,%d' % (cx, cy), (3, 14), cv2.FONT_HERSHEY_SIMPLEX, .45,
                    (0, 255, 0), 1, cv2.LINE_AA)
        crops.append(patch)
    return crops


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frame')
    parser.add_argument('--out', default='build/party-crops.png')
    parser.add_argument('--count', type=int, default=8)
    parser.add_argument('--side', type=int, default=96)
    parser.add_argument('--value', type=int, default=140)
    parser.add_argument('--region', default='',
                        help='x0,y0,x1,y1: crop and upscale this rectangle instead')
    args = parser.parse_args(argv)
    image = cv2.imread(str(args.frame))
    if image is None:
        print('no such frame: %s' % args.frame)
        return 1
    if args.region:
        try:
            x0, y0, x1, y1 = [int(v) for v in args.region.split(',')]
        except ValueError:
            print('--region wants x0,y0,x1,y1')
            return 1
        patch = image[y0:y1, x0:x1]
        if patch.size == 0:
            print('empty region')
            return 1
        scale = max(1.0, 900.0 / max(1, patch.shape[1]))
        big = cv2.resize(patch, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_NEAREST)
        for gx in range(0, patch.shape[1], 50):
            cv2.line(big, (int(gx * scale), 0), (int(gx * scale), big.shape[0]),
                     (90, 90, 90), 1)
            cv2.putText(big, str(x0 + gx), (int(gx * scale) + 2, 12),
                        cv2.FONT_HERSHEY_SIMPLEX, .35, (0, 255, 0), 1)
        for gy in range(0, patch.shape[0], 50):
            cv2.line(big, (0, int(gy * scale)), (big.shape[1], int(gy * scale)),
                     (90, 90, 90), 1)
            cv2.putText(big, str(y0 + gy), (2, int(gy * scale) + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, .35, (0, 255, 0), 1)
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), big)
        print('wrote %s region=%s x%.2f' % (out, args.region, scale))
        return 0
    crops = candidates(image, count=args.count, side=args.side, value=args.value)
    if not crops:
        print('no candidate above V=%d inside the board' % args.value)
        return 2
    rows = []
    for start in range(0, len(crops), 4):
        row = crops[start:start + 4]
        while len(row) < 4:
            row.append(np.zeros_like(crops[0]))
        rows.append(np.hstack(row))
    montage = np.vstack(rows)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), montage)
    print('wrote %s with %d candidate(s) from %s' % (out, len(crops), args.frame))
    return 0


if __name__ == '__main__':
    sys.exit(main())
