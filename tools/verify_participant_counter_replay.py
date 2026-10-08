"""Production Maa OCR over actual deployment frames, never connected to a device."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.team_vision import participants
from maalimbus.vision import Text

def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    results=[]
    cases=[('window-20261008-044013/frame-0054',12),('window-20261008-044810/frame-0002',1),
           ('window-20261008-045028/frame-0015',8)]
    for stem,expected in cases:
        source=ROOT/f'evidence/runtime/{stem}.png'
        journal=Journal(ROOT/f'evidence/runtime/participant-replay-{time.time_ns()}')
        rec=LimbusRecognition('en',journal);controller=Replay(cv2.imread(str(source)));resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'PRE_BATTLE_TEAM'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+15)
        frame=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        actual=participants([Text(t['text'],tuple(t['box']),t['score']) for t in frame['ocr']],(1920,1080))
        assert actual==(expected,12),(stem,actual)
        results.append(dict(source=str(source),participants=actual,device_input=False,evidence=str(journal.directory)))
    (ROOT/'build/participant-counter-replay.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results))
if __name__=='__main__':main()
