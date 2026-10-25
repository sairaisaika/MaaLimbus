"""One auto-assignment per turn, and the badge is what says which turn it is (D157)."""

import types

from maalimbus.runner import MirrorRunner


def _loop(signature=None, seen=None):
    loop = MirrorRunner.__new__(MirrorRunner)
    loop.state = {} if signature is None else {'turn_signature': signature}
    if seen is not None:
        loop.state['assign_signature'] = seen
    return loop


def test_a_second_assignment_in_the_same_turn_is_known():
    """A signal that has never differed cannot say "same turn" (2026-10-25).

    `packaged-mirror-20261025-014906` carried one identical badge vector on every
    battle frame, so the old rule suppressed the assignment for the whole fight and the
    submit pressed an unassigned board.  Two distinct signatures first, then a repeat.
    """
    loop = _loop()
    loop.state['assign_signature'] = [1, 2, 3]
    assert loop._assign_already_sent({'turn_signature': [9, 9, 9]}) is False   # one sight is no proof
    assert loop._assign_already_sent({'turn_signature': [1, 2, 3]}) is True    # two sights, same turn
    assert loop._assign_already_sent({'turn_signature': [4, 4, 4]}) is False   # a new turn


def test_a_constant_badge_is_not_evidence_of_the_same_turn():
    loop = _loop()
    loop.state['assign_signature'] = [5, 5, 5]
    for _ in range(4):
        assert loop._assign_already_sent({'turn_signature': [5, 5, 5]}) is False

def test_a_new_turn_may_be_assigned():
    loop = _loop([9, 9, 9], [1, 2, 3])
    assert loop._assign_already_sent({'turn_signature': [9, 9, 9]}) is False


def test_no_recorded_assignment_means_no_evidence_against_assigning():
    loop = _loop([1, 2, 3], None)
    assert loop._assign_already_sent({'turn_signature': [1, 2, 3]}) is False


def test_a_frame_without_a_badge_is_not_a_repeat():
    loop = _loop([1, 2, 3], [1, 2, 3])
    assert loop._assign_already_sent({}) is False
