import numpy as np
import pytest

from maalimbus.map_vision import (HEADER_PATTERN, MapHeader, enter_target, map_header,
                                  map_page, node_panel, pre_battle_team_page,
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


def test_battle_hud_identity_is_pinned_to_the_live_battle_frame():
    """The HUD is the WAVE/TURN corner; bitmap values may be absent from OCR."""
    import json
    from pathlib import Path
    from maalimbus.battle_vision import battle_hud
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/team-page-battle-20261006-010230/frame-0007.json'
    if not path.exists():
        pytest.skip('retained live battle evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    hud = battle_hud(records, tuple(data['size']))
    assert hud is not None
    assert hud['wave_box'] == (16, 39, 54, 30) and hud['turn_box'] == (18, 95, 44, 24)
    assert hud['wave'] is None and hud['turn'] is None   # gold bitmap glyphs
    assert hud['diagnostics'] == ['Damage', 'Rate', 'Win']
    for other in ('live-20261005-231221/frame-0002.json',
                  'map-settle-20261006-000930/frame-0001.json',
                  'map-probe-20261006-000748/frame-0002.json'):
        other_path = root / 'evidence/runtime' / other
        if not other_path.exists():
            continue
        other_data = json.loads(other_path.read_text(encoding='utf-8'))
        other_records = [Text(r['text'], tuple(r['box']), r['score']) for r in other_data['ocr']]
        assert battle_hud(other_records, tuple(other_data['size'])) is None, other


def test_node_panel_is_distinct_from_the_map_and_names_its_enter_action():
    """Regression pinned to the actual post-click panel from the MuMu probe."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/map-probe-20261006-000748/frame-0002.json'
    if not path.exists():
        pytest.skip('retained live panel evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    size = tuple(data['size'])
    assert data['scene'] == 'UNKNOWN'      # the production classifier missed it then
    assert map_header(records, size) is None
    panel = node_panel(records, size)
    assert panel is not None
    assert panel.title == 'To be Cleaved'
    assert panel.clear_rewards.box == (1052, 744, 138, 32)
    assert panel.enter.box == (1668, 780, 124, 63)
    assert panel.cost_texts == ('85',)
    assert enter_target(panel) == (1668, 780, 124, 63)
    # A plain map page must never look like a panel.
    map_path = root / 'evidence/runtime/live-20261005-231221/frame-0002.json'
    if map_path.exists():
        map_data = json.loads(map_path.read_text(encoding='utf-8'))
        map_records = [Text(r['text'], tuple(r['box']), r['score']) for r in map_data['ocr']]
        assert node_panel(map_records, tuple(map_data['size'])) is None


def test_map_observe_node_is_a_bounded_read_only_continuation():
    """The stopped-session continuation must observe the map and never click."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    nodes = json.loads((root / 'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
    node = nodes['MapObserve']
    assert node['recognition'] == 'DirectHit'
    assert node['action'] == 'Custom' and node['custom_action'] == 'limbus_map_observe'
    assert node['max_hit'] == 1 and node['next'] == []
    assert node['on_error'] == ['LimbusUnknown']
    # It must not be reachable from the theme-pack drag, which stays a stop point.
    drag = nodes['ThemePackDrag']
    assert 'MapObserve' not in drag['next']
    run_native = (root / 'tools/run_native.py').read_text(encoding='utf-8')
    assert "'limbus_map_observe'" in run_native


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

def test_pre_battle_page_survives_the_captions_it_actually_renders():
    # Live proof: evidence/runtime/window-20261006-030941/frame-0022.json (a team of
    # 12/12) reads the button as "To" + "Battle!" under a Chain badge and the clear
    # action as " Clear Selection" with a leading space, which the strict patterns
    # missed and the page fell back to TEAM_LIBRARY.
    recs = [Text('To', (1622, 865, 54, 36), 1.0),
            Text('Battle!', (1674, 859, 144, 44), 1.0),
            Text(' Clear Selection', (1616, 704, 214, 26), .975),
            Text('12/12', (1698, 754, 128, 57), .993)]
    page = pre_battle_team_page(recs, SIZE)
    assert page is not None
    assert page.participants == ('12/12',)
    # The disabled state renders as a single Battle! caption.
    disabled = [Text('Battle!', (1678, 857, 136, 46), 1.0),
                Text('Clear Selection', (1640, 702, 190, 26), .997)]
    assert pre_battle_team_page(disabled, SIZE) is not None
    # Both captions stay required together.
    assert pre_battle_team_page([Text('Battle!', (1678, 857, 136, 46), 1.0)], SIZE) is None
    # A second Battle! inside the button band makes the page ambiguous, while one
    # outside it is just another page's caption and is ignored.
    in_band = [Text('Battle!', (1678, 857, 136, 46), 1.0),
               Text('Battle!', (1700, 870, 100, 40), 1.0),
               Text('Clear Selection', (1640, 702, 190, 26), .997)]
    assert pre_battle_team_page(in_band, SIZE) is None
    off_band = in_band[:1] + [Text('Battle!', (200, 100, 136, 46), 1.0)] + in_band[2:]
    assert pre_battle_team_page(off_band, SIZE).battle.box == (1678, 857, 136, 46)
