"""Review one map frame's labels by eye, and write the correction back.

Usage:
    python tools/map_label_review.py --frame <run>/<frame>.png [--boxes "x,y,w,h;..."]
    python tools/map_label_review.py --frame <run>/<frame>.png --show

The rule's labels are printed with the frame, and the corrections are appended to
`build/map-dataset/hand-reviewed.jsonl`. A reviewed frame wins over the rule's labels
whenever the two disagree: the point of the file is that a rule did not produce it.

`node_type` uses the game's own node taxonomy (`battle`, `event`, `shop`, `reward`,
`rest`, `unknown`); the runtime does not read it yet -- it is there so a classifier can
learn "which node", not only "a node is here".
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.map_vision import gold_badge_drop, gold_marks  # noqa: E402

NODE_TYPES = ('battle', 'event', 'shop', 'reward', 'rest', 'unknown')
OUT = ROOT / 'build/map-dataset/hand-reviewed.jsonl'


def parse_boxes(text):
    boxes = []
    for chunk in str(text or '').replace(' ', '').split(';'):
        if not chunk:
            continue
        parts = [int(float(value)) for value in chunk.split(',')]
        if len(parts) != 4:
            raise SystemExit('每个框要写成 x,y,w,h：%s' % chunk)
        boxes.append(parts)
    return boxes


def rule_boxes(image):
    drop = gold_badge_drop(image)
    return [[int(x - 60), int(y + drop - 60), 120, 120] for x, y in gold_marks(image)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', required=True, help='<run>/<frame>.png，相对 evidence/runtime')
    parser.add_argument('--boxes', default='', help='人工框，x,y,w,h 用分号分隔')
    parser.add_argument('--types', default='', help='每个框的 node_type，逗号分隔')
    parser.add_argument('--show', action='store_true', help='只打印规则给出的框')
    parser.add_argument('--image', default='build/map-dataset/hand-reviewed.png')
    args = parser.parse_args(argv)
    import cv2
    path = Path(args.frame)
    if not path.is_file():
        path = ROOT / 'dist/MaaLimbus/evidence/runtime' / args.frame
    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit('读不到帧：%s' % path)
    from_rule = rule_boxes(image)
    if args.show:
        print(json.dumps(dict(frame=args.frame, rule=from_rule), ensure_ascii=False))
        return 0
    boxes = parse_boxes(args.boxes)
    types = [value.strip() for value in args.types.split(',') if value.strip()]
    for name in types:
        if name not in NODE_TYPES:
            raise SystemExit('未知 node_type：%s（可用 %s）' % (name, ', '.join(NODE_TYPES)))
    drawn = image.copy()
    for x, y, w, h in from_rule:
        cv2.rectangle(drawn, (x, y), (x + w, y + h), (0, 0, 255), 2)
    for x, y, w, h in boxes:
        cv2.rectangle(drawn, (x, y), (x + w, y + h), (0, 255, 0), 3)
    target = ROOT / args.image
    target.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(target), drawn)
    record = dict(frame=args.frame, rule_boxes=from_rule, boxes=boxes, node_types=types,
                  label_source='by_eye', reviewer='agent')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
    print('已记录 %s：人工 %d 框，规则 %d 框 -> %s' % (args.frame, len(boxes), len(from_rule), OUT))
    print('核对图=%s' % target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
