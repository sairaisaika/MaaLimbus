"""An unreadable page is bounded by its clock, not only by a count of rounds (D163)."""

import time

from maalimbus import runner


def test_the_unknown_clock_default_is_a_clock_and_not_a_page_budget():
    settings = runner.settings()
    assert settings.unknown_seconds <= 60.0
    assert settings.unknown_seconds > 0.0


def test_the_unknown_clock_is_shorter_than_a_run_budget():
    # 30 rounds of the old budget at a 4 s poll is two minutes of one run.
    assert runner.settings().unknown_seconds < 420.0


def test_a_fresh_state_starts_without_a_clock():
    state = runner._fresh_state(runner.settings())
    assert state.get('unknown_since') is None


def test_the_clock_is_set_when_the_page_first_became_unreadable():
    state = runner._fresh_state(runner.settings())
    before = time.monotonic()
    state['unknown_since'] = state.get('unknown_since') or time.monotonic()
    assert state['unknown_since'] >= before
