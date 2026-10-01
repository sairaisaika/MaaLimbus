"""Actual Maa OCR/Pipeline drags over derived glyph/title frames, no game input."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from dataclasses import replace

import cv2
import numpy as np
from maa.controller import CustomController
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'agent')]
from recognition import Journal,LimbusRecognition,LimbusTerminal,ThemeObservation,TeamAction
from maalimbus.policies import Team
from maalimbus.theme_vision import ThemeCatalog
from maalimbus.jobs import wait_job,wait_task
from maalimbus.storage import ProfileStore


class Replay(CustomController):
    def __init__(self,frame,target):
        super().__init__();self.frame=frame;self.target=target;self.drags=[]
    def connect(self):return True
    def request_uuid(self):return 'theme-replay-no-game'
    def get_features(self):return 0
    def screencap(self):return self.frame.copy()
    def click(self,x,y):raise AssertionError('Theme routing must never click or refresh')
    def swipe(self,x1,y1,x2,y2,duration):
        assert self.target is not None,'No drag on unsafe or unidentified frame'
        left=135 if self.target=='ASEA' else 535
        assert left+65<=x1<=left+105 and 250<=y1<=275,(x1,y1)
        assert left+65<=x2<=left+105 and 650<=y2<=675,(x2,y2)
        assert 480<=duration<=680,duration
        self.drags.append([x1,y1,x2,y2,duration])
        self.frame=np.zeros_like(self.frame)
        return True


def derived_frame(cat,*,normal=False,new=False,unknown=False,paid=False,seed=7):
    image=np.random.default_rng(seed).integers(0,90,(720,1280,3),dtype=np.uint8)
    def paste(key,x,y):
        icon=cv2.cvtColor(cat.glyphs[key],cv2.COLOR_GRAY2BGR)
        image[y:y+icon.shape[0],x:x+icon.shape[1]]=icon
    paste('normal_mode' if normal else 'hard_mode',830,25);paste('pack_search',1060,40)
    for x,title in [(252,'ASEA'),(652,'Automated Factory')]:
        paste('theme_pack_detail',x,203)
        left=x-117
        cv2.rectangle(image,(left,440),(left+170,495),(15,15,15),-1)
        cv2.putText(image,'Mystery' if unknown else title,(left+7,462),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),1,cv2.LINE_AA)
    if new:paste('mirror_theme_pack_new',140,190)
    if paid:
        cv2.rectangle(image,(380,320),(920,390),(0,0,0),-1)
        cv2.putText(image,'Purchase Lunacy',(400,370),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    return image


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=Path,required=True)
    args=parser.parse_args();Library.open(args.binary,agent_server=False)
    Toolkit.init_option(ROOT/'build/theme-replay-debug');cat=ThemeCatalog(ROOT/'assets/resource/base')
    team=Team(1,frozenset(),pack_weights=(('ASEA',20),('Automated Factory',1)))
    cases=[('weighted',{},team,'ASEA'),('changed_art',dict(seed=42),team,'ASEA'),
           ('new',dict(new=True),team,'Automated Factory'),('unknown',dict(unknown=True),team,None),
           ('normal',dict(normal=True),team,None),('paid',dict(paid=True),team,None),
           ('blocked',{},Team(1,frozenset(),pack_weights=(('ASEA',0),('Automated Factory',0))),None)]
    results=[]
    for name,options,configured,target in cases:
        directory=ROOT/f'evidence/runtime/theme-replay-{name}'/str(time.time_ns())
        journal=Journal(directory);rec=LimbusRecognition('en',journal)
        store=ProfileStore(directory/'config/user-team-profiles.json')
        initial=replace(configured,pack_weights=(('ASEA',5),('Automated Factory',1))) if name=='weighted' else configured
        store.save([initial])
        controller=Replay(derived_frame(cat,**options),target);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_theme_observe',ThemeObservation(rec))
        resource.register_custom_action('limbus_team',TeamAction(rec))
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        nodes={'ThemePackStart':{'action':'DoNothing'},
            'ThemePackConfigure':{'timeout':1200},
            'ThemePackDrag':{'post_delay':50}}
        if name=='weighted':
            nodes['ThemePackPreference']={'custom_action_param':{'mode':'pack','name':'ASEA'}}
            nodes['ThemePackWeight']={'custom_action_param':{'mode':'weight','weight':20}}
        previous=os.environ.get('MAALIMBUS_DATA_PATH')
        os.environ['MAALIMBUS_DATA_PATH']=str(store.path.parent)
        try:
            result=wait_task(tasker,tasker.post_task('ThemePackStart',nodes),deadline=time.monotonic()+20)
        finally:
            if previous is None:os.environ.pop('MAALIMBUS_DATA_PATH',None)
            else:os.environ['MAALIMBUS_DATA_PATH']=previous
        assert store.load()==(configured,), (name,store.load())
        assert not result['timed_out'] and result['stop_confirmed'],(name,result)
        assert len(controller.drags)==(1 if target else 0),(name,controller.drags)
        events=[json.loads(line) for line in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        ranks=[e for e in events if e['event']=='theme_pack_ranking']
        if target:
            assert ranks[-1]['ranking'][0]['name']==target,(name,ranks)
            post=next(e for e in events if e['event']=='theme_drag_observation')
            assert post['scene']=='UNKNOWN' and not post['selected'] and not post['verified_clear']
        assert all(not e['selected'] and not e['refreshed'] for e in ranks)
        results.append(dict(case=name,target=target,drags=controller.drags,result=result,
                            selected=False,verified_clear=False,evidence=str(directory)))
    output=ROOT/'build/theme-replay-verification.json'
    output.write_text(json.dumps(dict(passed=True,device_controller=False,cases=results,
        scope='Derived fixed glyphs and English text with actual Maa OCR/native Swipe; no live theme selection, Japanese text or map transition verification.'),indent=2)+'\n',encoding='utf-8')
    print(output.read_text())


if __name__=='__main__':main()
