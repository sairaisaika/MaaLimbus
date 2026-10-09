"""Native garden dialogue/control proof and image negatives; no device input."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.event_vision import choice_options,garden_refusal_choice
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    original=cv2.imread(str(ROOT/'evidence/runtime/window-20261009-071129/frame-0134.png'))
    results=[]
    for case in ('actual','missing_question','missing_refuse'):
        image=original.copy()
        if case=='missing_question':image[700:745,106:415]=0
        if case=='missing_refuse':image[285:335,1080:1210]=0
        journal=Journal(ROOT/f'evidence/runtime/garden-event-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'EVENT_CHOICE'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+12)
        data=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        error=None;ranking=None
        try:
            options=choice_options(records,(1920,1080))
            ranking=garden_refusal_choice(records,(1920,1080),options)
        except ValueError as exc:error=str(exc)
        if case=='actual':assert ranking==0 and error is None
        else:assert error is not None
        results.append(dict(case=case,error=error,ranking=ranking,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/garden-event-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
