"""Offline native OCR crop diagnostics; no device connection or inputs."""
import json,time,cv2
from maa.custom_action import CustomAction
from maa.pipeline import JOCR,JRecognitionType
from verify_grace_balance_replay import Replay
from verify_theme_replay import ROOT,Library,Resource,Tasker,wait_job,wait_task


class Probe(CustomAction):
    def __init__(self,image):super().__init__();self.image=image;self.rows=[]
    def run(self,context,argv):
        for roi in [(1368,43,110,55),(1372,48,64,38),(1368,48,70,38),(1370,43,72,47)]:
            d=context.run_recognition_direct(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,threshold=.9),self.image)
            self.rows.append(dict(roi=roi,text=[dict(text=r.text,score=r.score) for r in d.all_results] if d else []))
        return True


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    image=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-081811/frame-0001.png'))
    controller=Replay(image);resource=Resource();probe=Probe(image)
    resource.register_custom_action('mode_probe',probe)
    for layer in ('base','en'):wait_job(resource.post_bundle(ROOT/f'assets/resource/{layer}'),timeout=20)
    wait_job(controller.post_connection());controller.set_screenshot_target_long_side(1920)
    tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
    wait_task(tasker,tasker.post_task('Probe',{'Probe':{'recognition':'DirectHit','action':'Custom','custom_action':'mode_probe'}}),deadline=time.monotonic()+12)
    print(json.dumps(probe.rows))


if __name__=='__main__':main()
