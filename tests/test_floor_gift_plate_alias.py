"""Native complete-caption i/l confusion must not merge neighbouring trials."""
import json
from pathlib import Path
from dataclasses import replace
import pytest
from maalimbus.vision import Text
from maalimbus.reward_vision import gift_cards
from maalimbus.floor_gifts import observe
from maalimbus.gift_vision import GiftCatalog
ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-174217/frame-0084.json'


def test_actual_four_cards_preserve_four_separate_trial_bindings():
    if not FRAME.exists():pytest.skip('Local actual frame unavailable')
    frame=json.loads(FRAME.read_text(encoding='utf-8'))
    rows=[Text(r['text'],tuple(r['box']),r['score']) for r in frame['ocr']]
    assert len(gift_cards(rows,frame['size']))==4
    offers,counter=observe(rows,frame['size'],GiftCatalog(ROOT/'assets/resource/base'))
    assert [o.title for o in offers]==['Cantabile','Thorny Path','Rebate Token','Oracle']
    assert [o.trial.level for o in offers]==[2,1,2,2]
    assert offers[0].unpriced=='Final Power +1, Max HP +5%'
    assert counter=={'chosen':0,'required':2}
    wrong=[replace(r,text='E.G.O Glft') if r.text=='Acqulre E.G.O Glft' else r for r in rows]
    with pytest.raises(ValueError):observe(wrong,frame['size'],GiftCatalog(ROOT/'assets/resource/base'))
