"""Native OCR on a supplied screenshot; reconcile isolated copies, never live state."""
import pathlib as _pathlib
import sys as _sys
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / 'src'))
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
    parser.add_argument('--apply',action='store_true',help='retire the ended scope on the live store (never settles a purchase)')
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
    extra={}
    if args.apply:
        # Retire the ended scope on the live store. The proof must be this screenshot and
        # the store must still hold an active scope; the grace transaction is hashed before
        # and after to prove this path never settles a pending purchase (that is
        # verify_grace_balance_recovery.py --apply).
        assert args.config.resolve()==(ROOT/'config').resolve(),args.config
        ledger=args.config/'user-run-ledger.json'
        grace=args.config/'user-grace-transaction.json'
        grace_sha=sha(grace) if grace.is_file() else None
        live=read_json(ledger);assert live['active'] is not None,'nothing to retire'
        shutil.copyfile(ledger,output/'ledger-before-apply.json')
        real=RunStore(ledger,[SimpleNamespace(slot=s) for s in live['team_slots']])
        outcome=reconcile_idle_entry(real,proof)
        after=read_json(ledger)
        assert after['active'] is None,after['active']
        assert len(after['abandoned'])==len(live['abandoned'])+1
        assert after['completed_runs']==live['completed_runs'] and len(after['receipts'])==len(live['receipts'])
        assert grace_sha is None or sha(grace)==grace_sha
        extra=dict(applied=True,retired_scope=live['active']['id'],retired_outcome=outcome,
                   abandoned=len(after['abandoned']),ledger_sha256_after=sha(ledger),grace_hash_unchanged=True)
    report=dict(passed=True,scene=record['scene'],frame=str(proof),png_sha256=record['image_sha256'],
                json_sha256=sha(proof),cases=cases,private_hashes_unchanged=unchanged,
                device_controller=False,game_input=False,
                scope='Native OCR + isolated state only; not GUI Start or gameplay',**extra)
    write_json(ROOT/'build/mirror-idle-entry-native-verification.json',report)
    print(json.dumps(dict(passed=True,scene=record['scene'],cases=cases,private_hashes_unchanged=unchanged,
                         game_input=False)))


if __name__=='__main__':main()
