"""Offline native counter crops on the retained seven-sinner planning HUD."""
import sys,json
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.pipeline import JOCR,JRecognitionType
from maalimbus.jobs import wait_job
from verify_sinner_neural_native import Offline
Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
r=Resource();wait_job(r.post_bundle(ROOT/'assets/resource/base'))
c=Offline();wait_job(c.post_connection());t=Tasker();assert t.bind(r,c)
image=cv2.imread(str(ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-180805/frame-0109.png'))
rows=[]
for roi in [(68,90,82,40),(94,90,40,42),(95,90,38,42),(94,91,40,40),(94,92,40,39),(93,89,42,43)]:
    job=t.post_recognition(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,threshold=.9),image);wait_job(job)
    detail=job.get().nodes[-1].recognition
    rows.append(dict(roi=roi,results=[dict(text=x.text,score=x.score) for x in detail.all_results] if detail else []))
(ROOT/'build/turn-seven-native-measurement.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows))
from maalimbus.battle_counter_native import repair_turn
from maalimbus.battle_vision import battle_hud,start_button
from maalimbus.vision import Text
source=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-180805/frame-0109.json'
original=json.loads(source.read_text(encoding='utf-8'))
records=[Text(x['text'],tuple(x['box']),x['score']) for x in original['ocr']]
def native(kind,params,image):
    job=t.post_recognition(kind,params,image);wait_job(job);return job.get().nodes[-1].recognition
fixed,proof=repair_turn(native,image,records)
assert battle_hud(fixed,[1920,1080])['turn']=='7'
assert start_button(fixed,[1920,1080],image) is None # still unassigned, no guessed START
masked=image.copy();masked[85:140,65:155]=0
negative,_=repair_turn(native,masked,records)
assert battle_hud(negative,[1920,1080]) is None
from maalimbus.storage import write_json
write_json(ROOT/'build/turn-seven-native-repair-verification.json',dict(passed=True,turn='7',
    proof=proof,masked_digit_refused=True,dim_start_refused=True,device_input=False))
