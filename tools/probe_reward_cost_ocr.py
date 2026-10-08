"""Diagnostic native OCR of retained reward cost; no device input."""
import json,time,cv2
from verify_theme_replay import ROOT,Library,Resource,Tasker,wait_job,wait_task
from verify_grace_balance_replay import Replay
from maa.custom_recognition import CustomRecognition
from maa.pipeline import JOCR,JRecognitionType

class Probe(CustomRecognition):
    def __init__(self):super().__init__();self.readings=[]
    def analyze(self,context,argv):
        for roi in ((1428,790,50,50),(1420,780,75,70)):
            detail=context.run_recognition_direct(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,threshold=.9),argv.image)
            self.readings.append(dict(roi=roi,results=[dict(text=r.text,score=r.score) for r in detail.all_results]))
        return CustomRecognition.AnalyzeResult(box=(0,0,1,1),detail='diagnostic')

def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    controller=Replay(cv2.imread(str(ROOT/'evidence/runtime/window-20261008-144554/frame-0458.png')))
    resource=Resource();rec=Probe();resource.register_custom_recognition('probe',rec)
    for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
    wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
    tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
    wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'Custom','custom_recognition':'probe','action':'DoNothing'}}),deadline=time.monotonic()+12)
    output=ROOT/'build/reward-cost-native-diagnostic.json';output.write_text(json.dumps(dict(readings=rec.readings,device_input=False,production_gate_enabled=False),indent=2)+'\n');print(output)

if __name__=='__main__':main()
