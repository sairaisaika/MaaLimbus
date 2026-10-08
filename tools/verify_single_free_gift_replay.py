"""Replay retained single-gift frame through native Maa; device input forbidden."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.floor_gifts import observe
from maalimbus.gift_vision import GiftCatalog
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    original=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-084911/frame-0167.png'))
    catalog=GiftCatalog(ROOT/'assets/resource/base');results=[]
    for case in ('actual','selected','missing_title','missing_refuse','missing_outline'):
        image=original.copy()
        if case in ('selected','missing_outline'):
            image=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-091114/frame-0002.png'))
        if case=='missing_outline':image[250:810,760:772]=0
        if case=='missing_title':image[263:301,868:1044]=0
        if case=='missing_refuse':image[845:892,1345:1508]=0
        journal=Journal(ROOT/f'evidence/runtime/single-free-gift-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'GIFT_PICK'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+12)
        data=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        error=None;count=None
        try:
            offers,count=observe(records,(1920,1080),catalog,image=image,select_box=(1620,851,100,36))
        except ValueError as exc:error=str(exc)
        if case in ('actual','selected'):assert count==dict(chosen=int(case=='selected'),required=1) and offers[0].title=='Lightning Rod'
        else:assert error is not None
        results.append(dict(case=case,count=count,error=error,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/single-free-gift-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
