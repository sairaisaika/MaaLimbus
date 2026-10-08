"""Replay retained single-gift frame through native Maa; device input forbidden."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.run_summary import completed_hard_summary
from maalimbus.gift_vision import GiftCatalog
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    original=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-144554/frame-0457.png'))
    catalog=GiftCatalog(ROOT/'assets/resource/base');results=[]
    for case in ('actual','missing_progress','missing_floor5','missing_hard'):
        image=original.copy()
        if case=='missing_progress':image[750:860,265:440]=0
        if case=='missing_floor5':image[610:650,255:445]=0
        if case=='missing_hard':image[380:407,475:548]=0
        journal=Journal(ROOT/f'evidence/runtime/floor-five-summary-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'RUN_CLAIM'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+12)
        data=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        target=completed_hard_summary(data)
        assert bool(target)==(case=='actual')
        results.append(dict(case=case,target=target,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/floor-five-summary-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
