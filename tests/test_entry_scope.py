from types import SimpleNamespace
import pytest
from maalimbus.storage import RunStore,read_json
from maalimbus.run_wiring import reconcile


def fixture(tmp_path):
    store=RunStore(tmp_path/'ledger.json',[SimpleNamespace(slot=7)])
    proof=tmp_path/'frame.json';proof.write_text('actual frame fixture')
    return store,proof


def test_multiple_loadout_windows_preserve_preparing_scope(tmp_path):
    store,proof=fixture(tmp_path);scope=store.start()
    for _ in range(3):
        assert reconcile(store,page='DUNGEON_TEAM',proof=proof) is None
        store=RunStore(store.path,[SimpleNamespace(slot=7)])
        assert store.start()==scope
    assert not store.data.get('abandoned')


def test_confirmation_is_durable_and_cannot_be_repeated_or_discarded(tmp_path):
    store,proof=fixture(tmp_path);scope=store.start()
    store.entry_intent(scope,7,proof)
    store=RunStore(store.path,[SimpleNamespace(slot=7)])
    with pytest.raises(ValueError):store.entry_intent(scope,7,proof)
    with pytest.raises(ValueError):reconcile(store,page='DUNGEON_TEAM',proof=proof)
    assert store.data['active']['id']==scope and store.data['active']['phase']=='entry_pending'


@pytest.mark.parametrize('page',['DUNGEON_TEAM','UNKNOWN','LEVEL_WARNING'])
def test_unproven_entry_successor_never_completes_intent(tmp_path,page):
    store,proof=fixture(tmp_path);scope=store.start();store.entry_intent(scope,7,proof)
    with pytest.raises(ValueError):store.entry_observed(scope,page,proof)
    assert store.data['active']['phase']=='entry_pending'


def test_entry_successor_does_not_credit_clear_reward_or_rotation(tmp_path):
    store,proof=fixture(tmp_path);scope=store.start();store.entry_intent(scope,7,proof)
    store.entry_observed(scope,'STAR_GRACES',proof)
    active=read_json(store.path)['active']
    assert active['phase']=='entered' and active['id']==scope
    assert active['floors']==[] and not active['victory'] and not active['reward']
    assert store.data['rotation']==0 and store.data['completed_runs']==0


def test_level_warning_is_a_separate_once_only_confirmation(tmp_path):
    store,proof=fixture(tmp_path);scope=store.start();store.entry_intent(scope,7,proof)
    store.entry_warning_intent(scope,proof)
    with pytest.raises(ValueError):store.entry_warning_intent(scope,proof)
    assert store.data['active']['phase']=='entry_pending'
    store.entry_observed(scope,'STAR_GRACES',proof)
    assert store.data['active']['entry']['warning_sent'] is True
