"""A battle board is walked at the battle's own spacing (D158)."""

import time

from maalimbus import runner
from maalimbus.runner import MirrorRunner


def _loop(page):
    loop = MirrorRunner.__new__(MirrorRunner)
    loop.state = {'last_named_page': page}
    loop.artifacts = {'input_at': time.monotonic()}
    return loop


def test_a_battle_page_is_walked_at_the_shorter_spacing():
    assert _loop('BATTLE_HUD')._pause_between_steps(6.0) <= runner.BATTLE_INTERVAL + 1e-6


def test_another_page_keeps_the_callers_spacing():
    assert _loop('MAP')._pause_between_steps(6.0) > runner.BATTLE_INTERVAL


def test_the_spacing_never_exceeds_the_callers_interval():
    assert _loop('BATTLE_HUD')._pause_between_steps(0.5) <= 0.5 + 1e-6


def test_the_battle_spacing_is_shorter_than_a_page_interval():
    assert runner.BATTLE_INTERVAL < runner.settings().interval
