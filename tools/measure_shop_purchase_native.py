"""Read actual purchase balance crops through Maa, offline and without input."""
import pathlib as _pathlib
import sys as _sys
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / 'src'))
import json,sys
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'agent')]
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.pipeline import JOCR,JRecognitionType
from maalimbus.jobs import wait_job
from maalimbus.replay import blank_replay as Offline
Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
r=Resource();wait_job(r.post_bundle(ROOT/'assets/resource/base'))
c=Offline();wait_job(c.post_connection());t=Tasker();assert t.bind(r,c)
p=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-170045/frame-0239.png'
im=cv2.imread(str(p));assert im is not None
rows=[]
for roi in ((1230,236,53,34),(1228,234,59,39),(1305,235,57,35),(1303,233,61,40),
            (1287,239,18,27)):
    job=t.post_recognition(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,threshold=.9),im)
    wait_job(job);d=job.get().nodes[-1].recognition
    rows.append(dict(roi=roi,results=[dict(text=x.text,score=x.score) for x in d.all_results] if d else []))
print(json.dumps(rows))
(ROOT/'build/shop-purchase-native-measurement.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
from recognition import LimbusRecognition,Journal
from maalimbus.shop_vision import matching_purchase_question
from maalimbus.shop_transaction import ShopTransaction
from maalimbus.storage import read_json,write_json
import shutil,hashlib,copy
class Context:
    def run_recognition_direct(self,kind,params,image):
        job=t.post_recognition(kind,params,image);wait_job(job)
        return job.get().nodes[-1].recognition
out=ROOT/'build/shop-purchase-dialog-native-replay';out.mkdir(exist_ok=True)
reader=LimbusRecognition('en',Journal(out));records,scene,name=reader.observe(Context(),im)
assert scene=='SHOP_PURCHASE'
assert matching_purchase_question(records,"Devil's Share",144,[1920,1080],coins=2707)==[1092,706,128,34]
assert matching_purchase_question(records,"Devil's Share",145,[1920,1080],coins=2707) is None
assert matching_purchase_question(records,'Prestige Card',144,[1920,1080],coins=2707) is None
from maalimbus.shop_native import repair_purchase_balances
masked=im.copy();masked[232:275,1300:1370]=0
raw=[x for x in records if x.text not in ('2707','2563')]
negative,proof=repair_purchase_balances(Context().run_recognition_direct,masked,raw)
assert matching_purchase_question(negative,"Devil's Share",144,[1920,1080],coins=2707) is None
source=ROOT/'config/user-shop-f855ac82c2b1429aae9c747a122213b8.json'
before_sha=hashlib.sha256(source.read_bytes()).hexdigest()
clone=out/'isolated-transaction.json';shutil.copyfile(source,clone)
tx=ShopTransaction(clone)
assert tx.reserve_confirm(tx.data['scope'],tx.data['current_visit'],out/(name+'.json'))==[1092,706,128,34]
try:tx.reserve_confirm(tx.data['scope'],tx.data['current_visit'],out/(name+'.json'))
except ValueError:pass
else:raise AssertionError('Second Purchase intent must refuse')
assert hashlib.sha256(source.read_bytes()).hexdigest()==before_sha
write_json(out/'verification.json',dict(passed=True,scene=scene,quote_before=2707,quote_after=2563,price=144,
    matched_name="Devil's Share",source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    private_transaction_unchanged=True,device_input=False,repeat_purchase_refused=True,
    negatives=['changed_price','changed_title','masked_after_balance']))
print(json.dumps(dict(passed=True,actual_agent_observer=True,device_input=False)))
