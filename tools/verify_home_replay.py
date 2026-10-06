"""Actual Maa OCR/Pipeline on a retained private home frame; intercepted input."""
import argparse
import json
import os
from pathlib import Path
import sys
import cv2
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'agent')]
from maa.controller import CustomController
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from recognition import Journal, LimbusRecognition, LimbusTerminal, TeamAction
from maalimbus.jobs import wait_job, wait_task
import time


class Replay(CustomController):
    def __init__(self, frame, drive=False, tutorial=False, confirm=False, dungeon_team=False, stuck=False):
        super().__init__(); self.frame=frame; self.clicks=[]; self.drive=drive; self.tutorial=tutorial; self.confirm=confirm; self.dungeon_team=dungeon_team; self.stuck=stuck
    def connect(self): return True
    def request_uuid(self): return 'home-offline'
    def get_features(self): return 0
    def screencap(self): return self.frame.copy()
    def click(self,x,y):
        if self.dungeon_team: assert 1600<x<1820 and 825<y<945
        elif self.confirm: assert 1020<x<1290 and 680<y<770
        elif self.tutorial: assert 110<x<175 and 50<y<92
        else: assert (550<x<810 and 450<y<535) if self.drive else (1400<x<1556 and 928<y<1037)
        self.clicks.append([x,y])
        if not self.stuck:self.frame=np.zeros_like(self.frame)
        return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--frame',type=Path,required=True)
    parser.add_argument('--drive',action='store_true')
    parser.add_argument('--tutorial',action='store_true')
    parser.add_argument('--confirm',action='store_true')
    parser.add_argument('--dungeon-team',action='store_true')
    parser.add_argument('--warning',action='store_true')
    args=parser.parse_args(); Library.open(args.binary,agent_server=False)
    original=cv2.imread(str(args.frame)); assert original is not None
    results=[]
    for name,frame in [('real',original),('changed_art',original.copy()),('missing_anchor',original.copy()),
                       ('foreground_changed',original.copy()),('stuck',original.copy())]:
        if name=='changed_art':
            if args.warning: frame[900:]=0; frame[100:320,700:1280]=0
            elif args.dungeon_team: frame[235:795,350:1550]=0
            elif args.confirm: frame[100:900,:500]=0
            elif args.tutorial: frame[180:680,600:1220]=0
            elif args.drive: frame[320:700,900:1800]=0
            else: frame[:900,:1300]=0
        if name=='missing_anchor':
            if args.warning: frame[680:770,620:930]=0
            elif args.dungeon_team: frame[780:829,1600:1800]=0
            elif args.confirm: frame[680:770,620:930]=0
            elif args.tutorial: frame[25:115,75:210]=0
            elif args.drive: frame[150:280,1550:1830]=0
            else: frame[925:1040,1310:1420]=0
        resource=Resource(); controller=Replay(frame,args.drive,args.tutorial,args.confirm or args.warning,args.dungeon_team,name=='stuck')
        kind='level-warning' if args.warning else ('dungeon-team' if args.dungeon_team else ('confirm' if args.confirm else ('tutorial' if args.tutorial else ('drive' if args.drive else 'home'))))
        journal=Journal(ROOT/f'evidence/runtime/{kind}-replay-{time.time_ns()}-{name}')
        os.environ['MAALIMBUS_DATA_PATH']=str(journal.directory/'private-config')
        recognition=LimbusRecognition('en',journal)
        if name=='foreground_changed':
            def reject():raise RuntimeError('Limbus no longer foreground')
            recognition.input_validator=reject
        resource.register_custom_recognition('limbus_scene',recognition)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(recognition))
        resource.register_custom_action('limbus_team',TeamAction(recognition))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5)
        controller.set_screenshot_target_long_side(1920)
        tasker=Tasker(); assert tasker.bind(resource=resource,controller=controller)
        entry='LevelWarningConfigure' if args.warning else ('DungeonTeamConfigure' if args.dungeon_team else ('MirrorEntryConfirm' if args.confirm else ('MirrorTutorialBack' if args.tutorial else ('MirrorDrive' if args.drive else 'MirrorHome'))))
        wait_task(tasker,tasker.post_task(entry,{'MirrorHome':{'timeout':1000},'MirrorDrive':{'timeout':1000},'MirrorEnter':{'timeout':1000}}),deadline=time.monotonic()+12)
        assert len(controller.clicks)==(0 if name in ('missing_anchor','foreground_changed') else 1), (name,controller.clicks)
        if name=='foreground_changed':assert recognition.callback_failure is not None
        results.append(dict(case=name,clicks=controller.clicks,device_input=False))
    (ROOT/f'build/{kind}-replay-verification.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results))


if __name__=='__main__': main()
