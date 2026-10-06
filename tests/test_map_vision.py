import numpy as np
import pytest

from maalimbus.map_vision import (HEADER_PATTERN, MapHeader, map_header, map_page,
                                  route_decision)
from maalimbus.vision import Text, classify

SIZE = (1920, 1080)


def frame(floor=1, pack='To be Cleaved', *, header=True, pack_line=True, extra=()):
    records = []
    if header:
        records.append(Text('Exploring Floor %d' % floor, (58, 127, 332, 47), .9981))
    if pack_line and pack:
        records.append(Text(pack, (60, 186, 138, 28), .9888))
    records.extend(extra)
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    return records, image


def test_header_identity_requires_floor_text_and_pack_line():
    records, image = frame()
    assert map_page(records, SIZE)
    header = map_header(records, SIZE)
    assert isinstance(header, MapHeader) and header.floor == 1
    assert header.pack == 'To be Cleaved'
    assert header.exploring_text.box == (58, 127, 332, 47)


def test_before_entry_wording_also_identifies_floor():
    records = [Text('Before Entry Floor 3', (58, 127, 332, 47), .99),
               Text('The Forgotten', (60, 186, 138, 28), .95)]
    header = map_header(records, SIZE)
    assert header is not None and (header.floor, header.pack) == (3, 'The Forgotten')


def test_missing_floor_or_pack_line_fails_closed():
    assert map_page([], SIZE) is False
    no_pack, _ = frame(pack_line=False)
    assert map_page(no_pack, SIZE) is False
    assert map_page([Text('Exploring Floor 1', (58, 127, 332, 47), .9981)], SIZE) is False


def test_ambiguous_or_out_of_range_floor_fails_closed():
    two = [Text('Exploring Floor 1', (58, 127, 332, 47), .9981),
           Text('Exploring Floor 2', (60, 180, 332, 47), .99),
           Text('To be Cleaved', (60, 240, 138, 28), .99)]
    assert map_page(two, SIZE) is False
    nine, _ = frame(floor=9)
    assert map_page(nine, SIZE) is False
    low, _ = frame()
    assert map_page([Text(r.text, r.box, .5) for r in low], SIZE) is False


def test_pack_line_must_sit_in_its_own_band():
    # Foreign text below the panel must not be borrowed as the pack identity.
    records, _ = frame(pack_line=False, extra=(Text('Claim Rewards', (60, 900, 200, 30), .99),))
    assert map_page(records, SIZE) is False
    records, _ = frame(pack_line=False, extra=(Text('Faith & Erosion', (60, 186, 138, 28), .4),))
    assert map_page(records, SIZE) is False


def test_header_pattern_matches_only_the_two_supported_wordings():
    assert HEADER_PATTERN
    import re
    assert re.match(HEADER_PATTERN, 'Exploring Floor 1', re.I)
    assert re.match(HEADER_PATTERN, 'Before Entry Floor 5', re.I)
    assert not re.match(HEADER_PATTERN, 'Explore the Floor 1', re.I)
    assert not re.match(HEADER_PATTERN, 'Exploring Floor 6', re.I)


def test_live_231221_terminal_records_identify_the_map_page():
    """Regression pinned to the retained actual session, not a derived frame."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/live-20261005-231221/frame-0002.json'
    if not path.exists():
        pytest.skip('retained live session evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    size = tuple(data['size'])
    assert data['scene'] == 'UNKNOWN'
    header = map_header(records, size)
    assert header is not None
    assert (header.floor, header.pack) == (1, 'To be Cleaved')
    assert header.exploring_text.box == (58, 127, 332, 47)


def test_other_scene_text_is_not_promoted_to_map():
    assert map_page([Text('Drive', (100, 100, 60, 20), .99)], SIZE) is False
    # The entry page carries `Exploring` in the upper right without a floor header.
    import json
    from pathlib import Path
    locale = json.loads((Path(__file__).resolve().parents[1] /
                         'assets/resource/en/locale.json').read_text(encoding='utf-8'))
    records = [Text('Exploring', (1600, 200, 80, 20), .99), Text('Enter', (1600, 700, 80, 30), .99)]
    assert classify(records, locale, SIZE) == 'MIRROR_ENTRY'
    assert map_page(records, SIZE) is False


def test_route_decision_refuses_without_proven_evidence():
    records, image = frame()
    header = map_header(records, SIZE)
    assert route_decision(None, SIZE)['reason'] == 'map_header_not_identified'
    assert route_decision(header, SIZE)['reason'] == 'current_position_not_proven'
    assert route_decision(header, SIZE, current='entry')['reason'] == 'no_unvisited_candidate_observed'
    assert route_decision(header, SIZE, current='entry', candidates=())['next_node'] is None
    assert route_decision(header, SIZE, current='entry', cleared=('entry', 'a'),
                          candidates=('entry', 'a'))['reason'] == 'no_unvisited_reachable_node'
    assert route_decision(header, SIZE, current='entry', candidates=('a', 'b'))['reason'] == \
        'ambiguous_unvisited_candidates'
    only = route_decision(header, SIZE, current='entry', cleared=('entry',), candidates=('a',))
    assert only == dict(next_node='a', reason='single_unvisited_candidate')


def test_header_pattern_matches_only_the_two_supported_wordings():
    assert HEADER_PATTERN
    import re
    assert re.match(HEADER_PATTERN, 'Exploring Floor 1', re.I)
    assert re.match(HEADER_PATTERN, 'Before Entry Floor 5', re.I)
    assert not re.match(HEADER_PATTERN, 'Explore the Floor 1', re.I)
    assert not re.match(HEADER_PATTERN, 'Exploring Floor 6', re.I)
