"""Actual Maa saved-team graph: retained library plus clearly marked derived title.

No game controller is constructed; derived title cases test transitions and OCR,
not an actual change of identities or a live dungeon team.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import cv2
import numpy as np
from maa.controller import CustomController
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'agent')]
from recognition import Journal,LimbusRecognition,LimbusTerminal,TeamAction


class Replay(CustomController):
    def __init__(self,frame,after=None):
        super().__init__(); self.frame=frame; self.after=after
        self.clicks=[]; self.swipes=[]
    def connect(self): return True
    def request_uuid(self): return 'team-replay-no-device'
    def get_features(self): return 0
    def screencap(self): return self.frame.copy()
    def click(self,x,y):
        h,w=self.frame.shape[:2]
        assert .04*w<x<.19*w and .28*h<y<.80*h, 'Never touch edit/delete controls'
        self.clicks.append([x,y])
        if self.after is not None: self.frame=self.after
        return True
    def swipe(self,x1,y1,x2,y2,duration):
        h,w=self.frame.shape[:2]
        assert .08*w<x1<.13*w and .08*w<x2<.13*w
        assert 420<=duration<=620
        self.swipes.append([x1,y1,x2,y2,duration]); return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--frame',type=Path,required=True)
    args=parser.parse_args(); Library.open(args.binary,agent_server=False)
    Toolkit.init_option(ROOT/'build/team-replay-debug')
    source=cv2.imread(str(args.frame)); h,w=source.shape[:2]
    source[int(.81*h):]=0
    derived=source.copy()
    derived[int(.116*h):int(.16*h),int(.16*w):int(.33*w)]=(50,40,30)
    cv2.putText(derived,'TEAMS #2',(round(.175*w),round(.148*h)),cv2.FONT_HERSHEY_SIMPLEX,
                1.05,(240,230,220),2,cv2.LINE_AA)
    paid=source.copy()
    cv2.rectangle(paid,(int(.3*w),int(.34*h)),(int(.73*w),int(.5*h)),(10,10,10),-1)
    cv2.putText(paid,'Refill Enkephalin',(int(.34*w),int(.43*h)),cv2.FONT_HERSHEY_SIMPLEX,
                1.3,(255,255,255),2,cv2.LINE_AA)
    results=[]
    cases=[('already_selected',source,None,1,0,0,True),
           ('derived_switch',source,derived,2,1,0,True),
           ('stuck_selection',source,None,2,3,0,False),
           ('missing_slot',source,None,20,0,1,False),
           ('resource_dialog',paid,None,2,0,0,False),
           ('unknown',np.zeros_like(source),None,1,0,0,False)]
    for name,frame,after,slot,clicks,swipes,expected in cases:
        directory=ROOT/f'evidence/runtime/team-replay-{name}'
        # New directory per invocation keeps event assertions independent.
        directory=directory/str(time.time_ns())
        os.environ['MAALIMBUS_DATA_PATH']=str(directory/'private-config')
        journal=Journal(directory); recognize=LimbusRecognition('en',journal)
        controller=Replay(frame.copy(),after); resource=Resource()
        resource.register_custom_recognition('limbus_scene',recognize)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(recognize))
        resource.register_custom_action('limbus_team',TeamAction(recognize))
        assert resource.post_bundle(ROOT/'assets/resource/base').wait().succeeded
        assert resource.post_bundle(ROOT/'assets/resource/en').wait().succeeded
        assert controller.post_connection().wait().succeeded
        tasker=Tasker(); assert tasker.bind(resource=resource,controller=controller)
        overrides={n:{'timeout':1800,'post_delay':60} for n in
                   ('TeamLibraryConfigure','TeamLibraryName','TeamLibraryRow','TeamLibraryScroll','TeamLibraryVerified')}
        overrides['TeamLibraryStart']={'action':'DoNothing'} # No OS input in saved-frame replay.
        overrides['TeamLibraryConfigure']['custom_action_param']={'mode':'configure','slot':slot,'name':''}
        job=tasker.post_task('TeamLibraryStart',overrides)
        deadline=time.monotonic()+20
        while not job.done and time.monotonic()<deadline: time.sleep(.1)
        if not job.done:
            tasker.post_stop().wait(); raise AssertionError('Bounded team replay timed out')
        events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
        selected=[e for e in events if e['event']=='team_selected']
        assert bool(selected)==expected,(name,events)
        assert len(controller.clicks)==clicks,(name,controller.clicks)
        assert len(controller.swipes)==swipes,(name,controller.swipes)
        assert job.succeeded==expected,(name,job.succeeded)
        results.append(dict(case=name,selected=bool(selected),clicks=controller.clicks,
                            swipes=controller.swipes,derived=name=='derived_switch'))
    result={'passed':True,'device_controller':False,'cases':results,
            'scope':'Saved-team library selection only. Title change is derived; no live team/deployment claim.'}
    (ROOT/'build/team-replay-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
