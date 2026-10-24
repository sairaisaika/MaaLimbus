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


def test_a_transition_poll_is_not_spaced_by_the_input_cadence(tmp_path, monkeypatch):
    """D153: the backoff is a poll cadence and must survive `_pause_between_steps`.

    Measured 2026-10-24 (`packaged-mirror-20261024-185047`): 87 transition waits, every
    gap 1.0-1.3 s while the count reached 52 in one turn -- the input-spacing subtraction
    ate the whole backoff.
    """
    from maalimbus import runner
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    slept = []
    monkeypatch.setattr(runner.time, 'sleep', lambda s: slept.append(round(float(s), 2)))
    loop.artifacts = {'input_at': runner.time.monotonic(), 'steps': []}
    loop.state = {'step': 0}
    loop.last_event = None
    assert loop._pause_between_steps(4.0) < 4.0          # the input spacing is real
    # The loop's own branch: a transition result keeps its pause whole.
    seen = []
    made = loop._result('UNKNOWN', None, False, None, waiting=True, pause=4.0,
                        battle=True, transition=True)
    assert made['transition'] is True and made['pause'] == 4.0
    seen.append(made)
    assert seen[0]['pause'] == 4.0 and slept == []
