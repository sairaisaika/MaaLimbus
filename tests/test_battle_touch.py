"""Android touch battle: the auto-assign step is planned from the page itself.

These are offline contracts: no test here sends input. They pin the geometry to the
retained live battle frame so a live step can only click inside the game's own
`Win Rate` button, and they pin the pipeline node that performs that click.
"""
import json
from pathlib import Path

import pytest

from maalimbus.battle_vision import (auto_assign_buttons, auto_assign_plan, battle_hud,
                                     begin_turn_plan, start_button)
from maalimbus.vision import Text

ROOT = Path(__file__).resolve().parents[1]
BATTLE = ROOT / 'evidence/runtime/team-page-battle-20261006-010230/frame-0007.json'
ASSIGNED = ROOT / 'evidence/runtime/battle-auto-assign-20261006-011029/frame-0006.json'


def load(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    return [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']], tuple(data['size'])


SHIFTED = ROOT / 'evidence/runtime/battle-step-20261006-013429/frame-0001.json'


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
