"""Capture one anchor from a recorded frame and register it in the anchor registry.

The maintenance story of docs/script-mode-plan.md section 5.3 is "turning screenshot
harvesting into a single command": a human names the control, points at the frame and
the box, and this tool crops the template, stores it on the 1280 baseline and appends
(or replaces, with --force) the matching entry in assets/resource/base/anchors.json.

Two kinds are supported:

* ``--kind template`` (default): crops the box, rescales it to the registry baseline,
  stores it under the template root and registers
  ``{id, kind: 'template', template: <relative path>, roi, threshold}``.  The freshly
  written template is matched back against its own source frame; a capture that does not
  hit is a failure (exit 1) instead of a silently broken anchor.
* ``--kind geometry``: registers ``{id, kind: 'geometry', verified_on: {frame, sha256,
  box, source}}`` for a control that is only proven on that exact frame sha
  (``anchors.check_geometry`` reports ``stale`` on every other frame).

Examples
--------
    python tools/capture_anchors.py --label battle.win_rate_glyph \
        --from evidence/runtime/battle-step-20261006-012951/frame-0006.png \
        --box 1198,796,48,41 --page battle_hud

    python tools/capture_anchors.py --label entry.enter_button --kind geometry \
        --from evidence/runtime/window-20261006-025617/frame-0002.json \
        --box 1056,447,168,60 --page mirror_entry --note "灰=禁用/亮=可进"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / 'src') not in sys.path:
    sys.path.insert(0, str(REPO / 'src'))

from maalimbus import anchors as anchor_module  # noqa: E402

DEFAULT_REGISTRY = REPO / 'assets' / 'resource' / 'base' / 'anchors.json'
DEFAULT_TEMPLATE_ROOT = REPO / 'assets' / 'resource' / 'base'
DEFAULT_REPORT = REPO / 'build' / 'capture-anchors.json'


def parse_box(value):
    parts = [piece.strip() for piece in str(value).replace('x', ',').split(',') if piece.strip()]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError('--box needs x,y,w,h in frame pixels, got %r' % value)
    try:
        box = [int(round(float(piece))) for piece in parts]
    except ValueError:
        raise argparse.ArgumentTypeError('--box needs numbers, got %r' % value)
    if box[2] <= 0 or box[3] <= 0:
        raise argparse.ArgumentTypeError('--box width and height must be positive')
    return box


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def resolve_frame(source):
    """Return (png_path, json_path_or_None, sha256_of_png_bytes, sha256_from_journal)."""
    source = Path(source)
    if not source.is_absolute():
        candidate = (REPO / source)
        source = candidate if candidate.exists() else source
    if source.suffix.lower() == '.json':
        json_path, png_path = source, source.with_suffix('.png')
    else:
        png_path = source
        json_path = source.with_suffix('.json') if source.with_suffix('.json').exists() else None
    if not png_path.exists():
        raise SystemExit('frame image not found: %s' % png_path)
    digest = hashlib.sha256(png_path.read_bytes()).hexdigest()
    journal_sha = None
    if json_path is not None and json_path.exists():
        journal_sha = read_json(json_path).get('image_sha256')
    return png_path, json_path if (json_path and json_path.exists()) else None, digest, journal_sha


def image_size(png_path):
    import cv2

    image = cv2.imread(str(png_path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit('frame image unreadable: %s' % png_path)
    return image, (image.shape[1], image.shape[0])


def unit_roi(box, size):
    """Center-normalized roi for the box, padded by one pixel on the far edges.

    anchors._pixels() truncates (int()) instead of rounding, so an exact roi can come back a
    pixel short of the captured template; the pad keeps the replay region a superset of it.
    """
    left, top, width, height = box
    frame_width, frame_height = size
    return [round(left / frame_width, 5), round(top / frame_height, 5),
            round(min(1.0, (left + width) / frame_width + 1.0 / frame_width), 5),
            round(min(1.0, (top + height) / frame_height + 1.0 / frame_height), 5)]


def template_path_for(label, image_dir):
    """image/battle + battle.win_rate_glyph -> image/battle/win_rate_glyph.png"""
    name = label.split('.', 1)[1] if '.' in label else label
    return '%s.png' % '/'.join([image_dir.replace('\\', '/').strip('/'), name])


def group_of(label):
    return label.split('.', 1)[0] if '.' in label else label


def template_name_of(label):
    return label.split('.', 1)[1] if '.' in label else label


DEFAULT_TEMPLATE_THRESHOLD = getattr(anchor_module, '_DEFAULT_TEMPLATE_THRESHOLD', 0.8)


def relative(path):
    path = Path(path)
    try:
        return str(path.relative_to(REPO)).replace('\\', '/')
    except ValueError:
        return str(path).replace('\\', '/')


def find_page(registry, page_id):
    for page in registry.get('pages', []):
        if page.get('id') == page_id:
            return page
    raise SystemExit('page %r is not in the registry (known: %s)'
                     % (page_id, ', '.join(sorted(p.get('id', '?') for p in registry.get('pages', [])))))


def capture(args):
    registry = read_json(args['registry'])
    reference_width = registry.get('reference_width', 1280)
    png_path, json_path, digest, journal_sha = resolve_frame(args['from'])
    image, size = image_size(png_path)
    left, top, width, height = args['box']
    if left < 0 or top < 0 or left + width > size[0] or top + height > size[1]:
        raise SystemExit('box %s does not fit the %dx%d frame' % (args['box'], size[0], size[1]))

    label = args['label']
    page_id = args['page'] or group_of(label)
    page = find_page(registry, page_id)
    controls = page.setdefault('controls', [])
    existing = [entry for entry in controls if entry.get('id') == label]
    if existing and not args['force']:
        raise SystemExit('anchor %s already registered on page %s; re-run with --force to replace it'
                         % (label, page_id))

    note = args.get('note') or ''
    source = '%s:%s [%d,%d,%d,%d]' % (relative(png_path), (journal_sha or digest)[:12], left, top, width, height)
    roi = unit_roi(args['box'], size)
    verdict = {'label': label, 'page': page_id, 'kind': args['kind'], 'frame': relative(png_path),
               'frame_sha256': digest, 'journal_sha256': journal_sha, 'box': args['box'], 'roi': roi}

    if args['kind'] == 'template':
        import tempfile

        import cv2

        crop = image[top:top + height, left:left + width]
        scale = reference_width / float(size[0])
        if abs(scale - 1) > 1e-6:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        image_dir = args['image_dir'] or ('image/%s' % group_of(label))
        relative_template = template_path_for(label, image_dir)
        destination = Path(args['template_root']) / relative_template
        if args['dry_run']:
            handle = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            handle.close()
            staged = Path(handle.name)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged = destination
        if not cv2.imwrite(str(staged), crop):
            raise SystemExit('could not write the template to %s' % staged)
        relative_staged = relative_template if not args['dry_run'] else str(staged)
        entry = {'id': label, 'kind': 'template', 'template': relative_staged,
                 'roi': roi, 'threshold': args['threshold'], 'box': list(args['box'])}
        if note:
            entry['note'] = note
        entry['note'] = (entry.get('note') + ' ' if entry.get('note') else '') + \
            'captured from %s' % source
        checked = anchor_module.check_template(entry, str(png_path), size, reference_width,
                                               str(args['template_root']))
        if args['dry_run']:
            staged.unlink(missing_ok=True)
            entry['template'] = relative_template
        verdict['template'] = relative_template
        verdict['template_size'] = [crop.shape[1], crop.shape[0]]
        verdict['check'] = checked
    else:
        entry = {'id': label, 'kind': 'geometry',
                 'verified_on': {'frame': relative(json_path or png_path),
                                 'sha256': journal_sha or digest,
                                 'box': list(args['box']), 'source': note or source}}
        verdict['check'] = anchor_module.check_geometry(entry, {'image_sha256': journal_sha or digest})

    if existing:
        controls[controls.index(existing[0])] = entry
        verdict['replaced'] = True
    else:
        controls.append(entry)
    verdict['entry'] = entry

    try:
        anchor_module.validate(registry)
    except ValueError as error:
        raise SystemExit('the registry would become invalid: %s' % error)
    verdict['registry_valid'] = True

    if args['kind'] == 'template' and not verdict['check'].get('hit'):
        verdict['written'] = False
        if not args['dry_run']:
            (Path(args['template_root']) / relative_template).unlink(missing_ok=True)
        return 1, verdict

    if args['dry_run']:
        verdict['written'] = False
        return 0, verdict
    write_json(args['registry'], registry)
    verdict['written'] = True
    return 0, verdict


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--label', required=True, help='anchor id, e.g. battle.win_rate_glyph')
    parser.add_argument('--from', dest='from_', required=True,
                        help='recorded frame (png or its journal json) to capture from')
    parser.add_argument('--box', type=parse_box, required=True, help='control box in frame pixels: x,y,w,h')
    parser.add_argument('--page', default=None, help='page id to register on (default: the label prefix)')
    parser.add_argument('--kind', default='template', choices=('template', 'geometry'))
    parser.add_argument('--threshold', type=float, default=DEFAULT_TEMPLATE_THRESHOLD)
    parser.add_argument('--image-dir', default=None, help='template directory under --template-root')
    parser.add_argument('--registry', default=str(DEFAULT_REGISTRY))
    parser.add_argument('--template-root', default=str(DEFAULT_TEMPLATE_ROOT))
    parser.add_argument('--note', default=None)
    parser.add_argument('--report', default=str(DEFAULT_REPORT))
    parser.add_argument('--force', action='store_true', help='replace an already registered anchor')
    parser.add_argument('--dry-run', action='store_true', help='validate everything but do not write')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = vars(args)
    payload['from'] = payload.pop('from_')
    if payload['kind'] == 'geometry' and payload['threshold'] != DEFAULT_TEMPLATE_THRESHOLD:
        parser.error('--threshold only applies to --kind template')
    status, verdict = capture(payload)
    write_json(payload['report'], verdict)
    if verdict.get('written'):
        print('registered %s on page %s -> %s' % (verdict['label'], verdict['page'],
                                                 verdict.get('template') or verdict['entry'].get('verified_on', {}).get('frame')))
    elif verdict.get('check', {}).get('hit') is False:
        print('the captured template does not hit its own frame: %s' % verdict['check'], file=sys.stderr)
        print('nothing written (score %s < threshold %s)'
              % (verdict['check'].get('score'), verdict['check'].get('threshold')), file=sys.stderr)
    else:
        print('dry run: %s would be registered on page %s' % (verdict['label'], verdict['page']))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
