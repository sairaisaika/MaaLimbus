"""A click that has not settled is retried before the offer is re-read (D197)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src')]

from maalimbus.runner import pending_target


def test_a_pending_click_is_reused_within_its_budget():
    state = {'map_pending': [10, 20, 30, 40]}
    plan = {'target': [99, 99, 10, 10]}
    assert pending_target(state, plan, tries=3) == ([10, 20, 30, 40], True)
    assert pending_target(state, plan, tries=3) == ([10, 20, 30, 40], True)
    assert pending_target(state, plan, tries=3) == ([10, 20, 30, 40], True)
    assert pending_target(state, plan, tries=3) == ([99, 99, 10, 10], False)
    assert state['map_retries'] == 0


def test_no_pending_click_plans_normally():
    assert pending_target({}, {'target': [1, 2, 3, 4]}, tries=3) == ([1, 2, 3, 4], False)


def test_a_zero_budget_stops_reusing_immediately():
    state = {'map_pending': [1, 1, 1, 1]}
    assert pending_target(state, {'target': [2, 2, 2, 2]}, tries=0) == ([2, 2, 2, 2], False)


def test_the_reused_target_is_a_copy():
    pending = [1, 2, 3, 4]
    state = {'map_pending': pending}
    target, _ = pending_target(state, {'target': [9, 9, 9, 9]}, tries=1)
    target[0] = 77
    assert pending == [1, 2, 3, 4]
