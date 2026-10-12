import json
from pathlib import Path
import pytest
from maalimbus.floor_gifts import observe,rank
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text

ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'evidence/runtime/window-20261008-100508/frame-0004.json'


def fixture():
    data=json.loads(FRAME.read_text())
    return [Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']],GiftCatalog(ROOT/'assets/resource/base')


def test_actual_complete_wrapped_title_and_base_power_trial():
    records,catalog=fixture();offers,count=observe(records,(1920,1080),catalog)
    assert count==dict(chosen=0,required=2)
    assert offers[2].title=='Material Interference Force Field'
    assert offers[1].trial.components==(('base_power',1),('hp',2.5))
    ranking=rank(offers,Team(2,frozenset({'Charge','Tremor'})),[])
    assert [r['score'] for r in ranking]==[65,75,97.5,242.5]
    assert [r['title'] for r in ranking[:2]]==['Material Interference Force Field','Midwinter Nightmare']


@pytest.mark.parametrize('missing',['Field','0/2'])
def test_missing_title_suffix_or_counter_cannot_be_ignored(missing):
    records,catalog=fixture()
    with pytest.raises(ValueError):observe([r for r in records if r.text!=missing],(1920,1080),catalog)


@pytest.mark.parametrize('missing',['Base Power +1, Max HP','+2.5%'])
def test_a_trial_that_lost_a_fragment_is_carried_and_never_chosen(missing):
    records,catalog=fixture()
    offers,_=observe([r for r in records if r.text!=missing],(1920,1080),catalog)
    carried=[o for o in offers if o.unpriced]
    assert len(carried)==1 and carried[0].unpriced
    assert all(r['title']!=carried[0].title
               for r in rank(offers,Team(2,frozenset({'Charge','Tremor'})),[]))


def test_an_unknown_title_stops_while_unknown_trial_text_is_carried():
    records,catalog=fixture()
    unknown_title=[Text('Secret Variant',r.box,r.score) if r.text=='Field' else r for r in records]
    with pytest.raises(ValueError,match='identity_unknown'):
        observe(unknown_title,(1920,1080),catalog)
    unknown_trial=[Text('Coin Power +1, Max HP',r.box,r.score) if r.text=='Base Power +1, Max HP' else r
                   for r in records]
    offers,_=observe(unknown_trial,(1920,1080),catalog)
    carried=[o.unpriced for o in offers if o.unpriced]
    assert len(carried)==1 and 'Coin Power +1, Max HP' in carried[0]
