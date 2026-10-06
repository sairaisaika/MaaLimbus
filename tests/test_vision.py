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


def test_dungeon_progress_prompt_is_a_named_resume_page():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261006-025617/frame-0002.json is the
    # prompt an in-progress run shows when Enter is pressed again. Halt
    # Exploration would throw that run away, so the page has to be named here
    # instead of being vetoed as an unnamed dialog.
    page = [Text('Dungeon Progress', (445, 310, 120, 26), .99),
            Text('Resume', (470, 536, 62, 30), .99),
            Text('Halt Exploration', (440, 600, 140, 30), .99),
            Text('Cancel', (455, 666, 70, 28), .99)]
    assert classify(page, words, (1000, 1000)) == 'RESUME_DIALOG'
    assert classify(page[1:], words, (1000, 1000)) == 'UNKNOWN_DIALOG'


def test_encounter_reward_card_is_named_before_the_generic_dialog():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261006-034714/frame-0022.json is the
    # pick-one screen a cleared node hands back. It also carries Cancel, so the
    # generic dialog veto would swallow it; Cancel must never be the plan target.
    page = [Text('Select Encounter Reward Card', (434, 174, 734, 54), .99),
            Text('Selectable', (1326, 176, 174, 50), .99),
            Text('X Cancel', (690, 770, 150, 41), .94),
            Text('Confirm', (1130, 766, 164, 45), .99)]
    assert classify(page, words, (1920, 1080)) == 'REWARD_CARD'
    without_title = [item for item in page
                     if item.text != 'Select Encounter Reward Card']
    assert classify(without_title, words, (1920, 1080)) == 'UNKNOWN_DIALOG'


def test_the_shop_node_is_named_by_its_title_and_leave_button():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261006-042123/frame-0001.json is what
    # the "Thick Rumbling Hum" encounter panel's Enter handed back (a Shop node).
    # Leave is the only budget-safe input there, so the page has to be named
    # instead of falling into the generic dialog veto.
    page = [Text('Shop', (334, 154, 98, 54), .99),
            Text('Super Shop', (1000, 176, 128, 28), .99),
            Text('Leave', (1622, 945, 150, 53), 1.0)]
    assert classify(page, words, (1920, 1080)) == 'SHOP'
    without_leave = [item for item in page if item.text != 'Leave']
    assert classify(without_leave, words, (1920, 1080)) != 'SHOP'
    # Leaving asks first, and the shop labels stay visible behind the prompt, so
    # the question has to outrank SHOP (live: window-20261006-042529/frame-0002).
    asking = page + [Text('Leave the shop?', (846, 496, 224, 40), .99),
                     Text('Confirm', (1116, 722, 110, 34), 1.0),
                     Text('X Cancel', (706, 720, 138, 36), .94)]
    assert classify(asking, words, (1920, 1080)) == 'SHOP_LEAVE'


def test_the_cutscene_is_named_by_its_rec_badge_and_skip_button():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261006-044556/frame-0023.json is the
    # abnormality intro the floor's first node handed back. It never advanced by
    # itself, so the window has to name it and skip it instead of waiting.
    page = [Text('A thing wearing human skin was dancing in place, clicking and',
                 (108, 504, 738, 36), .99),
            Text('Clopping like a spider, it talks to me', (114, 611, 422, 28), .99),
            Text('00:00:02:12', (124, 194, 126, 22), .999),
            Text('REC', (870, 192, 64, 28), 1.0),
            Text('SKIP', (1620, 919, 152, 99), 1.0)]
    assert classify(page, words, (1920, 1080)) == 'CUTSCENE'
    # Without the REC badge the page is not claimed: a stray SKIP-shaped token
    # elsewhere must not turn an unknown page into an input target.
    without_rec = [item for item in page if item.text != 'REC']
    assert classify(without_rec, words, (1920, 1080)) != 'CUTSCENE'


