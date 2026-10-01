"""Real Maa one-shot P planning on derived glyph frames; no game or turn submission."""
import argparse
import json
from pathlib import Path
import sys
import time

from maa.controller import CustomController
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'agent'),str(ROOT/'tests')]
from recognition import Journal,LimbusRecognition,LimbusTerminal,BattlePlanObservation
from test_battle_vision import derived_battle_frame
from maalimbus.jobs import wait_job,wait_task


class Replay(CustomController):
    def __init__(self,case):
        super().__init__();self.case=case;self.keys=[]
        self.image=derived_battle_frame(missing=case=='missing',duplicate=case=='duplicate',
            paid=case=='paid',defeat=case=='defeat')
    def connect(self):return True
    def request_uuid(self):return 'battle-plan-offline-no-game'
    def get_features(self):return 0
    def screencap(self):return self.image.copy()
    def click(self,*args):raise AssertionError('No mouse or EGO input in planning task')
    def click_key(self,keycode):
        return self.key_down(keycode) and self.key_up(keycode)
    def key_down(self,keycode):
        assert self.case in ('plan','stuck') and not self.keys and keycode==80
        self.keys.append(keycode);return True
    def key_up(self,keycode):
        assert keycode==80
        if self.case=='plan':self.image=derived_battle_frame(after=True)
        return True


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=Path,required=True)
    args=parser.parse_args();Library.open(args.binary,agent_server=False)
    Toolkit.init_option(ROOT/'build/battle-plan-replay-debug')
    results=[]
    for case in ('plan','stuck','missing','duplicate','paid','defeat','jp'):
        directory=ROOT/f'evidence/runtime/battle-plan-{case}'/str(time.time_ns())
        journal=Journal(directory);rec=LimbusRecognition('jp' if case=='jp' else 'en',journal)
        resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_battle_plan_observe',BattlePlanObservation(rec))
        for layer in ('base', 'jp' if case=='jp' else 'en'):
            wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        controller=Replay(case);wait_job(controller.post_connection(),timeout=5)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        overrides={'BattlePlanStart':{'action':'DoNothing','timeout':900},
            'BattlePlanOnce':{'post_delay':50,'timeout':900}}
        result=wait_task(tasker,tasker.post_task('BattlePlanStart',overrides),deadline=time.monotonic()+15)
        assert not result['timed_out'] and result['stop_confirmed'],(case,result)
        assert len(controller.keys)==(1 if case in ('plan','stuck') else 0),(case,controller.keys)
        events=[json.loads(line) for line in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        observations=[e for e in events if e['event']=='battle_plan_observed']
        if observations:
            assert observations[0]['frame_changed']==(case=='plan')
            assert not observations[0]['plan_verified'] and not observations[0]['turn_submitted']
            assert not observations[0]['victory_verified'] and not observations[0]['verified_clear']
        results.append({'case':case,'keys':controller.keys,'result':result,'observations':observations,'evidence':str(directory)})
    report={'passed':True,'device_controller':False,'cases':results,'verified_clear':False,
        'scope':'Actual Maa OCR/small-glyph recognition/ClickKey on derived frames; no live geometry, skill coverage, turn or victory proof'}
    (ROOT/'build/battle-plan-replay-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'cases':len(results),'key_presses':[len(r['keys']) for r in results],'turn_submitted':False}))


if __name__=='__main__':main()
