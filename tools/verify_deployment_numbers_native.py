"""Replay printed deployment digits with native OCR; never a game controller."""
import json,sys,hashlib
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.pipeline import JRecognitionType,JOCR
from verify_sinner_neural_native import Offline
from maalimbus.jobs import wait_job
from maalimbus.deployment_numbers_native import read_assignments
from maalimbus.team_vision import assignment_numbers,carries_saved_order
from maalimbus.runner import REGISTRY,controls_by_id
from maalimbus.vision import Text


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'))
    controller=Offline();wait_job(controller.post_connection())
    tasker=Tasker();assert tasker.bind(resource,controller)
    frame=ROOT/'evidence/runtime/packaged-mirror-20261012-101555/frame-0027.json'
    data=json.loads(frame.read_text(encoding='utf-8'));image=cv2.imread(str(frame.with_suffix('.png')))
    def native(kind,param,pixels):
        job=tasker.post_recognition(kind,param,pixels);wait_job(job)
        return job.get().nodes[-1].recognition
    controls=controls_by_id(json.loads(REGISTRY.read_text(encoding='utf-8')))
    boxes=[controls['pre_battle.card_%02d'%i] for i in range(1,13)]
    original=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
    fixed,rows=read_assignments(native,image,original,boxes)
    numbers=assignment_numbers(fixed,boxes,data['size'],threshold=.9)
    order=[6,2,4,9,12,7,11,10,3,1,8,5]
    assert carries_saved_order(numbers,order,(12,12))
    masked=image.copy();masked[580:648,815:880]=0
    absent,negative=read_assignments(native,masked,original,boxes)
    absent_numbers=assignment_numbers(absent,boxes,data['size'],threshold=.9)
    assert absent_numbers[8] is None and not carries_saved_order(absent_numbers,order,(12,12))
    result=dict(frame=str(frame),image_sha256=hashlib.sha256(frame.with_suffix('.png').read_bytes()).hexdigest(),
        rows=rows,numbers=numbers,order=order,masked_negative=negative,
        masked_numbers=absent_numbers,passed=True,input_sent=False,controller='offline CustomController')
    (ROOT/'build/deployment-numbers-native-20261012.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
