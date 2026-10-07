"""The rule that turns an observed page into one ledger event, and no more."""
from maalimbus.run_wiring import (ENTRY_CONFIRM_REASON, MAP_FORWARD_REASON,
                                 REWARD_CONFIRM_REASON, ledger_event)

MAP = dict(page='MAP', reason=MAP_FORWARD_REASON)


def test_standing_on_a_floor_proves_the_one_before_it():
    first = ledger_event(**MAP, floor=2, cleared=())
    assert (first.kind, first.floor) == ('floor_clear', 1)
    event = ledger_event(**MAP, floor=3, cleared=(1,))
    assert (event.kind, event.floor) == ('floor_clear', 2)


def test_floor_one_proves_nothing_and_a_gap_proves_nothing():
    assert ledger_event(**MAP, floor=1, cleared=()) is None
    # Floor 4 with only floor 1 on the ledger is a gap, not a clear of floor 3.
    assert ledger_event(**MAP, floor=4, cleared=(1,)) is None


def test_the_same_floor_does_not_clear_itself_twice():
    assert ledger_event(**MAP, floor=3, cleared=(1, 2)) is None
    # The ledger already holds floor 4, so standing on floor 5 offers nothing new.
    assert ledger_event(**MAP, floor=5, cleared=(1, 2, 3, 4)) is None
    event = ledger_event(**MAP, floor=5, cleared=(1, 2, 3))
    assert (event.kind, event.floor) == ('floor_clear', 4)


def test_a_map_frame_without_the_floor_digit_settles_nothing():
    assert ledger_event(**MAP, floor=None, cleared=(1,)) is None


def test_the_run_summary_is_the_victory_only_with_all_five_floors():
    assert ledger_event(page='RUN_CLAIM', cleared=(1, 2, 3, 4)) is None
    event = ledger_event(page='RUN_CLAIM', cleared=(1, 2, 3, 4, 5))
    assert (event.kind, event.floor) == ('final_victory', None)
    assert ledger_event(page='RUN_CLAIM', cleared=(1, 2, 3, 4, 5), victory=True) is None


def test_the_reward_is_claimed_by_the_modal_s_own_confirm():
    page = dict(page='RUN_REWARD_CONFIRM')
    assert ledger_event(**page, reason=REWARD_CONFIRM_REASON, cleared=(1, 2, 3, 4, 5)) is None
    event = ledger_event(**page, reason=REWARD_CONFIRM_REASON, cleared=(1, 2, 3, 4, 5),
                         victory=True)
    assert event.kind == 'reward_received'
    assert ledger_event(**page, reason='the_reward_modal_is_claimed_and_never_given_up',
                        cleared=(1, 2, 3, 4, 5), victory=True) is None


def test_the_next_entry_is_the_loadout_picker_s_confirm():
    page = dict(page='DUNGEON_TEAM')
    assert ledger_event(**page, reason=ENTRY_CONFIRM_REASON, victory=True) is None
    event = ledger_event(**page, reason=ENTRY_CONFIRM_REASON, victory=True, reward=True)
    assert event.kind == 'entry_returned'
    # Selecting the slot is not the entry; only Confirm is.
    assert ledger_event(**page, reason='dungeon_team_slot_is_selected_for_the_rotation',
                        victory=True, reward=True) is None


def test_nothing_is_offered_once_the_run_has_returned():
    settled = dict(cleared=(1, 2, 3, 4, 5), victory=True, reward=True, returned=True)
    assert ledger_event(**MAP, floor=3, **settled) is None
    assert ledger_event(page='RUN_CLAIM', **settled) is None
    assert ledger_event(page='RUN_REWARD_CONFIRM', reason=REWARD_CONFIRM_REASON, **settled) is None
    assert ledger_event(page='DUNGEON_TEAM', reason=ENTRY_CONFIRM_REASON, **settled) is None
