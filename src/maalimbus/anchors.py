"""Anchor registry: every image-derived assumption in one machine-checked file.

An anchor is either
  `ocr`      - a regex that must match inside a centre-normalized ROI,
  `template` - a reference-width template that must match inside that ROI,
  `geometry` - a control box proven on one exact frame (by image sha256).

`evaluate` never guesses: an anchor that cannot be checked on the supplied
observation reports `hit: None`, and geometry proven on another frame reports
`stale`, so a UI change produces a list of broken names instead of a silent
wrong click.
"""
import json
import re
from pathlib import Path

from .vision import Text, find

KINDS = ('ocr', 'template', 'geometry')
_DEFAULT_OCR_THRESHOLD = .65
_DEFAULT_TEMPLATE_THRESHOLD = .80


def load(path):
    path = Path(path)
    registry = json.loads(path.read_text(encoding='utf-8'))
    validate(registry)
    return registry


def validate(registry):
    """Raise ValueError on a registry we cannot evaluate honestly."""
    if not isinstance(registry, dict) or not isinstance(registry.get('pages'), list):
        raise ValueError('registry needs a page list')
    if not registry['pages']:
        raise ValueError('registry needs at least one page')
    seen = set()
    for page in registry['pages']:
        page_id = page.get('id')
        if not isinstance(page_id, str) or not page_id:
            raise ValueError('page needs an id')
        if page_id in seen:
            raise ValueError('duplicate page id %s' % page_id)
        seen.add(page_id)
        if not isinstance(page.get('identity'), list) or not page['identity']:
            raise ValueError('page %s needs identity anchors' % page_id)
        for group in ('identity', 'controls'):
            for anchor in page.get(group) or ():
                validate_anchor(anchor, page_id)
    return registry


def validate_anchor(anchor, page_id):
    if not isinstance(anchor, dict):
        raise ValueError('anchor must be an object in page %s' % page_id)
    anchor_id = anchor.get('id')
    if not isinstance(anchor_id, str) or not anchor_id:
        raise ValueError('anchor needs an id in page %s' % page_id)
    kind = anchor.get('kind')
    if kind not in KINDS:
        raise ValueError('anchor %s has unsupported kind %r' % (anchor_id, kind))
    roi = anchor.get('roi')
    if kind != 'geometry' or roi is not None:
        if (not isinstance(roi, (list, tuple)) or len(roi) != 4
                or not all(isinstance(v, (int, float)) for v in roi)):
            raise ValueError('anchor %s needs a four-number roi' % anchor_id)
        left, top, right, bottom = roi
        if not 0 <= left < right <= 1 or not 0 <= top < bottom <= 1:
            raise ValueError('anchor %s roi must be an ordered unit box' % anchor_id)
    if kind == 'ocr':
        if not isinstance(anchor.get('pattern'), str) or not anchor['pattern']:
            raise ValueError('ocr anchor %s needs a pattern' % anchor_id)
        try:
            re.compile(anchor['pattern'])
        except re.error as error:
            raise ValueError('ocr anchor %s has an invalid pattern: %s' % (anchor_id, error))
    if kind == 'template' and not isinstance(anchor.get('template'), str):
        raise ValueError('template anchor %s needs a template path' % anchor_id)
    if kind == 'geometry':
        record = anchor.get('verified_on')
        if not isinstance(record, dict):
            raise ValueError('geometry anchor %s needs a verified_on record' % anchor_id)
        if not (record.get('sha256') or record.get('frame')):
            raise ValueError('geometry anchor %s needs a frame or a sha256 proof' % anchor_id)
        box = record.get('box')
        if (not isinstance(box, (list, tuple)) or len(box) != 4
                or not all(isinstance(v, int) for v in box)):
            raise ValueError('geometry anchor %s needs an integer box' % anchor_id)
    return anchor


