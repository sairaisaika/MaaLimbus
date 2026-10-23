"""Retained real Mounting Trials native OCR, with no device/input controller."""
import pathlib as _pathlib
import sys as _sys
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / 'src'))
import hashlib,json,sys
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from verify_sinner_neural_native import Offline
from maalimbus.jobs import wait_job
from maalimbus.vision import Text
from maalimbus.floor_trial_vision import repair_levels
from maalimbus.floor_gifts import observe
from maalimbus.gift_vision import GiftCatalog


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'))
    controller=Offline();wait_job(controller.post_connection())
    tasker=Tasker();assert tasker.bind(resource,controller)
    def native(kind,param,image):
        job=tasker.post_recognition(kind,param,image);wait_job(job)
        return job.get().nodes[-1].recognition
    path=ROOT/'evidence/runtime/packaged-mirror-20261012-043307/frame-0001.json'
    d=json.loads(path.read_text()); records=[Text(t['text'],tuple(t['box']),t['score']) for t in d['ocr']]
    image=cv2.imread(str(path.with_suffix('.png')))
    fixed,proof=repair_levels(native,image,records)
    offers,count=observe(fixed,d['size'],GiftCatalog(ROOT/'assets/resource/base'))
    assert count==dict(chosen=1,required=2) and offers[0].trial.level==1
    masked=image.copy();masked[662:714,196:264]=0
    absent,negative=repair_levels(native,masked,records)
    assert absent==records
    report=dict(passed=True,controller='offline CustomController',device_input=False,
                frame=str(path),png_sha256=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest(),
                count=count,positive=proof,masked_negative=negative)
    from maalimbus.shop_native import repair_refresh_cost
    from maalimbus.shop_vision import refreshes
    shelf=ROOT/'evidence/runtime/window-20261012-024300/frame-0173.json'
    sr=json.loads(shelf.read_text());st=[Text(t['text'],tuple(t['box']),t['score']) for t in sr['ocr']]
    si=cv2.imread(str(shelf.with_suffix('.png')))
    repaired,shop_proof=repair_refresh_cost(native,si,st)
    assert refreshes([t for t in repaired if t.score>=.9],sr['size'])['regular'].cost==15
    absent=si.copy();absent[212:262,1485:1530]=0
    unchanged,shop_negative=repair_refresh_cost(native,absent,st)
    assert unchanged==st
    report['shop_refresh']=dict(frame=str(shelf),png_sha256=hashlib.sha256(shelf.with_suffix('.png').read_bytes()).hexdigest(),
                               positive=shop_proof,masked_negative=shop_negative)
    (ROOT/'build/floor-trial-level-native-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':main()
