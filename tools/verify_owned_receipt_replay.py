"""Actual Maa read-only acknowledgement proof on retained gift-search Owned tiles."""
import argparse
import json
import os
import time
from pathlib import Path
import cv2
from verify_star_replay import ROOT, Replay, Library, Resource, Tasker, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task, write_json
from recognition import InitialReceiptProof
from maalimbus.storage import read_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',required=True)
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(args.frame);assert original is not None
    results=[]
    for case in ('real','changed_background','missing_owned','missing_icon','wrong_proof'):
        frame=original.copy();directory=ROOT/f'evidence/runtime/owned-receipt-replay-{time.time_ns()}-{case}'
        journal=Journal(directory);data=directory/'private-config';os.environ['MAALIMBUS_DATA_PATH']=str(data)
        if case=='changed_background':frame[110:230,300:1100]=0
        if case=='missing_owned':frame[694:732,148:240]=0;frame[692:732,397:485]=0
        if case=='missing_icon':frame[730:824,132:272]=0
        progress=read_json(ROOT/'config/initial-gift-progress.json')
        if case=='wrong_proof':
            source=Path(progress['proof']);copy=directory/'bad-source.png';copy.write_bytes(source.read_bytes())
            metadata=read_json(source.with_suffix('.json'));metadata['image_sha256']='00'
            write_json(copy.with_suffix('.json'),metadata);progress['proof']=str(copy)
        write_json(data/'initial-gift-progress.json',progress)
        rec=LimbusRecognition('en',journal);resource=Resource();controller=Replay(frame)
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_initial_receipt_proof',InitialReceiptProof(rec))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        result=wait_task(tasker,tasker.post_task('InitialReceiptProof'),deadline=time.monotonic()+8)
        assert not controller.clicks
        events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
        observations=[e for e in events if e['event']=='initial_receipt_ack_observation']
        assert bool(observations and observations[-1]['verified'])==(case in ('real','changed_background')),(case,events)
        results.append(dict(case=case,observations=observations,device_input=False,stop_confirmed=result['stop_confirmed']))
    write_json(ROOT/'build/owned-receipt-replay-verification.json',dict(passed=True,cases=results))
    print(json.dumps(results))


if __name__=='__main__':main()
