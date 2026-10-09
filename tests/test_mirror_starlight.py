import json
from pathlib import Path
import pytest
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore,write_json
from maalimbus.mirror_starlight import apply,resolve,affordable,collect
from maalimbus.grace_transaction import GraceTransaction


def profiles(directory):
    p=ProfileStore(directory/'user-team-profiles.json')
    p.save([Team(2,frozenset({'Charge','Tremor'}),graces=('1','3','4','6'),grace_budget=100,
                 allow=frozenset({'Portable Battery Socket'})),
            Team(7,frozenset({'Poise'}),graces=('0','9'),grace_budget=60)])
    return p


def test_team_rules_follow_actual_rotation_and_lix_zero_based_positions(tmp_path):
    profiles(tmp_path)
    apply(tmp_path,'team',dict(choices=[],budget=0))
    assert resolve(tmp_path,2)['graces']=='2,4,5,7'
    assert resolve(tmp_path,2)['grace_budget']==100
    assert resolve(tmp_path,7)['graces']=='1,10'
    assert resolve(tmp_path,7)['grace_budget']==60


def test_task_override_and_auto_use_explicit_budget_caps(tmp_path):
    profiles(tmp_path)
    apply(tmp_path,'task',dict(choices=[2,5],budget=35))
    assert resolve(tmp_path,2)['graces']=='3,6'
    apply(tmp_path,'auto',dict(choices=[8],budget=80))
    a=resolve(tmp_path,7)
    assert a['grace_auto'] and a['graces']=='1,10' and a['grace_budget']==60


def test_build_edit_changes_only_star_fields_and_saved_source_is_inert(tmp_path):
    p=profiles(tmp_path);old=p.load()
    apply(tmp_path,'saved',None,dict(slot=2,choices=[0,6],budget=50))
    new=p.load()
    assert new[0].graces==('0','6') and new[0].grace_budget==50
    assert new[0].keywords==old[0].keywords and new[0].allow==old[0].allow
    assert new[1]==old[1]
    assert resolve(tmp_path,2) is None


@pytest.mark.parametrize('fault',['duplicate','active','budget','unknown','enhance'])
def test_invalid_edits_or_enhanced_imports_do_not_authorize_input(tmp_path,fault):
    p=profiles(tmp_path);before=p.path.read_bytes()
    edit=dict(slot=2,choices=[1,3],budget=100)
    if fault=='duplicate':edit['choices']=[1,1]
    if fault=='active':write_json(tmp_path/'user-run-ledger.json',dict(active=dict(team=2)))
    if fault=='budget':edit['budget']=-1
    if fault=='unknown':edit['slot']=19
    if fault=='enhance':
        p.save([Team(2,frozenset({'Charge'}),graces=('1+',),grace_budget=100)])
        apply(tmp_path,'team',dict(choices=[],budget=0))
        with pytest.raises(ValueError):resolve(tmp_path,2)
        return
    with pytest.raises(ValueError):apply(tmp_path,'task',dict(choices=[0],budget=30),edit)
    assert p.path.read_bytes()==before and not (tmp_path/'user-mirror-starlight.json').exists()


def test_auto_plan_freezes_visible_affordable_subset_and_survives_restart(tmp_path):
    p=tmp_path/'grace.json';t=GraceTransaction(p);t.begin('run',[1,4,10],40,'entry')
    costs=[10,0,0,20,0,0,0,0,0,60]
    assert t.seal_auto('run',[1,4,10],40,35,costs,'actual-board')==[1,4]
    t.intent(1,10,35,'before')
    with pytest.raises(ValueError):GraceTransaction(p).seal_auto('run',[1,4,10],40,35,costs,'retry')
    t.observe(25,'after')
    t=GraceTransaction(p)
    assert t.seal_auto('run',[1,4,10],40,25,costs,'new-board')==[1,4]
    assert t.validate('run',[1,4],40,25)['selected']==[1]
    costs[3]=15
    with pytest.raises(ValueError):t.seal_auto('run',[1,4,10],40,25,costs,'changed-board')
    with pytest.raises(ValueError):t.seal_auto('other',[1,4,10],40,25,None,'wrong-scope')


def test_auto_zero_budget_selects_nothing_and_missing_prices_refuse():
    assert affordable([1,4],0,200,[10,0,0,20])==[]
    with pytest.raises(ValueError):affordable([1,4],100,200,[10,0,0,0])
    with pytest.raises(ValueError):affordable([4,4],0,0,[10,0,0,20])


def test_native_options_are_mirror_children_and_independent_values():
    root=Path(__file__).resolve().parents[1]
    pi=json.loads((root/'assets/interface.json').read_text(encoding='utf8'))
    task=next(t for t in pi['task'] if t['name']=='mirror_loop')
    assert 'mirror_star_source' in task['option'] and 'mirror_star_source' not in pi['global_option']
    nodes=json.loads((root/'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf8'))
    node=lambda name:nodes[name]
    source,plan,edit=collect(node)
    assert (source,plan,edit)==('saved',None,None)
    nodes['MirrorStarSource']['attach']['source']='auto'
    nodes['MirrorTaskStarBudget']['attach']['budget']='100'
    nodes['MirrorTaskStar1']['attach']['selected']=True
    assert collect(node)[1]==dict(choices=[1],budget=100)


def test_actual_runner_resolves_active_team_before_building_purchase_state(tmp_path):
    from maalimbus.storage import RunStore
    from maalimbus.runner import MirrorRunner,FakeDevice
    p=profiles(tmp_path)
    apply(tmp_path,'team',dict(choices=[],budget=0))
    store=RunStore(tmp_path/'user-run-ledger.json',p.load())
    scope=store.start()
    device=FakeDevice([])
    actual=MirrorRunner(device,settings=dict(graces='10',grace_budget=60),store=store,
        run_id=scope,directory=tmp_path/'runtime')
    assert actual.settings.graces=='2,4,5,7' and actual.settings.grace_budget==100
    assert actual.state['grace_wanted']==[2,4,5,7]
    assert not actual.settings.grace_auto and device.clicks==[] and device.swipes==[] and device.keys==[]

