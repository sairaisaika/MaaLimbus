"""Maa one-touch Hard toggle; patched Hard glyph is a derived proof fixture."""
import argparse
import json
import os
import time
from pathlib import Path
import cv2
from verify_star_replay import ROOT, Replay, Library, Resource, Tasker, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task, write_json
from recognition import DifficultyProof
from maalimbus.theme_vision import ThemeCatalog


class ToggleReplay(Replay):
    def click(self,x,y):
        assert 1355<x<1410 and 50<y<85
        self.clicks.append([x,y])
        if self.after is not None:self.frame=self.after.copy()
        return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',required=True)
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(args.frame);assert original is not None
    catalog=ThemeCatalog(ROOT/'assets/resource/base');derived=original.copy()
    glyph=cv2.cvtColor(cv2.resize(catalog.glyphs['hard_mode'],None,fx=1.5,fy=1.5),cv2.COLOR_GRAY2BGR)
    derived[34:98,1243:1480]=0
    derived[42:42+glyph.shape[0],1252:1252+glyph.shape[1]]=glyph
    results=[]
    for case in ('unchanged','derived_hard','changed_covers','missing_refresh','missing_header','pending','foreground_changed'):
        frame=original.copy();directory=ROOT/f'evidence/runtime/hard-toggle-replay-{time.time_ns()}-{case}'
        journal=Journal(directory);data=directory/'private-config';os.environ['MAALIMBUS_DATA_PATH']=str(data)
        if case=='changed_covers':frame[370:640,515:1420]=0
        if case=='missing_refresh':frame[34:99,1510:1745]=0
        if case=='missing_header':frame[145:211,750:1180]=0
        if case=='pending':write_json(data/'difficulty-switch-progress.json',dict(pending={'unknown':True}))
        rec=LimbusRecognition('en',journal);resource=Resource();controller=ToggleReplay(frame,derived if case=='derived_hard' else None)
        if case=='foreground_changed':
            def reject():raise RuntimeError('Foreground changed')
            rec.input_validator=reject
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_difficulty_proof',DifficultyProof(rec))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        result=wait_task(tasker,tasker.post_task('ThemeHardToggle',{'ThemeHardToggle':{'timeout':1000}}),deadline=time.monotonic()+8)
        assert len(controller.clicks)==int(case in ('unchanged','derived_hard','changed_covers')),(case,controller.clicks,directory)
        events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
        observations=[e for e in events if e['event']=='difficulty_switch_observation']
        assert bool(observations and observations[-1]['verified'])==(case=='derived_hard'),(case,events)
        results.append(dict(case=case,clicks=controller.clicks,observations=observations,
            derived=case=='derived_hard',device_input=False,stop_confirmed=result['stop_confirmed']))
    write_json(ROOT/'build/hard-toggle-replay-verification.json',dict(passed=True,cases=results,
        scope='actual Maa replay; patched Hard label is derived, not actual Hard entry proof'))
    print(json.dumps(results))


if __name__=='__main__':main()
