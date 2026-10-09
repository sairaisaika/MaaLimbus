import numpy as np
import pytest

from maalimbus.map_vision import (BADGE_TO_CENTRE, HEADER_PATTERN, LATTICE_PITCH, MapHeader,
                                  ORNAMENT_LIFT, advance_candidates, enter_target,
                                  highlighted_nodes, lattice_neighbours, lit_nodes, map_clicks,
                                  map_header, map_page, node_markers, node_panel,
                                  pre_battle_team_page, route_decision, yellow_flame_player,
                                  clear_selection_caption)
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


def test_an_encounter_panel_without_clear_rewards_is_still_a_panel():
    """The second panel shape names the encounter and hides only half the map.

    Live run window-20261006-040751 clicked the map six times and reported every click
    as opening no panel, because this shape carries no `Clear Rewards` caption: the
    page fell back to MAP (its floor header stays legible behind the panel) and the
    window walked on to the next candidate.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-041345/frame-0002.json'
    if not path.exists():
        pytest.skip('retained live encounter-panel evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    size = tuple(data['size'])
    assert map_header(records, size) is not None     # the header really is still readable
    panel = node_panel(records, size)
    assert panel is not None
    assert panel.title == 'Thick Rumbling Hum'
    assert panel.clear_rewards is None               # this shape has no reward caption
    assert panel.enter.box == (1670, 784, 122, 57)
    assert enter_target(panel) == (1670, 784, 122, 57)
    # ...and a page with an Enter but no floor header is still not a panel.
    entry = [Text('Enter', (1670, 784, 122, 57), .99)]
    assert node_panel(entry, size) is None


def test_the_marked_step_is_offered_before_the_badge_nodes():
    """Live run window-20261006-040751: four badge nodes refused, the marked gate opened.

    The gate is the pale hexagon the game draws around the step it will accept; the
    ADB tap that landed on it (device 730,73) opened the encounter panel, while every
    crescent-badge node around the player was a no-op.
    """
    import json
    from pathlib import Path
    pytest.importorskip('cv2')
    from maalimbus.map_vision import NODE_BADGE_TEMPLATE, map_clicks
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-040938/frame-0001.png'
    template_path = root / 'assets/resource/base' / NODE_BADGE_TEMPLATE
    if not path.exists() or not template_path.exists():
        pytest.skip('retained live map evidence is not present')
    import cv2
    image = cv2.imread(str(path))
    clicks = map_clicks(image, template=cv2.imread(str(template_path)))
    assert clicks, 'the live map must offer at least one candidate'
    assert clicks[0]['kind'] == 'highlighted_node'
    point = clicks[0]['point']
    assert abs(point[0] - 1088) <= 25 and abs(point[1] - 115) <= 45, point
    assert all(item['kind'] in ('highlighted_node', 'chevron_target', 'lattice_step',
                                'node_away_from_player', 'badge_mark', 'lit_node',
                                'lit_ring', 'lit_icon', 'bright_lit_icon', 'cyan_node', 'path_node')
               for item in clicks)


def test_the_cyan_lit_node_is_the_first_candidate_on_the_floor_that_stalled():
    """Live evidence/runtime/window-20261006-201831/frame-0065.png.

    Run build/window-run64.json stalled on this floor: six clicks on the badge and
    lattice candidates opened no panel, then no_candidate_node_observed. The node the
    game was offering is the cyan-lit one at (1087,737) in 1920-space; naming it from
    its own pixels puts the accepted click first.

    The cyan line leaving the player ends 66 px short of that centre, so the path reading
    is offered first and snapped onto the ring -- the path names the node, the ring names
    the pixel, and both name the node the panel really opened on.
    """
    import json
    from pathlib import Path
    pytest.importorskip('cv2')
    from maalimbus.map_vision import NODE_BADGE_TEMPLATE, highlighted_nodes, map_clicks
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-201831/frame-0065.png'
    template_path = root / 'assets/resource/base' / NODE_BADGE_TEMPLATE
    if not path.exists() or not template_path.exists():
        pytest.skip('retained live map evidence is not present')
    import cv2
    image = cv2.imread(str(path))
    lit = highlighted_nodes(image)
    assert len(lit) == 1, lit
    assert abs(lit[0][0] - 1087) <= 12 and abs(lit[0][1] - 737) <= 12, lit
    clicks = map_clicks(image, template=cv2.imread(str(template_path)))
    assert clicks[0]['kind'] == 'path_node'
    point = clicks[0]['point']
    assert abs(point[0] - 1087) <= 12 and abs(point[1] - 737) <= 12, point
    # The badge nodes are still offered behind it, so a refused click can fall back.
    assert any(item['kind'] == 'node_away_from_player' for item in clicks)
    assert all(item['kind'] in ('cyan_node', 'highlighted_node', 'chevron_target',
                                'node_away_from_player', 'lattice_step', 'badge_mark',
                                'lit_node', 'lit_icon', 'bright_lit_icon', 'path_node', 'lit_ring')
               for item in clicks)


def test_the_offered_question_node_outranks_the_lifted_badge_boxes():
    """Live evidence/runtime/window-20261007-023156/frame-0053.png, floor 1.

    Run build/window-run107.json stalled here: every click went to a lifted badge box
    ((578,14), (194,334), (232,14) -- ordinary nodes the floor does not connect to the
    player) and the panel never opened, while the one step the floor offers is the red
    "?" hexagon. Its own icon is read at (1087,409); a manual 1920-space tap on
    (1080,428) opened that node's panel, so the icon is offered before the lift.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    image, template = live_map(root, 'window-20261007-023156/frame-0053.png')
    clicks = map_clicks(image, template=template)
    assert clicks[0]['kind'] == 'lit_icon', clicks[:3]
    point = clicks[0]['point']
    assert abs(point[0] - 1087) <= 12 and abs(point[1] - 409) <= 12, point
    lifted = [item for item in clicks if item['kind'] == 'node_away_from_player']
    assert lifted, 'the badge nodes are still offered behind it'
    assert min(index for index, item in enumerate(clicks)
               if item['kind'] == 'node_away_from_player') >= 2
    assert all(item['kind'] in ('cyan_node', 'highlighted_node', 'chevron_target',
                                'node_away_from_player', 'lattice_step', 'badge_mark',
                                'lit_node', 'lit_icon', 'bright_lit_icon', 'path_node', 'lit_ring')
               for item in clicks)


