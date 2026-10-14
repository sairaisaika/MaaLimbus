import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from maalimbus.storage import RunStore, ProfileStore, SINNERS, read_json, write_json
from maalimbus.policies import Team
from maalimbus.run_wiring import reconcile_idle_entry


def frame(folder, *, page='MIRROR_ENTRY', before='Before Entry', score=.99):
    folder.mkdir(parents=True,exist_ok=True)
    p=folder/'frame-0001.json';png=p.with_suffix('.png')
    cv2.imwrite(str(png),np.zeros((1080,1920,3),dtype=np.uint8))
    record=dict(scene=page,size=[1920,1080],image_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),
        ocr=[dict(text=before,box=[1530,220,175,30],score=score),
             dict(text='Enter',box=[1610,755,115,40],score=.99)])
    write_json(p,record);return p


def old_run(config):
    config.mkdir(parents=True,exist_ok=True)
    slots=[5,4,1,6,2,7,3]
    ProfileStore(config/'user-team-profiles.json').save([Team(n,frozenset({'Charge','Tremor'}),deployment=SINNERS) for n in slots])
    store=RunStore(config/'user-run-ledger.json',[SimpleNamespace(slot=s) for s in slots])
    store.data['rotation']=5;scope=store.start()
    store.data['active']['phase']='entered'
    write_json(store.path,store.data);return store,scope


def test_independent_idle_entry_retires_old_scope_without_inventing_payout(tmp_path):
    store,scope=old_run(tmp_path/'config');proof=frame(tmp_path/'evidence')
    result=reconcile_idle_entry(store,proof)
    assert result['retired'] and store.data['active'] is None
    assert store.data['rotation']==5 and store.data['completed_runs']==0
    archived=store.data['abandoned'][-1]
    assert archived['id']==scope and not archived['victory'] and not archived['reward']
    assert archived['ended_entry_proof']['outcome_inferred'] is False
    saved=store.path.read_bytes();assert not reconcile_idle_entry(store,proof)['retired']
    assert store.path.read_bytes()==saved


@pytest.mark.parametrize('fault',['ongoing','reward_overlay','low','entry_pending','paid_pending','hash'])
def test_uncertain_or_pending_old_run_is_never_erased(tmp_path,fault):
    store,scope=old_run(tmp_path/'config')
    proof=frame(tmp_path/'evidence',before='Exploring Floor 3' if fault=='ongoing' else 'Before Entry',
                page='RUN_REWARD_DIALOG' if fault=='reward_overlay' else 'MIRROR_ENTRY',
                score=.8 if fault=='low' else .99)
    if fault=='entry_pending':store.data['active']['phase']='entry_pending';write_json(store.path,store.data)
    if fault=='paid_pending':write_json(store.path.parent/'user-reward-claim-transaction.json',dict(scope=scope,pending='receipt',completed=False))
    if fault=='hash':proof.with_suffix('.png').write_bytes(b'changed')
    before=store.path.read_bytes()
    try:result=reconcile_idle_entry(store,proof);assert not result['retired']
    except ValueError:pass
    assert store.path.read_bytes()==before


