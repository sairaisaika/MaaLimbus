from copy import deepcopy
from types import SimpleNamespace
import pytest
from maalimbus.storage import RunStore, write_json


def idle(tmp_path, slots=(5,4,1,6,2,7,3), cursor=5):
    store=RunStore(tmp_path/'user-run-ledger.json',[SimpleNamespace(slot=s) for s in slots])
    store.data['rotation']=cursor
    store.data['receipts']=[dict(team=4, floors=[1,2,3,4,5], victory=True, reward=True)]
    store.data['completed_runs']=1
    write_json(store.path,store.data)
    return store


def test_manual_skip_moves_team7_to_team3_without_inventing_completion(tmp_path):
    store=idle(tmp_path);before=deepcopy(store.data)
    result=store.skip_current('a'*32,expected_rotation=5)
    assert result['previous_team']==7 and result['next_team']==3
    assert store.data['receipts']==before['receipts'] and store.data['completed_runs']==1
    assert store.data['active'] is None and result['counts_as_completion'] is False
    saved=store.path.read_bytes()
    assert store.skip_current('a'*32,expected_rotation=5)['repeated'] is True
    assert store.path.read_bytes()==saved


@pytest.mark.parametrize('case',['active','stale','invalid','single'])
def test_skip_refusals_preserve_exact_ledger_bytes(tmp_path,case):
    store=idle(tmp_path,slots=(7,) if case=='single' else (1,2,7),cursor=0)
    if case=='active':store.start()
    saved=store.path.read_bytes()
    with pytest.raises(ValueError):
        store.skip_current('bad' if case=='invalid' else 'b'*32,
                           expected_rotation=2 if case=='stale' else 0)
    assert store.path.read_bytes()==saved


def test_abandon_keeps_queue_and_skip_wraps_only_on_explicit_request(tmp_path):
    store=idle(tmp_path,slots=(1,2),cursor=1)
    scope=store.start();store.data['active'].update(floors=[1,2,3,4,5],victory=True)
    write_json(store.path,store.data)
    store.abandon(note='user ended run; payout not independently recorded')
    assert store.team_slot==2 and store.data['abandoned'][-1]['victory'] is True
    assert store.data['abandoned'][-1]['id']==scope
    store.skip_current('c'*32,expected_rotation=1)
    assert store.team_slot==1 and store.data['completed_runs']==1


def test_launcher_routes_skip_without_update_launch_or_real_state(tmp_path,monkeypatch,capsys):
    import importlib.util
    import sys
    from pathlib import Path
    from maalimbus.storage import ProfileStore
    from maalimbus.policies import Team
    from maalimbus.task_preferences import TaskPreferences
    from maalimbus.runtime_paths import ROOT
    store=idle(tmp_path,slots=(1,2),cursor=0)
    ProfileStore(tmp_path/'user-team-profiles.json').save([Team(1,frozenset({'Burn'})),Team(2,frozenset({'Tremor'}))])
    preferences=TaskPreferences(tmp_path)
    preferences.save(dict(version=1,mirror=dict(difficulty='hard',team_mode='rotation',teams=[1,2]),
                          luxcavation=dict(experience_team=1,thread_team=2)))
    settings=preferences.path.read_bytes()
    spec=importlib.util.spec_from_file_location('test_rotation_launcher',ROOT/'tools/launch_app.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Lease:
        def __init__(self,path):pass
        def close(self):pass
    monkeypatch.setenv('MAALIMBUS_DATA_PATH',str(tmp_path))
    monkeypatch.setattr(module,'ControllerLease',Lease)
    monkeypatch.setattr(module,'startup_update',lambda *a,**k:pytest.fail('skip must not update'))
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**k:pytest.fail('skip must not launch'))
    monkeypatch.setattr(sys,'argv',['launcher','--app',str(tmp_path),'--rotation-status'])
    module.main()
    import json
    assert json.loads(capsys.readouterr().out)['team']==1
    monkeypatch.setattr(sys,'argv',['launcher','--app',str(tmp_path),'--skip-team','d'*32,'--expected-rotation','0'])
    module.main()
    assert json.loads(capsys.readouterr().out)['next_team']==2
    assert preferences.path.read_bytes()==settings
    assert RunStore(store.path,[SimpleNamespace(slot=1),SimpleNamespace(slot=2)]).data['completed_runs']==1
    saved=store.path.read_bytes()
    monkeypatch.setattr(sys,'argv',['launcher','--app',str(tmp_path),'--skip-team','','--expected-rotation','1'])
    with pytest.raises(ValueError,match='Invalid manual skip request'):
        module.main()
    assert store.path.read_bytes()==saved
