"""The rule that turns an observed page into one ledger event, and no more."""
import json
from types import SimpleNamespace

from maalimbus.run_wiring import (BONUS_CONFIRM_REASON, ENTRY_CONFIRM_REASON,
                                 EXPIRED_CONFIRM_REASON,
                                 MAP_FORWARD_REASON, REWARD_CONFIRM_REASON,
                                 earned_its_payout, expire, ledger_event, reconcile, settle)
from maalimbus.storage import RunStore, read_json, seed_run_store

MAP = dict(page='MAP', reason=MAP_FORWARD_REASON)
ORDER = (5, 4, 1, 6, 2, 7, 3)


def store_at(tmp_path, rotation=0):
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER, rotation=rotation)
    return path, RunStore(path, [SimpleNamespace(slot=s) for s in ORDER])


def frame(tmp_path, name):
    path = tmp_path/name
    path.write_bytes(('frame ' + name).encode())
    return path


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


def test_the_run_summary_proves_floor_five_and_then_the_victory():
    # Nothing else can prove floor 5: standing on floor 6 never happens, so the
    # summary is the proof, and the very next turn of the same loop proves the win.
    floor_five = ledger_event(page='RUN_CLAIM', cleared=(1, 2, 3, 4))
    assert (floor_five.kind, floor_five.floor) == ('floor_clear', 5)
    victory = ledger_event(page='RUN_CLAIM', cleared=(1, 2, 3, 4, 5))
    assert (victory.kind, victory.floor) == ('final_victory', None)
    assert ledger_event(page='RUN_CLAIM', cleared=(1, 2, 3, 4, 5), victory=True) is None
    # A summary reached with a gap in the floors proves nothing at all.
    assert ledger_event(page='RUN_CLAIM', cleared=(1, 2, 3)) is None
    assert ledger_event(page='RUN_CLAIM', cleared=()) is None


def test_modal_confirmation_never_proves_reward_receipt():
    page = dict(page='RUN_REWARD_CONFIRM')
    assert ledger_event(**page, reason=REWARD_CONFIRM_REASON, cleared=(1, 2, 3, 4, 5)) is None
    event = ledger_event(**page, reason=REWARD_CONFIRM_REASON, cleared=(1, 2, 3, 4, 5),
                         victory=True)
    assert event is None
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


def test_settling_opens_a_run_only_when_a_page_really_settles_something(tmp_path):
    """A window that outlives its own receipt keeps recording the dungeon after it.

    Live: run-continue-7 paid out its run (entry_returned) and the very next dungeon
    began in the same window, so the store stood with no active run. The map page's floor
    clear is what opens the run after it; a page that settles nothing must not open one.
    """
    path, store = store_at(tmp_path)
    proof = frame(tmp_path, 'frame.png')
    assert settle(store, page='MAP', floor=1, proof=proof) == []
    assert read_json(path)['active'] is None

    events = settle(store, **MAP, floor=2, proof=proof)
    assert [(e.kind, e.floor) for e in events] == [('floor_clear', 1)]
    assert read_json(path)['active']['floors'] == [1]


def test_settling_never_offers_a_page_the_store_would_refuse(tmp_path):
    path, store = store_at(tmp_path)
    proof = frame(tmp_path, 'frame.png')
    store.start()
    settle(store, **MAP, floor=2, proof=proof)
    settle(store, **MAP, floor=3, proof=proof)
    # Floors 1 and 2 are on the ledger, so standing on floor 5 would need floor 3 on it
    # too: the page offers nothing and the window never has to swallow a refusal.
    assert settle(store, **MAP, floor=5, proof=proof) == []
    assert read_json(path)['active']['floors'] == [1, 2]


def test_settling_reports_a_refusal_instead_of_raising(tmp_path, monkeypatch):
    path, store = store_at(tmp_path)
    proof = frame(tmp_path, 'frame.png')

    def refuse(*args, **kwargs):
        raise ValueError('Observation does not belong to the active run')

    monkeypatch.setattr(store, 'record', refuse)
    refusals = []
    assert settle(store, **MAP, floor=2, proof=proof,
                  on_refusal=lambda event, error: refusals.append((event, str(error)))) == []
    assert refusals and refusals[0][0].kind == 'floor_clear'
    assert 'does not belong' in refusals[0][1]


