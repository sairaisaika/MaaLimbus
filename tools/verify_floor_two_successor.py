"""Native Maa read-only floor-two identity replay; no device or action."""
import json
import time
import cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.theme_vision import selection_floor,theme_page
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    source=ROOT/'evidence/runtime/window-20261008-081512/frame-0005.png'
    original=cv2.imread(str(source));results=[]
    for case in ('actual','missing_header','missing_refresh','missing_search','changed_covers'):
        frame=original.copy()
        if case=='missing_header':frame[140:207,730:1180]=0
        if case=='missing_refresh':frame[25:105,1500:1745]=0
        if case=='missing_search':frame[28:109,185:388]=0
        if case=='changed_covers':frame[250:800,290:1185]=0
        journal=Journal(ROOT/f'evidence/runtime/floor-two-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(frame);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'THEME_PACKS'},'action':'DoNothing','timeout':1200}}),deadline=time.monotonic()+12)
        observed=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        texts=[Text(t['text'],tuple(t['box']),t['score']) for t in observed['ocr']]
        expected=case in ('actual','changed_covers')
        assert (selection_floor(texts,(1920,1080))==2)==expected
        assert observed['scene']==('THEME_PACKS' if expected else 'UNKNOWN')
        mode=theme_page(frame,rec.theme_catalog(),texts,rec.locale)
        assert mode==('hard' if expected else None)
        # Mode OCR is independent of cards; changed covers grant no pack target.
        results.append(dict(case=case,page=observed['scene'],mode=mode,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/floor-two-successor-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n')
    print(output)


if __name__=='__main__':main()
