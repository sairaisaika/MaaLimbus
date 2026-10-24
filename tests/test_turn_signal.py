"""D113: the turn badge is a signal, and the loop reads it from the picture.

Measured on evidence/runtime/packaged-mirror-20261024-095825: within one turn the badge
crop varies by <= 0.06 (mean absolute difference); across a turn boundary by 13.56.
"""

import pathlib
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import cv2  # noqa: E402

from maalimbus import battle_vision  # noqa: E402
from maalimbus import runner as mirror  # noqa: E402

EVIDENCE = pathlib.Path(__file__).resolve().parent.parent / "evidence/runtime"


def _frame(name, number):
    path = EVIDENCE / name / f"frame-{number:04d}.png"
    if not path.exists():
        pytest.skip(f"no retained live frame {path.name}")
    return cv2.imread(str(path))


def test_the_badge_picture_is_stable_within_a_turn():
    first = battle_vision.turn_signature(_frame("packaged-mirror-20261024-095825", 2))
    later = battle_vision.turn_signature(_frame("packaged-mirror-20261024-095825", 27))
    assert battle_vision.turn_changed(first, later) is False


def test_the_badge_picture_moves_across_a_turn_boundary():
    first = battle_vision.turn_signature(_frame("packaged-mirror-20261024-095825", 2))
    next_turn = battle_vision.turn_signature(_frame("packaged-mirror-20261024-095825", 70))
    assert battle_vision.turn_changed(first, next_turn) is True


def test_the_threshold_sits_between_the_two_populations():
    # The margin is what makes this safe: a within-turn wobble must never be a new turn.
    same = battle_vision.turn_changed([100] * 64, [101] * 64)
    new = battle_vision.turn_changed([100] * 64, [120] * 64)
    assert same is False and new is True


def test_a_missing_picture_is_not_a_change():
    assert battle_vision.turn_changed(None, [1] * 64) is False
    assert battle_vision.turn_changed([1] * 64, [2] * 32) is False


class _Observer:
    def __init__(self, scene, signature):
        self.record = {"scene": scene, "turn_signature": signature}
        self.directory = None


def _loop():
    return mirror.MirrorRunner.__new__(mirror.MirrorRunner)


def test_a_new_turn_clears_the_pair_count():
    loop = _loop()
    loop.state = {"battle_pairs": 2, "battle_assigns": 3}
    loop.notes = []
    loop.note = lambda name, **fields: loop.notes.append((name, fields))
    loop._turn_signal("BATTLE_HUD", {"turn_signature": [0] * 64})
    assert loop.state["battle_pairs"] == 2  # first picture is a baseline, not a turn
    loop._turn_signal("BATTLE_HUD", {"turn_signature": [90] * 64})
    assert loop.state["battle_pairs"] == 0
    assert loop.state["battle_assigns"] == 0
    assert loop.notes == [("battle_turn_advanced", {"page": "BATTLE_HUD", "pairs_cleared": 2})]


def test_the_same_turn_leaves_the_count_alone():
    loop = _loop()
    loop.state = {"battle_pairs": 2, "battle_assigns": 1}
    loop.notes = []
    loop.note = lambda name, **fields: loop.notes.append((name, fields))
    loop._turn_signal("BATTLE_HUD", {"turn_signature": [10] * 64})
    loop._turn_signal("BATTLE_HUD", {"turn_signature": [10] * 64})
    assert loop.state["battle_pairs"] == 2
    assert loop.notes == []


def test_a_page_that_is_not_the_board_teaches_nothing():
    loop = _loop()
    loop.state = {}
    loop.notes = []
    loop.note = lambda name, **fields: loop.notes.append((name, fields))
    loop._turn_signal("MAP", {"turn_signature": [0] * 64})
    assert "turn_signature" not in loop.state