def test_settling_walks_the_summary_through_floor_five_and_the_victory(tmp_path):
    path, store = store_at(tmp_path, rotation=1)
    store.start()
    for floor in range(1, 5):
        assert [e.kind for e in settle(store, **MAP, floor=floor + 1,
                                       proof=frame(tmp_path, 'f%d.png' % floor))] == ['floor_clear']
    seen = []
    proof = frame(tmp_path, 'summary.png')
    seen += settle(store, page='RUN_CLAIM', proof=proof)
    seen += settle(store, page='RUN_CLAIM', proof=proof)
    assert [(e.kind, e.floor) for e in seen] == [('floor_clear', 5), ('final_victory', None)]
    # Asking the same summary a third time settles nothing: the page is done.
    assert settle(store, page='RUN_CLAIM', proof=proof) == []
    assert read_json(path)['active']['floors'] == [1, 2, 3, 4, 5]


def test_an_expired_session_files_the_run_and_leaves_the_rotation_alone(tmp_path):
    # The weekly reset can invalidate a dungeon mid-run: the next entry answers "The
    # previous session has expired. / Please claim your rewards." (live
    # evidence/runtime/window-20261007-170653/frame-0009.json, run-continue-9 step 2).
    # That run never reached floor 5, so it is abandoned and the team is not rotated.
    path, store = store_at(tmp_path, rotation=1)
    store.start()
    settle(store, **MAP, floor=2, proof=frame(tmp_path, 'f1.png'))
    proof = frame(tmp_path, 'expired.png')
    seen = []
    filed = expire(store, page='EXPIRED_SESSION', reason=EXPIRED_CONFIRM_REASON, proof=proof,
                   on_event=seen.append)
    assert filed is not None and filed['floors'] == [1]
    assert [run['id'] for run in seen] == [filed['id']]
    data = read_json(path)
    assert data['active'] is None
    assert data['abandoned'][-1]['id'] == filed['id']
    assert data['abandoned'][-1]['floors'] == [1]
    assert 'expired.png' in data['abandoned'][-1]['note']
    assert data['rotation'] == 1
    # Only that page files anything, and it does it once.
    assert expire(store, page='DRIVE', reason=EXPIRED_CONFIRM_REASON, proof=proof) is None
    assert expire(store, page='EXPIRED_SESSION', reason='something_else', proof=proof) is None
    assert expire(store, page='EXPIRED_SESSION', reason=EXPIRED_CONFIRM_REASON,
                  proof=proof) is None


def test_the_team_picker_files_a_run_the_game_no_longer_holds(tmp_path):
    # A run still in progress answers the entry with the Dungeon Progress dialog, so the
    # loadout picker is only drawn for a new dungeon. Reaching it while the ledger still
    # calls a run active means that run ended without a receipt -- a wipe the player
    # accepted (live: run-continue-18 was wiped on floor 5 and its dialog offers 'Accept
    # results and return to Stage select') -- and the ledger must let the next run open.
    path, store = store_at(tmp_path, rotation=1)
    store.start()
    settle(store, **MAP, floor=2, proof=frame(tmp_path, 'f1.png'))
    proof = frame(tmp_path, 'picker.png')
    seen = []
    filed = reconcile(store, page='DUNGEON_TEAM', proof=proof, on_event=seen.append)
    assert filed is not None and filed['floors'] == [1]
    assert [run['id'] for run in seen] == [filed['id']]
    data = read_json(path)
    assert data['active'] is None
    assert data['abandoned'][-1]['id'] == filed['id']
    assert 'picker.png' in data['abandoned'][-1]['note']
    assert data['rotation'] == 1
    # The next team select (or the same one, seen twice) files nothing more.
    assert reconcile(store, page='DUNGEON_TEAM', proof=proof) is None
    # And no other page files a run.
    store.start()
    assert reconcile(store, page='MIRROR_ENTRY', proof=proof) is None
    assert read_json(path)['active'] is not None