@pytest.mark.parametrize('mode,queue',[('single',[2]),('rotation',[1,2,3,4,5])])
def test_gui_start_prepares_old_run_before_applying_both_real_option_shapes(tmp_path,monkeypatch,mode,queue):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agent'))
    import recognition
    import maalimbus.controller_lease as leases
    monkeypatch.setattr(leases,'lease_path',lambda p:tmp_path/'unit-start.lock')
    config=tmp_path/'config';store,scope=old_run(config);evidence=tmp_path/'evidence'
    monkeypatch.setenv('MAALIMBUS_DATA_PATH',str(config))
    proof=frame(evidence)
    monkeypatch.setattr(recognition,'data_directory',lambda *a:config)
    monkeypatch.setattr(recognition.InputPreflight,'run',lambda *a:True)
    monkeypatch.setattr(recognition.runner,'observe',lambda *a:read_json(proof))
    # Exercise the real GlobalSettingsAction.apply and actual option collectors.
    def node(name):
        if name.startswith('Global_global_team_'):return dict(attach=dict(global_build=dict(edit=False)))
        if name=='MirrorTaskTeamMode':return dict(attach=dict(team_mode=mode))
        if name=='MirrorTaskSingleTeam':return dict(attach=dict(slot=2))
        if name=='MirrorTaskQueueCount':return dict(attach=dict(count=len(queue)))
        if name.startswith('MirrorTaskQueue'):return dict(attach=dict(slot=queue[int(name[len('MirrorTaskQueue'):])-1]))
        if name=='MirrorPreferenceEdit':return dict(attach=dict(enabled=False))
        if name=='MirrorStarSource':return dict(attach=dict(source='saved'))
        if name=='MirrorTeamStarEdit':return dict(attach=dict(edit=False))
        if name=='MirrorInitialKeyword':return dict(attach=dict(keyword='saved'))
        if name=='MirrorGiftSearch':return dict(attach=dict(mode='saved'))
        if name=='MirrorRunBounds':return dict(attach=dict(steps='saved'))
        if name=='MirrorRunCount':return dict(attach=dict(run_count='saved'))
        if name=='MirrorBattleAssignment':return dict(attach=dict(mode='saved'))
        for n,f in [('MirrorShopPolicy','shop_policy'),('MirrorShopRefreshLimit','shop_refreshes'),('MirrorShopCoinReserve','shop_reserve_coins')]:
            if name==n:return dict(attach={f:'saved'})
        if name=='MirrorLoop':return dict(action=dict(param=dict(custom_action_param=dict(steps=120,run_store='config/user-run-ledger.json'))))
        raise KeyError(name)
    seen=[]
    def loop(self,context,argv):
        parameters=json.loads(argv.custom_action_param)
        settings,_=recognition.loop_parameters(parameters)
        current,run=recognition.loop_store(settings,self.recognition.journal)
        seen.append((current.data['team_slots'],current.team_slot,run));return True
    monkeypatch.setattr(recognition.MirrorLoopAction,'run',loop)
    owner=SimpleNamespace(callback_failure=None,journal=None)
    context=SimpleNamespace(get_node_data=node,tasker=SimpleNamespace(controller=SimpleNamespace()))
    args=SimpleNamespace(custom_action_param=json.dumps(dict(task='mirror',directory=str(evidence))),node_name='MirrorTask')
    assert recognition.MainTaskAction(owner).run(context,args)
    assert seen[0][0]==queue and seen[0][1]==queue[0] and seen[0][2]!=scope
    assert read_json(store.path)['completed_runs']==0 and owner.callback_failure is None


def test_settings_refusal_has_result_human_log_and_no_callback_poison(tmp_path,monkeypatch):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agent'))
    import recognition
    import maalimbus.controller_lease as leases
    monkeypatch.setattr(leases,'lease_path',lambda p:tmp_path/'unit-start.lock')
    monkeypatch.setattr(recognition,'data_directory',lambda *a:tmp_path/'config')
    monkeypatch.setattr(recognition.InputPreflight,'run',lambda *a:True)
    def refuse(*a):raise ValueError('Finish the active run before changing its rotation')
    monkeypatch.setattr(recognition.GlobalSettingsAction,'apply',refuse)
    owner=SimpleNamespace(callback_failure=None,journal=None)
    args=SimpleNamespace(custom_action_param=json.dumps(dict(task='mirror',directory=str(tmp_path/'evidence'))),node_name='MirrorTask')
    assert not recognition.MainTaskAction(owner).run(SimpleNamespace(),args)
    result=read_json(tmp_path/'evidence/agent-result.json')
    assert result['reason']=='mirror_settings_rejected' and result['clicks_sent']==0
    assert 'active run' in result['error'] and owner.callback_failure is None
    assert (tmp_path/'evidence/run.log').exists()


def test_native_journal_continuation_never_overwrites_retained_proof(tmp_path):
    import recognition
    journal=recognition.Journal(tmp_path)
    image=np.zeros((1080,1920,3),dtype=np.uint8)
    journal.frame(image,[],'MIRROR_ENTRY')
    before=(tmp_path/'frame-0001.json').read_bytes()
    resumed=recognition.Journal(tmp_path)
    assert resumed.frame(image,[],'DUNGEON_TEAM')=='frame-0002'
    assert (tmp_path/'frame-0001.json').read_bytes()==before


def test_existing_clear_is_preserved_without_adding_reward_or_advancing_rotation(tmp_path):
    store,scope=old_run(tmp_path/'config')
    store.data['active'].update(floors=[1,2,3,4,5],victory=True,reward=False)
    write_json(store.path,store.data)
    reconcile_idle_entry(store,frame(tmp_path/'evidence'))
    row=store.data['abandoned'][-1]
    assert row['id']==scope and row['victory'] and not row['reward']
    assert row['floors']==[1,2,3,4,5] and store.data['rotation']==5
