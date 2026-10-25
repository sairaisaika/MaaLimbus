"""One auto-assignment per turn, and the badge is what says which turn it is (D157)."""

import types

from maalimbus.runner import MirrorRunner


def _loop(signature, seen):
    loop = MirrorRunner.__new__(MirrorRunner)
    loop.state = {'turn_signature': signature}
    if seen is not None:
        loop.state['assign_signature'] = seen
    return loop


def test_a_second_assignment_in_the_same_turn_is_known():
    loop = _loop([1, 2, 3], [1, 2, 3])
    assert loop._assign_already_sent({'turn_signature': [1, 2, 3]}) is True


def test_a_new_turn_may_be_assigned():
    loop = _loop([9, 9, 9], [1, 2, 3])
    assert loop._assign_already_sent({'turn_signature': [9, 9, 9]}) is False


def test_no_recorded_assignment_means_no_evidence_against_assigning():
    loop = _loop([1, 2, 3], None)
    assert loop._assign_already_sent({'turn_signature': [1, 2, 3]}) is False


def test_a_frame_without_a_badge_is_not_a_repeat():
    loop = _loop([1, 2, 3], [1, 2, 3])
    assert loop._assign_already_sent({}) is False
