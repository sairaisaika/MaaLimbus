"""Intercepted Maa entry proof on a retained fully selected star page."""
import argparse
import json
import os
import time
from pathlib import Path
import cv2
from verify_star_replay import ROOT, Replay, Library, Resource, Tasker, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task, write_json


class EntryReplay(Replay):
    def click(self,x,y):
        if getattr(self,'confirm',False):assert 1040<x<1200 and 780<y<815
        elif getattr(self,'conversion',False):assert 1075<x<1104 and 532<y<563
        else:assert 1740<x<1845 and 985<y<1028
        self.clicks.append([x,y])
        return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',required=True)
    p.add_argument('--conversion',action='store_true')
    p.add_argument('--confirm',action='store_true')
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(args.frame);assert original is not None
    results=[]
    modal=args.conversion or args.confirm
    cases=('ready','incomplete','pending','conversion_enabled','missing_check') if modal else ('ready','incomplete','pending','over_budget','balance_changed')
    for case in cases:
        directory=ROOT/f'evidence/runtime/star-entry-replay-{time.time_ns()}-{case}'
        journal=Journal(directory);data=directory/'private-config'
        os.environ['MAALIMBUS_DATA_PATH']=str(data)
        write_json(data/'user-mirror-settings.json',dict(graces=['1','3','4','6'],enhance=False,
            max_starlight=99 if case=='over_budget' else 100,
            convert_remaining_starlight=case=='conversion_enabled'))
        write_json(data/'star-selection-progress.json',dict(selected=['1','3','4'] if case=='incomplete'
            else ['1','3','4','6'],pending={'unconfirmed':True} if case=='pending' else None,
            available_after=8 if case=='balance_changed' else 7,
            entry_pending={'choices':['1','3','4','6'],'cost':100} if modal else None))
        frame=original.copy()
        if case=='missing_check':frame[529:565,1071:1107]=0
        rec=LimbusRecognition('en',journal);resource=Resource();controller=EntryReplay(frame)
        controller.conversion=args.conversion
        controller.confirm=args.confirm
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        node='StarConfirm' if args.confirm else 'StarDisableConversion' if args.conversion else 'StarEnter'
        result=wait_task(tasker,tasker.post_task(node,{node:{'timeout':1000}}),
                         deadline=time.monotonic()+8)
        assert len(controller.clicks)==int(case=='ready'),(case,controller.clicks)
        results.append(dict(case=case,clicks=controller.clicks,stop_confirmed=result['stop_confirmed'],device_input=False))
    report='star-confirm-replay-verification.json' if args.confirm else 'star-conversion-replay-verification.json' if args.conversion else 'star-entry-replay-verification.json'
    write_json(ROOT/'build'/report,dict(passed=True,cases=results))
    print(json.dumps(results))


if __name__=='__main__':main()
