"""Native OCR on a supplied screenshot; reconcile isolated copies, never live state."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
from types import SimpleNamespace
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
from maalimbus.storage import RunStore,read_json,write_json
from maalimbus.task_preferences import TaskPreferences
from maalimbus.run_wiring import reconcile_idle_entry


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--png',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'dist/MaaLimbus/maafw')
    parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    output=ROOT/'build'/('mirror-idle-native-'+uuid.uuid4().hex)
    output.mkdir(parents=True)
    names=('user-run-ledger.json','user-team-profiles.json','user-task-settings.json','user-mirror-settings.json',
           'user-reward-claim-transaction.json')
    protected={n:sha(args.config/n) for n in names if (args.config/n).is_file()}
    Library.open(args.binary,agent_server=False);Toolkit.init_option(output/'debug')
    image=cv2.imread(str(args.png));assert image is not None
    journal=Journal(output/'evidence');recognition=LimbusRecognition('en',journal)
    resource=Resource();resource.register_custom_recognition('limbus_scene',recognition)
    resource.register_custom_action('limbus_map_observe',MapObservation(recognition))
    for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/'assets/resource'/layer),timeout=30)
    controller=Replay(image);wait_job(controller.post_connection(),timeout=5)
    tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
    wait_task(tasker,tasker.post_task('MapObserve',{'MapObserve':dict(next=[],on_error=[],post_delay=0)}),
              deadline=time.monotonic()+30)
    assert not controller.input_attempts and recognition.callback_failure is None
    frames=sorted(journal.directory.glob('frame-*.json'));assert frames
    proof=frames[-1];record=read_json(proof);cases=[]
    for mode,queue in [('single',[2]),('rotation',[1,2,3,4,5])]:
        config=output/mode;config.mkdir()
        for name in names:
            if (args.config/name).is_file():shutil.copyfile(args.config/name,config/name)
        value=read_json(config/'user-run-ledger.json')
        store=RunStore(config/'user-run-ledger.json',[SimpleNamespace(slot=s) for s in value['team_slots']])
        old_completed=value['completed_runs'];old_receipts=value['receipts']
        outcome=reconcile_idle_entry(store,proof)
        TaskPreferences(config).set_mirror_queue(mode,queue)
        updated=read_json(store.path)
        assert updated['team_slots']==queue and updated['active'] is None
        assert updated['completed_runs']==old_completed and updated['receipts']==old_receipts
        cases.append(dict(mode=mode,queue=queue,next_team=queue[updated['rotation']],
                          retired=outcome['retired'],completion_unchanged=True,receipts_unchanged=True))
    unchanged=protected=={n:sha(args.config/n) for n in protected}
    assert unchanged
    report=dict(passed=True,scene=record['scene'],frame=str(proof),png_sha256=record['image_sha256'],
                json_sha256=sha(proof),cases=cases,private_hashes_unchanged=unchanged,
                device_controller=False,game_input=False,scope='Native OCR + isolated state only; not GUI Start or gameplay')
    write_json(ROOT/'build/mirror-idle-entry-native-verification.json',report)
    print(json.dumps(dict(passed=True,scene=record['scene'],cases=cases,private_hashes_unchanged=unchanged,
                         game_input=False)))


if __name__=='__main__':main()
