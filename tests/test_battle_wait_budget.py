"""D149: a battle transition is counted by its own clock, not by the page wait budget.

Measured 2026-10-24 (`packaged-mirror-20261024-172437`): a healthy fight spent 41
transition waits, `WAIT_LIMIT = 40` ended the run at 85 s, and the battle had not finished.
"""
import inspect

from maalimbus import runner


def test_a_battle_wait_does_not_count_towards_the_page_budget():
    source = inspect.getsource(runner.MirrorRunner._walk)
    assert "if not result.get('battle'):" in source
    assert "self._waited += 1" in source


def test_the_transition_result_carries_whether_it_was_a_battle():
    source = inspect.getsource(runner.MirrorRunner.step)
    assert 'battle=in_battle' in source


def test_a_page_wait_still_ends_after_the_limit():
    assert runner.wait_decision(runner.WAIT_LIMIT)['stop'] is False
    assert runner.wait_decision(runner.WAIT_LIMIT + 1) == {
        'note': True, 'stop': True, 'reason': 'the_loop_waited_without_a_new_page'}


def test_the_transition_clock_still_bounds_a_battle():
    assert 0 < runner.settings().transition_seconds <= 120
