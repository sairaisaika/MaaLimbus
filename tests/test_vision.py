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


def test_the_weekly_reset_notice_is_named_and_its_confirm_is_not_the_identified_form():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261007-164753/frame-0252.json — the notice
    # run-continue-8 raised over the floor 3 map (step 64, "Dregs of the Manor"). Its
    # Confirm leaves the dungeon for the Window, so the page must be named instead of
    # being vetoed as an unnamed dialog and silently clicked through.
    frame = json.loads((Path(__file__).resolve().parents[1]
                        / 'evidence/runtime/window-20261007-164753/frame-0252.json').read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    size = tuple(frame['size'])
    assert classify(records, words, size) == 'WINDOW_RESET'
    # The button pair is what names it: with the two notice lines alone the frame is
    # only an unnamed dialog, which is why this page was stopping the driver.
    labels = [t for t in records if 'ancel' not in t.text and 'onfirm' not in t.text]
    assert classify(labels, words, size) == 'UNKNOWN'


def test_the_pass_level_notice_is_named_over_the_menu_it_covers():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261007-171928/frame-0005.json (sha
    # aa7c595bbc77). Spending a weekly bonus at the claim levelled the battle pass, and
    # the notice landed on top of Before Entry while that page's own Enter stayed
    # readable: run-continue-12 pressed it and nothing moved. Naming the notice has to
    # win over the menu underneath, or the driver keeps clicking a covered button.
    frame = json.loads((Path(__file__).resolve().parents[1]
                        / 'evidence/runtime/window-20261007-171928/frame-0005.json').read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    size = tuple(frame['size'])
    assert classify(records, words, size) == 'PASS_LEVEL_UP'
    # Take the notice away and the same frame is the menu it was covering.
    menu = [t for t in records if t.text.strip() not in ('Pass Level Up', 'Battle Pass XP')]
    assert classify(menu, words, size) == 'MIRROR_ENTRY'


def test_the_weekly_bonus_question_is_named_before_anything_is_spent():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261007-171228/frame-0003.json (sha
    # be5d7c3077df) is the second question that follows a claim -- "Spend your 'Weekly
    # Bonuses, to claim the / bonus rewards?" over '× Cancel' and 'Confirm', with the
    # reward modal dimmed behind it. run-continue-11 stopped on it as an unnamed dialog,
    # and it is the one page where clicking Confirm spends a limited weekly resource.
    frame = json.loads((Path(__file__).resolve().parents[1]
                        / 'evidence/runtime/window-20261007-171228/frame-0003.json').read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    size = tuple(frame['size'])
    assert classify(records, words, size) == 'RUN_REWARD_BONUS'
    # Without the question line it is not this page: the buttons alone are shared with
    # every other confirmation in the game.
    asked = [t for t in records if 'Weekly' not in t.text]
    assert classify(asked, words, size) != 'RUN_REWARD_BONUS'


def test_the_reward_modal_is_named_whichever_way_the_game_leaves_it():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261007-171021/frame-0006.json (sha
    # 24ab86917b97) is what the game leaves behind when a weekly reset expires a run and
    # the player claims what it earned: 'Exploration Reward' over 'To List' and 'Claim',
    # with 'GiveUpRewards' beside them. run-continue-10 waited on it as UNKNOWN because
    # the modal was only recognised when that button read 'To Window'.
    frame = json.loads((Path(__file__).resolve().parents[1]
                        / 'evidence/runtime/window-20261007-171021/frame-0006.json').read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    size = tuple(frame['size'])
    assert classify(records, words, size) == 'RUN_REWARD_DIALOG'
    # Neither label: then the modal is not named, and the window watches instead of
    # clicking a button it cannot read.
    unlabelled = [t for t in records if t.text.strip() not in ('To List', 'To Window')]
    assert not [t for t in unlabelled if t.text.strip() == 'To List']
    assert classify(unlabelled, words, size) == 'UNKNOWN'


def test_the_gift_pickup_popup_is_named_over_the_map_behind_it():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    # Live proof: evidence/runtime/window-20261006-201621/frame-0001.json — the modal
    # the run raises over the map after picking a gift up.
    page = [Text('E.G.O Gifts', (832, 170, 256, 58), 1.0),
            Text('Wound Clerid', (546, 327, 252, 42), 1.0),
            Text('View Desc.', (482, 428, 152, 38), .96),
            Text('Confirm', (916, 825, 126, 40), 1.0)]
    assert classify(page, words, (1920, 1080)) == 'EGO_GIFT_POPUP'
    # The title alone is not enough: without the modal's Confirm it is not that page.
    assert classify([item for item in page if item.text != 'Confirm'],
                    words, (1920, 1080)) != 'EGO_GIFT_POPUP'


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


def test_the_cutscene_is_named_by_its_skip_button():
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
    # The live event story (window-20261006-203xxx: "What does this signboard say?")
    # carries SKIP at [1618,919,154,99] with no readable REC badge at all, so SKIP in
    # that corner band names the page on its own.
    story = [Text('What does this signboard say?', (114, 510, 368, 28), 1.0),
             Text('It hangs itself on a tree, trying to make its content known.',
                  (114, 543, 676, 28), .98),
             Text('SKIP', (1618, 919, 154, 99), 1.0)]
    assert classify(story, words, (1920, 1080)) == 'CUTSCENE'
    # A SKIP-shaped token anywhere else is still not enough to claim the page.
    moved = [item if item.text != 'SKIP' else Text('SKIP', (300, 300, 152, 99), 1.0)
             for item in story]
    assert classify(moved, words, (1920, 1080)) != 'CUTSCENE'


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
    # The live signboard event reaches the outcome page with a bright "Proceed" and no
    # readable REC badge, so the Result panel alone names the ready form.
    live = [Text('Result', (1068, 168, 140, 42), 1.0),
            Text('Its desperation is almost pitiable.', (110, 611, 386, 26), 1.0),
            Text('Pick a rose.', (1062, 315, 158, 34), .99),
            Text('Proceed', (1594, 945, 206, 49), 1.0)]
    assert classify(live, words, (1920, 1080)) == 'EVENT_RESULT_READY'
    # Without REC the page is still named from its Result panel, but with no Continue
    # or Proceed token it stays the dim form the story tap has to reveal.
    without_rec = [item for item in live if item.text != 'Proceed']
    assert classify(without_rec, words, (1920, 1080)) == 'EVENT_RESULT'


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


def test_the_skill_check_page_is_named_by_its_own_question():
    # Live proof: evidence/runtime/window-20261006-204421/frame-0001.json is the event's
    # skill check ("Who should do it?" over twelve identity odds). Its bottom-right SKIP
    # is the same slot the cutscene uses, but on this frame the button is too dark to
    # read, so the question is what names the page.
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((Path(__file__).resolve().parents[1]
                        / 'evidence/runtime/window-20261006-204421/frame-0001.json').read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert classify(records, words, tuple(frame['size'])) == 'EVENT_CHECK'
    # The run68 instance reads its SKIP and drops the prompt's second line entirely
    # (four tokens in all), and it must still be the check page rather than the
    # cutscene that shares its button.
    other = json.loads((Path(__file__).resolve().parents[1]
                        / 'evidence/runtime/window-20261006-204143/frame-0002.json').read_text())
    tokens = [Text(t['text'], tuple(t['box']), t['score']) for t in other['ocr']]
    assert any(t.text.strip().upper() == 'SKIP' for t in tokens)
    assert not any(t.text.startswith('Choose a character') for t in tokens)
    assert classify(tokens, words, tuple(other['size'])) == 'EVENT_CHECK'
    # Without the question the page is not the check, and the SKIP alone stays the
    # cutscene it belongs to.
    assert classify([t for t in tokens if not t.text.startswith('Who should')],
                    words, tuple(other['size'])) == 'CUTSCENE'


def test_the_second_skill_check_wording_is_the_same_page():
    """Live evidence/runtime/window-20261006-234203/frame-0006.json, floor 3 (run 82).

    The same event offered its check under a second prompt, "Who will take the
    challenge?", and the reader -- which only knew "Who should do it?" -- left the page
    UNKNOWN, where the run waited out its clock (build/window-run82.json,
    page_unreadable_after_waiting). frame-0006 carries the new question, the advantage
    banner and the SKIP, but never the "Choose a character" line.
    """
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261006-234203/frame-0006.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert any(t.text.strip().startswith('Who will take') for t in records)
    assert not any(t.text.startswith('Choose a character') for t in records)
    assert classify(records, words, tuple(frame['size'])) == 'EVENT_CHECK'


def test_the_picked_check_asks_what_will_you_do_and_is_still_the_check():
    """Live evidence/runtime/window-20261006-235032/frame-0013.json, floor 3 (run 84).

    Once an identity is picked the same page swaps its prompt for "What will you do?"
    over the prediction and its SKIP for Commence, and the reader -- which knew only
    the two questions -- left the page UNKNOWN while the run waited out its clock
    (build/window-run84.json). The page's own choice list (frame-0001 of the same
    window) is a different page and stays one.
    """
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261006-235032/frame-0013.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert any(t.text.strip() == 'What will you do?' for t in records)
    assert any(t.text.strip() == 'Commence' for t in records)
    assert classify(records, words, tuple(frame['size'])) == 'EVENT_CHECK'
    # A fourth wording, "Who will give it a try?", is the same page (run 86 on floor 3).
    fourth = json.loads((root / 'evidence/runtime/window-20261007-000045/frame-0097.json')
                        .read_text())
    asked = [Text(t['text'], tuple(t['box']), t['score']) for t in fourth['ocr']]
    assert any(t.text.strip() == 'Who will give it a try?' for t in asked)
    assert classify(asked, words, tuple(fourth['size'])) == 'EVENT_CHECK'
    # A fifth wording, "Who will enter?", is the same page again (run 91 on floor 3).
    fifth = json.loads((root / 'evidence/runtime/window-20261007-001439/frame-0108.json')
                       .read_text())
    entering = [Text(t['text'], tuple(t['box']), t['score']) for t in fifth['ocr']]
    assert any(t.text.strip() == 'Who will enter?' for t in entering)
    assert classify(entering, words, tuple(fifth['size'])) == 'EVENT_CHECK'
    choices = json.loads((root / 'evidence/runtime/window-20261006-235032/frame-0001.json')
                         .read_text())
    listed = [Text(t['text'], tuple(t['box']), t['score']) for t in choices['ocr']]
    assert classify(listed, words, tuple(choices['size'])) == 'EVENT_CHOICE'


def test_the_resolved_skill_check_is_its_own_page_while_its_control_is_dark():
    # Live proof: evidence/runtime/window-20261006-205922 is the aftermath of a roll -
    # 'Check Passed' over the threshold and the story written into the left panel.
    # Its frame-0025.json is one of the 42 frames of that window whose OCR never reaches
    # the bottom-right SKIP (only frame-0001 does), so the outcome is what names the page.
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261006-205922/frame-0025.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert any(t.text.strip() == 'Check Passed' for t in records)
    assert not any(t.text.strip().upper() == 'SKIP' for t in records)
    assert classify(records, words, tuple(frame['size'])) == 'EVENT_CHECK_RESULT'
    # Once the control does light up (frame-0001 of the same window, the only frame whose
    # OCR reaches it) the page belongs to the cutscene branch that owns that button, so
    # the SKIP is what forwards it instead of the story tap.
    first = json.loads((root / 'evidence/runtime/window-20261006-205922/frame-0001.json')
                       .read_text())
    lit = [Text(t['text'], tuple(t['box']), t['score']) for t in first['ocr']]
    assert any(t.text.strip().upper() == 'SKIP' for t in lit)
    assert classify(lit, words, tuple(first['size'])) == 'CUTSCENE'
    # The check page before the roll prints 'Predicted' where the outcome goes, so it can
    # never be mistaken for the resolved one.
    before = json.loads((root / 'evidence/runtime/window-20261006-204421/frame-0001.json')
                        .read_text())
    assert classify([Text(t['text'], tuple(t['box']), t['score']) for t in before['ocr']],
                    words, tuple(before['size'])) == 'EVENT_CHECK'


def test_the_resolved_skill_check_is_ready_once_its_control_lights_up():
    # Live proof: run72 kept tapping the story panel of the resolved check (window-
    # 20261006-210803, 28 frames). frame-0001.json is the dark form - 'Check Passed' with
    # nothing readable in the bottom-right slot - and from frame-0002.json on that slot
    # reads 'Continue' [1588,941,220,59] at score 1.0, which is the control that leaves it.
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    dark = json.loads((root / 'evidence/runtime/window-20261006-210803/frame-0001.json')
                      .read_text())
    tokens = [Text(t['text'], tuple(t['box']), t['score']) for t in dark['ocr']]
    assert any(t.text.strip() == 'Check Passed' for t in tokens)
    assert not any(t.text.strip() in ('Continue', 'Proceed') for t in tokens)
    assert classify(tokens, words, tuple(dark['size'])) == 'EVENT_CHECK_RESULT'
    lit = json.loads((root / 'evidence/runtime/window-20261006-210803/frame-0002.json')
                     .read_text())
    tokens = [Text(t['text'], tuple(t['box']), t['score']) for t in lit['ocr']]
    assert any(t.text.strip() == 'Continue' for t in tokens)
    assert classify(tokens, words, tuple(lit['size'])) == 'EVENT_CHECK_READY'


def test_the_skill_detail_popup_over_the_battle_is_its_own_page():
    """Live evidence/runtime/window-20261007-014613/frame-0094.json, floor 5 (run 99).

    A tap on a skill card opens that skill's detail over the left half of the board and
    covers the HUD's WAVE/TURN captions, so the page fell to UNKNOWN and the run stopped
    twenty rounds into the fifth floor. 'Skill Effects' is what names it.
    """
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261007-014613/frame-0094.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert any(t.text.strip() == 'Skill Effects' for t in records)
    assert classify(records, words, tuple(frame['size'])) == 'BATTLE_TIP'
    # The panel's own title is what names it: a frame without it is not this page.
    without = [t for t in records if t.text.strip() != 'Skill Effects']
    assert classify(without, words, tuple(frame['size'])) != 'BATTLE_TIP'


def test_the_victory_result_with_confirm_is_its_own_page():
    """Live evidence/runtime/window-20261007-015542/frame-0130.json, floor 5 boss (run 100).

    This second victory layout carries the Confirm that ends the battle, and it does not
    clear itself: the driver waited thirty rounds on it and stopped. The drop-show page
    keeps its own name (frame-0001.json of battle-step-20261006-013320 has neither
    'Victory' nor 'EX-CLEAR').
    """
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261007-015542/frame-0130.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert any(t.text.strip() == 'Victory' for t in records)
    assert any(t.text.strip() == 'EX-CLEAR' for t in records)
    assert any(t.text.strip() == 'Confirm' for t in records)
    assert classify(records, words, tuple(frame['size'])) == 'BATTLE_VICTORY'
    show = json.loads((root / 'evidence/runtime/battle-step-20261006-013320/frame-0001.json')
                      .read_text())
    tokens = [Text(t['text'], tuple(t['box']), t['score']) for t in show['ocr']]
    # The drop show carries neither word, so this rule never claims it; that page is
    # named by its own anchors (`Gain Corpus Ingredient` / `TOTAL`).
    assert classify(tokens, words, tuple(show['size'])) != 'BATTLE_VICTORY'
    # Only one of the two words is not enough: the pair is the page.
    half = [t for t in records if t.text.strip() != 'EX-CLEAR']
    assert classify(half, words, tuple(frame['size'])) != 'BATTLE_VICTORY'


def test_the_wiped_stage_dialog_is_its_own_page():
    """Live evidence/runtime/window-20261007-044408/frame-0001.json (floor 5 wipe, run 116).

    The second five-floor attempt was wiped by the floor 5 boss. The game does not end the
    run: it asks how to continue (Return to Stage Select / Retry Stage / Accept results) and
    the driver read the dialog as UNKNOWN, so it stopped on the one page that decides
    whether the run survives. The casualty line is what names the page -- the floor words
    alone also appear on the pause dialog.
    """
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261007-044408/frame-0001.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert any(t.text.strip() == 'Retry Stage' for t in records)
    assert any(t.text.strip() == 'All participating Sinners have been' for t in records)
    assert any(t.text.strip().startswith('Remaining Units') for t in records)
    assert classify(records, words, tuple(frame['size'])) == 'BATTLE_DEFEAT'
    # The floor line on its own is not the page: the pause dialog prints it too.
    without_casualties = [t for t in records
                          if not t.text.strip().startswith('All participating')]
    assert classify(without_casualties, words, tuple(frame['size'])) != 'BATTLE_DEFEAT'
    # And a battle frame that merely mentions a wipe keeps its own name.
    battle = json.loads((root / 'evidence/runtime/window-20261007-042342/frame-0283.json')
                        .read_text())
    tokens = [Text(t['text'], tuple(t['box']), t['score']) for t in battle['ocr']]
    assert classify(tokens, words, tuple(battle['size'])) != 'BATTLE_DEFEAT'


def test_the_run_summary_is_named_so_its_rewards_can_be_claimed():
    """Live evidence/runtime/window-20261007-020715/frame-0006.json (run 101).

    The first time the script ever reached the five-floor settlement: Floor1..Floor5 all
    6/6, Total Progress 100% and a Claim Rewards button beside Previous/Next.
    """
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261007-020715/frame-0006.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    for word in ('Exploration', 'Complete', 'Total Progress', 'Claim', 'Rewards'):
        assert any(t.text.strip() == word for t in records), word
    assert classify(records, words, tuple(frame['size'])) == 'RUN_CLAIM'
    # Claim and Rewards are required together: a frame that only shows Previous/Next is
    # not this page and must not be clicked through.
    without = [t for t in records if t.text.strip() != 'Claim']
    assert classify(without, words, tuple(frame['size'])) != 'RUN_CLAIM'


def test_the_reward_claim_question_is_named_before_the_summary_behind_it():
    """Live evidence/runtime/window-20261007-021916/frame-0002.json (run 103).

    The reward modal's Claim does not grant anything: it asks 'Claim the rewards?' over
    Cancel and Confirm, with the modal and the summary dimmed behind it. That frame's
    'To Window' is unreadable, so the modal rule did not fire and the four summary words
    (still visible behind everything) named it RUN_CLAIM -- the driver then alternated
    the two claim buttons for twenty steps.
    """
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261007-021916/frame-0002.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert classify(records, words, tuple(frame['size'])) == 'RUN_REWARD_CONFIRM'
    # The summary's own words are all in this frame, which is why the order matters.
    for word in ('Exploration', 'Complete', 'Claim', 'Rewards'):
        assert any(t.text.strip() == word for t in records), word
    assert not any(t.text.strip() == 'To Window' for t in records)
    # Without the question the frame is the summary behind it.
    without = [t for t in records if t.text.strip() != 'Claim the rewards?']
    assert classify(without, words, tuple(frame['size'])) == 'RUN_CLAIM'
    # Cancel alone must never be enough to name this page.
    no_confirm = [t for t in records if t.text.strip() != 'Confirm']
    assert classify(no_confirm, words, tuple(frame['size'])) != 'RUN_REWARD_CONFIRM'


def test_the_reward_modal_is_named_before_the_summary_behind_it():
    """Live evidence/runtime/window-20261007-021150/frame-0002.json (run 102).

    The claim opens a modal whose three controls are Give Up Rewards, To Window and
    Claim, while the summary behind it still reads 'Claim Rewards'. Seventy steps of the
    run clicked that dead background button, so the modal must win the page name.
    """
    root = Path(__file__).resolve().parents[1]
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = json.loads((root / 'evidence/runtime/window-20261007-021150/frame-0002.json')
                       .read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert any(t.text.strip() == 'Exploration Reward' for t in records)
    assert any(t.text.strip() == 'To Window' for t in records)
    assert classify(records, words, tuple(frame['size'])) == 'RUN_REWARD_DIALOG'
    # Both Claims are in this frame -- the modal's [1238,796,98,41] and the summary's
    # [1682,865,82,30] -- so the page name must not depend on the word alone.
    claims = [t for t in records if t.text.strip() == 'Claim']
    assert len(claims) == 2
    # Without the modal's own title the page is the summary behind it.
    without = [t for t in records if t.text.strip() != 'Exploration Reward']
    assert classify(without, words, tuple(frame['size'])) == 'RUN_CLAIM'


def test_the_result_screen_is_named_when_the_story_box_covers_its_first_letter():
    """Live evidence/runtime/window-20261007-174525/frame-0159.json.

    window-run-continue-14 stalled there as UNKNOWN with window_unknown_wait: the
    post-battle story box sits over the V of the banner, so OCR returns 'ICTORY'
    [830,444,342,187] .85 next to the story lines, and the result screen -- which is
    only ever waited out, never clicked -- was not recognised at all.
    """
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    frame = Path(__file__).resolve().parents[1] / 'evidence/runtime/window-20261007-174525/frame-0159.json'
    if not frame.exists():
        pytest.skip('retained live result-screen evidence is not present')
    data = json.loads(frame.read_text(encoding='utf-8'))
    records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
    assert classify(records, words, tuple(data['size'])) == 'BATTLE_RESULT'
    # Take the banner away and the page is nothing this reader knows.
    trimmed = [r for r in records if 'ICTORY' not in r.text]
    assert classify(trimmed, words, tuple(data['size'])) == 'UNKNOWN'
