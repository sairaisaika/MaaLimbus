"""Retained highlighted Hard mode: Maa OCR fallback and negative proof cases."""
import argparse
import json
import os
import time
from pathlib import Path
import cv2
from verify_star_replay import ROOT, Replay, Library, Resource, Tasker, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task, write_json
from recognition import DifficultyProof
from maalimbus.storage import read_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',required=True)
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(args.frame);assert original is not None;results=[]
    for case in ('real','changed_covers','missing_mode','missing_header','missing_refresh'):
        frame=original.copy();directory=ROOT/f'evidence/runtime/difficulty-proof-replay-{time.time_ns()}-{case}'
        journal=Journal(directory);data=directory/'private-config';os.environ['MAALIMBUS_DATA_PATH']=str(data)
        if case=='changed_covers':frame[370:640,515:1420]=0
        if case=='missing_mode':frame[28:111,1242:1489]=0
        if case=='missing_header':frame[145:211,750:1180]=0
        if case=='missing_refresh':frame[34:99,1510:1745]=0
        write_json(data/'difficulty-switch-progress.json',read_json(ROOT/'config/difficulty-switch-progress.json'))
        rec=LimbusRecognition('en',journal);resource=Resource();controller=Replay(frame)
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_difficulty_proof',DifficultyProof(rec))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        result=wait_task(tasker,tasker.post_task('DifficultyProof'),deadline=time.monotonic()+8)
        assert not controller.clicks
        events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
        observations=[e for e in events if e['event']=='difficulty_switch_observation']
        assert bool(observations and observations[-1]['verified'])==(case in ('real','changed_covers')),(case,events)
        results.append(dict(case=case,observations=observations,device_input=False,stop_confirmed=result['stop_confirmed']))
    write_json(ROOT/'build/difficulty-proof-replay-verification.json',dict(passed=True,cases=results))
    print(json.dumps(results))


if __name__=='__main__':main()
