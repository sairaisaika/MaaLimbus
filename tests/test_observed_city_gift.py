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
def test_a_mangled_title_is_carried_under_its_own_printed_name(replacement):
    # A title the catalogue cannot confirm is no longer a stop (wiki 9.3.9): the offer
    # keeps the name the page printed as its identity and ranks with no keywords.  What
    # it must never do is stand in for the catalogued gift -- the identity stays the
    # page's own string, so a mangled title and the real one never merge.
    changed = [Text(replacement,r.box,r.score) if r.text=='For You Who Love the City' else r for r in records()]
    offers, _ = observe(changed,(1920,1080),GiftCatalog(ROOT/'assets/resource/base'))
    carried = [offer for offer in offers if offer.title == replacement]
    assert len(carried) == 1
    assert carried[0].canonical == replacement
    assert carried[0].keywords == frozenset()


def test_missing_trial_amount_refuses_entire_offer():
    changed = [r for r in records() if not (r.text=='+7.5%' and r.box[0]<900)]
    offers,_=observe(changed,(1920,1080),GiftCatalog(ROOT/'assets/resource/base'))
    assert offers[1].unpriced and offers[1].identity()['trial'] is None
    assert 'For You Who Love the City' not in [r['title'] for r in rank(offers,Team(7,frozenset({'Poise'})),[])]
