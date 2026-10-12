"""Native retained shelf replay; audit a clone, never send game input."""
import hashlib,json,sys,shutil
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'agent')]
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maalimbus.jobs import wait_job
from verify_sinner_neural_native import Offline
from recognition import LimbusRecognition,Journal
from maalimbus.shop_transaction import ShopTransaction
from maalimbus.shop_vision import offers,shelf_tokens,wanted_offers
from maalimbus.storage import write_json
Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
r=Resource();wait_job(r.post_bundle(ROOT/'assets/resource/base'))
c=Offline();wait_job(c.post_connection());t=Tasker();assert t.bind(r,c)
class Context:
    def run_recognition_direct(self,kind,params,image):
        job=t.post_recognition(kind,params,image);wait_job(job)
        return job.get().nodes[-1].recognition
out=ROOT/'build/actual-purchased-shelf-replay';out.mkdir(exist_ok=True)
source=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-173651/frame-0005.png'
image=cv2.imread(str(source));assert image is not None
reader=LimbusRecognition('en',Journal(out))
rows,scene,name=reader.observe(Context(),image)
assert scene=='SHOP'
found=offers(shelf_tokens(rows),[1920,1080])
print([(o.name,o.purchased) for o in found])
assert len(found)==6 and [o.name for o in found if o.purchased]==["Devil's Share"]
assert not wanted_offers(found,["Devil's Share"])
actual=ROOT/'config/user-shop-f855ac82c2b1429aae9c747a122213b8.json'
sha=hashlib.sha256(actual.read_bytes()).hexdigest()
clone=out/'isolated-transaction.json';shutil.copyfile(actual,clone)
tx=ShopTransaction(clone)
assert tx.reconcile_purchase(tx.data['scope'],tx.data['current_visit'],out/(name+'.json'))
assert tx.data['pending'] is None and tx.data['bought'][-1]['shelf_evidence']=='own_purchased_badge'
masked=image.copy();masked[545:595,1080:1250]=0
negrows,negscene,negname=reader.observe(Context(),masked)
shutil.copyfile(actual,clone);tx=ShopTransaction(clone);original=clone.read_bytes()
try:tx.reconcile_purchase(tx.data['scope'],tx.data['current_visit'],out/(negname+'.json'))
except ValueError:pass
else:raise AssertionError('Missing Purchased must retain pending')
assert clone.read_bytes()==original
assert hashlib.sha256(actual.read_bytes()).hexdigest()==sha
write_json(out/'verification.json',dict(passed=True,actual_shelf_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    amount_before=2707,amount_after=2563,price=144,name="Devil's Share",purchased_badge_proven=True,
    original_transaction_unchanged=True,device_input=False,masked_badge_refused=True,
    gui_receipt_completed=False))
print('passed')
