"""Native no-WAVE battle OCR replay; all inputs intercepted and forbidden."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.battle_vision import battle_hud
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    source=ROOT/'evidence/runtime/window-20261008-084129/frame-0024.png'
    original=cv2.imread(str(source));results=[]
    for case in ('actual','missing_turn','missing_digit','missing_controls'):
        image=original.copy()
        if case=='missing_turn':image[85:130,10:65]=0
        if case=='missing_digit':image[88:133,67:153]=0
        if case=='missing_controls':image[788:895,1460:1590]=0
        journal=Journal(ROOT/f'evidence/runtime/regular-battle-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'BATTLE_HUD'},'action':'DoNothing','timeout':1200}}),deadline=time.monotonic()+12)
        observed=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        texts=[Text(t['text'],tuple(t['box']),t['score']) for t in observed['ocr']]
        hud=battle_hud(texts,(1920,1080))
        if case=='actual':assert hud and hud['turn']=='1' and hud['wave'] is None and observed['scene']=='BATTLE_HUD'
        else:assert hud is None
        results.append(dict(case=case,hud=hud,scene=observed['scene'],device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/regular-battle-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
