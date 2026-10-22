"""Train a map node detector on the ring-labelled frames and score it on the held-out run.

Usage:
    python tools/train_map_model.py [--epochs N] [--model yolo11n.pt]

The rule (`maalimbus.map_vision.gold_marks`) labels the data; this trains a native detector
on those labels and reports its precision/recall on the one run the rule never labelled.
Nothing here is enabled in the runtime: the loop still reads the rule until the detector
beats it on the same frames.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'build/map-yolo/data.yaml'
OUT = ROOT / 'build/map-model'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epochs', type=int, default=25)
    parser.add_argument('--model', default='yolo11n.pt')
    parser.add_argument('--imgsz', type=int, default=960)
    args = parser.parse_args(argv)
    from ultralytics import YOLO
    model = YOLO(args.model)
    results = model.train(data=str(DATA), epochs=args.epochs, imgsz=args.imgsz,
                          project=str(OUT), name='run-%d' % args.imgsz, exist_ok=True, seed=7,
                          val=True, batch=8, workers=2, verbose=False)
    metrics = model.val(data=str(DATA), split='test', imgsz=args.imgsz,
                        project=str(OUT), name='val-%d' % args.imgsz, exist_ok=True)
    report = dict(model=args.model, epochs=args.epochs, imgsz=args.imgsz,
                  precision=float(metrics.box.mp), recall=float(metrics.box.mr),
                  map50=float(metrics.box.map50), map50_95=float(metrics.box.map),
                  weights=str(model.trainer.best if model.trainer else ''))
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
