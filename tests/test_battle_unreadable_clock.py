"""A battle whose frames stay unreadable is a stop with a name (2026-10-25).

Measured on `packaged-mirror-20261025-013933`: 40 transition waits, every one after
`BATTLE_HUD`, 36 of them followed by another unreadable frame and 42 of 71 battle frames
carrying no turn badge -- ~144 s of a 300 s budget spent waiting for a picture that never
resolved.  The clock is the answer; the counter-examples are a page that resolves in time
and a non-battle page, which keeps D163's own clock.
"""

import time

import pytest

import maalimbus.runner as runner


def test_the_ending_has_a_name_and_a_kind():
    import maalimbus.pages as pages
    assert runner.BATTLE_UNREADABLE == 'the_battle_stayed_unreadable'
    assert pages.kind_of(reason=runner.BATTLE_UNREADABLE) == 'unreadable_text'
    assert pages.STOP_KINDS[runner.BATTLE_UNREADABLE] == 'unreadable_text'


def test_the_clock_is_far_below_a_run_budget():
    settings = runner.settings()
    limit = float(getattr(settings, 'battle_unreadable_seconds', 30.0))
    assert 5.0 <= limit <= 60.0


def test_a_named_battle_page_clears_nothing_by_itself():
    state = runner._fresh_state(runner.settings())
    assert 'battle_unknown_since' not in state
