"""The ledger's acceptance contract: five floors, the reward, the way out, rotation.

The objective names this exact bar -- clear five floors of Hard, claim the
reward, return to the entrance, then rotate the saved team -- so the rule that
decides it gets a case of its own, including the ways it must refuse: a run that
misses a floor, a victory without the reward, or being back at the entrance
without having won must all leave the rotation where it was.
"""

import pytest

from maalimbus.policies import RunLedger

ORDER = (5, 4, 1, 6, 2, 7, 3)


def _arm(ledger):
    """Put a finished-looking run back on the ledger before the next check."""
    ledger.cleared_floors = {1, 2, 3, 4, 5}
    ledger.final_victory = True
    ledger.reward_received = True
    ledger.entry_returned = True
    return ledger


def _run():
    return _arm(RunLedger(team_slots=ORDER))


def test_a_complete_run_is_accepted():
    ledger = _run()
    assert ledger.complete() is True
    assert ledger.completed_runs == 1
    assert ledger.rotation == 1


def test_a_run_missing_a_floor_or_the_reward_is_refused():
    ledgers = []
    for name in ('final_victory', 'reward_received', 'entry_returned'):
        ledger = _run()
        setattr(ledger, name, False)
        ledgers.append(ledger)
    short = _run()
    short.cleared_floors = {1, 2, 3, 4}
    ledgers.append(short)
    for ledger in ledgers:
        assert ledger.complete() is False
        assert ledger.completed_runs == 0
        assert ledger.rotation == 0


def test_each_completed_run_advances_the_rotation_and_clears_the_run():
    ledger = _run()
    ledger.complete()
    assert ledger.cleared_floors == set()
    assert ledger.final_victory is False
    assert ledger.reward_received is False
    assert ledger.entry_returned is False
    assert ledger.rotation == 1  # the order's second slot is team 4


def test_the_rotation_wraps_once_every_saved_team_has_had_a_turn():
    ledger = _run()
    for expected in range(1, len(ORDER) + 1):
        assert ledger.complete() is True
        assert ledger.rotation == expected % len(ORDER)
        _arm(ledger)  # the next run fills the ledger again
    assert ledger.completed_runs == len(ORDER)
    assert ledger.rotation == 0


def test_saved_team_slots_are_validated():
    with pytest.raises(ValueError):
        RunLedger(team_slots=())
    with pytest.raises(ValueError):
        RunLedger(team_slots=(0, 3))
    with pytest.raises(ValueError):
        RunLedger(team_slots=(21,))
