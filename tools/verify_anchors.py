#!/usr/bin/env python
"""Offline anchor self-check: replay the anchor registry against retained frames.

A UI update should produce a short list of broken anchor names, not a silent
wrong click. Every anchor in assets/resource/base/anchors.json is replayed here
against the frames that were recorded when it was proven; a page stays green only
if its identity anchors still match. Geometry anchors are matched by frame
sha256, so they go stale the moment the frame changes.
"""
import argparse
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', default=DEFAULT_REGISTRY)
    parser.add_argument('--page', action='append', default=None,
                        help='only these page ids (repeatable)')
    parser.add_argument('--observation', action='append', default=None,
                        help='check these observation JSONs for every selected page')
    parser.add_argument('--template-root', default=DEFAULT_TEMPLATE_ROOT)
    parser.add_argument('--report', default=DEFAULT_REPORT)
    parser.add_argument('--strict-geometry', action='store_true',
                        help='also fail when a control geometry is stale')
    args = parser.parse_args(argv)

    registry = anchors.load(args.registry)
    anchors.resolve_evidence(registry, Path('.'))
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
