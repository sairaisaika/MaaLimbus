"""Replay the complete Agent observer on retained GUI frames, without device input."""
import pathlib as _pathlib
import sys as _sys
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / 'src'))
import json,sys,hashlib
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'agent')]
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maalimbus.jobs import wait_job
from maalimbus.replay import blank_replay as Offline
from recognition import LimbusRecognition,Journal


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'))
    controller=Offline();wait_job(controller.post_connection())
    tasker=Tasker();assert tasker.bind(resource,controller)
    class Context:
        def run_recognition_direct(self,kind,params,image):
            job=tasker.post_recognition(kind,params,image);wait_job(job)
            return job.get().nodes[-1].recognition
    out=ROOT/'build/actual-agent-map-replay-20261012';out.mkdir(exist_ok=True)
    rows=[]
    # Previously the GUI observer raised NameError only when caption recovery hit.
    for name in ('frame-0008','frame-0014','frame-0015'):
        path=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-111430'/(name+'.png')
        pixels=cv2.imread(str(path));assert pixels is not None
        observer=LimbusRecognition('en',Journal(out/name))
        records,scene,frame=observer.observe(Context(),pixels)
        local=json.loads((out/name/(frame+'.json')).read_text(encoding='utf-8'))
        rows.append(dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         scene=scene,local_ocr=local.get('local_ocr'),callback_error=observer.callback_failure))
        assert observer.callback_failure is None
    (out/'verification.json').write_text(json.dumps(dict(passed=True,rows=rows,device_input=False,
        observer='actual LimbusRecognition.observe',controller='offline'),indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,scenes=[r['scene'] for r in rows],device_input=False)))

if __name__=='__main__':main()
