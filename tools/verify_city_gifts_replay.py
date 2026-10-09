"""Native retained-frame positive/negative City gift proof; no device input."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.floor_gifts import observe,rank
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    original=cv2.imread(str(ROOT/'evidence/runtime/window-20261009-063605/frame-0285.png'))
    catalog=GiftCatalog(ROOT/'assets/resource/base');results=[]
    for case in ('actual','missing_title_suffix','missing_hp_amount'):
        image=original.copy()
        if case=='missing_title_suffix':image[260:306,854:920]=0
        if case=='missing_hp_amount':image[758:793,718:797]=0
        journal=Journal(ROOT/f'evidence/runtime/city-gifts-replay-{time.time_ns()}-{case}')
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
            ranking=rank(offers,Team(7,frozenset({'Poise','Rupture'})),[])
        except ValueError as exc:error=str(exc)
        if case=='actual':
            assert count==dict(chosen=0,required=2)
            assert [r['title'] for r in ranking[:2]]==['For You Who Love the City','Smoking Gunpowder']
            assert all(r['visible_benefit']==0 for r in ranking)
        else:assert error is not None
        results.append(dict(case=case,error=error,ranking=ranking,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/city-gifts-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
