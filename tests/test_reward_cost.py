import copy,json
from pathlib import Path
import pytest
from maalimbus.reward_cost import page_anchors,combine_evidence
from maalimbus.vision import Text

FRAME=Path(__file__).resolve().parents[1]/'evidence/runtime/window-20261008-144554/frame-0458.json'

def readings():
    return [dict(purpose=purpose,results=[dict(score=score,**extra)])
        for purpose,score,extra in [('currency',.99,{}),('deduction',.99,{}),
            ('cost_digit_a',.99,dict(text='6')),('cost_digit_b',.99,dict(text='6')),
            ('weekly_count',.99,dict(text='1/3'))]]

def test_real_page_and_consistent_evidence_only_prove_offer():
    data=json.loads(FRAME.read_text());records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
    assert page_anchors(records,data['size'])
    assert combine_evidence(readings())==dict(currency='enkephalin_modules',cost=6,weekly=1)

@pytest.mark.parametrize('purpose',['currency','deduction','cost_digit_a','cost_digit_b','weekly_count'])
def test_missing_low_confidence_duplicate_results_refuse(purpose):
    rows=readings();index=next(i for i,r in enumerate(rows) if r['purpose']==purpose)
    for change in ('missing','low','duplicate'):
        changed=copy.deepcopy(rows)
        if change=='missing':changed.pop(index)
        if change=='low':changed[index]['results'][0]['score']=.89
        if change=='duplicate':changed[index]['results']*=2
        assert combine_evidence(changed) is None

@pytest.mark.parametrize('text',['18','0','-6','6?'])
def test_disagreement_or_invalid_digit_never_implies_cost(text):
    rows=readings();rows[3]['results'][0]['text']=text
    assert combine_evidence(rows) is None

@pytest.mark.parametrize('title',['Exploration Reward','Floor 5','To Window','Claim','Weekly','Bonuses'])
def test_missing_independent_page_anchor_refuses(title):
    data=json.loads(FRAME.read_text());records=[Text(t['text'],tuple(t['box']),t['score'])
        for t in data['ocr'] if t['text']!=title]
    assert not page_anchors(records,data['size'])
