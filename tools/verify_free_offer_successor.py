"""Explicit reconciliation of an already acknowledged GET to a proven free offer."""
import json,hashlib,sys,cv2
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.floor_gifts import observe
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.gift_vision import GiftCatalog
from maalimbus.initial_gifts import receipt_name
from maalimbus.vision import Text


def main():
    directory=ROOT/'evidence/runtime/window-20261008-100819'
    result=json.loads((directory/'result.json').read_text());step=result['steps'][-1]
    tx=FloorGiftTransaction(ROOT/'config/user-floor-gift-transaction.json');pending=tx.data['pending']
    ledger=json.loads((ROOT/'config/user-run-ledger.json').read_text())
    assert tx.data['scope']==ledger['active']['id']==result['run_ledger']['run']
    assert pending['kind']=='receipt' and pending['title']=='Material Interference Force Field'
    assert Path(pending['proof']).resolve()==(directory/'frame-0004.json').resolve()
    assert step['page_before']=='GIFT_GET' and step['page_after']=='GIFT_PICK' and step['clicks_sent']==1
    assert step['reason']=='floor_gift_receipt_successor_not_proven'
    assert step['plan']['reason']=='the_gift_get_notice_is_cleared_with_its_own_confirm'
    x,y,w,h=step['plan']['target'];px,py=step['click_point']
    assert x<=px<x+w and y<=py<y+h
    frames=[]
    for index,record in ((4,step['observation']),(5,step['settled'])):
        path=directory/f'frame-{index:04}.json';data=json.loads(path.read_text())
        assert hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()==data['image_sha256']==record['image_sha256']
        frames.append((path,data,[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]))
    assert receipt_name(frames[0][2],frames[0][1]['size'])==pending['title']
    path,data,records=frames[1]
    offers,count=observe(records,data['size'],GiftCatalog(ROOT/'assets/resource/base'),image=cv2.imread(str(path.with_suffix('.png'))),select_box=(1620,851,100,36))
    assert count==dict(chosen=0,required=1) and all(o.selection_source=='three_free_select_button' for o in offers)
    tx.observe_receipt('GIFT_PICK',None,path,next_free_offer=dict(count=count,source=offers[0].selection_source,offer=tx.signature(offers)))
    output=ROOT/'build/floor-three-extra-offer-real-verification-20261008.json'
    output.write_text(json.dumps(dict(scope=tx.data['scope'],receipt=pending['proof'],successor=str(path),device_input=False,
        completed_prior_receipts=True,floor_clear_verified=False,next_titles=[o.title for o in offers]),indent=2)+'\n');print(output)


if __name__=='__main__':main()
