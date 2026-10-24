"""D103: the skill-detail overlay is a toggle on the card that opened it.

Measured, not assumed: over every retained run, the anchored dismissal at the empty
board closed the overlay **0 of 52 times** -- run `packaged-mirror-20261024-070705`
sent 43 of them, one per click, and the page stayed `BATTLE_TIP` throughout.  So the
close is the same card again, and the point has to travel with the state.
"""
import json
from pathlib import Path

import pytest

from maalimbus import runner

REPO = Path(__file__).resolve().parents[1]


def _loop(tmp_path):
    loop = runner.MirrorRunner(runner.FakeDevice(),
                               settings={'rounds': 1, 'interval': 0},
                               directory=tmp_path)
    return loop


def test_the_card_that_opened_the_overlay_is_the_card_that_closes_it(tmp_path):
    loop = _loop(tmp_path)
    loop.state['battle_tip_from'] = [740, 948]
    assert loop._battle_tip_control('BATTLE_TIP', loop.state) == [738, 946, 4, 4]


def test_another_page_gets_no_such_control(tmp_path):
    loop = _loop(tmp_path)
    loop.state['battle_tip_from'] = [740, 948]
    for page in ('BATTLE_HUD', 'BATTLE_RESULT', 'MAP'):
        assert loop._battle_tip_control(page, loop.state) is None


def test_a_run_that_never_pressed_a_card_closes_it_on_a_skill_slot(tmp_path):
    """D106: with no card in hand the tap goes to the measured skill row, not the board."""
    from maalimbus.battle_vision import SKILL_ROW_POINT
    loop = _loop(tmp_path)
    box = loop._battle_tip_control('BATTLE_TIP', loop.state)
    assert box is not None
    centre = (box[0] + box[2] / 2, box[1] + box[3] / 2)
    assert centre == (SKILL_ROW_POINT[0], SKILL_ROW_POINT[1])


def test_the_anchored_board_point_is_not_what_the_loop_uses(tmp_path):
    """The old anchor is kept as evidence, but it is not the close (D103)."""
    anchors = json.loads((REPO / 'assets/resource/base/anchors.json').read_text(encoding='utf-8'))

    def find(node):
        if isinstance(node, dict):
            if node.get('id') == 'battle_tip.dismiss_point':
                return node
            for value in node.values():
                got = find(value)
                if got is not None:
                    return got
        elif isinstance(node, list):
            for value in node:
                got = find(value)
                if got is not None:
                    return got
        return None

    anchor = find(anchors)
    assert anchor is not None and anchor.get('box'), 'the old anchor should stay as evidence'
    loop = _loop(tmp_path)
    loop.state['battle_tip_from'] = [740, 948]
    used = loop._battle_tip_control('BATTLE_TIP', loop.state)
    assert used != list(anchor['box']), 'the measured-dud point must not be the plan'
    assert abs(used[0] - anchor['box'][0]) > 400, 'the close moved from the board to the card row'


def test_the_plan_consumes_the_control(tmp_path):
    from maalimbus import window
    loop = _loop(tmp_path)
    loop.state['battle_tip_from'] = [740, 948]
    box = loop._battle_tip_control('BATTLE_TIP', loop.state)
    plan = window.plan_step('BATTLE_TIP', controls={'battle_tip.dismiss_point': box})
    assert plan['action'] == 'click' and plan['reason'] == 'the_skill_detail_popup_is_dismissed_off_the_board'
    assert list(plan['target']) == box
