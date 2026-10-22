"""Export labelled map frames: the gold-ring reader is the labeler, not the runtime.

Usage:
    python tools/export_map_dataset.py [--runs N] [--out build/map-dataset]

A map frame is labelled by the same reader the live loop already trusts
(`maalimbus.map_vision.gold_marks`): the game draws a gold ring above every node it
offers, and the node itself sits a fixed distance below that ring.  The exporter turns
that into object-detection boxes so a native `NeuralNetworkDetect` candidate can be
trained and then compared against the rule on held-out frames.

Splits are made per run, never per frame: two frames of one floor are the same
situation and would leak.  A frame whose page is not a map is skipped; a map frame with
no ring is written with an empty box list as a negative.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.map_vision import gold_badge_drop, gold_marks  # noqa: E402

NODE_SIDE = 120


def is_map_page(record):
    """The classifier's own scene label; the header OCR is too often unreadable."""
    return str(record.get('scene') or '').upper() == 'MAP'


def image_of(record_path):
    for suffix in ('.png', '.jpg', '.jpeg'):
        candidate = record_path.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None


def label_frame(path):
    import cv2
    image = cv2.imread(str(path))
    if image is None:
        return None
    drop = gold_badge_drop(image)
    half = NODE_SIDE // 2
    boxes = []
    for x, y in gold_marks(image):
        cx, cy = x, y + drop
        boxes.append([int(cx - half), int(cy - half), NODE_SIDE, NODE_SIDE])
    return boxes


def reviewed(root):
    """Frames somebody looked at by eye: their boxes are the truth, not the rule's.

    A reviewed frame only carries the nodes that are targets; the player's own node and
    unoffered nodes are left out, so an empty list here means "nothing to click", which is
    different from "the rule found nothing".
    """
    path = root / 'assets/resource/base/map-labels/hand-reviewed.jsonl'
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        key = str(record['frame']).replace('\\', '/')
        for suffix in ('.png', '.jpg', '.jpeg'):
            if key.endswith(suffix):
                key = key[: -len(suffix)]
                break
        out[key] = record
    return out


def export(runs, out):
    runtime = ROOT / 'dist/MaaLimbus/evidence/runtime'
    folders = sorted(p for p in runtime.glob('pi-*') if p.is_dir())[-runs:]
    by_eye = reviewed(ROOT)
    samples, skipped = [], 0
    for folder in folders:
        for record_path in sorted(folder.glob('frame-*.json')):
            try:
                record = json.loads(record_path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                skipped += 1
                continue
            if not is_map_page(record):
                continue
            image = image_of(record_path)
            if image is None:
                skipped += 1
                continue
            boxes = label_frame(image)
            if boxes is None:
                skipped += 1
                continue
            looked_at = by_eye.get('%s/%s' % (folder.name, record_path.stem))
            if looked_at is not None:
                boxes = looked_at['boxes']
                source = 'by_eye'
            else:
                source = 'gold_ring_above_the_offered_node'
            samples.append(dict(run=folder.name, frame=record_path.stem,
                                image=str(image.relative_to(ROOT)), boxes=boxes,
                                label_source=source))
    runs_seen = sorted({sample['run'] for sample in samples})
    held_out = runs_seen[-1:] if len(runs_seen) > 1 else []
    for sample in samples:
        sample['split'] = 'test' if sample['run'] in held_out else 'train'
    return samples, runs_seen, held_out, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=40)
    parser.add_argument('--out', default='build/map-dataset')
    args = parser.parse_args(argv)
    samples, runs_seen, held_out, skipped = export(args.runs, args.out)
    target = ROOT / args.out
    target.mkdir(parents=True, exist_ok=True)
    (target / 'samples.jsonl').write_text(
        '\n'.join(json.dumps(sample, ensure_ascii=False, sort_keys=True) for sample in samples) + '\n',
        encoding='utf-8')
    positives = [sample for sample in samples if sample['boxes']]
    print('地图帧：%d 张（有标记 %d，负样本 %d），来自 %d 局，跳过 %d'
          % (len(samples), len(positives), len(samples) - len(positives), len(runs_seen), skipped))
    print('留出一局：%s' % (held_out or '无（局数不足，先全部当训练）'))
    print('箱子总数：%d（人工复核 %d 帧）'
          % (sum(len(sample['boxes']) for sample in samples),
             sum(1 for sample in samples if sample['label_source'] == 'by_eye')))
    print('清单=%s' % (target / 'samples.jsonl'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
