"""Derived count/order-marker frames through the real Maa deployment graph.

No Windows controller, actual sinner identity, encounter or battle-clear proof.
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
from recognition import Journal,LimbusRecognition,LimbusTerminal,TeamAction,DeploymentProof
from maalimbus.deployment import CENTERS
from maalimbus.storage import ProfileStore,SINNERS
from maalimbus.policies import Team
from maalimbus.jobs import wait_job,wait_task

ORDER=('Outis','Yi Sang','Faust')


def derived_frame(order=(),*,count=None,capacity=3,paid=False,missing=False,seed=7):
    image=np.full((720,1280,3),18,np.uint8)
    rng=np.random.default_rng(seed)
    for name,(x,y) in CENTERS.items():
        image[y-20:y+40,x-45:x+45]=rng.integers(0,150,(60,90,3),dtype=np.uint8)
    cv2.putText(image,'Details',(1070,105),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
    if not missing:
        cv2.putText(image,f'{len(order) if count is None else count}/{capacity}',(1140,535),cv2.FONT_HERSHEY_SIMPLEX,.85,(255,255,255),2)
    for index,name in enumerate(order,1):
        x,y=CENTERS[name]
        cv2.putText(image,str(index),(x-8,y-56),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
    if paid:cv2.putText(image,'Purchase Lunacy',(440,370),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    return image


class Replay(CustomController):
    def __init__(self,case,order=ORDER):
        super().__init__();self.case=case;self.clicks=[];self.expected_order=order
        initial={'resume':order[:1],'already_ready':order,'wrong_order':('Yi Sang',)}.get(case,())
        self.order=initial
        self.frame=derived_frame(initial,paid=case=='paid',missing=case=='missing_count')
    def connect(self):return True
    def request_uuid(self):return 'deployment-replay-no-game'
    def get_features(self):return 0
    def screencap(self):return self.frame.copy()
    def swipe(self,*args):raise AssertionError('No deployment swipe or reset')
    def click(self,x,y):
        assert self.case not in ('already_ready','wrong_order','missing_count','paid','unconfigured')
        expected=self.expected_order[len(self.order)];cx,cy=CENTERS[expected]
        assert abs(x-cx)<18 and abs(y-cy)<18,(x,y,expected)
        assert not (self.case in ('stuck','missing_badge') and self.clicks),'Never repeat an unconfirmed choice'
        self.clicks.append([expected,x,y])
        if self.case=='stuck':return True
        self.order=(*self.order,expected)
        self.frame=derived_frame(self.order if self.case!='missing_badge' else (),
            count=len(self.order),seed=42)
        return True


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=Path,required=True)
    args=parser.parse_args();Library.open(args.binary,agent_server=False)
    Toolkit.init_option(ROOT/'build/deployment-replay-debug')
    results=[]
    for case,clicks,ready in [('ordered',3,True),('natural',3,True),('resume',2,True),('already_ready',0,True),
            ('wrong_order',0,False),('missing_count',0,False),('paid',0,False),
            ('stuck',1,False),('missing_badge',1,False),('unconfigured',0,False)]:
        directory=ROOT/f'evidence/runtime/deployment-replay-{case}'/str(time.time_ns())
        journal=Journal(directory);rec=LimbusRecognition('en',journal);resource=Resource()
        store=ProfileStore(directory/'config/user-team-profiles.json')
        saved=Team(2,frozenset({'Burn'}),name='Saved team 2',deployment=ORDER if case not in ('unconfigured','natural') else ())
        store.save([saved])
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_team',TeamAction(rec))
        resource.register_custom_action('limbus_deployment_proof',DeploymentProof(rec))
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        expected_order=SINNERS[:3] if case=='natural' else ORDER
        controller=Replay(case,expected_order);wait_job(controller.post_connection(),timeout=5)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        overrides={'DeploymentStart':{'action':'DoNothing'},
            'DeploymentConfigure':{'custom_action_param':{'mode':'configure','slot':2}},
            'DeploymentPreset':{'timeout':1300},'DeploymentNext':{'post_delay':50,'timeout':1300}}
        if case=='natural':overrides['DeploymentPreset']['custom_action_param']={'mode':'deployment','preset':'natural'}
        previous=os.environ.get('MAALIMBUS_DATA_PATH');os.environ['MAALIMBUS_DATA_PATH']=str(store.path.parent)
        try:result=wait_task(tasker,tasker.post_task('DeploymentStart',overrides),deadline=time.monotonic()+25)
        finally:
            if previous is None:os.environ.pop('MAALIMBUS_DATA_PATH',None)
            else:os.environ['MAALIMBUS_DATA_PATH']=previous
        assert not result['timed_out'] and result['stop_confirmed'],(case,result)
        assert len(controller.clicks)==clicks,(case,controller.clicks)
        expected_profile=Team(2,saved.keywords,saved.name,deployment=SINNERS) if case=='natural' else saved
        assert store.load()==(expected_profile,)
        events=[json.loads(l) for l in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        proof=[e for e in events if e['event']=='deployment_order_observed']
        assert bool(proof)==ready,(case,events)
        if ready:assert tuple(proof[-1]['order'])==expected_order
        assert all(not e['battle_started'] and not e['verified_clear'] for e in proof)
        results.append(dict(case=case,clicks=controller.clicks,order_observed=ready,result=result,
                            battle_started=False,verified_clear=False,evidence=str(directory)))
    record=dict(passed=True,device_controller=False,cases=results,
        scope='Actual Maa OCR/Pipeline over derived counters/order badges and experimental LALC grid. No live deployment geometry, identity, battle start or clear proof.')
    path=ROOT/'build/deployment-replay-verification.json';path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
