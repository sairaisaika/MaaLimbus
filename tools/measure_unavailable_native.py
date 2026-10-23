"""Read retained HP zero independently, without a device."""
import pathlib as _pathlib
import sys as _sys
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / 'src'))
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
image=cv2.imread(str(ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-180805/frame-0198.png'))
def native(kind,params,image):
    job=t.post_recognition(kind,params,image);wait_job(job);return job.get().nodes[-1].recognition
rows=[]
for roi in [(704,1020,25,32),(706,1021,21,30),(702,1018,29,36),(708,1022,18,29)]:
    d=native(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,threshold=.9),image)
    rows.append(dict(roi=roi,results=[dict(text=x.text,score=x.score) for x in d.all_results] if d else []))
print(json.dumps(rows))
from maalimbus.deployment_availability_native import read_availability
from maalimbus.vision import Text
from maalimbus.storage import write_json
from maalimbus.deployment_transaction import DeploymentTransaction
import tempfile,hashlib
source=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-180805/frame-0198.json'
record=json.loads(source.read_text(encoding='utf-8'))
texts=[Text(x['text'],tuple(x['box']),x['score']) for x in record['ocr']]
anchors=json.loads((ROOT/'assets/resource/base/anchors.json').read_text(encoding='utf-8'))
def entries(value):
    if isinstance(value,dict):
        if 'id' in value and 'verified_on' in value:yield value
        for x in value.values():yield from entries(x)
    elif isinstance(value,list):
        for x in value:yield from entries(x)
boxes={v['id']:v['verified_on']['box'] for v in entries(anchors)}
boxes=[boxes['pre_battle.card_%02d'%i] for i in range(1,13)]
proof=read_availability(native,image,texts,boxes)[0]
assert proof['accepted'] and proof['unavailable']==[6],proof
masked=image.copy();masked[1014:1060,700:739]=0
negative=read_availability(native,masked,texts,boxes)[0]
assert not negative['accepted']
wrong=[Text('0 / 12',x.box,x.score) if '/' in x.text and x.box[0]>=1680 else x for x in texts]
assert read_availability(native,image,wrong,boxes)==[]
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'tx.json';p.write_bytes((ROOT/'config/user-deployment-transaction.json').read_bytes())
    tx=DeploymentTransaction(p);proof.update(frame=str(source),image_sha256=record['image_sha256'])
    tx.reconcile_unavailable(record.get('scope') or tx.data['scope'],(0,11),[6],proof)
    order=[6,2,4,9,12,7,11,10,3,1,8,5]
    result=tx.prepare(tx.data['scope'],order,(0,11),unavailable=[6],availability_proof=proof)
    assert result['order']==order[1:] and tx.data['saved_order']==order
write_json(ROOT/'build/deployment-unavailable-native-verification.json',dict(passed=True,
    before_png_sha256=hashlib.sha256(source.with_suffix('.png').read_bytes()).hexdigest(),
    proof=proof,masked_hp_refused=True,capacity_alone_refused=True,isolated_pending_recovery=True,
    actual_transaction_unchanged=True,device_input=False))
