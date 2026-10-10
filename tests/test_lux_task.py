from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
import pytest
from maalimbus.lux_task import target,execute
from maalimbus.storage import read_json,write_json
ROOT=Path(__file__).resolve().parents[1]


def retained(number):
    p=ROOT/f'evidence/runtime/window-20261008-190502/frame-{number}.json'
    if not p.exists():pytest.skip('Private native frame absent')
    return read_json(p)


def test_actual_retained_home_and_drive_controls():
    assert target(retained('0001'))==([1438,968,68,28],'DRIVE')
    assert target(retained('0002'))==([590,270,166,25],None)


@pytest.mark.parametrize('fault',['missing','low','duplicate','wrong_scene'])
def test_lux_menu_control_negative(fault):
    record=deepcopy(retained('0002'))
    token=next(x for x in record['ocr'] if x['text']=='Luxcavation')
    if fault=='missing':record['ocr'].remove(token)
    if fault=='low':token['score']=.8
    if fault=='duplicate':record['ocr'].append(deepcopy(token))
    if fault=='wrong_scene':record['scene']='UNKNOWN'
    with pytest.raises(ValueError):target(record)


def test_active_mirror_blocks_before_observation_and_input(tmp_path):
    write_json(tmp_path/'user-run-ledger.json',dict(active={'id':'unpaid-mirror'}))
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),SimpleNamespace(),'experience',SimpleNamespace(slot=7))
    assert not result['input_sent'] and result['reason']=='active_mirror_run_blocks_lux_navigation'


def test_unresolved_lux_intent_is_not_repeated(tmp_path,monkeypatch):
    import maalimbus.lux_task as task
    write_json(tmp_path/'user-lux-task-transaction.json',dict(task='thread',team=2,pending=True,expected_successor=None))
    monkeypatch.setattr(task.runner,'observe',lambda *a:retained('0002'))
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),SimpleNamespace(record=lambda *a,**k:None),'thread',SimpleNamespace(slot=2))
    assert not result['input_sent'] and 'Unresolved' in result['reason']


def test_intent_is_durable_before_device_attempt(tmp_path,monkeypatch):
    import maalimbus.lux_task as task
    record=retained('0001')
    monkeypatch.setattr(task.runner,'observe',lambda *a:record)
    monkeypatch.setattr(task.runner,'frame_file',lambda *a:ROOT/'evidence/runtime/window-20261008-190502/frame-0001.json')
    attempts=[]
    def click(*args):
        tx=read_json(tmp_path/'user-lux-task-transaction.json')
        assert tx['pending'] and tx['task']=='experience' and tx['team']==7
        attempts.append(args)
        raise RuntimeError('injected device interruption')
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(click=click),SimpleNamespace(record=lambda *a,**k:None),'experience',SimpleNamespace(slot=7))
    assert result['input_sent'] and not result['passed'] and len(attempts)==1


@pytest.mark.parametrize('ledger',[{},[],{'rotation':1}])
def test_malformed_ledger_blocks_navigation(tmp_path,ledger):
    write_json(tmp_path/'user-run-ledger.json',ledger)
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),SimpleNamespace(),'thread',SimpleNamespace(slot=2))
    assert not result['input_sent'] and 'Invalid Mirror' in result['reason']


def test_known_drive_successor_continues_in_same_task_and_retains_both_reports(tmp_path,monkeypatch):
    import maalimbus.lux_task as task
    pages=[retained('0001'),retained('0002'),dict(scene='UNKNOWN')]
    cursor=[0];attempts=[]
    monkeypatch.setattr(task.runner,'observe',lambda *a:pages[cursor[0]])
    monkeypatch.setattr(task.runner,'frame_file',lambda *a:ROOT/f'evidence/runtime/window-20261008-190502/frame-000{cursor[0]+1}.json')
    def one_shot(device,observer,box,**kwargs):
        current=pages[cursor[0]]
        actual=kwargs['preflight'](current)
        device.click(actual[0],actual[1])
        cursor[0]+=1
        return dict(settled=pages[cursor[0]],observation=current,passed=True)
    monkeypatch.setattr(task.runner,'one_shot_click',one_shot)
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(click=lambda *a:attempts.append(a)),
                   SimpleNamespace(record=lambda *a,**k:None),'experience',SimpleNamespace(slot=7))
    assert not result['passed'] and result['input_sent'] and len(attempts)==2
    state=read_json(tmp_path/'user-lux-task-transaction.json')
    assert state['pending'] and state['expected_successor'] is None
    assert not state['prior']['pending'] and state['prior']['expected_successor']=='DRIVE'
    for scene in ('home','drive'):
        assert read_json(tmp_path/f'lux-menu-{scene}-input.json')['clicks_sent']==1
    assert len(state['before_png_sha256'])==64 and len(state['prior']['before_png_sha256'])==64


def test_changed_pending_input_proof_does_not_reconcile_or_click(tmp_path,monkeypatch):
    import maalimbus.lux_task as task
    path=tmp_path/'user-lux-task-transaction.json'
    write_json(path,dict(task='thread',team=2,pending=True,expected_successor='DRIVE',
        before=str(ROOT/'evidence/runtime/window-20261008-190502/frame-0001.json'),
        before_json_sha256='changed',before_png_sha256='changed'))
    before=path.read_bytes()
    monkeypatch.setattr(task.runner,'observe',lambda *a:retained('0002'))
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),
                   SimpleNamespace(record=lambda *a,**k:None),'thread',SimpleNamespace(slot=2))
    assert not result['input_sent'] and 'binding differs' in result['reason']
    assert path.read_bytes()==before


@pytest.mark.parametrize('fault',['changed','missing'])
def test_successor_png_failure_preserves_pending_bytes(tmp_path,monkeypatch,fault):
    import hashlib
    import maalimbus.lux_task as task
    original=ROOT/'evidence/runtime/window-20261008-190502/frame-0001.json'
    successor=tmp_path/'frame-0002.json'
    write_json(successor,retained('0002'))
    if fault=='changed':successor.with_suffix('.png').write_bytes(b'altered image')
    path=tmp_path/'user-lux-task-transaction.json'
    write_json(path,dict(task='thread',team=2,pending=True,expected_successor='DRIVE',
        before=str(original),before_json_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
        before_png_sha256=hashlib.sha256(original.with_suffix('.png').read_bytes()).hexdigest()))
    before=path.read_bytes()
    monkeypatch.setattr(task.runner,'observe',lambda *a:retained('0002'))
    monkeypatch.setattr(task.runner,'frame_file',lambda *a:successor)
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),
        SimpleNamespace(record=lambda *a,**k:None),'thread',SimpleNamespace(slot=2))
    assert not result['input_sent'] and not result['passed']
    assert path.read_bytes()==before


@pytest.mark.parametrize('value',['{broken', '[]', 'null'])
def test_invalid_lux_transaction_stops_before_observation(tmp_path,value):
    path=tmp_path/'user-lux-task-transaction.json'
    path.write_text(value,encoding='utf-8')
    before=path.read_bytes()
    result=execute(tmp_path,tmp_path,SimpleNamespace(),SimpleNamespace(),
        SimpleNamespace(record=lambda *a,**k:None),'thread',SimpleNamespace(slot=2))
    assert not result['input_sent'] and not result['passed']
    assert path.read_bytes()==before
