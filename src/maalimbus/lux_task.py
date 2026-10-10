"""Bounded Luxcavation menu navigation; never a farming completion claim."""
from pathlib import Path
import time
import hashlib
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
        for _ in range(2):
            record=runner.observe(observer,deadline)
            if state.get('pending'):
                if state.get('expected_successor')!='DRIVE' or record.get('scene')!='DRIVE':
                    raise ValueError('Unresolved Lux navigation intent; do not repeat input')
                before=Path(state['before'])
                if (hashlib.sha256(before.read_bytes()).hexdigest()!=state.get('before_json_sha256')
                        or hashlib.sha256(before.with_suffix('.png').read_bytes()).hexdigest()!=state.get('before_png_sha256')):
                    raise ValueError('Previous Lux input frame binding differs')
                target(record)  # A scene label alone does not reconcile the intent.
                successor_frame=runner.frame_file(directory)
                state.update(pending=False,successor_proof=str(successor_frame),
                    successor_json_sha256=hashlib.sha256(successor_frame.read_bytes()).hexdigest())
                write_json(path,state)
            box,successor=target(record)
            if state and not state.get('pending') and record.get('scene')!='DRIVE':
                raise ValueError('Lux navigation moved away from its verified successor')
            report=directory/('lux-menu-'+record['scene'].lower()+'-input.json')
            def preflight(fresh):
                nonlocal state
                actual,expected=target(fresh)
                if actual!=box or expected!=successor:raise ValueError('Fresh Lux menu changed')
                frame=runner.frame_file(directory)
                png_hash=hashlib.sha256(frame.with_suffix('.png').read_bytes()).hexdigest()
                if png_hash!=fresh.get('image_sha256'):
                    raise ValueError('Fresh Lux frame hash differs')
                next_state=dict(task=task,team=build.slot,pending=True,expected_successor=successor,
                    before=str(frame),before_json_sha256=hashlib.sha256(frame.read_bytes()).hexdigest(),
                    before_png_sha256=png_hash,input_report=str(report),prior=state)
                write_json(path,next_state)
                state=next_state
                return actual
            class Tracked:
                def click(self,x,y):
                    nonlocal sent
                    sent=True
                    return device.click(x,y)
            entry=runner.one_shot_click(Tracked(),observer,box,label='lux_menu_'+task,
                journal=journal,deadline=deadline,rounds=3,interval=1,preflight=preflight)
            write_json(report,dict(task=task,team=build.slot,clicks_sent=1,steps=[entry]))
            if successor=='DRIVE' and entry['settled'].get('scene')=='DRIVE':
                target(entry['settled'])
                continue  # The next fresh read and preflight still have to prove Drive.
            return dict(passed=False,reason='lux_navigation_successor_requires_verification',
                        task=task,input_sent=sent,observation=entry['settled'],verified_clear=False)
        return dict(passed=False,reason='lux_navigation_input_bound_reached',task=task,
                    input_sent=sent,verified_clear=False)
    except (ValueError,KeyError,OSError,RuntimeError) as error:
        journal.record('lux_navigation_stopped',task=task,error=str(error),input_sent=sent)
        return dict(passed=False,reason=str(error),task=task,input_sent=sent,verified_clear=False)
