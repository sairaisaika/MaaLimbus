"""Native OCR on retained frames; no device connection or input."""
import json,time,cv2
from pathlib import Path
from verify_theme_replay import ROOT,CustomController,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.grace_vision import available_starlight
class Replay(CustomController):
    def __init__(self,image):super().__init__();self.image=image
    def connect(self):return True
    def request_uuid(self):return 'grace-balance-offline'
    def get_features(self):return 0
    def screencap(self):return self.image.copy()
    def click(self,*args):raise AssertionError('Offline replay must never input')
    def swipe(self,*args):raise AssertionError('Offline replay must never input')
def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    results=[]
    for number,expected in [(1,116),(4,86),(5,86),(6,86)]:
        source=ROOT/f'evidence/runtime/window-20261008-034445/frame-{number:04}.png'
        journal=Journal(ROOT/f'evidence/runtime/grace-balance-replay-{time.time_ns()}')
        rec=LimbusRecognition('en',journal);controller=Replay(cv2.imread(str(source)));resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        scene='STAR_CONFIRM' if number==6 else 'STAR_GRACES'
        result=wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':scene},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+10)
        events=[json.loads(l) for l in (journal.directory/'events.jsonl').read_text().splitlines()]
        frame=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        from maalimbus.vision import Text
        actual=available_starlight([Text(t['text'],tuple(t['box']),t['score']) for t in frame['ocr']],(1920,1080))
        assert actual==expected,(number,actual,expected)
        results.append(dict(source=str(source),available=actual,device_input=False,evidence=str(journal.directory)))
    (ROOT/'build/grace-balance-replay.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results))
if __name__=='__main__':main()
