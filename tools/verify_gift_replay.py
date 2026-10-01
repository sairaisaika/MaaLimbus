"""Actual Maa OCR/custom-recognition target routing on derived reward frames.

Frames contain only pinned public icons and drawn labels. A target click is
verified; acquired rewards, selection quota and dungeon transitions are not.
"""
import argparse
import json
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
from recognition import Journal,LimbusRecognition,LimbusTerminal
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.jobs import wait_job,wait_task


class Replay(CustomController):
    def __init__(self,frame,expected):
        super().__init__();self.frame=frame;self.expected=expected;self.clicks=[]
    def connect(self):return True
    def request_uuid(self):return 'gift-replay-no-game'
    def get_features(self):return 0
    def screencap(self):return self.frame.copy()
    def click(self,x,y):
        assert self.expected is not None, 'No input on paid or unidentified choices'
        expected_x=220 if self.expected=='Bloody Mist' else 620
        assert expected_x-110<x<expected_x+120 and 110<y<180,(x,y,self.expected)
        self.clicks.append([x,y]);return True


def derived_frame(catalog,*,owned=False,paid=False,icons_only=False):
    frame=np.full((720,1280,3),(30,40,30),np.uint8)
    for x,name in [(100,'Bloody Mist'),(500,'Ardent Flower')]:
        cv2.putText(frame,'Acquire E.G.O Gift',(x,145),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
        if not icons_only:
            cv2.putText(frame,name,(x+35,210),cv2.FONT_HERSHEY_SIMPLEX,.75,(255,255,255),2)
        icon=next(i for n,i in catalog.icons if n==name)
        frame[290:290+icon.shape[0],x+100:x+100+icon.shape[1]]=icon
    if owned:
        # Owned needs its own column; no overlap with the Acquire text.
        cv2.putText(frame,'Owned',(100,115),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
    cv2.putText(frame,'Confirm',(1090,600),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
    if paid:
        cv2.putText(frame,'Purchase Lunacy',(400,380),cv2.FONT_HERSHEY_SIMPLEX,1.1,(255,255,255),2)
    return frame


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    args=parser.parse_args()
    Library.open(args.binary,agent_server=False)
    Toolkit.init_option(ROOT/'build/gift-replay-debug')
    catalog=GiftCatalog(ROOT/'assets/resource/base')
    cases=[('preferred',False,False,False,Team(1,frozenset({'Bleed'})),'Bloody Mist'),
           ('owned_preferred',True,False,False,Team(1,frozenset({'Bleed'})),'Ardent Flower'),
           ('blocked',False,False,False,Team(1,frozenset({'Bleed'}),block=frozenset({'Bloody Mist','Ardent Flower'})),None),
           ('paid',False,True,False,Team(1,frozenset({'Bleed'})),None),
           ('locale_independent_icons',False,False,True,Team(1,frozenset({'Burn'})),'Ardent Flower')]
    results=[]
    for name,owned,paid,icons_only,team,expected in cases:
        directory=ROOT/f'evidence/runtime/gift-replay-{name}'/str(time.time_ns())
        journal=Journal(directory)
        locale='jp' if icons_only else 'en'
        recognizer=LimbusRecognition(locale,journal);recognizer.team=team;recognizer.gifts=catalog
        controller=Replay(derived_frame(catalog,owned=owned,paid=paid,icons_only=icons_only),expected)
        resource=Resource()
        resource.register_custom_recognition('limbus_scene',recognizer)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(recognizer))
        for layer in ('base',locale):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection())
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        nodes={
            'GiftReplayStart':{'recognition':'DirectHit','action':'DoNothing',
                              'next':['LimbusSafety','GiftReplayChoose'],'timeout':1000,'on_error':['LimbusUnknown']},
            'GiftReplayChoose':{'recognition':'Custom','custom_recognition':'limbus_scene',
                'custom_recognition_param':{'scene':'FLOOR_GIFTS','gift_mode':'recommend'},
                'action':'Click','target':True,'max_hit':1,'next':[]}}
        job=tasker.post_task('GiftReplayStart',nodes)
        result=wait_task(tasker,job,deadline=time.monotonic()+30)
        assert not result['timed_out'] and result['stop_confirmed'],(name,result)
        assert len(controller.clicks)==(1 if expected else 0),(name,controller.clicks)
        events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
        ranked=[e for e in events if e['event']=='floor_gift_ranking']
        if expected:assert ranked[-1]['ranking'][0]['name']==expected,(name,ranked)
        assert all(not e['selected'] and not e['reward_received'] for e in ranked)
        results.append({'case':name,'locale':locale,'target':expected,'clicks':controller.clicks,
                        'last_scene':recognizer.last_scene,'verified_clear':False,'derived':True})
    output=ROOT/'build/gift-replay-verification.json'
    output.write_text(json.dumps({'passed':True,'device_controller':False,'cases':results,
        'scope':'Derived public-icon frames; actual Maa OCR/ranking/target click. No live gift acquisition, Japanese text rendering, quota or floor-clear assertion.'},indent=2),encoding='utf-8')
    print(output.read_text())


if __name__=='__main__':main()
