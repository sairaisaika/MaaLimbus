"""The board's speed caption is a fixed control, and it is pressed once per fight."""

import json
from pathlib import Path
import types

import pytest

import maalimbus.window as window


def _record(caption, box=(1664, 57, 92, 30)):
    return [types.SimpleNamespace(text=caption, box=list(box), score=0.99)]


def test_the_speed_toggle_is_the_max_caption():
    from maalimbus import battle_vision
    box = battle_vision.speed_toggle(_record('MAX'), (1920, 1080))
    assert list(box) == [1664, 57, 92, 30]


def test_a_board_without_the_caption_offers_no_speed_control():
    from maalimbus import battle_vision
    assert battle_vision.speed_toggle(_record('TURN'), (1920, 1080)) is None


def test_a_caption_outside_its_band_is_not_the_speed_control():
    from maalimbus import battle_vision
    assert battle_vision.speed_toggle(_record('MAX', (200, 700, 92, 30)), (1920, 1080)) is None


def test_the_speed_toggle_is_planned_before_any_assignment():
    plan = window.plan_step('BATTLE_HUD', controls={'battle.speed': [1664, 57, 92, 30]},
                            auto_assign={'win_rate': [1, 2, 3, 4]},
                            battle_assignment='win_rate')
    assert plan['reason'] == 'the_battles_speed_toggle_is_enabled_once_per_battle'
    assert plan['target'] == [1664, 57, 92, 30]
    assert plan['settle_rounds'] == 1


def test_without_the_control_the_board_still_assigns_and_submits():
    plan = window.plan_step('BATTLE_HUD', controls={},
                            auto_assign={'win_rate': [1, 2, 3, 4]},
                            battle_assignment='win_rate')
    assert plan['reason'] != 'the_battles_speed_toggle_is_enabled_once_per_battle'
