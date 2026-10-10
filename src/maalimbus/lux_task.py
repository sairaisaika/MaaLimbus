"""Bounded Luxcavation menu navigation; never a farming completion claim."""
from pathlib import Path
import time
from . import runner
from .storage import read_json,write_json
from .vision import Text,find


def target(record):
    size=record.get('size')
    if size!=[1920,1080]:raise ValueError('Lux navigation layout unknown')
    texts=[Text(x['text'],tuple(x['box']),x['score']) for x in record.get('ocr',[])]
    scene=record.get('scene')
    if scene=='HOME':
        checks=[(r'^Window$',(.60,.86,.69,.96)),(r'^Sinners$',(.66,.86,.74,.96)),
                (r'^Inventory$',(.46,.90,.55,.97))]
        if any(len(find(texts,p,b,size,.9))!=1 for p,b in checks):
            raise ValueError('Independent HOME controls missing')
        buttons=find(texts,r'^Drive$',(.73,.86,.81,.96),size,.9)
        successor='DRIVE'
    elif scene=='DRIVE':
        buttons=find(texts,r'^Luxcavation$',(.28,.23,.42,.30),size,.9)
        successor=None  # No retained Lux stage page has yet been independently verified.
    else:raise ValueError('Lux stage selection policy not implemented')
    if len(buttons)!=1:raise ValueError('Unique Lux navigation control missing')
    return list(buttons[0].box),successor


def execute(config,directory,observer,device,journal,task,build):
    config,directory=Path(config),Path(directory)
    if task not in ('experience','thread'):raise ValueError('Unknown Lux task')
    ledger=config/'user-run-ledger.json'
    try:
        if ledger.exists():
            data=read_json(ledger)
            if not isinstance(data,dict) or 'active' not in data:
                raise ValueError('Invalid Mirror run ledger blocks Lux navigation')
            if data['active'] is not None:
                return dict(passed=False,reason='active_mirror_run_blocks_lux_navigation',input_sent=False,task=task)
    except (ValueError,OSError) as error:
        return dict(passed=False,reason=str(error),input_sent=False,task=task)
    path=config/'user-lux-task-transaction.json'
    state=read_json(path) if path.exists() else {}
    sent=False;deadline=time.monotonic()+45
    try:
        if state and (state.get('task')!=task or state.get('team')!=build.slot):
            raise ValueError('Existing Lux intent belongs to another task/team')
        record=runner.observe(observer,deadline)
        if state.get('pending'):
            if state.get('expected_successor')!='DRIVE' or record.get('scene')!='DRIVE':
                raise ValueError('Unresolved Lux navigation intent; do not repeat input')
            target(record)  # A scene label alone does not reconcile the intent.
            state.update(pending=False,successor_proof=str(runner.frame_file(directory)))
            write_json(path,state)
        box,successor=target(record)
        if state and not state.get('pending') and record.get('scene')!='DRIVE':
            raise ValueError('Lux navigation moved away from its verified successor')
        def preflight(fresh):
            actual,expected=target(fresh)
            if actual!=box or expected!=successor:raise ValueError('Fresh Lux menu changed')
            next_state=dict(task=task,team=build.slot,pending=True,expected_successor=successor,
                before=str(runner.frame_file(directory)),prior=state)
            write_json(path,next_state)
            return actual
        class Tracked:
            def click(self,x,y):
                nonlocal sent
                sent=True
                return device.click(x,y)
        entry=runner.one_shot_click(Tracked(),observer,box,label='lux_menu_'+task,
            journal=journal,deadline=deadline,rounds=3,interval=1,preflight=preflight)
        write_json(directory/'lux-navigation-input.json',dict(task=task,clicks_sent=1,steps=[entry]))
        return dict(passed=False,reason='lux_navigation_successor_requires_verification',
                    task=task,input_sent=sent,observation=entry['settled'],verified_clear=False)
    except (ValueError,KeyError,OSError,RuntimeError) as error:
        journal.record('lux_navigation_stopped',task=task,error=str(error),input_sent=sent)
        return dict(passed=False,reason=str(error),task=task,input_sent=sent,verified_clear=False)