def test_the_ring_is_read_in_whatever_colour_the_floor_draws_it():
    """Live evidence/runtime/window-20261006-214057/frame-0025.png, floor 3.

    Every click the run tried on this floor (build/window-run78.json: nine of them,
    badge nodes and lattice steps) opened nothing, because the reader only ever knew
    the cyan ring of floor 1. This floor lights the offered node with an orange ring:
    the cyan reader returns nothing on this frame, while the saturated-blob reader
    returns the ring itself first, ahead of the node icons and the path's glow.
    """
    import cv2
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-214057/frame-0025.png'
    if not path.exists():
        pytest.skip('retained live map evidence is not present')
    image = cv2.imread(str(path))
    assert highlighted_nodes(image) == []
    lit = lit_nodes(image)
    assert abs(lit[0][0] - 318) <= 20 and abs(lit[0][1] - 140) <= 20, lit
    clicks = map_clicks(image)
    kinds = [item['kind'] for item in clicks]
    # The lit path is the strongest reading and may lead it (it does on the zoomed
    # frames), but the ring must still come before every badge and lattice guess.
    ring = next(item for item in clicks if item['kind'] == 'lit_node')
    assert abs(ring['point'][0] - 318) <= 20 and abs(ring['point'][1] - 140) <= 20, ring
    for kind in ('node_away_from_player', 'badge_mark', 'lattice_step'):
        if kind in kinds:
            assert kinds.index('lit_node') < kinds.index(kind)


