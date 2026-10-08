"""Native OCR of compound trials; retained frames only, all input forbidden."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.floor_gifts import observe,rank
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    original=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-091754/frame-0178.png'))
    catalog=GiftCatalog(ROOT/'assets/resource/base');results=[]
    for case in ('actual','fresh_actual','missing_wrapped_amount','missing_counter'):
        image=original.copy()
        if case=='fresh_actual':image=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-093745/frame-0001.png'))
        if case=='missing_wrapped_amount':image[754:796,326:395]=0
        if case=='missing_counter':image[839:898,1735:1810]=0
        journal=Journal(ROOT/f'evidence/runtime/compound-gift-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'GIFT_PICK'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+12)
        data=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        error=None;ranking=None
        try:
            offers,count=observe(records,(1920,1080),catalog)
            ranking=rank(offers,Team(2,frozenset({'Charge','Tremor'})),[])
        except ValueError as exc:error=str(exc)
        if case in ('actual','fresh_actual'):
            assert count==dict(chosen=0,required=2)
            assert [o.trial.penalty for o in offers]==[155,55,240,202.5]
            assert [r['title'] for r in ranking[:2]]==['Blood, Sweat, and Tears',"Tomorrow's Fortune"]
        else:assert error is not None
        results.append(dict(case=case,error=error,ranking=ranking,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/compound-gift-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
