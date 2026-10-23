"""A waiting step is counted, reported every fifth, and ends the loop at the limit."""

from maalimbus.runner import WAIT_LIMIT, wait_decision


def test_four_waits_say_nothing():
    assert wait_decision(4)['note'] is False
    assert wait_decision(4)['stop'] is False


def test_every_fifth_wait_is_reported():
    assert wait_decision(5)['note'] is True
    assert wait_decision(10)['note'] is True
    assert wait_decision(5)['stop'] is False


def test_the_limit_itself_still_waits():
    assert wait_decision(WAIT_LIMIT)['stop'] is False


def test_past_the_limit_the_loop_ends_itself():
    decision = wait_decision(WAIT_LIMIT + 1)
    assert decision['stop'] is True
    assert decision['reason'] == 'the_loop_waited_without_a_new_page'
