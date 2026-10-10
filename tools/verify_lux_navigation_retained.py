"""Retained Lux menu plans and current Mirror exclusion; no controller/input."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.lux_task import target,execute,prepare
from maalimbus.storage import read_json,write_json
from maalimbus.storage import ProfileStore
config=ROOT/'config';names=['user-run-ledger.json','user-mirror-settings.json','user-reward-claim-transaction.json','user-team-profiles.json']
names+=['user-task-settings.json','user-lux-task-transaction.json']
hashes={n:hashlib.sha256((config/n).read_bytes()).hexdigest() if (config/n).exists() else None for n in names}
frames=[]
for number in ('0001','0002'):
 p=ROOT/f'evidence/runtime/window-20261008-190502/frame-{number}.json';record=read_json(p)
 digest=hashlib.sha256(p.with_suffix('.png').read_bytes()).hexdigest();assert digest==record['image_sha256']
 box,successor=target(record);frames.append(dict(frame=str(p),png_sha256=digest,target=box,expected_successor=successor))
build=ProfileStore(config/'user-team-profiles.json').load()[0]
blocked=[]
preparation_blocked=[]
for task in ('experience','thread'):
 for choice in (None,2):
  try:prepare(config,task,choice)
  except ValueError as error:
   assert str(error)=='active_mirror_run_blocks_lux_navigation'
   preparation_blocked.append(dict(task=task,choice=choice,reason=str(error),input_sent=False))
  else:raise AssertionError('Current unpaid run did not block Lux preparation')
 result=execute(config,ROOT/'build',SimpleNamespace(),SimpleNamespace(),SimpleNamespace(),task,build)
 assert result['reason']=='active_mirror_run_blocks_lux_navigation' and not result['input_sent'];blocked.append(result)
assert all((hashlib.sha256((config/n).read_bytes()).hexdigest() if (config/n).exists() else None)==hashes[n] for n in names)
write_json(ROOT/'build/lux-navigation-retained-verification.json',dict(passed=True,retained_frames=frames,current_run_exclusion=blocked,
 preparation_exclusion=preparation_blocked,private_hashes=hashes,private_hashes_unchanged=True,device_controller=False,input_sent=False,lux_stage_selection_verified=False,lux_farming_verified=False,
 source_sha256=hashlib.sha256((ROOT/'src/maalimbus/lux_task.py').read_bytes()).hexdigest()))
print('Two retained menu frames and current Mirror exclusion verified with zero inputs.')
