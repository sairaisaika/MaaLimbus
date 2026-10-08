import pytest
from maalimbus.task_preferences import TaskPreferences
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore,SINNERS,write_json,read_json


def setup(tmp_path):
    profiles=ProfileStore(tmp_path/'user-team-profiles.json')
    profiles.save([Team(n,frozenset({'Charge','Tremor'}),deployment=SINNERS) for n in range(1,6)])
    preferences=TaskPreferences(tmp_path)
    value=dict(version=1,mirror=dict(difficulty='hard',team_mode='rotation',teams=[5,4,1,2,3]),
               luxcavation=dict(experience_team=2,thread_team=2))
    return preferences,profiles,value


def test_five_team_cycle_and_luxcavations_reference_global_builds(tmp_path):
    preferences,profiles,value=setup(tmp_path)
    preferences.save(value)
    assert [preferences.build_for('mirror',n).slot for n in range(7)]==[5,4,1,2,3,5,4]
    assert preferences.build_for('experience')==preferences.build_for('thread')==profiles.load()[1]


def test_single_team_is_reloaded_after_global_order_and_system_edit(tmp_path):
    preferences,profiles,value=setup(tmp_path)
    value['mirror'].update(team_mode='single',teams=[2])
    preferences.save(value)
    changed=Team(2,frozenset({'Bleed'}),deployment=tuple(reversed(SINNERS)))
    profiles.save([p if p.slot!=2 else changed for p in profiles.load()])
    assert preferences.build_for('mirror',99)==preferences.build_for('thread')==changed


@pytest.mark.parametrize('change',[dict(teams=[1,1]),dict(teams=[21]),dict(teams=[]),
    dict(team_mode='single',teams=[1,2]),dict(difficulty='unknown')])
def test_invalid_task_references_preserve_saved_settings(tmp_path,change):
    preferences,profiles,value=setup(tmp_path)
    preferences.save(value)
    original=preferences.path.read_bytes()
    value['mirror'].update(change)
    with pytest.raises(ValueError):preferences.save(value)
    assert preferences.path.read_bytes()==original


def test_idle_queue_change_retains_receipts_and_next_team(tmp_path):
    preferences,profiles,value=setup(tmp_path)
    path=tmp_path/'user-run-ledger.json'
    receipt={'id':'real-completed-run','team':2,'reward_received':True}
    write_json(path,dict(version=1,team_slots=[5,4,1,2,3],rotation=3,
                        completed_runs=1,active=None,receipts=[receipt]))
    preferences.set_mirror_queue('rotation',[1,2,3])
    actual=read_json(path)
    assert actual['rotation']==1 and actual['team_slots']==[1,2,3]
    assert actual['receipts']==[receipt] and actual['completed_runs']==1
    assert actual['queue_changes'][0]['previous']==[5,4,1,2,3]


def test_active_run_rejects_new_queue_without_changing_either_file(tmp_path):
    preferences,profiles,value=setup(tmp_path)
    preferences.save(value)
    path=tmp_path/'user-run-ledger.json'
    write_json(path,dict(version=1,team_slots=value['mirror']['teams'],rotation=0,
                        active={'id':'active','team':5},receipts=[]))
    original=(path.read_bytes(),preferences.path.read_bytes())
    with pytest.raises(ValueError,match='active run'):
        preferences.set_mirror_queue('single',[2])
    assert original==(path.read_bytes(),preferences.path.read_bytes())
