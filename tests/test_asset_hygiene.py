"""The asset tables the runtime depends on must parse and stay consistent.

These are the cheap invariants that catch a hand-edited JSON going wrong: the
anchor registry's proven pages and its pending list are two halves of one
document and must not overlap, every proven page needs evidence and an identity
anchor, and every pending entry must say what is missing and why.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'assets' / 'resource' / 'base'


def registry():
    return json.loads((BASE / 'anchors.json').read_text(encoding='utf-8'))


def test_every_base_asset_is_valid_json_with_the_expected_top_level_shape():
    for path in sorted(BASE.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        assert isinstance(data, (dict, list)), path.name
        if path.name in ('anchors.json', 'route-policy.json', 'budget.json'):
            assert isinstance(data, dict) and 'version' in data, path.name


def test_proven_pages_and_pending_pages_never_overlap():
    data = registry()
    pages = {page['id'] for page in data['pages']}
    pending = {entry['id'] for entry in data['pending']}
    assert pages and pending
    assert not (pages & pending), sorted(pages & pending)
    for entry in data['pending']:
        assert entry['what'] and entry['why'], entry['id']


def test_every_proven_page_carries_evidence_and_an_identity_anchor():
    """Each identity anchor needs an id and a search box; the matcher may vary."""
    offenders = []
    for page in registry()['pages']:
        if not page.get('evidence'):
            offenders.append('%s: no evidence' % page['id'])
        if not page.get('identity'):
            offenders.append('%s: no identity anchors' % page['id'])
        for anchor in page.get('identity') or []:
            if not anchor.get('id') or not anchor.get('roi'):
                offenders.append('%s: %r' % (page['id'], anchor.get('id')))
    assert offenders == [], offenders
