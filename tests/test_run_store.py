"""The persisted rotation ledger: seeding, one active run, and the exact advance.

The window hands RunStore the frame every event was read from, so these cases keep a
real file on disk and check the stored order: floors only in sequence, one victory,
one reward, one entry back, and then -- only then -- the rotation moves.
"""
from types import SimpleNamespace

import pytest

from maalimbus.storage import RunStore, read_json, seed_run_store

ORDER = (5, 4, 1, 6, 2, 7, 3)


def teams(slots=ORDER):
    return [SimpleNamespace(slot=slot) for slot in slots]


def proof(tmp_path, name):
    path = tmp_path/name
    path.write_bytes(('frame ' + name).encode())
    return path


def test_a_seeded_ledger_names_the_team_the_next_run_brings(tmp_path):
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER, rotation=1)
    value = read_json(path)
    assert value['team_slots'] == list(ORDER)
    assert value['rotation'] == 1
    assert value['active'] is None and value['receipts'] == []
    assert RunStore(path, teams()).team_slot == 4


def test_seeding_never_overwrites_a_ledger_without_the_force(tmp_path):
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER)
    with pytest.raises(ValueError):
        seed_run_store(path, ORDER, rotation=1)


def test_force_reseeds_only_a_ledger_that_recorded_nothing(tmp_path):
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER)
    # The case this exists for: a run finished outside the harness and the player's
    # order moved on while our ledger still pointed at the retired team.
    seed_run_store(path, ORDER, rotation=1, overwrite=True)
    assert read_json(path)['rotation'] == 1

    store = RunStore(path, teams())
    run = store.start()
    for floor in range(1, 6):
        store.record(run, 'floor_clear-%d' % floor, 'floor_clear',
                     proof(tmp_path, 'f%d.png' % floor), floor=floor)
    store.record(run, 'final_victory', 'final_victory', proof(tmp_path, 'win.png'))
    store.record(run, 'reward_received', 'reward_received', proof(tmp_path, 'reward.png'))
    store.record(run, 'entry_returned', 'entry_returned', proof(tmp_path, 'entry.png'))
    value = read_json(path)
    assert value['rotation'] == 2 and value['completed_runs'] == 1
    assert value['active'] is None and len(value['receipts']) == 1
    with pytest.raises(ValueError):
        seed_run_store(path, ORDER, rotation=0, overwrite=True)


def test_starting_a_second_window_continues_the_same_active_run(tmp_path):
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER)
    first = RunStore(path, teams())
    run = first.start()
    second = RunStore(path, teams())
    assert second.start() == run


def test_the_store_refuses_a_floor_out_of_sequence_and_a_foreign_run(tmp_path):
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER)
    store = RunStore(path, teams())
    run = store.start()
    with pytest.raises(ValueError):
        store.record(run, 'floor_clear-5', 'floor_clear', proof(tmp_path, 'a.png'), floor=5)
    with pytest.raises(ValueError):
        store.record('someone-else', 'floor_clear-1', 'floor_clear',
                     proof(tmp_path, 'b.png'), floor=1)
    with pytest.raises(ValueError):
        store.record(run, 'reward_received', 'reward_received', proof(tmp_path, 'c.png'))
    assert read_json(path)['active']['floors'] == []


def test_a_repeated_event_with_the_same_frame_is_not_recorded_twice(tmp_path):
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER)
    store = RunStore(path, teams())
    run = store.start()
    frame = proof(tmp_path, 'f1.png')
    assert store.record(run, 'floor_clear-1', 'floor_clear', frame, floor=1) is True
    assert store.record(run, 'floor_clear-1', 'floor_clear', frame, floor=1) is False
    assert read_json(path)['active']['floors'] == [1]


def test_giving_up_a_run_files_it_and_keeps_the_rotation_where_it_stands(tmp_path):
    """A wipe the player accepts leaves the next entry on the same team.

    The driver never taps the wipe dialog's "Accept results" row, so a run the player
    gives up on stayed active for ever and nothing could clear it -- reseeding refuses a
    ledger that already recorded a run. Abandoning has to drop `active` and leave
    `rotation` pointing at the same slot, or the next entry would silently bring the
    wrong team.
    """
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER, rotation=1)
    store = RunStore(path, teams())
    run = store.start()
    store.record(run, 'floor_clear-1', 'floor_clear', proof(tmp_path, 'f1.png'), floor=1)
    dropped = store.abandon(note='wiped on the floor-5 boss')
    assert dropped['id'] == run and dropped['floors'] == [1]
    value = read_json(path)
    assert value['active'] is None
    assert value['rotation'] == 1 and RunStore(path, teams()).team_slot == 4
    assert value['completed_runs'] == 0 and value['receipts'] == []
    assert value['abandoned'][-1]['floors'] == [1]
    assert value['abandoned'][-1]['note'] == 'wiped on the floor-5 boss'
    with pytest.raises(ValueError):
        RunStore(path, teams()).abandon()
    # The next window starts a fresh run on the same slot instead of resuming the dead one.
    second = RunStore(path, teams())
    assert second.start() != run and second.data['active']['team'] == 4


def test_the_player_can_aim_the_next_entry_at_a_named_team(tmp_path):
    """The rotation is a queue; the player sometimes names a team instead.

    "Test team 2 now" cannot be said through the rotation, which only moves after a run
    is receipted, and reseeding refuses a ledger that already holds a run. Pointing has
    to move `rotation` alone: the receipts and the abandoned runs are the record of what
    actually happened and may never be rewritten by a preference.
    """
    path = tmp_path/'ledger.json'
    seed_run_store(path, ORDER, rotation=1)
    store = RunStore(path, teams())
    run = store.start()
    with pytest.raises(ValueError):
        store.point_at(2)  # an open run pins the slot the window will click
    store.record(run, 'floor_clear-1', 'floor_clear', proof(tmp_path, 'f1.png'), floor=1)
    store.abandon(note='the player asked for team 2')
    before = read_json(path)
    assert store.point_at(2) == 4
    value = read_json(path)
    assert value['rotation'] == 4 and RunStore(path, teams()).team_slot == 2
    assert value['receipts'] == before['receipts']
    assert value['abandoned'] == before['abandoned']
    assert value['completed_runs'] == before['completed_runs']
    assert store.start() and store.data['active']['team'] == 2
    with pytest.raises(ValueError):
        store.point_at(9)  # a slot that is not in the rotation is a typo, not a choice
