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


@pytest.mark.parametrize('missing',['Field','Base Power +1, Max HP','+2.5%','0/2'])
def test_missing_title_suffix_or_trial_cannot_be_ignored(missing):
    records,catalog=fixture()
    with pytest.raises(ValueError):observe([r for r in records if r.text!=missing],(1920,1080),catalog)


def test_unknown_title_suffix_and_unknown_coin_power_stop():
    records,catalog=fixture()
    for original,replacement in [('Field','Secret Variant'),('Base Power +1, Max HP','Coin Power +1, Max HP')]:
        changed=[Text(replacement,r.box,r.score) if r.text==original else r for r in records]
        with pytest.raises(ValueError):observe(changed,(1920,1080),catalog)
