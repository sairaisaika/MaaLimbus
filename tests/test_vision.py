import json
from pathlib import Path

import pytest

from maalimbus.vision import Text, classify, inset_box


LOCALES = Path(__file__).resolve().parents[1] / 'assets/resource'


def test_gift_receipt_vetoes_underlying_initial_page_and_requires_confirm():
    words=json.loads((LOCALES/'en/locale.json').read_text())
    records=[Text('E.G.O Gift GET!',(430,240,150,30),.99),
             Text('Confirm',(465,730,80,25),.99),
             Text('Selected E.G.O Gift',(620,210,150,25),.99),
             Text('Refuse Gift',(640,805,90,30),.99),Text('2/2',(878,805,35,30),.99)]
    assert classify(records,words,(1000,1000))=='GIFT_GET'
    assert classify([r for r in records if r.text!='Confirm'],words,(1000,1000))=='UNKNOWN_DIALOG'


def test_gift_search_has_separate_scene_and_modal_veto():
    words=json.loads((LOCALES/'en/locale.json').read_text())
    records=[Text('E.G.O Gift Search',(110,40,160,35),.99),Text('0/3',(870,800,35,30),.99)]
    assert classify(records,words,(1000,1000))=='GIFT_SEARCH'
    assert classify(records+[Text('Cancel',(400,630,80,30),.99)],words,(1000,1000))=='UNKNOWN_DIALOG'
    assert classify(records+[Text('E.G.O Gift GET!',(430,240,150,30),.99),
        Text('Confirm',(465,730,80,25),.99)],words,(1000,1000))=='GIFT_GET'


@pytest.mark.parametrize('locale,mirror,inferno,enter,exploring', [
    ('en', 'Mirror', 'Inferno', 'Enter', 'Before Entry'),
    ('jp', '鏡ダンジョン', '地獄', '入場', '探索状況'),
])
def test_stable_words_and_position_ignore_artwork_and_values(locale, mirror, inferno, enter, exploring):
    words = json.loads((LOCALES / locale / 'locale.json').read_text(encoding='utf-8'))
    drive = [Text(mirror, (300, 400, 100, 30), .99), Text(inferno, (820, 100, 100, 40), .99)]
    assert classify(drive, words, (1000, 1000)) == 'DRIVE'
    entry = [Text(enter, (830, 680, 80, 35), .99), Text(exploring, (760, 160, 100, 30), .99), Text('7498', (800, 70, 100, 30), .99)]
    assert classify(entry, words, (1000, 1000)) == 'MIRROR_ENTRY'
    assert classify(entry[:-1], words, (1000, 1000)) == 'MIRROR_ENTRY'
    assert classify([Text(enter, (100, 100, 80, 35), .99)], words, (1000, 1000)) == 'UNKNOWN'


def test_resource_dialog_wins_over_menu():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    records = [Text('Mirror', (300, 400, 100, 30), .99), Text('Inferno', (820, 100, 100, 40), .99), Text('Purchase Lunacy', (400, 400, 200, 40), .99)]
    assert classify(records, words, (1000, 1000)) == 'RESOURCE_DIALOG'


def test_retained_drive_truncated_menu_needs_independent_heading():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    records = [Text('Mirro', (300, 400, 100, 30), .92), Text('Inferno', (820, 100, 100, 40), .99)]
    assert classify(records, words, (1000, 1000)) == 'DRIVE'
    assert classify(records[:1], words, (1000, 1000)) == 'UNKNOWN'
    assert classify([Text('MIRROR OF', (300, 400, 100, 30), .99), records[1]], words, (1000, 1000)) == 'UNKNOWN'


def test_box_inset_always_remains_inside_recognition():
    for width in (1, 2, 5, 100):
        x, y, w, h = inset_box((10, 20, width, width))
        assert 10 <= x < x + w <= 10 + width
        assert 20 <= y < y + h <= 20 + width


def test_tutorial_and_incomplete_modal_veto_underlying_enter():
    words=json.loads((LOCALES/'en/locale.json').read_text())
    underneath=[Text('Enter',(830,680,80,35),.99),Text('Before Entry',(760,160,100,30),.99)]
    # Live proof (evidence/runtime/window-20261006-023714/frame-0001.json): this
    # overlay shows the entry page and its sentence underneath, and the click on
    # Enter did nothing, so the tutorial veto has to keep winning.
    assert classify(underneath+[Text('Select the door',(630,510,180,30),.99)],words,(1000,1000))=='TUTORIAL'
    prompt=Text('Will you enter Anything?',(330,460,300,30),.99)
    cancel=Text('Cancel',(370,650,80,30),.99)
    confirm=Text('Enter',(580,650,80,30),.99)
    assert classify(underneath+[prompt,cancel,confirm],words,(1000,1000))=='ENTRY_CONFIRM'
    for incomplete in ([prompt,confirm],[cancel,confirm],[prompt,cancel]):
        assert classify(underneath+incomplete,words,(1000,1000))=='UNKNOWN_DIALOG'
