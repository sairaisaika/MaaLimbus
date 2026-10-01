import json
from pathlib import Path

import pytest

from maalimbus.deployment import CENTERS,counts,deployment_page,observe_deployment,next_sinner,target_box
from maalimbus.policies import Team
from maalimbus.storage import SINNERS
from maalimbus.vision import Text,classify

ROOT=Path(__file__).resolve().parents[1]


def records(order=(),capacity=6):
    items=[Text('Details',(1060,90,90,25),.99),Text(f'{len(order)}/{capacity}',(1135,515,70,25),.99)]
    for index,name in enumerate(order,1):
        x,y=CENTERS[name];items.append(Text(str(index),(x-10,y-70,20,24),.99))
    return items


def test_adaptive_count_and_order_plan_including_resume():
    team=Team(2,frozenset(),deployment=tuple(reversed(SINNERS)))
    for capacity in (1,6,12):
        for selected in range(capacity+1):
            state=observe_deployment(records(team.deployment[:selected],capacity),(1280,720))
            assert state.order==team.deployment[:selected]
            assert next_sinner(state,team)==(('select',team.deployment[selected]) if selected<capacity else ('complete',None))
    assert next_sinner(observe_deployment(records(('Faust',)),(1280,720)),team)==('stop',None)
    assert next_sinner(observe_deployment(records(),(1280,720)),Team(1,frozenset()))==('stop',None)


@pytest.mark.parametrize('text',['','0/0','13/12','11/5','0/13','six/6','0/6 1/6'])
def test_counter_never_falls_back_to_zero_one(text):
    assert counts([Text(text,(1135,515,70,25),.99)],(1280,720)) is None


def test_duplicate_missing_low_confidence_badges_refused():
    good=records(('Yi Sang','Faust'))
    assert observe_deployment(good,(1280,720)) is not None
    assert observe_deployment(good[:-1],(1280,720)) is None
    assert observe_deployment(good+[good[-1]],(1280,720)) is None
    wrong=[*good[:-1],Text('1',good[-1].box,.99)]
    assert observe_deployment(wrong,(1280,720)) is None
    assert counts([Text('0/6',(1135,515,70,25),.7)],(1280,720)) is None
    assert counts([good[1],good[1]],(1280,720)) is None


def test_positions_scale_and_library_resource_priority():
    words=json.loads((ROOT/'assets/resource/en/locale.json').read_text())
    assert deployment_page(records(),words,(1280,720))
    scaled=[Text(t.text,tuple(round(v*1.5) for v in t.box),t.score) for t in records(('Yi Sang',))]
    assert observe_deployment(scaled,(1920,1080)).order==('Yi Sang',)
    x,y,w,h=target_box('Gregor',(1920,1080))
    assert x<1410<x+w and y<660<y+h and w<54 and h<54
    assert not deployment_page(records(),words,(1280,800))
    japanese=json.loads((ROOT/'assets/resource/jp/locale.json').read_text(encoding='utf-8'))
    assert deployment_page([Text('詳細',(1060,90,90,25),.99),records()[1]],japanese,(1280,720))
    paid=[*records(),Text('Purchase Lunacy',(450,320,240,40),.99)]
    assert classify(paid,words,(1280,720))=='RESOURCE_DIALOG'
    library=[*records(),Text('TEAMS',(90,180,95,30),.99),Text('SIN COST',(1080,90,100,20),.99)]
    assert classify(library,words,(1280,720))=='TEAM_LIBRARY'
