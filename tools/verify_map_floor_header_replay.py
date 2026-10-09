"""Native retained-frame OCR of wrapped names/Base Power; inputs forbidden."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.floor_gifts import observe,rank
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    catalog=GiftCatalog(ROOT/'assets/resource/base');results=[]
    for source, expected, case in (
        ('window-20261008-124955',5,'actual'),
        ('window-20261008-124955',5,'missing_digit'),
        ('window-20261008-124955',5,'missing_floor'),
        ('window-20261009-053445',3,'actual'),
        ('window-20261009-053445',3,'missing_digit'),
        ('window-20261009-053445',3,'missing_floor')):
        original=cv2.imread(str(ROOT/f'evidence/runtime/{source}/frame-0001.png'))
        image=original.copy()
        if case=='missing_digit':image[125:177,362:410]=0
        if case=='missing_floor':image[125:178,238:362]=0
        journal=Journal(ROOT/f'evidence/runtime/map-floor-header-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'MAP'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+12)
        data=json.loads(sorted(journal.directory.glob('frame-*.json'))[-1].read_text())
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        from maalimbus.map_vision import map_header
        header=map_header(records,(1920,1080))
        error=None;ranking=None
        if case=='actual':assert header and header.floor==expected
        else:assert not header or header.floor is None
        results.append(dict(source=source,expected_floor=expected,case=case,error=error,ranking=ranking,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/map-floor-header-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
