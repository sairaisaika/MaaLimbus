import json
import pytest
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore, RunStore, team_from_json


def teams():
    return [Team(1,frozenset({'Bleed'}),deployment=('Yi Sang','Faust')),
            Team(8,frozenset({'Burn','Tremor'}),name='BURN-TREMOR')]


def test_profiles_persist_rotation_order_keywords_and_deployment(tmp_path):
    store=ProfileStore(tmp_path/'private.json')
    assert store.save(teams())==tuple(teams())
    assert ProfileStore(store.path).load()==tuple(teams())
    with pytest.raises(ValueError): store.save([teams()[0],teams()[0]])
    assert store.load()==tuple(teams())


@pytest.mark.parametrize('value',[
    {'slot':True},{'slot':'1'},{'slot':0},{'slot':21},
    {'slot':1,'keywords':['MadeUp']}, {'slot':1,'deployment':['Faust','Faust']},
    {'slot':1,'deployment':['Unknown']}, {'slot':1,'name':'a'*81},
])
def test_invalid_team_configuration_rejected(value):
    with pytest.raises(ValueError): team_from_json(value)


def test_run_resume_and_rotation_need_ordered_proof(tmp_path):
    path,proof=tmp_path/'run.json',tmp_path/'observation.json'
    proof.write_text('{}')
    store=RunStore(path,teams())
    run=store.start()
    with pytest.raises(ValueError): store.record(run,'wrong','floor_clear',proof,floor=5)
    with pytest.raises(ValueError): store.record(run,'wrong','reward_received',proof)
    for floor in range(1,4):
        assert store.record(run,f'floor-{floor}','floor_clear',proof,floor=floor)
    resumed=RunStore(path,teams())
    assert resumed.start()==run and resumed.team_slot==1
    assert not resumed.record(run,'floor-3','floor_clear',proof,floor=3)
    assert resumed.data['active']['floors']==[1,2,3]
    with pytest.raises(ValueError): resumed.record(run,'done','entry_returned',proof)
    for floor in (4,5): resumed.record(run,f'floor-{floor}','floor_clear',proof,floor=floor)
    resumed.record(run,'victory','final_victory',proof)
    resumed.record(run,'reward','reward_received',proof)
    assert RunStore(path,teams()).team_slot==1
    resumed.record(run,'entry','entry_returned',proof)
    assert resumed.team_slot==8 and resumed.data['completed_runs']==1
    with pytest.raises(ValueError): resumed.record(run,'entry','entry_returned',proof)
    assert RunStore(path,teams()).data['completed_runs']==1
    with pytest.raises(ValueError): RunStore(path,list(reversed(teams())))


def test_missing_proof_and_failed_write_do_not_advance_memory_or_disk(tmp_path,monkeypatch):
    from maalimbus import storage
    store=RunStore(tmp_path/'run.json',teams()); run=store.start()
    with pytest.raises(FileNotFoundError): store.record(run,'missing','floor_clear',tmp_path/'missing',floor=1)
    proof=tmp_path/'frame.json'; proof.write_text('{}')
    previous=store.path.read_bytes()
    def fail(*args): raise OSError('Disk unavailable')
    monkeypatch.setattr(storage.os,'replace',fail)
    with pytest.raises(OSError): store.record(run,'floor','floor_clear',proof,floor=1)
    assert store.data['active']['floors']==[] and store.path.read_bytes()==previous
    assert not list(tmp_path.glob('*.tmp'))