def resolve_evidence(registry, root):
    """Fill each geometry proof with the sha256 of the frame it references."""
    root = Path(root)
    for page in registry['pages']:
        for anchor in page.get('controls') or ():
            record = anchor.get('verified_on')
            if not isinstance(record, dict):
                continue
            if record.get('sha256') or not record.get('frame'):
                continue
            try:
                payload = json.loads((root/record['frame']).read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            record['sha256'] = payload.get('image_sha256') or ''
    return registry


def _records(observation):
    return [Text(r['text'], tuple(r['box']), float(r.get('score', 0)))
            for r in observation.get('ocr') or () if isinstance(r, dict) and 'box' in r]


def _pixels(roi, size):
    width, height = size
    left, top, right, bottom = roi
    return (max(0, int(left*width)), max(0, int(top*height)),
            min(int(right*width), width), min(int(bottom*height), height))


def check_ocr(anchor, records, size):
    matches = find(records, anchor['pattern'], tuple(anchor['roi']), size,
                   anchor.get('threshold', _DEFAULT_OCR_THRESHOLD))
    if not matches:
        return {'hit': False, 'observed': None}
    best = matches[0]
    return {'hit': True, 'observed': {'text': best.text, 'box': list(best.box),
                                      'score': round(best.score, 4)}}


def check_template(anchor, image_path, size, reference_width, template_root):
    import cv2
    image_path, template_root = Path(image_path), Path(template_root)
    template_path = template_root/anchor['template']
    frame = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if frame is None:
        return {'hit': None, 'reason': 'frame image unreadable: %s' % image_path}
    if not template_path.exists():
        return {'hit': None, 'reason': 'template missing: %s' % template_path}
    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        return {'hit': None, 'reason': 'template unreadable: %s' % template_path}
    scale = frame.shape[1]/float(reference_width)
    if abs(scale - 1) > 1e-6:
        template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    left, top, right, bottom = _pixels(anchor['roi'], size)
    region = frame[top:bottom, left:right]
    if region.shape[0] < template.shape[0] or region.shape[1] < template.shape[1]:
        return {'hit': False, 'reason': 'roi smaller than the template'}
    result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    box = (left + location[0], top + location[1], template.shape[1], template.shape[0])
    threshold = anchor.get('threshold', _DEFAULT_TEMPLATE_THRESHOLD)
    return {'hit': bool(score >= threshold), 'score': round(float(score), 4),
            'threshold': threshold, 'observed': {'box': list(box)}}


def check_geometry(anchor, observation):
    record = anchor['verified_on']
    sha = observation.get('image_sha256')
    if record.get('sha256') and sha and record['sha256'] == sha:
        return {'hit': True, 'observed': {'box': record.get('box')},
                'note': record.get('source') or 'geometry proven on this exact frame'}
    return {'hit': False, 'stale': True, 'observed': {'box': record.get('box')},
            'note': 'geometry was proven on another frame; re-verify against the device'}


def evaluate_anchor(anchor, observation, *, image_path=None, reference_width=1280,
                    template_root=None):
    size = tuple(observation.get('size') or ())
    kind = anchor['kind']
    if kind == 'ocr':
        if len(size) != 2:
            return {'hit': None, 'reason': 'observation has no size'}
        result = check_ocr(anchor, _records(observation), size)
    elif kind == 'template':
        if image_path is None:
            return {'hit': None, 'reason': 'template anchor needs the retained image'}
        result = check_template(anchor, image_path, size, reference_width, template_root)
    else:
        result = check_geometry(anchor, observation)
    result['id'] = anchor['id']
    result['kind'] = kind
    if isinstance(anchor.get('roi'), (list, tuple)):
        result['roi'] = list(anchor['roi'])
    if anchor.get('note'):
        result['note'] = anchor['note']
    return result


def evaluate(registry, observation, *, page=None, image_path=None, template_root=None):
    """Report every anchor of the matching pages against one observation."""
    reference_width = registry.get('reference_width', 1280)
    pages = []
    for entry in registry['pages']:
        if page and entry['id'] != page:
            continue
        anchors = [evaluate_anchor(a, observation, image_path=image_path,
                                  reference_width=reference_width, template_root=template_root)
                   for a in entry['identity']]
        controls = [evaluate_anchor(a, observation, image_path=image_path,
                                    reference_width=reference_width, template_root=template_root)
                    for a in entry.get('controls') or ()]
        required = [a for a in anchors if a.get('hit') is not True]
        page_ok = not required
        pages.append({'page': entry['id'], 'title': entry.get('title', ''),
                      'identity_ok': page_ok, 'identity': anchors, 'controls': controls})
    return {'pages': pages, 'evaluated': sum(len(p['identity']) + len(p['controls']) for p in pages)}


def failures(report, *, require_geometry=False):
    """Anchor ids that did not prove out on this observation."""
    broken = []
    for page in report['pages']:
        for anchor in page['identity']:
            if anchor.get('hit') is not True:
                broken.append((page['page'], anchor['id'], anchor.get('reason') or anchor.get('note') or 'no match'))
        for anchor in page['controls']:
            if anchor.get('hit') is not True and (require_geometry or anchor.get('stale')):
                broken.append((page['page'], anchor['id'], anchor.get('reason') or anchor.get('note') or 'no match'))
    return broken
