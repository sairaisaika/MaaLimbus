"""Retained initial gift page; native Maa, intercepted group click."""
import argparse
import os
import json
import time
from pathlib import Path
import cv2
from verify_star_replay import ROOT, Replay, Library, Resource, Tasker, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task, write_json
from recognition import InitialGiftProof
from maalimbus.storage import read_json


class GroupReplay(Replay):
    def click(self,x,y):
        if getattr(self,'commit',False):assert 1510<x<1630 and 855<y<905
        elif getattr(self,'pick',False):
            top=335+160*(getattr(self,'choice',1)-1)
            assert 1300<x<1740 and top<y<top+35
        else:assert 495<x<600 and 237<y<275
        self.clicks.append([x,y]);return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',required=True)
    p.add_argument('--pick',action='store_true')
    p.add_argument('--proof',action='store_true')
    p.add_argument('--commit',action='store_true')
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(args.frame);assert original is not None
    results=[]
    cases=('real','changed_icons','missing_counter','wrong_title','unselected') if args.proof else ('real','changed_icons','missing_counter','foreground_changed','wrong_profile')
    for case in cases:
        frame=original.copy()
        if case=='changed_icons':
            for y in (277,589):frame[y:y+225,240:1080]=(20,20,20)
        if case=='missing_counter':frame[820:929,1600:1780]=0
        if case=='unselected':frame[322:333,1185:1728]=0
        directory=ROOT/f'evidence/runtime/initial-gift-replay-{time.time_ns()}-{case}'
        journal=Journal(directory);data=directory/'private-config'
        os.environ['MAALIMBUS_DATA_PATH']=str(data)
        write_json(data/'user-team-profiles.json',dict(version=1,teams=[dict(slot=2 if case=='wrong_profile' else 1,
            keywords=['Bleed'],formation_keywords=['Bleed'],initial_gifts=[1,2,3])]))
        if args.proof:
            progress=read_json(ROOT/'config/initial-gift-progress.json')
            if case=='wrong_title':progress['pending']['title']='Unrecognized gift'
            write_json(data/'initial-gift-progress.json',progress)
        elif (args.pick or args.commit) and (ROOT/'config/initial-gift-progress.json').exists():
            write_json(data/'initial-gift-progress.json',read_json(ROOT/'config/initial-gift-progress.json'))
        rec=LimbusRecognition('en',journal);resource=Resource();controller=GroupReplay(frame)
        controller.pick=args.pick
        controller.commit=args.commit
        if args.pick and (data/'initial-gift-progress.json').exists():
            selected=read_json(data/'initial-gift-progress.json')['selected']
            controller.choice=next(g for g in (1,2,3) if g not in selected)
        if case=='foreground_changed':
            def reject():raise RuntimeError('Foreground changed')
            rec.input_validator=reject
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_initial_gift_proof',InitialGiftProof(rec))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        node='InitialGiftCommit' if args.commit else 'InitialGiftProof' if args.proof else 'InitialGiftPick' if args.pick else 'InitialGiftGroup'
        result=wait_task(tasker,tasker.post_task(node,{node:{'timeout':1000}}),deadline=time.monotonic()+8)
        if args.proof:
            assert not controller.clicks
            assert (read_json(data/'initial-gift-progress.json')['pending'] is None)==(case in ('real','changed_icons')),(case,directory)
        else:assert len(controller.clicks)==int(case in ('real','changed_icons')),(case,controller.clicks,directory)
        results.append(dict(case=case,clicks=controller.clicks,device_input=False,stop_confirmed=result['stop_confirmed']))
    report='initial-gift-commit-replay-verification.json' if args.commit else 'initial-gift-proof-replay-verification.json' if args.proof else 'initial-gift-pick-replay-verification.json' if args.pick else 'initial-gift-replay-verification.json'
    write_json(ROOT/'build'/report,dict(passed=True,cases=results))
    print(json.dumps(results))


if __name__=='__main__':main()
