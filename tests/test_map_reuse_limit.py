"""A refused target is not re-clicked on a budget (D204)."""

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src')]

from maalimbus import runner  # noqa: E402


def _state(**extra):
    state = {'map_pending': [985, 480, 40, 40], 'map_retries': 0}
    state.update(extra)
    return state


def test_the_first_attempt_is_the_plan():
    assert runner.pending_target(_state(map_pending=None), {'target': [1, 2, 3, 4]}) == ([1, 2, 3, 4], False)


def test_one_re_send_is_allowed():
    target, reused = runner.pending_target(_state(), {'target': [1, 2, 3, 4]})
    assert reused is True and target == [985, 480, 40, 40]


def test_a_second_re_send_is_refused():
    target, reused = runner.pending_target(_state(map_retries=1), {'target': [1, 2, 3, 4]})
    assert reused is False and target == [1, 2, 3, 4]


def test_the_limit_is_one():
    assert runner.REUSE_LIMIT == 1
