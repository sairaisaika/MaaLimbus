import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'agent'))
import recognition
from maalimbus.storage import ProfileStore,read_json
from maalimbus.policies import Team
from maalimbus.task_preferences import TaskPreferences


@pytest.fixture(autouse=True)
def isolate_fake_dispatch_controller_lease(tmp_path,monkeypatch):
    # These fake-controller unit tests must not compete with a real live runner.
    # Production lock identity/exclusion is covered in test_controller_lease.py.
    import maalimbus.controller_lease as leases
    monkeypatch.setattr(leases,'lease_path',lambda path:tmp_path/'unit-dispatch.lock')


def test_six_main_tasks_reference_saved_builds_and_no_diagnostic_entry():
    pi=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    assert [t['name'] for t in pi['task']]==['open_game','mirror_loop','experience','thread','rewards','stamina']
    assert all(not t['default_check'] for t in pi['task'])
    nodes=json.loads((ROOT/'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
    assert all(nodes[t['entry']]['custom_action']=='limbus_main_task' for t in pi['task'])
    assert 'grace_budget' not in nodes['MirrorLoop']['custom_action_param']


def test_lux_default_edits_preserve_active_mirror_scope(tmp_path):
    ProfileStore(tmp_path/'user-team-profiles.json').save([Team(2,frozenset({'Charge'})),Team(7,frozenset({'Poise'}))])
    ledger=dict(team_slots=[2,7],rotation=1,active={'id':'actual-run','team':7})
    path=tmp_path/'user-run-ledger.json';path.write_text(json.dumps(ledger))
    p=TaskPreferences(tmp_path);p.set_lux_defaults(experience_team=7,thread_team=2)
    assert p.build_for('experience').slot==7 and p.build_for('thread').slot==2
    assert read_json(path)==ledger
    before=p.path.read_bytes()
    with pytest.raises(ValueError):p.set_lux_defaults(thread_team=19)
    assert p.path.read_bytes()==before


def test_unimplemented_task_captures_evidence_and_returns_failure_without_input(tmp_path,monkeypatch):
    monkeypatch.setattr(recognition.InputPreflight,'run',lambda *args:True)
    monkeypatch.setattr(recognition.runner,'observe',lambda *args:dict(scene='STAR_GRACES',frame='actual-frame',input_sent=False))
    action=recognition.MainTaskAction(SimpleNamespace(callback_failure=None,journal=None))
    context=SimpleNamespace(tasker=SimpleNamespace(controller=SimpleNamespace()))
    args=SimpleNamespace(custom_action_param=json.dumps(dict(task='stamina',directory=str(tmp_path))),node_name='StaminaTask')
    assert not action.run(context,args)
    result=read_json(tmp_path/'agent-result.json')
    assert result['reason']=='task_page_policy_not_implemented' and not result['input_sent']
    assert not result['verified_clear'] and result['observation']['scene']=='STAR_GRACES'


def test_mirror_dispatch_reads_parsed_native_action_and_preserves_params(tmp_path,monkeypatch):
    monkeypatch.setattr(recognition.InputPreflight,'run',lambda *args:True)
    monkeypatch.setattr(recognition.GlobalSettingsAction,'run',lambda *args:True)
    seen=[]
    def run(self,context,args):
        seen.append(json.loads(args.custom_action_param));return True
    monkeypatch.setattr(recognition.MirrorLoopAction,'run',run)
    def node(name):
        if name=='MirrorPreferenceEdit':return dict(attach=dict(enabled=False))
        if name=='MirrorStarSource':return dict(attach=dict(source='saved'))
        if name=='MirrorTeamStarEdit':return dict(attach=dict(edit=False))
        if name=='MirrorInitialKeyword':return dict(attach=dict(keyword='poise'))
        if name=='MirrorGiftSearch':return dict(attach=dict(mode='refuse'))
        if name=='MirrorRunBounds':return dict(attach=dict(steps='saved'))
        if name=='MirrorBattleAssignment':return dict(attach=dict(mode='damage'))
        return dict(action=dict(type='Custom',param=dict(custom_action_param=dict(steps=120,run_store='config/user-run-ledger.json',stop_page='STAR_GRACES'))))
    context=SimpleNamespace(get_node_data=node)
    action=recognition.MainTaskAction(SimpleNamespace(callback_failure=None,journal=None))
    args=SimpleNamespace(custom_action_param=json.dumps(dict(task='mirror',directory=str(tmp_path))),node_name='MirrorTask')
    assert action.run(context,args)
    assert seen==[dict(steps=120,run_store='config/user-run-ledger.json',stop_page='STAR_GRACES',
                       gift_keyword='poise',gift_search='refuse',battle_assignment='damage')]


def test_windows_open_task_requires_actual_existing_game_and_does_not_launch(tmp_path,monkeypatch):
    checked=[]
    def check(*args):checked.append(True);return True
    monkeypatch.setattr(recognition.InputPreflight,'run',check)
    context=SimpleNamespace(tasker=SimpleNamespace(controller=SimpleNamespace(info={'type':'win32'})))
    action=recognition.MainTaskAction(SimpleNamespace(callback_failure=None,journal=None))
    args=SimpleNamespace(custom_action_param=json.dumps(dict(task='open_game',directory=str(tmp_path))),node_name='OpenGameTask')
    assert action.run(context,args) and checked
    assert read_json(tmp_path/'agent-result.json')==dict(passed=True,reason='existing_windows_game_verified',input_sent=False)


def test_reward_entry_dispatches_bounded_executor_and_preserves_failure(tmp_path,monkeypatch):
    import maalimbus.reward_task as task
    monkeypatch.setattr(recognition.InputPreflight,'run',lambda *args:True)
    device=object();seen=[]
    monkeypatch.setattr(recognition.runner,'local_device',lambda *a,**k:device)
    def execute(config,directory,observer,received,journal):
        assert received is device
        seen.append(directory)
        return dict(passed=False,reason='Current claim scope/budget is not authorized',input_sent=False)
    monkeypatch.setattr(task,'execute',execute)
    context=SimpleNamespace(tasker=SimpleNamespace(controller=SimpleNamespace()),
                            get_node_data=lambda name:dict(attach=dict(maximum='saved')))
    action=recognition.MainTaskAction(SimpleNamespace(callback_failure=None,journal=None))
    args=SimpleNamespace(custom_action_param=json.dumps(dict(task='rewards',directory=str(tmp_path))),node_name='RewardsTask')
    assert not action.run(context,args) and seen==[tmp_path]
    assert not read_json(tmp_path/'agent-result.json')['input_sent']
