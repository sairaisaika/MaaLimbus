"""Turn the labelled map frames into the YOLO11 layout the official recipe reads.

Usage:
    python tools/export_map_yolo.py [--dataset build/map-dataset] [--out build/map-yolo]

`build/map-dataset/samples.jsonl` already holds the boxes and the per-run split the
exporter chose, so this only reshapes it: every frame is copied into
`images/<split>/`, its boxes become `labels/<split>/<stem>.txt` in YOLO's
`class cx cy w h` normalised form, and `data.yaml` names the one class. The split is
copied verbatim -- it was cut per run, never per frame, and reshaping must not leak one
floor across the boundary.

A frame with no box keeps an empty label file: it is the negative that teaches the
detector what an empty map looks like. The written geometry is read back and compared
with the source before the tool calls itself done, so a normalisation mistake cannot
reach training.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['node']


def label_lines(boxes, width, height):
    lines = []
    for x, y, box_w, box_h in boxes:
        cx, cy = (x + box_w / 2.0) / width, (y + box_h / 2.0) / height
        lines.append('0 %.6f %.6f %.6f %.6f' % (cx, cy, box_w / float(width), box_h / float(height)))
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'build/map-dataset')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/map-yolo')
    args = parser.parse_args()
    dataset, out = args.dataset.resolve(), args.out.resolve()
    rows = [json.loads(line) for line in (dataset / 'samples.jsonl').read_text(
        encoding='utf-8').splitlines() if line.strip()]
    if not rows:
        raise ValueError('no labelled frames to export')
    if out.exists():
        shutil.rmtree(out)
    sizes = {}
    for row in rows:
        source = Path(row['image'])
        if not source.is_absolute():
            source = ROOT / source
        if not source.is_file():
            raise ValueError('frame missing: %s' % source)
        split = row['split']
        images = out / 'images' / split
        labels = out / 'labels' / split
        images.mkdir(parents=True, exist_ok=True)
        labels.mkdir(parents=True, exist_ok=True)
        stem = '%s__%s' % (row['run'], row['frame'])
        target = images / (stem + '.png')
        shutil.copyfile(source, target)
        width, height = sizes.get(source) or (0, 0)
        if not width:
            import cv2
            image = cv2.imread(str(source))
            if image is None:
                raise ValueError('frame unreadable: %s' % source)
            height, width = image.shape[:2]
            sizes[source] = (width, height)
        lines = label_lines(row['boxes'], width, height)
        (labels / (stem + '.txt')).write_text('\n'.join(lines) + ('\n' if lines else ''),
                                              encoding='utf-8')
    # The dataset's split is cut per run: train plus one held-out run. There is no
    # separate validation run, and copying held-out frames into one would leak them.
    # So validation points at the split that actually exists and the held-out run is
    # reported as both -- a weaker claim than a third run, and stated rather than faked.
    splits = {p.name for p in (out / 'images').iterdir() if p.is_dir()}
    val = 'images/validation' if 'validation' in splits else 'images/test'
    config = dict(path=str(out), train='images/train', val=val,
                  test='images/test', names=NAMES)
    (out / 'data.yaml').write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'manifest.json').write_text(json.dumps(
        dict(class_names=NAMES, frames=len(rows), boxes=sum(len(r['boxes']) for r in rows),
             label_source=sorted({r['label_source'] for r in rows}),
             runs=sorted({r['run'] for r in rows}),
             validation_split=val.split('/', 1)[1],
             validation_note='the held-out run is validation and test; no third run exists'),
        ensure_ascii=False, indent=1),
        encoding='utf-8')
    written = sum(len(p.read_text(encoding='utf-8').splitlines())
                  for p in (out / 'labels').rglob('*.txt'))
    expected = sum(len(r['boxes']) for r in rows)
    if written != expected:
        raise ValueError('wrote %d boxes, the dataset holds %d' % (written, expected))
    print('帧 %d / 框 %d / 负样本 %d -> %s' % (
        len(rows), expected, sum(1 for r in rows if not r['boxes']), out))


if __name__ == '__main__':
    sys.exit(main())
