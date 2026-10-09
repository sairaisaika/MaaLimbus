"""Native paid-offer recognition on retained frames; device input forbidden."""
import json,time,cv2
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,Journal,LimbusRecognition,wait_job,wait_task
from maalimbus.reward_cost import combine_evidence
from maalimbus.gift_vision import GiftCatalog
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    original=cv2.imread(str(ROOT/'evidence/runtime/window-20261009-093211/frame-0312.png'))
    catalog=GiftCatalog(ROOT/'assets/resource/base');results=[]
    for case in ('actual','later_frame','missing_currency','missing_sign','missing_digit','missing_title'):
        image=original.copy()
        if case=='later_frame':image=cv2.imread(str(ROOT/'evidence/runtime/window-20261009-093211/frame-0313.png'))
        if case=='missing_currency':image[785:850,1370:1431]=0
        if case=='missing_sign':image[805:838,1429:1448]=0
        if case=='missing_digit':image[790:840,1448:1480]=0
        if case=='missing_title':image[145:205,780:1140]=0
        journal=Journal(ROOT/f'evidence/runtime/team-seven-reward-cost-replay-{time.time_ns()}-{case}')
        rec=LimbusRecognition('en',journal);controller=Replay(image);resource=Resource()
        resource.register_custom_recognition('limbus_scene',rec)
        for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
        wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'limbus_scene','custom_recognition_param':{'scene':'RUN_REWARD_DIALOG'},'action':'DoNothing','timeout':2000}}),deadline=time.monotonic()+12)
        data=json.loads((journal.directory/(rec.cache[3]+'.json')).read_text())
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        target=data.get('reward_cost')
        assert bool(target)==(case in ('actual','later_frame')),(case,data.get('reward_cost_provenance'))
        if target:assert target==dict(currency='enkephalin_modules',cost=5,weekly=0)
        results.append(dict(case=case,target=target,device_input=False,evidence=str(journal.directory)))
    output=ROOT/'build/team-seven-reward-cost-replay.json'
    output.write_text(json.dumps(dict(passed=True,cases=results),indent=2)+'\n');print(output)


if __name__=='__main__':main()
