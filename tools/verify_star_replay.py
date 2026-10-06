"""Actual Maa star grid/OCR and transactional proof; all touch input intercepted."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'agent')]
from maa.controller import CustomController
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from recognition import Journal,LimbusRecognition,LimbusTerminal,StarProof
from maalimbus.jobs import wait_job,wait_task
from maalimbus.storage import write_json,read_json


class Replay(CustomController):
    def __init__(self,frame,after=None):
        super().__init__();self.frame=frame;self.after=after;self.clicks=[]
    def connect(self):return True
    def request_uuid(self):return 'star-offline'
    def get_features(self):return 0
    def screencap(self):return self.frame.copy()
    def click(self,x,y):
        assert 555<x<733 and 281<y<336, 'Only ordinal1 card body; never +/++'
        self.clicks.append([x,y])
        if self.after is not None:self.frame=self.after.copy()
        return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',type=Path,required=True)
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(str(args.frame));assert original is not None
    derived=original.copy();derived[45:85,1515:1569]=(10,10,10)
    cv2.putText(derived,'97',(1520,77),cv2.FONT_HERSHEY_SIMPLEX,.9,(230,220,200),2,cv2.LINE_AA)
    results=[]
    for name in ('source_unconfirmed','derived_balance','changed_buffs','missing_grid','over_budget','pending_input'):
        frame=original.copy()
        if name=='changed_buffs':
            for i in range(10):
                x,y=207+298*(i%5),226+356*(i//5)
                frame[y+45:y+290,x+12:x+265]=(25,70,20)
        if name=='missing_grid':frame[220:570,200:490]=0
        directory=ROOT/f'evidence/runtime/star-replay-{time.time_ns()}-{name}'
        journal=Journal(directory);data=directory/'private-config'
        os.environ['MAALIMBUS_DATA_PATH']=str(data)
        write_json(data/'user-mirror-settings.json',dict(graces=['1','3','4','6'],enhance=False,
            max_starlight=95 if name=='over_budget' else 100))
        if name=='pending_input':write_json(data/'star-selection-progress.json',dict(selected=[],pending={'unknown':True}))
        recognition=LimbusRecognition('en',journal);resource=Resource()
        controller=Replay(frame,derived if name=='derived_balance' else None)
        resource.register_custom_recognition('limbus_scene',recognition)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(recognition))
        resource.register_custom_action('limbus_star_proof',StarProof(recognition))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        result=wait_task(tasker,tasker.post_task('StarStep',{'StarStep':{'timeout':1000,'post_delay':50}}),
                         deadline=time.monotonic()+10)
        expected=1 if name in ('source_unconfirmed','derived_balance','changed_buffs') else 0
        assert len(controller.clicks)==expected,(name,controller.clicks)
        events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
        proofs=[e for e in events if e['event']=='star_selection_observation']
        assert bool(proofs and proofs[-1]['verified'])==(name=='derived_balance'),(name,events)
        if expected:
            intent=next(e for e in events if e['event']=='star_selection_intent')
            assert intent['all_costs']=={'1':10,'3':20,'4':30,'6':40}
            assert intent['available_before']==107 and not intent['enhance']
        results.append(dict(case=name,clicks=controller.clicks,proof=proofs,device_input=False,
            derived=name=='derived_balance',stop_confirmed=result['stop_confirmed']))
    write_json(ROOT/'build/star-replay-verification.json',dict(passed=True,cases=results,
        scope='retained/changed-buff/negative Maa replay; balance transition is derived, not resource spend proof'))
    print(json.dumps(results))


if __name__=='__main__':main()
