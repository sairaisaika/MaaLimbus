"""Reconcile one already-sent initial GET ack to its independently proven successor."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.initial_gifts import receipt_name
from maalimbus.vision import Text


def main():
    directory=ROOT/'evidence/runtime/window-20261009-011246'
    result=read_json(ROOT/'build/team-seven-initial-receipt-live.json')
    path=ROOT/'config/user-initial-transaction.json';tx=read_json(path)
    ledger=read_json(ROOT/'config/user-run-ledger.json')
    assert tx['scope']==ledger['active']['id']==result['run_ledger']['run']
    assert ledger['active']['team']==7 and tx['keyword']=='rupture'
    assert tx['selected']==[dict(row=1,title='Barbed Lasso'),dict(row=2,title='Fluorescent Lamp')]
    pending=tx['receipt_pending'];assert pending['title']=='Fluorescent Lamp'
    assert Path(pending['proof']).resolve()==(directory/'frame-0003.json').resolve()
    assert result['clicks_sent']==3
    for step in result['steps']:
        assert step['clicks_sent']==1
        x,y,w,h=step['plan']['target'];px,py=step['click_point']
        assert x<=px<x+w and y<=py<y+h
        assert 350<=step['delay_ms']<=750
    step=result['steps'][-1]
    assert step['page_before']=='GIFT_GET' and step['reason']=='initial_gift_receipt_successor_not_proven'
    def frame(path):
        v=read_json(path);assert hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()==v['image_sha256']
        return v,[Text(t['text'],tuple(t['box']),t['score']) for t in v['ocr']]
    receipts=[]
    for n,title in [(2,'Barbed Lasso'),(3,'Fluorescent Lamp')]:
        p=directory/f'frame-{n:04}.json';v,r=frame(p)
        assert v['scene']=='GIFT_GET' and receipt_name(r,v['size'])==title
        receipts.append(dict(title=title,proof=str(p),image_sha256=v['image_sha256']))
    current=ROOT/'evidence/runtime/window-20261009-011334/frame-0001.json'
    v,r=frame(current);assert v['scene']=='GIFT_SEARCH'
    for title in ('E.G.O Gift Search','Selected E.G.O Gift','Refuse Gift','0/3'):
        assert sum(t.text==title and t.score>=.9 for t in r)==1
    assert read_json(ROOT/'build/team-seven-after-initial-current-readonly.json')['clicks_sent']==0
    tx.setdefault('acknowledged',[]).append(dict(title=pending['title'],receipt=pending['proof'],successor=str(current)))
    tx['receipt_pending']=None
    write_json(path,tx)
    write_json(ROOT/'build/team-seven-initial-receipts-real-verification.json',dict(scope=tx['scope'],team=7,
        receipts=receipts,successor=str(current),successor_hash=v['image_sha256'],
        completed_already_sent_ack=True,device_input=False,floor_clear=False))
    print('Two named GET receipts and independently proven search successor; no repeated ack/input')


if __name__=='__main__':main()
