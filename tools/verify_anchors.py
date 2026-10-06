#!/usr/bin/env python
"""Offline anchor self-check: replay the anchor registry against retained frames.

A UI update should produce a short list of broken anchor names, not a silent
wrong click. Every anchor in assets/resource/base/anchors.json is replayed here
against the frames that were recorded when it was proven; a page stays green only
if its identity anchors still match. Geometry anchors are matched by frame
sha256, so they go stale the moment the frame changes.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

from maalimbus import anchors  # noqa: E402

DEFAULT_REGISTRY = 'assets/resource/base/anchors.json'
DEFAULT_TEMPLATE_ROOT = 'assets/resource/base'
DEFAULT_REPORT = 'build/anchors-report.json'


def load_observation(path):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def image_for(observation_path):
    candidate = Path(observation_path).with_suffix('.png')
    return candidate if candidate.exists() else None


def page_frames(args, page):
    if args.observation:
        return list(args.observation)
    return list(page.get('evidence') or ())


def evaluate_page(args, registry, page):
    frames = []
    for path in page_frames(args, page):
        observation = load_observation(path)
        if observation is None:
            frames.append({'frame': str(path), 'identity_ok': False,
                           'anchors': [], 'note': 'observation unreadable'})
            continue
        image_path = image_for(path)
        report = anchors.evaluate(registry, observation, page=page['id'],
                                  image_path=image_path,
                                  template_root=args.template_root)
        entry = report['pages'][0] if report['pages'] else {'identity': [], 'controls': [],
                                                            'identity_ok': False}
        frames.append({'frame': str(path), 'identity_ok': entry['identity_ok'],
                       'identity': entry['identity'], 'controls': entry['controls']})
    identity_ok = any(f['identity_ok'] for f in frames)
    return {'page': page['id'], 'title': page.get('title', ''), 'identity_ok': identity_ok,
            'frames': frames}


def frame_label(path):
    parts = Path(path).parts
    return '/'.join(parts[-2:]) if len(parts) >= 2 else str(path)


def print_page(result):
    state = 'OK  ' if result['identity_ok'] else 'FAIL'
    print('%s %-18s %s' % (state, result['page'], result['title']))
    for frame in result['frames']:
        if not frame.get('identity'):
            print('       %-18s (no observation: %s)' % ('', frame.get('note', frame['frame'])))
            continue
        mark = 'ok ' if frame['identity_ok'] else 'bad'
        print('       %s %s' % (mark, frame_label(frame['frame'])))
        for anchor in frame['identity'] + frame['controls']:
            if anchor.get('hit') is True:
                observed = anchor.get('observed') or {}
                if anchor['kind'] == 'template':
                    detail = 'score=%s box=%s' % (anchor.get('score'), observed.get('box'))
                else:
                    detail = observed.get('text') or observed.get('box') or anchor.get('note', '')
                print('           hit   %-26s %-9s %s' % (anchor['id'], anchor['kind'], detail))
            elif anchor.get('hit') is None:
                print('           skip  %-26s %-9s %s' % (anchor['id'], anchor['kind'],
                                                          anchor.get('reason', '')))
            else:
                print('           MISS  %-26s %-9s %s' % (anchor['id'], anchor['kind'],
                                                          anchor.get('note') or anchor.get('reason') or ''))


def frame_observation(path):
    """A live frame (a png, or its journal json) as an observation without OCR records.

    A bare frame carries no text recognition, so only template and geometry controls can be
    checked against it; the identity anchors are reported as unchecked instead of failing.
    """
    path = Path(path)
    json_path = None
    if path.suffix.lower() == '.json':
        json_path, image_path = path, path.with_suffix('.png')
    else:
        image_path = path
        sibling = path.with_suffix('.json')
        json_path = sibling if sibling.exists() else None
    if not image_path.exists():
        raise SystemExit('frame image not found: %s' % image_path)
    payload = load_observation(json_path) if json_path else None
    size = tuple(payload.get('size') or ()) if payload else ()
    if len(size) != 2:
        import cv2

        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise SystemExit('frame image unreadable: %s' % image_path)
        size = (image.shape[1], image.shape[0])
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    journal_sha = (payload or {}).get('image_sha256')
    observation = {'size': list(size), 'image_sha256': journal_sha or digest, 'live_frame': True}
    return observation, image_path, digest, journal_sha


def expected_box(roi, size):
    width, height = size
    return [int(round(roi[0] * width)), int(round(roi[1] * height)),
            int(round((roi[2] - roi[0]) * width)), int(round((roi[3] - roi[1]) * height))]


def verify_frame(args, registry):
    """Check every template/geometry control of the selected pages against one live frame."""
    observation, image_path, digest, journal_sha = frame_observation(args.frame)
    results, broken = [], []
    for page in registry['pages']:
        if args.page and page['id'] not in args.page:
            continue
        if not page.get('controls'):
            continue
        report = anchors.evaluate(registry, observation, page=page['id'], image_path=image_path,
                                  template_root=args.template_root)
        entry = report['pages'][0] if report['pages'] else {'controls': []}
        registered = {anchor['id']: anchor for anchor in (page.get('controls') or [])}
        controls = []
        for anchor in entry.get('controls') or ():
            row = dict(anchor)
            if anchor.get('hit') is True and anchor.get('observed', {}).get('box'):
                source = registered.get(anchor['id'], {})
                wanted = source.get('box') or (expected_box(anchor['roi'], observation['size'])
                                               if anchor.get('roi') else None)
                if wanted:
                    row['expected_box'] = list(wanted)
                    row['drift'] = [observed - expected
                                    for observed, expected in zip(anchor['observed']['box'], wanted)]
            controls.append(row)
            if row.get('stale') and not args.strict_geometry:
                continue  # a geometry anchor is only proven on its own frame sha; not a drift
            if row.get('hit') is not True:
                broken.append((page['id'], anchor['id'], row.get('reason') or 'miss'))
        results.append({'page': page['id'], 'title': page.get('title', ''), 'controls': controls})
    if not results:
        print('no page with controls matched the --page filter', file=sys.stderr)
        return None, None, None, None, None
    print('FRAME %s sha=%s size=%dx%d%s' % (image_path, (journal_sha or digest)[:12],
                                            observation['size'][0], observation['size'][1],
                                            '' if journal_sha else ' (png sha)'))
    print('      identity anchors are unchecked on a bare frame; controls only')
    for result in results:
        print('  page %s' % result['page'])
        for row in result['controls']:
            if row.get('hit') is True:
                detail = 'box=%s' % (row.get('observed') or {}).get('box')
                if row.get('expected_box'):
                    detail += ' expected=%s drift=%s' % (row['expected_box'], row['drift'])
                if row.get('score') is not None:
                    detail += ' score=%s' % row['score']
                print('    hit   %-26s %-9s %s' % (row['id'], row['kind'], detail))
            elif row.get('hit') is None or row.get('stale'):
                print('    skip  %-26s %-9s %s' % (row['id'], row['kind'], row.get('reason', '')))
            else:
                print('    MISS  %-26s %-9s %s' % (row['id'], row['kind'],
                                                   row.get('reason') or row.get('note') or ''))
    return results, broken, observation, image_path, journal_sha


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', default=DEFAULT_REGISTRY)
    parser.add_argument('--page', action='append', default=None,
                        help='only these page ids (repeatable)')
    parser.add_argument('--observation', action='append', default=None,
                        help='check these observation JSONs for every selected page')
    parser.add_argument('--frame', default=None,
                        help='check the controls against one live frame (png or journal json)')
    parser.add_argument('--template-root', default=DEFAULT_TEMPLATE_ROOT)
    parser.add_argument('--report', default=DEFAULT_REPORT)
    parser.add_argument('--strict-geometry', action='store_true',
                        help='also fail when a control geometry is stale')
    args = parser.parse_args(argv)

    registry = anchors.load(args.registry)
    anchors.resolve_evidence(registry, Path('.'))
    if args.frame:
        results, broken, observation, image_path, journal_sha = verify_frame(args, registry)
        if results is None:
            return 2
        report = {'registry': args.registry, 'mode': 'frame', 'frame': str(image_path),
                  'frame_sha256': observation['image_sha256'], 'size': observation['size'],
                  'pages': results, 'broken': [list(b) for b in broken], 'ok': not broken,
                  'note': 'identity anchors are unchecked on a bare frame'}
        destination = Path(args.report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
        print('\n%d page(s), %d drifted/missing control(s) -> %s'
              % (len(results), len(broken), destination))
        for page, anchor_id, reason in broken:
            print('  %s / %s: %s' % (page, anchor_id, reason))
        return 1 if broken else 0

    results = [evaluate_page(args, registry, page) for page in registry['pages']
               if not args.page or page['id'] in args.page]
    if not results:
        print('no page matched the --page filter', file=sys.stderr)
        return 2

    broken = []
    for result in results:
        print_page(result)
        page = next(p for p in registry['pages'] if p['id'] == result['page'])
        if not result['identity_ok']:
            broken.append((result['page'], 'identity', 'no evidence frame matched'))
        if args.strict_geometry:
            for frame in result['frames']:
                for anchor in frame.get('controls') or ():
                    if anchor.get('hit') is not True:
                        broken.append((result['page'], anchor['id'], anchor.get('note', 'stale')))

    report = {'registry': args.registry, 'reference_width': registry.get('reference_width', 1280),
              'pages': results, 'broken': [list(b) for b in broken], 'ok': not broken,
              'pending': registry.get('pending') or []}
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8')
    print('\n%d page(s), %d broken anchor group(s) -> %s'
          % (len(results), len(broken), destination))
    if broken:
        for page, anchor_id, reason in broken:
            print('  %s / %s: %s' % (page, anchor_id, reason))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
