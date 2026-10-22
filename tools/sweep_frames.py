"""Score many readings of the same archived frames at once, against what the game did.

The frames are already on disk, together with the journal that says which box the run
actually clicked and whether that click moved the page.  That makes the reading problem
a labelled dataset instead of something to be judged one screen at a time: every variant
in the family is measured on every frame, in parallel, and the output is a hit table.

Ground truth is the recorded intent box.  A variant hits a frame when one of its boxes
covers that point; it is wrong when it offers nothing (a miss) or offers boxes far from
it.  Nothing here guesses what the right answer is.

    python tools/sweep_frames.py --workers 8 --page MAP
"""
from __future__ import annotations
import argparse, json, multiprocessing as mp
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent


def labels(page):
    """frame path -> the point the run actually clicked on that frame."""
    found = {}
    for journal in sorted((ROOT / 'evidence/runtime').glob('*')):
        events = journal / 'events.jsonl'
        if not events.exists():
            continue
        pending = None
        for line in events.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get('event') == 'map_observed':
                pending = event.get('frame')
            elif event.get('event') == 'window_intent' and pending and event.get('page') == page:
                box = event.get('target')
                if box:
                    found[str(journal / (pending + '.png'))] = (
                        box[0] + box[2] // 2, box[1] + box[3] // 2)
                pending = None
    return found


def rule_plain(image):
    """The shipped reading: gold rings, each lifted onto the node below it."""
    from maalimbus.map_vision import gold_marks, gold_badge_drop
    return [(x, y + gold_badge_drop(image)) for (x, y) in gold_marks(image)]


def rule_rings_only(image):
    """The ring centres themselves, without lifting them onto the node."""
    from maalimbus.map_vision import gold_marks
    return list(gold_marks(image))


_MODEL = {}
_WEIGHTS = {960: 'build/map-model/run/weights/best.pt',
            1280: 'build/map-model/run-1280/weights/best.pt'}


def model_boxes(image, imgsz):
    """A detector's centres at its own training resolution (never a rescaled one)."""
    if imgsz not in _MODEL:
        from ultralytics import YOLO
        _MODEL[imgsz] = YOLO(str(ROOT / _WEIGHTS[imgsz]))
    result = _MODEL[imgsz].predict(image, conf=0.5, imgsz=imgsz, verbose=False, device='cpu')[0]
    boxes = getattr(result, 'boxes', None)
    if boxes is None:
        return []
    # xywh is already (centre_x, centre_y, width, height); adding half a width to a
    # centre shifted every box by ~60 px and turned every hit into a miss.
    return [(int(x), int(y)) for x, y, w, h in boxes.xywh.tolist()]


VARIANTS = {'rule_plain': rule_plain, 'rule_rings_only': rule_rings_only}
for _size in (960, 1280):
    if (ROOT / _WEIGHTS[_size]).exists():
        VARIANTS['model_%d' % _size] = _size


def score(job):
    name, frame, point = job[0], job[2], job[3]
    image = cv2.imread(frame)
    if image is None:
        return {'variant': name, 'frame': frame, 'result': 'unreadable'}
    try:
        reader = VARIANTS[name]
        boxes = model_boxes(image, reader) if isinstance(reader, int) else reader(image)
    except Exception as error:                      # a variant that crashes is a miss
        return {'variant': name, 'frame': frame, 'result': 'raised', 'error': str(error)[:200]}
    nearest = min((abs(x - point[0]) + abs(y - point[1]) for (x, y) in boxes), default=None)
    return {'variant': name, 'frame': frame, 'boxes': len(boxes), 'nearest': nearest,
            'result': 'hit' if nearest is not None and nearest <= 60 else 'miss'}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--page', default='MAP')
    parser.add_argument('--out', default='build/sweep-hits.jsonl')
    args = parser.parse_args()
    truth = labels(args.page)
    if not truth:
        print('no labelled %s frames' % args.page)
        return 2
    jobs = [(name, VARIANTS[name], frame, point)
            for name in VARIANTS for frame, point in truth.items()]
    with mp.Pool(args.workers) as pool:
        rows = pool.map(score, jobs)
    out = ROOT / args.out
    with out.open('w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    for name in sorted({row['variant'] for row in rows}):
        mine = [row for row in rows if row['variant'] == name]
        hits = sum(1 for row in mine if row['result'] == 'hit')
        errors = sum(1 for row in mine if row['result'] == 'raised')
        # A variant that crashed is not a variant that missed: keep them apart or a
        # broken environment reads as a bad reader.
        usable = len(mine) - errors
        print('%-16s frames %4d  errors %3d  hit %4d  (%5.1f%%)' % (
            name, len(mine), errors, hits, 100.0 * hits / max(1, usable)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
