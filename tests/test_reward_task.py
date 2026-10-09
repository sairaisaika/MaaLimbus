from pathlib import Path
from types import SimpleNamespace

from maalimbus.reward_task import execute, action_for
from maalimbus.storage import write_json,read_json


class Observer:
    def __init__(self,record,directory):self.record=record;self.directory=directory
    def observe(self,**kwargs):return self.record


def test_unapproved_current_scope_sends_no_input_and_preserves_old_transaction(tmp_path,monkeypatch):
    import maalimbus.reward_task as task
    config=tmp_path/'config';directory=tmp_path/'frames'
    directory.mkdir()
    active=dict(id='current',floors=[1,2,3,4,5],victory=True,reward=False)
    write_json(config/'user-run-ledger.json',dict(active=active))
    write_json(config/'user-mirror-settings.json',dict(reward_budget_scope='old',
        module_budget_pending=False,max_reward_modules=6))
    tx=config/'user-reward-claim-transaction.json'
    write_json(tx,dict(scope='old',completed=True,pending=None))
    before=tx.read_bytes()
    frame=directory/'frame-0001.json'
    record=dict(scene='RUN_REWARD_DIALOG',size=[1920,1080],ocr=[],
                reward_cost=dict(currency='enkephalin_modules',cost=5,weekly=0))
    write_json(frame,record)
    monkeypatch.setattr(task.runner,'frame_file',lambda p:frame)
    clicks=[]
    result=execute(config,directory,Observer(record,directory),SimpleNamespace(click=lambda *p:clicks.append(p)),
                   SimpleNamespace(record=lambda *a,**k:None))
    assert not result['passed'] and not result['input_sent'] and not clicks
    assert 'not authorized' in result['reason']
    assert tx.read_bytes()==before
    assert read_json(config/'user-run-ledger.json')['active']==active


def test_incomplete_run_refuses_before_observation_or_input(tmp_path):
    write_json(tmp_path/'user-run-ledger.json',dict(active=dict(id='run',floors=[1],victory=False)))
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),SimpleNamespace())
    assert result['reason']=='completed_mirror_run_required'
    assert not result['input_sent']


def test_caption_dispatch_is_not_payout():
    record=dict(scene='UNKNOWN',size=[1920,1080],ocr=[dict(text='Rewards Acquired',
        box=[800,340,260,40],score=.99)])
    assert action_for(record)=='receipt'
    record['ocr'][0]['score']=.8
    assert action_for(record) is None


def retained_bookkeeping(tmp_path):
    import pytest
    from copy import deepcopy
    root=Path(__file__).resolve().parents[1]
    home=root/'evidence/runtime/window-20261008-172705/frame-0001.json'
    source=root/'config/user-reward-claim-transaction.json'
    if not home.exists() or not source.exists():pytest.skip('Private retained evidence absent')
    tx=read_json(source)
    if tx.get('scope')!='d7c1499436f647208adc50860692a5c2':pytest.skip('Private scope advanced')
    scope=tx['scope'];tx=deepcopy(tx);tx['completed']=False
    names={'claim':'final-reward-authorized-claim-live','confirm':'final-reward-authorized-confirm-live',
           'receipt':'final-reward-receipt-ack-live','pass':'final-pass-receipt-ack-live'}
    tx['task_input_reports']={k:str(root/f'build/{v}-20261008.json') for k,v in names.items()}
    ledger=read_json(root/'config/user-run-ledger.json')
    archived=[r for r in ledger['receipts'] if r['id']==scope][0]
    ledger['active']=deepcopy(archived);ledger['active']['reward']=False
    ledger['active']['events']={}
    ledger['receipts']=[];ledger['completed_runs']=0
    write_json(tmp_path/'user-run-ledger.json',ledger)
    write_json(tmp_path/'user-team-profiles.json',read_json(root/'config/user-team-profiles.json'))
    write_json(tmp_path/'user-reward-claim-transaction.json',tx)
    return scope,home


def test_actual_retained_chain_completes_isolated_task_bookkeeping(tmp_path):
    from maalimbus.reward_task import finish
    scope,home=retained_bookkeeping(tmp_path)
    result=finish(tmp_path,scope,home)
    assert result['passed'] and result['reward_received'] and not result['mail_daily_verified']
    ledger=read_json(tmp_path/'user-run-ledger.json')
    assert ledger['active'] is None and ledger['completed_runs']==1
    assert read_json(tmp_path/'user-reward-claim-transaction.json')['completed']


def test_post_rotation_transaction_write_failure_recovers_without_second_rotation(tmp_path,monkeypatch):
    import pytest
    import maalimbus.reward_task as task
    scope,home=retained_bookkeeping(tmp_path)
    original=task.write_json
    def fail_completion(path,data):
        if Path(path).name=='user-reward-claim-transaction.json' and data.get('completed'):
            raise OSError('injected final write failure')
        return original(path,data)
    monkeypatch.setattr(task,'write_json',fail_completion)
    with pytest.raises(OSError):task.finish(tmp_path,scope,home)
    before=(tmp_path/'user-run-ledger.json').read_bytes()
    monkeypatch.setattr(task,'write_json',original)
    result=task.execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),SimpleNamespace())
    assert result['passed'] and not result['input_sent']
    assert (tmp_path/'user-run-ledger.json').read_bytes()==before


def test_input_failure_retains_attempt_and_does_not_retry(tmp_path,monkeypatch):
    import maalimbus.reward_task as task
    write_json(tmp_path/'user-run-ledger.json',dict(active=dict(id='run',victory=True,floors=[1,2,3,4,5])))
    monkeypatch.setattr(task.runner,'observe',lambda *a:dict(scene='RUN_REWARD_DIALOG'))
    def one_shot(device,*a,**k):device.click(1,1)
    monkeypatch.setattr(task.runner,'one_shot_click',one_shot)
    attempts=[]
    def click(*args):
        attempts.append(args)
        raise RuntimeError('device interrupted after intent')
    result=task.execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(click=click),
                        SimpleNamespace(record=lambda *a,**k:None))
    assert not result['passed'] and result['input_sent'] and len(attempts)==1


def test_missing_ledger_stops_without_observing_or_starting_run(tmp_path):
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),SimpleNamespace())
    assert not result['passed'] and not result['input_sent']
    assert not (tmp_path/'user-run-ledger.json').exists()
