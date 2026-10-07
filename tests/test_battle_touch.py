"""Android touch battle: the auto-assign step is planned from the page itself.

These are offline contracts: no test here sends input. They pin the geometry to the
retained live battle frame so a live step can only click inside the game's own
`Win Rate` button, and they pin the pipeline node that performs that click.
"""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from maalimbus.battle_vision import (auto_assign_buttons, auto_assign_plan, battle_hud,
                                     begin_turn_plan, dial_control, start_button)
from maalimbus.vision import Text

ROOT = Path(__file__).resolve().parents[1]
BATTLE = ROOT / 'evidence/runtime/team-page-battle-20261006-010230/frame-0007.json'
ASSIGNED = ROOT / 'evidence/runtime/battle-auto-assign-20261006-011029/frame-0006.json'


def load(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    return [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']], tuple(data['size'])


SHIFTED = ROOT / 'evidence/runtime/battle-step-20261006-013429/frame-0001.json'
SHIFTED_RIGHT = ROOT / 'evidence/runtime/window-20261006-031546/frame-0005.json'
ASSIGNED_RIGHT = ROOT / 'evidence/runtime/window-20261006-032224/frame-0003.json'
WIDEST_RIGHT = ROOT / 'evidence/runtime/window-20261006-032429/frame-0006.json'


def test_auto_assign_buttons_survive_a_shifted_board_layout():
    """The buttons move with the board; the bands must still find them."""
    if not SHIFTED.exists():
        pytest.skip('retained live shifted-layout evidence is not present')
    records, size = load(SHIFTED)
    hud = battle_hud(records, size)
    assert hud is not None and hud['turn'] == '3'      # the turn glyph is readable here
    buttons = auto_assign_buttons(records, size)
    assert buttons is not None
    assert buttons['win_rate'] == (1312, 796, 50, 43)
    assert buttons['damage'] == (1300, 861, 76, 28)
    plan = auto_assign_plan(records, size)
    assert plan['reason'] == 'win_rate_auto_assign' and plan['target'] == (1312, 796, 50, 43)
    assert plan['turn'] == '3'


def test_auto_assign_plan_is_pinned_to_the_live_battle_frame():
    if not BATTLE.exists():
        pytest.skip('retained live battle evidence is not present')
    records, size = load(BATTLE)
    buttons = auto_assign_buttons(records, size)
    assert buttons is not None
    assert buttons['win_rate'] == (1198, 796, 48, 41)
    assert buttons['damage'] == (1184, 861, 78, 28)
    plan = auto_assign_plan(records, size)
    assert plan['reason'] == 'win_rate_auto_assign'
    assert plan['target'] == buttons['win_rate']
    assert plan['wave'] is None and plan['turn'] is None   # bitmap glyphs unread


def test_auto_assign_refuses_without_the_battle_page():
    other = ROOT / 'evidence/runtime/map-settle-20261006-000930/frame-0001.json'
    if not other.exists():
        pytest.skip('retained team-page evidence is not present')
    records, size = load(other)
    assert battle_hud(records, size) is None
    assert auto_assign_buttons(records, size) is None
    assert auto_assign_plan(records, size) == dict(target=None, reason='battle_hud_not_identified')
    # A page with HUD counters but no auto-assign buttons must still refuse.
    wave = Text('WAVE', (16, 39, 54, 30), .99)
    turn = Text('TURN', (18, 95, 44, 24), .99)
    assert auto_assign_plan([wave, turn], size) == dict(target=None,
                                                       reason='auto_assign_buttons_not_present')


def test_turn_start_appears_only_after_auto_assign():
    """Pinned: Win Rate tap produced the START action the turn submission uses."""
    if not (ASSIGNED.exists() and BATTLE.exists()):
        pytest.skip('retained live battle evidence is not present')
    assigned, size = load(ASSIGNED)
    # The recognized word is a banner; the control it names is the warm blob below.
    assert start_button(assigned, size) == (1060, 738, 66, 30)
    import cv2
    image = cv2.imread(str(ASSIGNED.with_suffix('.png')))
    assert image is not None and image.shape[:2] == (size[1], size[0])
    assert start_button(assigned, size, image) == (1038, 771, 121, 133)
    plan = begin_turn_plan(assigned, size, image)
    assert plan['reason'] == 'submit_turn' and plan['target'] == (1038, 771, 121, 133)
    before, size_before = load(BATTLE)
    assert start_button(before, size_before) is None
    assert begin_turn_plan(before, size_before) == dict(target=None, reason='turn_start_not_present')
    # Without the HUD there is no turn submission at all.
    assert begin_turn_plan([Text('START', (1060, 738, 66, 30), .99)], size) == \
        dict(target=None, reason='battle_hud_not_identified')


def test_right_shifted_layouts_are_found_before_and_after_auto_assign():
    """Live: the board widens with the party, so the captions and START move right.

    `window-20261006-031546/frame-0005.json` is the state with no skill assigned at
    all: both captions sit at x .7865 and there is no START banner, so `Win Rate` is
    the only usable control. After that tap the banner appears
    (`window-20261006-032224/frame-0003.json`: [1348,738,66,30]); a wider party
    pushes everything further right
    (`window-20261006-032429/frame-0006.json`: [1548,794,40,23], [1410,742,52,24]).
    """
    for path, win, damage, start in (
            (SHIFTED_RIGHT, (1486, 796, 46, 41), (1472, 863, 76, 24), None),
            (ASSIGNED_RIGHT, (1486, 796, 46, 41), (1472, 861, 76, 26), (1348, 738, 66, 30)),
            (WIDEST_RIGHT, (1542, 794, 48, 43), (1530, 865, 74, 22), (1410, 742, 52, 24))):
        if not path.exists():
            pytest.skip('retained live shifted-layout evidence is not present')
        records, size = load(path)
        buttons = auto_assign_buttons(records, size)
        assert buttons is not None
        assert buttons['win_rate'] == win and buttons['damage'] == damage
        assert start_button(records, size) == start


def test_battle_auto_assign_node_is_bounded_and_not_wired_to_the_theme_drag():
    nodes = json.loads((ROOT / 'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
    node = nodes['BattleAutoAssign']
    assert node['custom_recognition_param'] == {'scene': 'BATTLE_HUD', 'battle_mode': 'win_rate'}
    assert node['action'] == 'Click' and node['target'] is True
    assert node['max_hit'] == 1 and node['on_error'] == ['LimbusUnknown']
    assert node['next'] == ['BattleObserve']
    turn = nodes['BattleStartTurn']
    assert turn['custom_recognition_param'] == {'scene': 'BATTLE_HUD', 'battle_mode': 'start_turn'}
    assert turn['action'] == 'Click' and turn['target'] is True and turn['max_hit'] == 1
    assert turn['next'] == ['BattleObserve']
    observe = nodes['BattleObserve']
    assert observe['custom_action'] == 'limbus_battle_observe' and observe['max_hit'] == 1
    for entry in ('ThemePackDrag', 'MapObserve'):
        assert 'BattleAutoAssign' not in nodes[entry]['next']
        assert 'BattleStartTurn' not in nodes[entry]['next']
    run_native = (ROOT / 'tools/run_native.py').read_text(encoding='utf-8')
    assert "'limbus_battle_observe'" in run_native
    agent = (ROOT / 'agent/recognition.py').read_text(encoding='utf-8')
    assert "battle_mode')=='win_rate'" in agent
    assert "battle_mode')=='start_turn'" in agent


def test_the_turn_dial_is_read_by_colour_when_no_start_word_is_drawn():
    """Live: evidence/runtime/window-20261007-004730/frame-0326.png has no START token.

    Floor 3's board keeps the word too small under its own dial, so start_button found
    nothing, the driver re-assigned skills instead, and the fight stood still at turn
    6/25 through 140 clicks (build/window-run95.json, build/window-run96.json). The dial
    is the large warm blob at 1920 (1327,741,125,154) area 6646, left of the Win Rate
    button, so it is read by colour inside a band that excludes those buttons.
    """
    size = (1920, 1080)
    frame = np.zeros((1080, 1920, 3), np.uint8)
    cv2.circle(frame, (1389, 818), 60, (40, 120, 235), -1)
    # The Win Rate / Damage buttons are warm as well, but they sit outside the band and
    # are smaller than the dial, so neither may be mistaken for it.
    cv2.rectangle(frame, (1486, 796), (1590, 838), (40, 120, 235), -1)
    cv2.rectangle(frame, (1472, 863), (1548, 889), (40, 120, 235), -1)
    assert dial_control(frame) == (1329, 758, 121, 121)
    # With no START word either, the dial is what the turn is submitted with.
    assert start_button([], size, frame) == (1329, 758, 121, 121)
    # A readable START word still wins: the label's own warm control is read under it
    # (the synthetic Win Rate button above), never the colour fallback.
    label = [Text('START', (1518, 738, 60, 28), 1.0)]
    assert start_button(label, size, frame) == (1486, 796, 105, 43)
    # A small warm speck is not a control at all.
    speck = np.zeros((1080, 1920, 3), np.uint8)
    cv2.circle(speck, (1389, 818), 12, (40, 120, 235), -1)
    assert dial_control(speck) is None
    assert dial_control(np.zeros((1080, 1920, 3), np.uint8)) is None