def test_the_event_choice_page_is_named_by_its_heading_and_rows():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261006-044943/frame-0015.json is the
    # abnormality event's "Choices" page. It also carries a REC badge, so it must be
    # named before anything can read it as a cutscene.
    page = [Text('Choices', (1050, 166, 168, 46), 1.0),
            Text('I think we will smile.', (1096, 311, 290, 28), .96),
            Text("Don't make any expression.", (1096, 464, 378, 28), .99),
            Text('Select to gain a Blunt E.G.O Gift', (1096, 500, 322, 26), .995),
            Text('Cry and cry until you sink.', (1096, 643, 366, 33), .997),
            Text('REC', (868, 200, 62, 22), 1.0)]
    assert classify(page, words, (1920, 1080)) == 'EVENT_CHOICE'
    # The heading alone is not enough: a Choices label with no column under it must
    # not turn a stray screen into an input target.
    heading_only = [item for item in page if item.text in ('Choices', 'REC')]
    assert classify(heading_only, words, (1920, 1080)) != 'EVENT_CHOICE'


def test_the_event_result_is_named_and_its_ready_form_is_its_own_page():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261006-045451/frame-0001.json is the
    # event's outcome page with the bottom-right control still dim, and frame-0002.json
    # is the same page one tap later, when that slot carries a bright Continue.
    dim = [Text('Result', (1068, 168, 138, 42), 1.0),
           Text("Don't make any expression.", (1066, 317, 352, 28), .997),
           Text("E.G.O Gift Today's Expression obtained!", (1088, 470, 524, 28), 1.0),
           Text('REC', (876, 200, 60, 22), .998)]
    assert classify(dim, words, (1920, 1080)) == 'EVENT_RESULT'
    lit = dim + [Text('Continue', (1588, 943, 218, 55), 1.0)]
    assert classify(lit, words, (1920, 1080)) == 'EVENT_RESULT_READY'
    # A dim SKIP (the cutscene slot before the story is tapped) must not be read as the
    # ready form, and the Result heading alone is not enough without the REC badge.
    with_skip = dim + [Text('SKIP', (1620, 923, 152, 93), 1.0)]
    assert classify(with_skip, words, (1920, 1080)) == 'EVENT_RESULT'
    without_rec = [item for item in lit if item.text != 'REC']
    assert classify(without_rec, words, (1920, 1080)) != 'EVENT_RESULT_READY'


def test_the_choices_page_beats_the_cutscene_badge_it_shares():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: the cutscene's SKIP press handed back a page that carries the story
    # playback's REC badge AND its SKIP control together with the Choices heading
    # (evidence/runtime/window-20261006-051213/frame-0002.json). Naming it a cutscene
    # would keep pressing SKIP on the event's options forever.
    page = [Text('REC', (864, 196, 64, 28), 1.0),
            Text('SKIP', (1632, 931, 132, 79), 1.0),
            Text('Choices', (1050, 166, 170, 46), 1.0),
            Text('Reach out and hold it.', (1090, 380, 300, 28), .98),
            Text('Step back and watch.', (1090, 520, 280, 28), .97)]
    assert classify(page, words, (1920, 1080)) == 'EVENT_CHOICE'


def test_the_floor_gift_pick_is_named_from_a_live_frame():
    # Regression: the page's locale keys were once dropped while re-writing
    # assets/resource/en/locale.json, and only the live driver noticed -- every unit
    # test built its own dictionary. This one reads the shipped file and a recorded
    # live frame (evidence/runtime/window-20261006-051524/frame-0036.json, whose
    # scene was UNKNOWN while the page was plainly the floor's gift pick).
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((Path(__file__).resolve().parents[1]
                        / 'evidence/runtime/window-20261006-051524/frame-0036.json').read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert classify(records, words, tuple(frame['size'])) == 'GIFT_PICK'
    # The counter merges into the button's own token on some frames ("Select 0/2"),
    # so the pattern has to tolerate it (same trap as "Selectable 1/1").
    merged = [r for r in records if r.text != 'Select']
    merged.append(Text('Select 0/2', (1618, 847, 194, 50), .99))
    assert classify(merged, words, tuple(frame['size'])) == 'GIFT_PICK'
