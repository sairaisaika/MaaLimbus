import json
from pathlib import Path
import pytest
from maalimbus.floor_gifts import observe, rank
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text

ROOT = Path(__file__).resolve().parents[1]
FRAME = ROOT/'evidence/runtime/window-20261009-063605/frame-0285.json'


def records():
    data = json.loads(FRAME.read_text())
    return [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]


def test_actual_city_trial_has_no_invented_healing_or_keywords():
    catalog = GiftCatalog(ROOT/'assets/resource/base')
    offers, count = observe(records(), (1920,1080), catalog)
    assert count == dict(chosen=0, required=2)
    assert offers[1].keywords == frozenset()
    assert offers[1].visible_benefit == 0
    assert offers[1].trial.components == (('defense',3),('hp',7.5))
    ranked = rank(offers, Team(7,frozenset({'Poise','Rupture'})), [])
    assert [r['title'] for r in ranked[:2]] == ['For You Who Love the City','Smoking Gunpowder']
    assert [r['score'] for r in ranked] == [97.5,177.5,212.5,335]


@pytest.mark.parametrize('replacement', ['For You Who Love the', 'For You Who Love a City', 'For You Who Love the City II'])
def test_observed_title_requires_complete_identity(replacement):
    changed = [Text(replacement,r.box,r.score) if r.text=='For You Who Love the City' else r for r in records()]
    with pytest.raises(ValueError):
        observe(changed,(1920,1080),GiftCatalog(ROOT/'assets/resource/base'))


def test_missing_trial_amount_refuses_entire_offer():
    changed = [r for r in records() if not (r.text=='+7.5%' and r.box[0]<900)]
    with pytest.raises(ValueError):
        observe(changed,(1920,1080),GiftCatalog(ROOT/'assets/resource/base'))
