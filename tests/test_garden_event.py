import json
from pathlib import Path
import pytest
from maalimbus.event_vision import (choice_options, garden_refusal_choice,
                                    refusal_choice)

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


def test_ocr_quote_variation_keeps_complete_words_required():
    d=json.loads(FRAME.read_text())
    altered=[dict(t,text=t['text'].replace('flowers."',"flowers.'")) for t in d['ocr']]
    assert garden_refusal_choice(altered,d['size'],choice_options(altered,d['size']))==0
    altered=[dict(t,text=t['text'].replace('full of flowers.', 'full of')) for t in altered]
    with pytest.raises(ValueError):garden_refusal_choice(altered,d['size'],choice_options(altered,d['size']))


def test_a_page_with_its_own_decline_row_is_answerable_without_a_name():
    """Live ``packaged-mirror-20261022-013228`` met an unnamed shoes event and stopped.

    The event's name is not what makes declining safe: the page prints ``Refuse.``.
    """
    size=(1920,1080)
    rows=[{'text':'Choices','box':(1090,190,170,40),'score':.95},
          {'text':'Put on the shoes.','box':(1090,280,610,80),'score':.96},
          {'text':'Refuse.','box':(1090,420,610,80),'score':.96}]
    options=choice_options(rows,size)
    assert [text for _,text in options]==['Put on the shoes.','Refuse.']
    assert refusal_choice(rows,size,options)==1


def test_two_declining_rows_or_none_are_not_guessed():
    size=(1920,1080)
    two=[{'text':'Choices','box':(1090,190,170,40),'score':.95},
         {'text':'Refuse.','box':(1090,280,610,80),'score':.96},
         {'text':'Decline.','box':(1090,420,610,80),'score':.96}]
    assert refusal_choice(two,size,choice_options(two,size)) is None
    none=[{'text':'Choices','box':(1090,190,170,40),'score':.95},
          {'text':'Put on the shoes.','box':(1090,280,610,80),'score':.96},
          {'text':'Keep walking.','box':(1090,420,610,80),'score':.96}]
    assert refusal_choice(none,size,choice_options(none,size)) is None
