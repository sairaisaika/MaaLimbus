"""Retained native balance readings and isolated pending-purchase recovery."""
import argparse,hashlib,json,shutil,sys,time,uuid
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'agent'),str(ROOT/'tools')]
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit
from recognition import Journal,LimbusRecognition,MapObservation
from verify_map_replay import Replay
from maalimbus.jobs import wait_job,wait_task
from maalimbus.grace_vision import available_starlight
from maalimbus.grace_transaction import GraceTransaction
from maalimbus.vision import Text
from maalimbus.storage import read_json,write_json

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--transaction',type=Path,required=True);a=p.parse_args()
 out=ROOT/'build'/('grace-native-'+uuid.uuid4().hex);out.mkdir()
 original=digest(a.transaction)
 Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False);Toolkit.init_option(out/'debug')
 journal=Journal(out/'evidence');recognition=LimbusRecognition('en',journal);recognition.data_directory=out/'private'
 resource=Resource();resource.register_custom_action('probe',MapObservation(recognition))
 for layer in ['base','en']:wait_job(resource.post_bundle(ROOT/'assets/resource'/layer),timeout=30)
 images=[(n,cv2.imread(str(a.evidence/(n+'.png'))),v) for n,v in [('frame-0009',105),('frame-0011',95),('frame-0012',75)]]
 image=images[-1][1]
 missing=image.copy();missing[40:90,1500:1600]=0;images.append(('missing-digit',missing,None))
 missing=image.copy();missing[40:90,1380:1485]=0;images.append(('missing-label',missing,None))
 controller=Replay(image);wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
 tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
 cases=[];current=None
 for name,image,expected in images:
  controller.frame=image
  wait_task(tasker,tasker.post_task('Probe',{'Probe':dict(recognition='DirectHit',action='Custom',custom_action='probe',next=[],on_error=[])}),deadline=time.monotonic()+45)
  assert recognition.callback_failure is None
  path=sorted(journal.directory.glob('frame-*.json'))[-1];record=read_json(path)
  value=available_starlight([Text(t['text'],tuple(t['box']),t['score']) for t in record['ocr']],record['size'])
  assert value==expected,(name,value,expected)
  cases.append(dict(case=name,expected=expected,actual=value,proof=str(path)))
  if name=='frame-0012':current=path
 clone=out/'transaction.json';shutil.copyfile(a.transaction,clone);tx=GraceTransaction(clone);before=read_json(clone);pending=before['pending']
 tx.recover(before['scope'],before['requested'],before['budget'],75,current)
 assert tx.data['pending'] is None and tx.data['selected']==before['selected']+[pending['card']]
 assert tx.data['spent']==before['spent']+pending['cost'] and digest(a.transaction)==original
 # Original/negative frames cannot consume the intent or alter its bytes.
 for case in cases[1:2]+cases[3:]:
  shutil.copyfile(a.transaction,clone);old=clone.read_bytes();tx=GraceTransaction(clone)
  try:tx.recover(before['scope'],before['requested'],before['budget'],case['actual'],case['proof'])
  except ValueError:pass
  else:raise AssertionError('Invalid successor accepted')
  assert clone.read_bytes()==old
 assert not controller.input_attempts
 report=dict(passed=True,cases=cases,recovered_card=pending['card'],recovery_no_input=True,private_hash_unchanged=True,device_input=0)
 write_json(ROOT/'build/grace-balance-recovery-native-verification.json',report);print(json.dumps(report))
if __name__=='__main__':main()
