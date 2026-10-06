"""Intercept native Swipe on a retained Hard page; never connect to a game."""
import argparse
import json
import os
import time
from pathlib import Path
import cv2
from verify_theme_replay import ROOT, CustomController, Library, Resource, Tasker, Journal, LimbusRecognition, LimbusTerminal, ThemeObservation, TeamAction, wait_job, wait_task, ProfileStore, Team


class Replay(CustomController):
    def __init__(self, frame, allowed):
        super().__init__(); self.frame=frame; self.allowed=allowed; self.drags=[]
    def connect(self): return True
    def request_uuid(self): return 'retained-hard-no-device'
    def get_features(self): return 0
    def screencap(self): return self.frame.copy()
    def click(self,x,y): raise AssertionError('Pack routing must use Swipe')
    def swipe(self,x1,y1,x2,y2,duration):
        assert self.allowed
        assert 633<=x1<=675 and 388<=y1<=406,(x1,y1)
        assert 633<=x2<=675 and 988<=y2<=1006,(x2,y2)
        assert y2-y1>=580 and 480<=duration<=680
        self.drags.append([x1,y1,x2,y2,duration])
        # Unchanged post-frame must never be accepted as selection proof.
        return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',required=True)
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(args.frame);assert original is not None and original.shape[:2]==(1080,1920)
    results=[]
    for case in ('real','changed_covers','missing_mode','missing_header','missing_refresh'):
        frame=original.copy();allowed=case=='real'
        if case=='changed_covers':frame[430:630,540:1390]=0
        if case=='missing_mode':frame[28:111,1242:1489]=0
        if case=='missing_header':frame[145:211,750:1180]=0
        if case=='missing_refresh':frame[34:99,1510:1745]=0
        directory=ROOT/f'evidence/runtime/real-theme-replay-{time.time_ns()}-{case}'
        journal=Journal(directory);store=ProfileStore(directory/'private-config/user-team-profiles.json')
        store.save([Team(1,frozenset())]);os.environ['MAALIMBUS_DATA_PATH']=str(store.path.parent)
        rec=LimbusRecognition('en',journal);controller=Replay(frame,allowed);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_theme_observe',ThemeObservation(rec))
        resource.register_custom_action('limbus_team',TeamAction(rec))
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        result=wait_task(tasker,tasker.post_task('ThemePackStart',{'ThemePackStart':{'action':'DoNothing'},'ThemePackConfigure':{'timeout':1200},'ThemePackDrag':{'post_delay':50}}),deadline=time.monotonic()+15)
        assert result['stop_confirmed'] and not result['timed_out']
        assert len(controller.drags)==int(allowed),(case,controller.drags)
        events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
        post=[e for e in events if e['event']=='theme_map_postcondition']
        if allowed:assert post and not post[-1]['selected'] and not post[-1]['verified_clear']
        results.append(dict(case=case,drags=controller.drags,device_input=False,selected=False,evidence=str(directory)))
    output=ROOT/'build/real-theme-drag-verification.json'
    output.write_text(json.dumps(dict(passed=True,source=args.frame,cases=results,scope='Retained Hard frame with intercepted Maa Swipe; no live selection or map proof'),indent=2)+'\n')
    print(output)


if __name__=='__main__':main()
