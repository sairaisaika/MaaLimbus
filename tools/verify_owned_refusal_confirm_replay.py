"""Replay retained single-gift frame through native Maa; device input forbidden."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.floor_gift_transaction import refusal_confirm_target
from maalimbus.gift_vision import GiftCatalog
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    original=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-144025/frame-0002.png'))
    catalog=GiftCatalog(ROOT/'assets/resource/base');results=[]
    for case in ('actual','missing_question','missing_cancel','missing_confirm'):
        image=original.copy()
        if case=='missing_question':image[497:537,680:1240]=0
        if case=='missing_cancel':image[713:763,700:855]=0
        if case=='missing_confirm':image[713:763,1105:1235]=0
        journal=Journal(ROOT/f'evidence/runtime/owned-refusal-confirm-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'GIFT_PICK'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+12)
        data=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        target=refusal_confirm_target(data)
        assert bool(target)==(case=='actual')
        results.append(dict(case=case,target=target,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/owned-refusal-confirm-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
