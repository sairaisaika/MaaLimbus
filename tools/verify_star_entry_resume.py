"""Read-only audit of the once-only Team7 starlight continuation; no controller."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify():
    scope='4734bfe68803421c8d261dccbc9120be'
    records=[]
    reports=['star-priority-resume-live.json','star-priority-confirm-live.json']
    sessions=['window-20261008-235225','window-20261008-235347']
    for name,session in zip(reports,sessions):
        report=json.loads((ROOT/'build'/name).read_text())
        assert report['controller']=='Maa AdbController'
        for s in report['steps']:
            before=s['observation']
            png=ROOT/'evidence/runtime'/session/(before['frame']+'.png')
            assert sha(png)==before['image_sha256']
            if s.get('clicks_sent'):
                assert s['clicks_sent']==1 and 350<=s['delay_ms']<=750
                x,y,w,h=s['plan']['target'];px,py=s['click_point']
                assert x<=px<x+w and y<=py<y+h
                records.append(dict(page=s['page_before'],reason=s['reason'],card=(s.get('graces') or {}).get('card'),
                    available=(s.get('graces') or {}).get('available'),target=s['plan']['target'],
                    point=s['click_point'],delay_ms=s['delay_ms'],before_png=str(png),before_sha256=sha(png)))
            if s.get('settled'):
                after=s['settled'];p=ROOT/'evidence/runtime'/session/(after['frame']+'.png')
                assert sha(p)==after['image_sha256']
    assert len(records)==6
    assert [r['card'] for r in records[:4]]==[2,4,5,7]
    assert [r['available'] for r in records[:4]]==[116,106,86,56]
    confirm=json.loads((ROOT/'build'/reports[1]).read_text())
    assert confirm['steps'][0]['graces']['conversion']=='unchecked'
    assert confirm['steps'][0]['graces']['cost']==0
    assert confirm['steps'][-1]['page_before']=='INITIAL_GIFTS' and confirm['steps'][-1]['clicks_sent']==0
    transaction=json.loads((ROOT/'config/user-grace-transaction.json').read_text())
    assert transaction['scope']==scope and transaction['selected']==[2,4,5,7]
    assert transaction['spent']==100 and transaction['available']==16 and transaction['pending'] is None
    ledger=ROOT/'config/user-run-ledger.json'
    assert sha(ledger)=='860b8fbdc16bb119684b3d64425b7062f8fc8e0602ca8d759f8c51d2048cc217'
    result=dict(scope=scope,team=7,selected=[2,4,5,7],spent=100,available=16,conversion=False,
        successor='INITIAL_GIFTS',inputs=records,ledger_sha256=sha(ledger),verified_floor_clear=False,
        game_input_sent=False)
    (ROOT/'build/star-entry-resume-real-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'}))
if __name__=='__main__':verify()