def test_the_team_picker_receipts_a_run_that_finished_and_was_paid(tmp_path):
    # A completed run whose only missing step is the walk back to the entry. The window that
    # filed the victory can stop before it (live run-continue-20 stopped on the stage-clear
    # panel after its summary had already recorded floor 5 and the final victory), so the
    # next window sees the game's next loadout instead. Filing the return advances the
    # rotation; abandoning a finished run leaves the same team in place forever, which is
    # what the live ledger did at 2026-10-08T00:39:35Z before this existed.
    path, store = store_at(tmp_path, rotation=1)
    store.start()
    for floor in range(1, 5):
        settle(store, **MAP, floor=floor + 1, proof=frame(tmp_path, 'f%d.png' % floor))
    settle(store, page='RUN_CLAIM', proof=frame(tmp_path, 'summary.png'))
    settle(store, page='RUN_REWARD_BONUS', reason=BONUS_CONFIRM_REASON,
           proof=frame(tmp_path, 'bonus.png'))
    assert read_json(path)['active']['reward'] is False
    # An independent verified receipt is supplied by this ledger-only fixture.
    store.record(store.data['active']['id'],'receipt-fixture','reward_received',frame(tmp_path,'actual-receipt.png'))
    seen = []
    filed = reconcile(store, page='DUNGEON_TEAM', proof=frame(tmp_path, 'picker.png'),
                      on_event=seen.append)
    data = read_json(path)
    assert filed is not None and filed['how'] == 'receipt'
    assert [run['id'] for run in seen] == [filed['id']]
    assert data['active'] is None
    assert data['receipts'][-1]['id'] == filed['id']
    assert data['receipts'][-1]['settled_at']
    assert data['rotation'] == 2, 'the finished run moves the rotation on'
    assert not data.get('abandoned')
    # Seen again (or on a later window) it files nothing more.
    assert reconcile(store, page='DUNGEON_TEAM', proof=frame(tmp_path, 'picker2.png')) is None


def test_only_a_run_that_earned_its_payout_may_spend_a_weekly_bonus(tmp_path):
    # The claim can ask a second question -- "Spend your 'Weekly Bonuses, to claim the
    # bonus rewards?" (live evidence/runtime/window-20261007-171228/frame-0003.json), the
    # frame a run the weekly reset expired is left with. Only three bonuses exist per
    # week and they reset rather than carry over, so the answer comes from the ledger:
    # the newest settled record decides.
    path, store = store_at(tmp_path, rotation=1)
    assert earned_its_payout(store) is False
    # A window that settled the run itself need not consult the ledger at all.
    assert earned_its_payout(store, settled_now=True) is True
    # The run the game expired keeps its bonus even though a receipt exists from before.
    store.start()
    for floor in range(1, 4):
        settle(store, **MAP, floor=floor + 1, proof=frame(tmp_path, 'e%d.png' % floor))
    expire(store, page='EXPIRED_SESSION', reason=EXPIRED_CONFIRM_REASON,
           proof=frame(tmp_path, 'expired.png'))
    assert earned_its_payout(store) is False
    # A receipt written before it carried settled_at cannot be compared with a run that
    # was filed later: live config/user-run-ledger.json was in exactly that state, and
    # spending there (the old fallback) spent one of three bonuses on rewards the run
    # never earned. Not knowing keeps the bonus.
    stale = read_json(path)
    for entry in stale['receipts']:
        entry.pop('settled_at', None)
    path.write_text(json.dumps(stale), encoding='utf-8')
    assert earned_its_payout(RunStore(path, [SimpleNamespace(slot=s) for s in ORDER])) is False
    # A run that reaches its receipt afterwards spends one.
    store.start()
    for floor in range(1, 5):
        settle(store, **MAP, floor=floor + 1, proof=frame(tmp_path, 'f%d.png' % floor))
    proof = frame(tmp_path, 'summary.png')
    settle(store, page='RUN_CLAIM', proof=proof)
    # The claim's question is this run's own payout: its five floors and its final victory
    # are in the ledger already, even though nothing has filed the run yet. Live
    # run-continue-20 was left in exactly that state -- the window that settled the victory
    # stopped, and the next window has only the active run to read.
    assert earned_its_payout(store) is True
    settle(store, page='RUN_CLAIM', proof=proof)
    assert settle(store, page='RUN_REWARD_CONFIRM', reason=REWARD_CONFIRM_REASON, proof=proof)==[]
    assert not store.data['active']['reward']
    store.record(store.data['active']['id'],'receipt-fixture','reward_received',frame(tmp_path,'paid-receipt.png'))
    settle(store, page='DUNGEON_TEAM', reason=ENTRY_CONFIRM_REASON, proof=proof)
    assert read_json(path)['receipts'], 'the finished run should have left a receipt'
    assert earned_its_payout(store) is True
    # A run that is given up after that receipt leaves the bonus on the table again.
    store.start()
    settle(store, **MAP, floor=2, proof=frame(tmp_path, 'g1.png'))
    expire(store, page='EXPIRED_SESSION', reason=EXPIRED_CONFIRM_REASON,
           proof=frame(tmp_path, 'expired2.png'))
    assert earned_its_payout(store) is False
