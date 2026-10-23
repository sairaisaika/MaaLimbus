from maalimbus import screen_state


def test_a_known_awake_device_spends_nothing():
    """The common case must cost no input: waking an awake device can misroute it."""
    assert screen_state.wake_commands(False) == ()


def test_an_unknown_device_may_be_woken_because_the_alternative_is_a_dead_run():
    assert screen_state.wake_commands(None) == screen_state.TO_WAKE


def test_the_dump_decides_locked_and_never_guesses():
    assert screen_state.is_locked('KeyguardShowing=false') is False
    assert screen_state.is_locked('KeyguardShowing=true') is True
    assert screen_state.is_locked('nothing here') is None
    assert screen_state.is_locked(None) is None


def test_a_dump_that_mentions_both_prefers_the_explicit_false():
    """A line that says `=false` is the framework saying awake; do not read the prefix."""
    assert screen_state.is_locked('KeyguardShowing=false KeyguardShowing') is False
