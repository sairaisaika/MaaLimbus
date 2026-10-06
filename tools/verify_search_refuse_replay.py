"""Native Maa zero-extra-spend gift-search refusal, intercepted input."""
import argparse
import json
import os
import time
from pathlib import Path
import cv2
from verify_star_replay import ROOT, Replay, Library, Resource, Tasker, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task, write_json
from maalimbus.storage import read_json


class RefuseReplay(Replay):
    def click(self,x,y):
        if getattr(self,'forgo',False):assert 1100<x<1240 and 720<y<775
        else:assert 1320<x<1440 and 845<y<885
        self.clicks.append([x,y]);return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',required=True)
    p.add_argument('--forgo',action='store_true')
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(args.frame);assert original is not None;results=[]
    for case in ('real','changed_art','missing_counter','missing_refuse','pending','foreground_changed'):
        frame=original.copy();directory=ROOT/f'evidence/runtime/search-refuse-replay-{time.time_ns()}-{case}'
        journal=Journal(directory);data=directory/'private-config';os.environ['MAALIMBUS_DATA_PATH']=str(data)
        if case=='changed_art':
            if args.forgo:frame[200:1000,:490]=0
            else:frame[340:805,130:1110]=0
        if case=='missing_counter':
            if args.forgo:frame[489:548,780:1140]=0
            else:frame[830:902,1660:1750]=0
        if case=='missing_refuse':
            if args.forgo:frame[725:771,695:843]=0
            else:frame[831:885,1298:1458]=0
        progress=read_json(ROOT/'config/initial-gift-progress.json')
        if case=='pending':progress['search_confirm_pending' if args.forgo else 'search_refuse_pending']={'unknown':True}
        write_json(data/'initial-gift-progress.json',progress)
        rec=LimbusRecognition('en',journal);resource=Resource();controller=RefuseReplay(frame)
        controller.forgo=args.forgo
        if case=='foreground_changed':
            def reject():raise RuntimeError('Foreground changed')
            rec.input_validator=reject
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        node='GiftSearchForgo' if args.forgo else 'GiftSearchRefuse'
        result=wait_task(tasker,tasker.post_task(node,{node:{'timeout':1000}}),deadline=time.monotonic()+8)
        assert len(controller.clicks)==int(case in ('real','changed_art')),(case,controller.clicks,directory)
        if not args.forgo:assert rec.last_scene=='GIFT_SEARCH'
        results.append(dict(case=case,clicks=controller.clicks,device_input=False,stop_confirmed=result['stop_confirmed']))
    report='search-forgo-replay-verification.json' if args.forgo else 'search-refuse-replay-verification.json'
    write_json(ROOT/'build'/report,dict(passed=True,cases=results))
    print(json.dumps(results))


if __name__=='__main__':main()
