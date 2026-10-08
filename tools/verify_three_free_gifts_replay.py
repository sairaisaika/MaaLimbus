"""Three-choice free gift layout on actual Maa OCR; zero device input."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.floor_gifts import observe,rank
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    original=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-100819/frame-0005.png'))
    catalog=GiftCatalog(ROOT/'assets/resource/base');results=[]
    for case in ('actual','selected','missing_title','missing_refuse','missing_selected_outline'):
        image=original.copy()
        if case in ('selected','missing_selected_outline'):
            image=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-101324/frame-0002.png'))
        if case=='missing_selected_outline':image[835:850,1180:1290]=0
        if case=='missing_title':image[265:303,1260:1443]=0
        if case=='missing_refuse':image[844:892,1345:1508]=0
        journal=Journal(ROOT/f'evidence/runtime/three-free-gifts-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'GIFT_PICK'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+12)
        data=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        error=None;count=None;ranking=None
        try:
            offers,count=observe(records,(1920,1080),catalog,image=image,select_box=(1620,851,100,36))
            ranking=rank(offers,Team(2,frozenset({'Charge','Tremor'})),[])
        except ValueError as exc:error=str(exc)
        if case in ('actual','selected'):assert count==dict(chosen=int(case=='selected'),required=1) and ranking[0]['title']=='Phantom Pain'
        else:assert error is not None
        results.append(dict(case=case,error=error,count=count,ranking=ranking,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/three-free-gifts-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
