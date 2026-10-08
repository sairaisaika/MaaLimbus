"""Explicit read-only reconciliation of the retained single Phantom Pain input.

Not a retry path: validates scope, durable intent, original input and both hashes.
No device connection. Only the already observed selection may be recorded.
"""
import hashlib,json,sys
from pathlib import Path
import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.floor_gifts import observe, single_free_selection_edges
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.gift_vision import GiftCatalog
from maalimbus.reward_vision import button_mean
from maalimbus.vision import Text


def main():
    directory=ROOT/'evidence/runtime/window-20261008-101324'
    result=json.loads((directory/'result.json').read_text());steps=result['steps']
    tx=FloorGiftTransaction(ROOT/'config/user-floor-gift-transaction.json')
    scope=json.loads((ROOT/'config/user-run-ledger.json').read_text())['active']['id']
    assert result['run_ledger']['run']==scope==tx.data['scope']
    assert len(steps)==1 and result['clicks_sent']==1 and steps[0]['clicks_sent']==1
    step=steps[0]
    assert step['reason']=='three_free_gift_outline_ambiguous'
    assert step['page_before']==step['page_after']=='GIFT_PICK'
    assert step['plan']['reason']=='the_floor_gift_card_must_be_picked_before_select'
    assert tx.data['pending']['kind']=='pick' and tx.data['pending']['title']=='Phantom Pain'
    assert Path(tx.data['pending']['proof']).resolve()==(directory/'frame-0001.json').resolve()
    catalog=GiftCatalog(ROOT/'assets/resource/base');proofs=[];observed=[]
    for index,record in ((1,step['observation']),(2,step['settled'])):
        path=directory/f'frame-{index:04}.json';data=json.loads(path.read_text())
        png=path.with_suffix('.png');sha=hashlib.sha256(png.read_bytes()).hexdigest()
        assert sha==data['image_sha256']==record['image_sha256']
        image=cv2.imread(str(png));records=[Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']]
        offers,count=observe(records,data['size'],catalog,image=image,select_box=(1620,851,100,36))
        assert offers[2].title=='Phantom Pain' and count==dict(chosen=index-1,required=1)
        observed.append((offers,count))
        proofs.append(dict(frame=str(path),sha256=sha,selection=count,
                           button_mean=button_mean(image,(1620,851,100,36)),
                           outline=single_free_selection_edges(image,offers[2].box,data['size'],bottom_span=110)))
    x,y,w,h=observed[0][0][2].box;px,py=step['click_point']
    assert step['plan']['target']==[x,y,w,h] and x<=px<x+w and y<=py<y+h
    assert tx.signature(observed[0][0])==tx.data['offer']==tx.signature(observed[1][0])
    tx.observe_pick(*observed[1],directory/'frame-0002.json')
    output=ROOT/'build/phantom-pain-selection-real-verification-20261008.json'
    output.write_text(json.dumps(dict(scope=scope,real_selection_verified=True,device_input=False,
        acquisition_verified=False,proofs=proofs,original_input=str(directory/'result.json')),indent=2)+'\n')
    print(output)


if __name__=='__main__':main()
