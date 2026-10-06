"""Compare the retained/live map frame with LALC's six path-node regions.

Read-only. Samples the six option regions that LixAssistantLimbusCompany
(431b432, `lalc_backend/utils/get_save_mirror_path.py:14-21`) uses for the mirror
path grid at both candidate authoring scales, and writes an annotated image. It
does not classify node types and never sends input.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# Pinned LALC path regions (x, y, w, h) in its own 1440x810 authoring space.
REGIONS = [
    (670, 90, 110, 90),   # first_up
    (670, 300, 110, 90),  # first_mid
    (670, 510, 110, 90),  # first_low
    (930, 90, 110, 90),   # second_up
    (930, 310, 110, 90),  # second_mid
    (930, 510, 110, 90),  # second_low
]
REGION_NAMES = ['first_up', 'first_mid', 'first_low', 'second_up', 'second_mid', 'second_low']


def sample(image, box, threshold=150):
    x, y, w, h = box
    height, width = image.shape[:2]
    if x < 0 or y < 0 or x + w > width or y + h > height:
        return None
    crop = image[y:y + h, x:x + w]
    gray = crop.max(axis=2)
    return dict(mean=float(gray.mean()), bright_ratio=float((gray >= threshold).mean()),
                max=float(gray.max()))


def scaled(box, factor):
    return tuple(int(round(value * factor)) for value in box)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', required=True)
    parser.add_argument('--annotation', default=str(ROOT / 'build/map-region-annotation.png'))
    args = parser.parse_args()
    image = cv2.imread(args.frame)
    assert image is not None, args.frame
    height, width = image.shape[:2]
    annotated = image.copy()
    results = {}
    for label, factor in (('1440x810-authoring', 1.0), ('720p-authoring', 0.5)):
        rows = []
        for name, box in zip(REGION_NAMES, REGIONS):
            projected = scaled(box, factor)
            rows.append(dict(region=name, lalc_box=list(box), projected_box=list(projected),
                             sample=sample(image, projected)))
        results[label] = rows
    # Draw both projections: solid for the 1440 authoring space, dashed for 720p.
    for name, box in zip(REGION_NAMES, REGIONS):
        for factor, colour in ((1.0, (0, 255, 0)), (0.5, (0, 200, 255))):
            x, y, w, h = scaled(box, factor)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), colour, 2)
            cv2.putText(annotated, f'{name}@{factor:g}', (x, max(14, y - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, .45, colour, 1, cv2.LINE_AA)
    cv2.imwrite(args.annotation, annotated)
    report = dict(source=args.frame, size=[width, height],
                  annotation=args.annotation,
                  lalc_source='LixAssistantLimbusCompany 431b432 lalc_backend/utils/get_save_mirror_path.py:14-21',
                  projections=results, input_sent=False,
                  scope='Region sampling only; no node classification, no route, no input.')
    output = ROOT / 'build/map-region-comparison.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