def test_the_lattice_offers_the_diagonals_before_the_straight_neighbours():
    """The hexagon rows are offset half a column, so the live step is a diagonal.

    Run 79 and run 80 (build/window-run79.json, build/window-run80.json) clicked the
    two nodes the lattice believed were straight below and straight above the player
    and neither moved the run; the player's lit path runs up and to the right.
    """
    first, second = lattice_neighbours((500, 400))[:2]
    assert first == (500 + LATTICE_PITCH[0] // 2, 400 - LATTICE_PITCH[1])
    assert second == (500 - LATTICE_PITCH[0] // 2, 400 - LATTICE_PITCH[1])
    # the straight neighbours are still offered, just behind every diagonal
    assert (500, 400 - LATTICE_PITCH[1]) in lattice_neighbours((500, 400))
    assert lattice_neighbours((500, 400))[-1] == (500, 400 - LATTICE_PITCH[1])
    assert lattice_neighbours(None) == []


def test_the_lit_path_leaving_the_player_names_the_next_node():
    """Live evidence/runtime/window-20261006-233633/frame-0001.png (floor 3).

    The run had been clicking the ring the game lit around a node and every badge
    candidate (build/window-run81.json: six clicks, all no-ops), while the path the run
    may still walk -- drawn bright violet, against the dull grey of the paths already
    spent -- leaves the player at (960,672) up and to the right. An ADB tap on its far
    end (1920 1162,607) opened the node panel, which is what the reader now offers first.
    """
    import cv2
    from pathlib import Path
    from maalimbus.map_vision import path_end
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-233633/frame-0001.png'
    if not path.exists():
        pytest.skip('retained live map evidence is not present')
    image = cv2.imread(str(path))
    point = path_end(image, (960, 672))
    assert point is not None
    assert abs(point[0] - 1162) <= 60 and abs(point[1] - 625) <= 60, point
    clicks = map_clicks(image, player=(960, 672))
    assert clicks[0]['kind'] == 'path_node'
    assert abs(clicks[0]['point'][0] - point[0]) <= 40
    assert abs(clicks[0]['point'][1] - point[1]) <= 40


def test_the_cyan_path_of_the_factory_floor_still_names_the_next_node():
    """Live evidence/runtime/window-20261007-172225/frame-0406.png, floor 2.

    "Automated Factory" draws the walkable path bright cyan over a dim teal grid, where
    floors 1 and 3 draw it violet, so the violet mask alone read nothing: ``path_end`` was
    None, the run fell back to the lattice steps around the player's own node, both clicks
    were no-ops, and it stopped with ``no_candidate_node_observed``
    (build/window-run-continue-13.json step 113). The node the line points at -- the cyan
    "?" hexagon whose centre is (1054,124) -- was never offered at all.
    """
    import cv2
    from pathlib import Path
    from maalimbus.map_vision import path_end
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261007-172225/frame-0406.png'
    if not path.exists():
        pytest.skip('retained live map evidence is not present')
    image = cv2.imread(str(path))
    point = path_end(image, (694, 384))
    assert point is not None
    assert abs(point[0] - 1054) <= 70 and abs(point[1] - 124) <= 70, point
    clicks = map_clicks(image, player=(694, 384))
    assert clicks[0]['kind'] == 'path_node'
    assert abs(clicks[0]['point'][0] - point[0]) <= 40
    assert abs(clicks[0]['point'][1] - point[1]) <= 40


def test_the_locomotive_names_the_player_when_no_badge_node_does():
    """Live floor-2 evidence/runtime/window-20261006-050106/frame-0003.json.

    The badge scan finds a single node on that frame, so the player cannot be scored
    from badge nodes at all; the locomotive pair (a small flame above a lit body)
    names it instead, and the step it is connected to by a path is offered first.
    """
    from pathlib import Path
    pytest.importorskip('cv2')
    from maalimbus.map_vision import NODE_BADGE_TEMPLATE, map_clicks, train_player
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-050106/frame-0003.png'
    template_path = root / 'assets/resource/base' / NODE_BADGE_TEMPLATE
    if not path.exists() or not template_path.exists():
        pytest.skip('retained live map evidence is not present')
    import cv2
    image = cv2.imread(str(path))
    player = train_player(image)
    assert player is not None, 'the live floor-2 frame must name the player'
    assert abs(player[0] - 694) <= 25 and abs(player[1] - 384) <= 25, player
    clicks = map_clicks(image, template=cv2.imread(str(template_path)))
    assert clicks, 'the live floor-2 map must offer at least one candidate'
    # The train's own node is never a candidate, and the first candidate is the step
    # the page's chevron points at rather than a badge node four columns away.
    first = clicks[0]
    assert first['kind'] == 'chevron_target'
    assert (first['point'][0] - player[0]) ** 2 + (first['point'][1] - player[1]) ** 2 \
        >= 300 * 300
    assert all(item['kind'] != 'highlighted_node' for item in clicks[:1])


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


def test_the_split_floor_header_still_identifies_the_map_page():
    """Regression pinned to the retained actual frame, not a derived one.

    On the floor-1 map the game renders 'Exploring' and 'Floor' as two OCR tokens
    and the stylised floor digit is not read at all
    (evidence/runtime/window-20261006-033107/frame-0005.json), which used to leave
    the page at UNKNOWN and stop the window in front of it.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-033107/frame-0005.json'
    if not path.exists():
        pytest.skip('retained live session evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    header = map_header(records, tuple(data['size']))
    assert header is not None
    assert (header.floor, header.pack) == (None, 'To be Cleaved')
    assert map_page(records, tuple(data['size'])) is True


def test_the_map_survives_a_frame_where_ocr_drops_the_floor_token():
    """The same live page, one frame later, with the "Floor" token missing.

    evidence/runtime/window-20261006-033259/frame-0002.json carries only
    "Exploring" and the pack line; the window used to fall back to UNKNOWN there
    and treat a harmless unreachable-node click as a broken successor.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-033259/frame-0002.json'
    if not path.exists():
        pytest.skip('retained live session evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    header = map_header(records, tuple(data['size']))
    assert header is not None
    assert (header.floor, header.pack) == (None, 'To be Cleaved')


def test_the_map_survives_a_label_whose_tail_ocr_dropped():
    """Live run window-20261007-030756: the label read as 'Explorin' on every frame.

    The run sat on floor 3 "To be Cleaved" with the truncated label, so map_header
    returned None, the page stayed UNKNOWN and the window stopped after five rounds
    (build/window-run111.json). The pack line below is still what gates identity.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261007-030756/frame-0096.json'
    if not path.exists():
        pytest.skip('retained live session evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    assert data['scene'] == 'UNKNOWN'
    assert not any(r.text.strip().startswith('Exploring') for r in records)
    header = map_header(records, tuple(data['size']))
    assert header is not None
    assert header.exploring_text.text.strip() == 'Explorin'
    assert header.pack == 'To be Cleaved'
    assert map_page(records, tuple(data['size'])) is True


def test_the_map_survives_a_header_that_lost_the_space_before_floor():
    """Live run window-20261007-034308: OCR merged the label and the floor word.

    frame-0198 reads the whole floor-5 line as 'ExploringFloor5' [56,121,356,63] 0.95
    with no space, so the strict separator in HEADER_PATTERN left the page UNKNOWN and
    build/window-run114.json stopped on page_unreadable_after_waiting right after the
    floor-4 battle. The pack line below still gates identity.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261007-034308/frame-0198.json'
    if not path.exists():
        pytest.skip('retained live session evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    assert data['scene'] == 'UNKNOWN'
    assert any(r.text.strip() == 'ExploringFloor5' for r in records)
    header = map_header(records, tuple(data['size']))
    assert header is not None
    assert header.floor == 5
    assert header.pack == 'Twining Threads'
    assert map_page(records, tuple(data['size'])) is True


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


def shipped_policy():
    from pathlib import Path

    from maalimbus.route_plan import load_policy

    root = Path(__file__).resolve().parents[1]
    return load_policy(root / 'assets' / 'resource' / 'base' / 'route-policy.json')


def test_a_policy_orders_the_candidates_nobody_else_could_separate():
    records, image = frame()
    header = map_header(records, SIZE)
    ranked = route_decision(header, SIZE, current='entry', candidates=('a', 'b', 'c'),
                            kinds={'a': 'empty', 'b': 'elite', 'c': 'event'},
                            policy=shipped_policy())
    assert ranked['next_node'] == 'b'
    assert ranked['reason'] == 'policy_ranked_candidate'
    assert ranked['plan']['score'] == 2.4
    assert [entry['id'] for entry in ranked['plan']['ranked']] == ['b', 'c', 'a']


def test_a_policy_refuses_rather_than_ranking_a_kind_nobody_read():
    records, image = frame()
    header = map_header(records, SIZE)
    blind = route_decision(header, SIZE, current='entry', candidates=('a', 'b'),
                           kinds={}, policy=shipped_policy())
    assert blind['next_node'] is None
    assert blind['reason'] == 'route_kind_unknown'
    assert blind['plan']['refused'] == 'route_kind_unknown'
    readable = route_decision(header, SIZE, current='entry', candidates=('a', 'b'),
                              kinds={'b': 'regular'}, policy=shipped_policy())
    assert readable['next_node'] == 'b'


def test_a_policy_does_not_change_a_single_candidate_or_the_evidence_first_path():
    records, image = frame()
    header = map_header(records, SIZE)
    single = route_decision(header, SIZE, current='entry', cleared=('entry',),
                            candidates=('a',), kinds={'a': 'boss'}, policy=shipped_policy())
    assert single == dict(next_node='a', reason='single_unvisited_candidate')
    ambiguous = route_decision(header, SIZE, current='entry', candidates=('a', 'b'),
                               kinds={'a': 'empty', 'b': 'boss'})
    assert ambiguous == dict(next_node=None, reason='ambiguous_unvisited_candidates')


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


def test_the_clear_caption_is_read_when_ocr_splits_it_into_its_two_words():
    # Live proof: evidence/runtime/window-20261008-030555/frame-0015.json reads the
    # clear action as two tokens on one line, 'Clear' [1640,706,74,22] and
    # 'Selection' [1706,706,122,22], where every earlier frame read it whole. The
    # split alone left the page named TEAM_LIBRARY and run-continue-26 stopped on it.
    recs = [Text('Battle!', (1678, 857, 134, 48), .999384),
            Text('Clear', (1640, 706, 74, 22), 1.0),
            Text('Selection', (1706, 706, 122, 22), .99976),
            Text('0/12', (1710, 758, 114, 52), .876134)]
    page = pre_battle_team_page(recs, SIZE)
    assert page is not None
    assert page.participants == ('0/12',)
    # The synthesised caption spans both words on the line the game drew them.
    assert page.clear_selection.box == (1640, 706, 188, 22)
    assert clear_selection_caption(recs, SIZE).text == 'Clear Selection'
    # One word alone is not the caption: the pair stays required.
    assert clear_selection_caption(recs[:1] + recs[2:], SIZE) is None
    assert pre_battle_team_page(recs[:1] + recs[2:], SIZE) is None
    # The two words must share a line, and the earlier one must come first.
    stacked = recs[:2] + [Text('Selection', (1706, 940, 122, 22), .99)]
    assert clear_selection_caption(stacked, SIZE) is None
    reversed_pair = recs[:1] + [Text('Selection', (1706, 706, 122, 22), .99),
                                Text('Clear', (1640, 706, 74, 22), .99)]
    assert clear_selection_caption(reversed_pair, SIZE).box == (1640, 706, 188, 22)
    # Two pairs in the band is ambiguous and must not promote the page.
    twice = recs + [Text('Clear', (1660, 730, 74, 22), .99),
                    Text('Selection', (1730, 730, 122, 22), .99)]
    assert clear_selection_caption(twice, SIZE) is None


def live_map(root, name):
    """The retained map frame and its badge template, or a skip."""
    cv2 = pytest.importorskip('cv2')
    image = root / 'evidence/runtime' / name
    template = root / 'assets/resource/base/image/map/node_badge.png'
    if not (image.exists() and template.exists()):
        pytest.skip('retained live map evidence is not present')
    return cv2.imread(str(image)), cv2.imread(str(template))


def test_the_node_badge_enumerates_every_node_on_the_page():
    """The badge under each hexagon is the complete node list; the old scan was not.

    Pinned to the frame that stopped the run: the bright-ornament scan saw only the
    leftmost node there (1 of 5) and the window then exhausted its candidates
    (evidence/runtime/window-20261006-035828). The orange path line runs through
    y 428 and the badges hang at y 506, so a node is BADGE_TO_CENTRE above its badge.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    image, template = live_map(root, 'window-20261006-035828/frame-0008.png')
    markers = node_markers(image, template=template)
    centres = [(m.node[0] + m.node[2] // 2, m.node[1] + m.node[3] // 2) for m in markers]
    assert centres == [(327, 109), (711, 109), (1364, 109), (327, 429), (711, 429)]
    assert {m.node[2] for m in markers} == {190}
    # The badge box itself is the template, scaled to the frame.
    badge = markers[-1].ornament
    assert badge[2] == round(template.shape[1] * image.shape[1] / 1280)
    assert badge[1] + badge[3] // 2 - BADGE_TO_CENTRE == 429


def test_the_player_is_the_node_burning_a_yellow_flame():
    """Only the player's locomotive is lit yellow: 211 px against 0-17 everywhere else."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    image, template = live_map(root, 'window-20261006-035828/frame-0008.png')
    markers = node_markers(image, template=template)
    assert yellow_flame_player(markers, image) == (711, 429)


def test_map_candidates_never_offer_the_players_own_node():
    """The player's node is dropped by radius, and the rest are ordered nearest first.

    A far chest two columns away opened the panel live while its neighbour did not, so
    the list is only an order; what it must never do is hand the player's own node back
    as the sole candidate (that is what made an unreachable-node retry loop pointless).
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    image, template = live_map(root, 'window-20261006-033107/frame-0005.png')
    markers = node_markers(image, template=template)
    player = yellow_flame_player(markers, image)
    assert player == (711, 429)
    centres = [(m.node[0] + m.node[2] // 2, m.node[1] + m.node[3] // 2)
               for m in advance_candidates(markers, player)]
    assert player not in centres
    assert centres[0] == (1095, 429)
    # Without a player reading the list is still complete, just ordered topmost first.
    topmost = [(m.node[0] + m.node[2] // 2, m.node[1] + m.node[3] // 2)
               for m in advance_candidates(markers)]
    assert topmost[0] == (327, 109)
    assert len(topmost) == len(markers)


def test_the_ornament_fallback_lifts_the_node_box_below_the_glyph():
    """A bright interior orbit sits near the top of the hexagon, not at its centre."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    image, _ = live_map(root, 'window-20261006-035828/frame-0008.png')
    markers = node_markers(image)
    assert len(markers) == 1
    ornament, node = markers[0].ornament, markers[0].node
    # The component's centroid is not exactly its bounding-box centre (the glyph is
    # irregular), so this only has to show the box was lifted, not by a pixel-exact 70.
    lifted = node[1] + node[3] // 2 - (ornament[1] + ornament[3] // 2)
    assert abs(lifted - ORNAMENT_LIFT) <= 4


def test_the_map_survives_a_header_ocr_merges_into_one_token():
    """The third live shape: 'Exploring Floor' as a single token, digit dropped.

    evidence/runtime/window-20261006-040651/frame-0001.json reads the header as
    'Exploring Floor' [60,133,330,41] with no floor number anywhere, which neither the
    combined pattern (it demanded a digit) nor the split one (it demanded the token be
    exactly 'Exploring') accepted, so the live page fell back to UNKNOWN.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-040651/frame-0001.json'
    if not path.exists():
        pytest.skip('retained live session evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    header = map_header(records, tuple(data['size']))
    assert header is not None
    assert (header.floor, header.pack) == (None, 'To be Cleaved')
    assert header.exploring_text.box == (60, 133, 330, 41)
    assert map_page(records, tuple(data['size'])) is True


def test_a_panel_frame_carries_no_node_badges():
    """The reward-card panel's bright art must not read as a map (0.695 at the same ROI)."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cv2 = pytest.importorskip('cv2')
    image = root / 'evidence/runtime/window-20261006-034714/frame-0022.png'
    template = root / 'assets/resource/base/image/map/node_badge.png'
    if not (image.exists() and template.exists()):
        pytest.skip('retained live panel evidence is not present')
    frame, badge = cv2.imread(str(image)), cv2.imread(str(template))
    size = (round(badge.shape[1] * frame.shape[1] / 1280),
            round(badge.shape[0] * frame.shape[0] / 1280))
    scaled = cv2.resize(badge, size, interpolation=cv2.INTER_LINEAR)
    assert float(cv2.matchTemplate(frame, scaled, cv2.TM_CCOEFF_NORMED).max()) < 0.80


def test_a_read_node_outranks_a_guessed_lattice_step():
    """The badge node must never be deduplicated away by a lattice guess.

    Live run build/window-run35 (floor 3) clicked four lattice points and stopped with
    no_candidate_node_observed: the one badge on that floor (center 1095,429) sat 48 px
    from the third guess, inside the 50 px dedupe radius, so the verified node was
    dropped from the list entirely.
    """
    from pathlib import Path
    from maalimbus.map_vision import map_clicks
    root = Path(__file__).resolve().parents[1]
    image, template = live_map(root, 'window-20261006-052530/frame-0020.png')
    clicks = map_clicks(image, template=template)
    assert clicks, 'the floor had one badge node to offer'
    # Readings taken off the frame come first, guesses last: the node the frame reads is
    # in front of every lattice step, whether the reading is the node's badge or a ring
    # the game lit around it.
    centre = (1000 + 190 // 2, 334 + 190 // 2)
    covers = [index for index, item in enumerate(clicks)
              if (item['point'][0] - centre[0]) ** 2
              + (item['point'][1] - centre[1]) ** 2 <= 45 * 45]
    assert covers, 'the node the frame reads is offered'
    reading = clicks[covers[0]]
    assert reading['kind'] in ('node_away_from_player', 'lit_node', 'badge_mark',
                               'lit_icon', 'highlighted_node', 'cyan_node', 'lit_ring')
    first_guess = min(index for index, item in enumerate(clicks)
                      if item['kind'] == 'lattice_step')
    assert covers[0] < first_guess, 'the read node outranks every guessed step'
    # The guess that used to swallow it is gone: every remaining lattice step keeps
    # clear of the node the frame actually read.
    for item in clicks[first_guess:]:
        x, y, w, h = item['box']
        assert ((x + w // 2 - centre[0]) ** 2 + (y + h // 2 - centre[1]) ** 2) > 50 * 50


def test_the_shop_node_survives_a_badge_hit_that_is_not_a_node():
    """Neither node source alone enumerates a floor, so the read keeps both.

    Live run build/window-run76 (floor 4, evidence/runtime/window-20261006-212950/
    frame-0058.png): the badge template matched the player's own crescent and one arc
    of the lit orange ring, whose box (232,14,190,190) sits off the top of the map, so
    the only candidate left was that empty spot and the run clicked it eight times --
    each time opening the gift tray over the map -- while the ornament scan still saw
    the shop node at (263,338,190,190).
    """
    from pathlib import Path
    from maalimbus.map_vision import map_clicks, node_markers
    root = Path(__file__).resolve().parents[1]
    image, template = live_map(root, 'window-20261006-212950/frame-0058.png')
    markers = node_markers(image, template=template)
    boxes = [marker.node for marker in markers]
    assert (263, 338, 190, 190) in boxes, 'the ornament scan read the shop node'
    clicks = map_clicks(image, template=template)
    # The off-screen spot the badge lift produced is never the whole offer any more: the
    # ring the game lit around that node names it from its own pixels.
    assert clicks[0]['box'] != (232, 14, 190, 190)
    shop = [item for item in clicks if item['box'] == (263, 338, 190, 190)]
    assert shop, 'the shop node is offered once the empty spot has had its turn'
    assert shop[0]['kind'] in ('highlighted_node', 'node_away_from_player')
    # The crescent hanging inside the lit ring is that node's badge, and the badge's own
    # centre (327,187) is the point the game answers to -- the registered lift put it off
    # the top of the map. The lit ring names that same node from its own pixels, so the
    # node is offered whether the badge lift lands on it or not, and the two reads of one
    # node are collapsed by the 50 px dedupe inside ``map_clicks``.
    offered = [item for item in clicks
               if (item['point'][0] - 327) ** 2 + (item['point'][1] - 187) ** 2 <= 60 * 60]
    assert offered, 'the lit ring node is offered'
    assert offered[0]['kind'] in ('lit_node', 'badge_mark', 'node_away_from_player')
    assert len(offered) == 1, 'one node, one candidate'


def test_the_battle_hud_survives_the_red_backdrop_reading_nave():
    """The WAVE caption loses a stroke once the floor is drawn in red.

    Live evidence/runtime/window-20261006-053000/frame-0030.json (floor 3's battle)
    reads "NAVE" beside a clean "TURN" while every other token of the HUD is present,
    and the driver then sat on an UNKNOWN page for a whole turn.
    """
    from pathlib import Path
    import json
    from maalimbus.battle_vision import battle_hud
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-053000/frame-0030.json'
    if not path.exists():
        pytest.skip('retained live battle evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    hud = battle_hud(records, tuple(data['size']))
    assert hud is not None
    assert hud['wave_box'] == (28, 41, 38, 24)
    assert hud['diagnostics'] == ['Damage', 'Rate', 'Win']


def test_the_battle_hud_survives_a_counter_that_lost_its_first_digit():
    """Live window-20261007-151655/frame-0529.json, floor 5's battle.

    The corner reads "/10" [98,39,34,24] 0.99 and "TURN" [20,97,42,22] 1.0, with
    START [1402,740,62,30] and the Win/Rate/Damage labels all readable, yet the page
    fell back to UNKNOWN: the wave pattern wanted a digit before the slash. The window
    then waited ten rounds on the battle and stopped the run.
    """
    from pathlib import Path
    import json
    from maalimbus.battle_vision import battle_hud
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261007-151655/frame-0529.json'
    if not path.exists():
        pytest.skip('retained live battle evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    hud = battle_hud(records, tuple(data['size']))
    assert hud is not None
    assert hud['turn_box'] == (20, 97, 42, 22)
    assert hud['wave'] == '/10'
    # A page whose corner holds neither caption nor counter is still not the HUD.
    assert battle_hud([Text('TURN', (20, 97, 42, 22), 1.0),
                       Text('WS', (24, 182, 34, 91), 0.385)], tuple(data['size'])) is None


def test_the_battle_hud_survives_a_frame_that_drops_the_wave_caption():
    """The red floor can cost the whole WAVE word, not just a stroke.

    Live evidence/runtime/window-20261006-053923/frame-0056.json reads "TURN" and the
    wave value "0/10" while the caption itself is missing ("WS" is the left skill
    column), and the driver sat on UNKNOWN until it gave up.
    """
    from pathlib import Path
    import json
    from maalimbus.battle_vision import battle_hud
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-053923/frame-0056.json'
    if not path.exists():
        pytest.skip('retained live battle evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    hud = battle_hud(records, tuple(data['size']))
    assert hud is not None
    assert hud['turn_box'] == (20, 97, 42, 22)
    assert hud['wave'] == '0/10'
    # A page with neither caption nor a wave counter in that corner is not the HUD.
    made_up = [Text('TURN', (20, 97, 42, 22), 1.0), Text('WS', (24, 182, 34, 91), 0.385)]
    assert battle_hud(made_up, tuple(data['size'])) is None


def test_the_start_control_is_read_at_the_right_edge_of_the_band():
    """The START banner's own centre sits at x=0.806 on a live floor-3 frame.

    Live evidence/runtime/window-20261006-103550/frame-0044.json reads "START"
    [1518,738,60,28] beside the Win/Damage labels; a band that ended at 0.80 dropped
    it, and the driver re-assigned skills for eight turns without submitting one.
    """
    from pathlib import Path
    import json
    import cv2
    import pytest as _pytest
    cv2 = _pytest.importorskip('cv2')
    from maalimbus.battle_vision import start_button
    root = Path(__file__).resolve().parents[1]
    json_path = root / 'evidence/runtime/window-20261006-103550/frame-0044.json'
    png_path = json_path.with_suffix('.png')
    if not json_path.exists():
        pytest.skip('retained live battle evidence is not present')
    data = json.loads(json_path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    size = tuple(data['size'])
    label = start_button(records, size)
    assert label == (1518, 738, 60, 28)
    if not png_path.exists():
        return
    control = start_button(records, size, cv2.imread(str(png_path)))
    assert control is not None
    x, y, w, h = control
    assert (x, y, w, h) == (1495, 772, 122, 134)
    # The banner is drawn above its button, so the control hangs under the label.
    assert y >= label[1] + label[3] - 10
    assert abs((x + w / 2) - (label[0] + label[2] / 2)) < 40


def test_the_map_survives_the_header_word_being_misread():
    """OCR turns "Floor" into "Flaor" and the whole map page fell back to UNKNOWN.

    Live evidence/runtime/window-20261006-104857/frame-0080.json reads the header as
    'Exploring Flaor' [56,127,310,53] with the pack 'Repressed Wrath' below it.
    """
    from pathlib import Path
    import json
    from maalimbus.map_vision import map_header
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261006-104857/frame-0080.json'
    if not path.exists():
        pytest.skip('retained live map evidence is not present')
    data = json.loads(path.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    header = map_header(records, tuple(data['size']))
    assert header is not None
    assert header.floor is None
    assert header.pack == 'Repressed Wrath'


def test_the_player_is_the_reading_the_flame_agrees_with():
    """Live evidence/runtime/window-20261007-174525/frame-0002.png, caught mid-fade.

    The readings of that frame disagree: the locomotive pair lands at (636,510) and the
    badge lift at (751,425) while the flame burns at (694,384). map_clicks believed the
    locomotive first, so the path reading started from a point 137 px off -- outside
    PATH_REACH -- and returned nothing, and the run's first click went to the hexagon
    between them (window-run-continue-14, step 0: MAP [852,276,40,40], passed false, the
    panel only opened on the retry from the next observation).
    """
    from pathlib import Path
    pytest.importorskip('cv2')
    from maalimbus.map_vision import flame_count, node_markers, player_of, train_player
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261007-174525/frame-0002.png'
    if not path.exists():
        pytest.skip('retained live map evidence is not present')
    import cv2
    image = cv2.imread(str(path))
    markers = node_markers(image)
    player = player_of(image, markers)
    assert player is not None
    # The badge lift is the reading the flame stands under, and the locomotive's own
    # lamp is why the flame score, not the reading order, has to settle it.
    assert abs(player[0] - 751) <= 25 and abs(player[1] - 425) <= 25, player
    locomotive = train_player(image)
    assert locomotive is not None, 'the live mid-fade frame must still offer the pair'
    assert abs(locomotive[0] - 636) <= 30 and abs(locomotive[1] - 510) <= 30, locomotive
    assert flame_count(image, player) > flame_count(image, locomotive)


def test_the_cyan_path_is_walked_even_when_the_player_is_read_mid_fade():
    """The same mid-fade frame: the path candidate has to survive the wrong player.

    ``player_of`` settles the reading above, and this pins what the caller gets: the node
    the cyan line points at (1054,124) is the first candidate, ahead of the hexagon the
    run actually clicked.
    """
    from pathlib import Path
    pytest.importorskip('cv2')
    from maalimbus.map_vision import map_clicks
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261007-174525/frame-0002.png'
    if not path.exists():
        pytest.skip('retained live map evidence is not present')
    import cv2
    image = cv2.imread(str(path))
    clicks = map_clicks(image)
    assert clicks, 'the live factory floor must offer candidates'
    first = clicks[0]
    assert first['kind'] == 'path_node', clicks[:3]
    point = first['point']
    assert abs(point[0] - 1054) <= 40 and abs(point[1] - 124) <= 40, point


def test_bright_offered_icon_remains_a_candidate_when_ring_merges():
    from pathlib import Path
    cv2 = pytest.importorskip('cv2')
    from maalimbus.map_vision import map_clicks
    path=Path(__file__).resolve().parents[1]/'evidence/runtime/window-20261009-053703/frame-0102.png'
    if not path.exists():
        pytest.skip('retained live map evidence is not present')
    clicks=map_clicks(cv2.imread(str(path)))
    offered=[(i,c) for i,c in enumerate(clicks) if abs(c['point'][0]-1087)<20 and abs(c['point'][1]-409)<20]
    assert offered and offered[0][0]<8
    assert offered[0][1]['kind']=='bright_lit_icon'


def test_the_offered_ring_is_named_first_on_a_floor_painted_the_same_gold():
    """Live evidence/runtime/window-20261007-175552/frame-0052.png, floor 3.

    "Emotional Indolence" paints its background in the offer's own gold, so the ring every
    other floor shows is merged into the web behind it and the page yields eight ordinary
    nodes' icons instead. The run spent eight clicks on them (run-continue-15, 21:59:18 to
    22:00:27) before the offered node's own box (1064,472,190,190) finally took one, which
    is what a map that runs out of ``--map-tries`` looks like from the inside. The ring is
    still there once the threshold clears the web: centre (1147,443).
    """
    from pathlib import Path
    pytest.importorskip('cv2')
    from maalimbus.map_vision import LIT_RING_MIN_VALUE, lit_rings, map_clicks
    root = Path(__file__).resolve().parents[1]
    path = root / 'evidence/runtime/window-20261007-175552/frame-0052.png'
    if not path.exists():
        pytest.skip('retained live map evidence is not present')
    import cv2
    image = cv2.imread(str(path))
    rings = lit_rings(image, min_value=LIT_RING_MIN_VALUE)
    assert len(rings) == 1, rings
    assert abs(rings[0][0] - 1147) <= 20 and abs(rings[0][1] - 443) <= 20, rings
    clicks = map_clicks(image)
    assert clicks[0]['kind'] == 'lit_ring', clicks[:3]
    point = clicks[0]['point']
    assert abs(point[0] - 1147) <= 20 and abs(point[1] - 443) <= 20, point
    # The icons that used to be offered first are still on the page, behind the ring.
    icons = [index for index, item in enumerate(clicks) if item['kind'] == 'lit_icon']
    assert icons and min(icons) > 0, clicks[:3]
