import json
from pathlib import Path
import pytest
from maalimbus.event_vision import choice_options,garden_refusal_choice

FRAME=Path(__file__).resolve().parents[1]/'evidence/runtime/window-20261009-071129/frame-0134.json'


def test_actual_garden_refusal_is_bound_to_story_and_controls():
    d=json.loads(FRAME.read_text());r=d['ocr'];size=d['size']
    assert garden_refusal_choice(r,size,choice_options(r,size))==0
    for text in ('Refuse.','Accept.','"Now, what will you do?"',
                 '"Our only wish is that our garden will bloom full of flowers."'):
        altered=[t for t in r if t['text']!=text]
        with pytest.raises(ValueError):garden_refusal_choice(altered,size,choice_options(altered,size))
    altered=[dict(t,score=.89) if t['text']=='Refuse.' else t for t in r]
    with pytest.raises(ValueError):garden_refusal_choice(altered,size,choice_options(altered,size))


def test_reversed_options_still_choose_refuse_by_label():
    d=json.loads(FRAME.read_text());options=choice_options(d['ocr'],d['size'])
    assert garden_refusal_choice(d['ocr'],d['size'],options[::-1])==1
