"""A long animation is polled by a loop that backs off (D128).

Measured on `packaged-mirror-20261024-135553`: a battle turn held 2..21
`window_transition_wait` rows of 1.0 s each plus a read, so a 45 s turn spent most of
it re-reading one animation.  The pause doubles with the number of waits spent on that
transition and stops at the ceiling; naming the page resets the count elsewhere, so a
short animation still gets a short poll.
"""
import pytest

from maalimbus.runner import transition_pause


def test_the_first_poll_is_the_measured_short_one():
    assert transition_pause(1.0, 1) == 2.0
    assert transition_pause(1.0, 0) == 1.0


def test_the_pause_doubles_and_then_stops_at_the_ceiling():
    assert [transition_pause(1.0, n) for n in (0, 1, 2, 3, 4, 9)] == [1.0, 2.0, 4.0, 4.0, 4.0, 4.0]


def test_the_ceiling_is_a_parameter_so_a_slower_poll_can_still_be_short():
    assert transition_pause(1.5, 3) == 4.0
    assert transition_pause(0.5, 1, ceiling=1.0) == 1.0


def test_a_count_that_is_not_a_number_is_the_first_poll():
    assert transition_pause(1.0, None) == 1.0
    # a numeric string is a count, not a first poll: int("3") is three waits
    assert transition_pause(1.0, "3") == 4.0


def test_the_pause_never_returns_a_bool_or_a_string():
    for seen in (0, 1, 2, 3):
        value = transition_pause(1.0, seen)
        assert isinstance(value, float) and not isinstance(value, bool)
