"""Score the trained map detector against the rule on the held-out run, frame by frame.

The dataset is labelled by `maalimbus.map_vision.gold_marks`, so "the detector agrees
with its labels" says nothing about whether it is right. What this tool reports is where
the two *disagree*, so those frames can be adjudicated by eye -- and, on the frames that
were adjudicated, which side was right.

Usage: python tools/compare_map_detector.py [--weights build/map-model/run/weights/best.pt]
                                            [--run pi-20261021-185251] [--conf 0.25]
                                            [--render 3]
"""
import argparse, glob, json
from pathlib import Path

import cv2
import numpy as np

from maalimbus.map_vision import gold_marks

ROOT = Path(__file__).resolve().parents[1]


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    return inter / float(aw * ah + bw * bh - inter)


def model_boxes(model, image, conf):
    result = model.predict(image, conf=conf, imgsz=960, verbose=False, device='cpu')[0]
    boxes = []
    for box in result.boxes:
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
        boxes.append((int(round(x1)), int(round(y1)), int(round(x2 - x1)), int(round(y2 - y1))))
    return boxes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', default='build/map-model/run/weights/best.pt')
    parser.add_argument('--run', default=None)
    parser.add_argument('--conf', type=float, default=0.5)
    parser.add_argument('--render', type=int, default=0)
    parser.add_argument('--report', default='build/map-compare.json')
    args = parser.parse_args()

    from ultralytics import YOLO
    model = YOLO(str(ROOT / args.weights))
    # The frames come from the dataset manifest, which is the same set the model was
    # trained and scored on; walking evidence/runtime by hand misses the packaged runs
    # (dist/MaaLimbus/evidence/runtime/pi-*) that supply much of it.
    dataset = ROOT / 'build/map-dataset/samples.jsonl'
    samples = [json.loads(line) for line in dataset.read_text(encoding='utf-8').splitlines() if line.strip()]
    if args.run:
        samples = [row for row in samples if args.run in str(row.get('run', ''))]
    rows = []
    for sample in samples:
        image_path = str(sample['image'])
        image = cv2.imread(image_path)
        if image is None:
            continue
        rule = [(x - 44, y - 44, 120, 120) for (x, y) in gold_marks(image)]
        detected = model_boxes(model, image, args.conf)
        matched = sum(1 for box in rule if any(iou(box, d) >= 0.3 for d in detected))
        rows.append({'run': str(sample.get('run', '')), 'frame': Path(image_path).stem,
                     'rule': len(rule), 'model': len(detected), 'matched': matched,
                     'rule_only': len(rule) - matched, 'model_only': len(detected) - matched,
                     'image': image_path})
    report = {'weights': args.weights, 'conf': args.conf, 'frames': len(rows),
              'rule_boxes': sum(r['rule'] for r in rows),
              'model_boxes': sum(r['model'] for r in rows),
              'matched': sum(r['matched'] for r in rows),
              'agreeing_frames': sum(1 for r in rows if r['rule'] == r['model'] and not r['rule_only']),
              'disagreements': sorted([r for r in rows if r['rule_only'] or r['model_only']],
                                      key=lambda r: -(r['rule_only'] + r['model_only']))[:20]}
    for row in report['disagreements']:
        row['image'] = str(row['image']).replace(str(ROOT) + '\\\\', '')
    (ROOT / args.report).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'disagreements'}, indent=2))
    for row in report['disagreements'][:args.render]:
        image = cv2.imread(str(ROOT / row['image']))
        for (x, y, w, h) in [(x - 44, y - 44, 120, 120) for (x, y) in gold_marks(image)]:
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 3)
        for (x, y, w, h) in model_boxes(model, image, args.conf):
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 3)
        out = ROOT / 'build' / ('compare-%s-%s.png' % (row['run'][-10:], row['frame']))
        cv2.imwrite(str(out), image)
        print('rendered', out.relative_to(ROOT))


if __name__ == '__main__':
    main()
