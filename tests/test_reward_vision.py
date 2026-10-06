"""The encounter reward page's pick counter (no device, no image)."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.reward_vision import (COUNTER_BAND, GIFT_COUNTER_BAND,
                                     SELECT_READY_MEAN, button_mean,
                                     counter_state, gift_cards,
                                     select_ready)  # noqa: E402
from maalimbus.vision import Text  # noqa: E402

import numpy as np  # noqa: E402

SIZE = (1920, 1080)

SELECT_BOX = (1620, 851, 100, 36)


def token(text, box, score=0.99):
    return {'text': text, 'box': list(box), 'score': score}


def test_the_live_label_and_its_own_counter_token():
    # evidence/runtime/window-20261006-034714/frame-0022.json, nothing picked yet.
    record = {'size': list(SIZE),
              'ocr': [token('Selectable', (1326, 176, 174, 50)),
                      token('0/1', (1488, 182, 52, 40))]}
    assert counter_state(record) == {'chosen': 0, 'required': 1}


def test_the_merged_token_once_a_card_is_picked():
    # evidence/runtime/window-20261006-035257/frame-0002.json: OCR merged the label
    # and the counter, which is what made the first attempt fall through to the
    # generic unknown-dialog veto.
    record = {'size': list(SIZE),
              'ocr': [token('Selectable 1/1', (1326, 178, 214, 48))]}
    assert counter_state(record) == {'chosen': 1, 'required': 1}


def test_a_ratio_outside_the_counter_band_is_not_the_counter():
    outside = [token('4/5', (300, 700, 60, 30))]
    assert counter_state({'size': list(SIZE), 'ocr': outside}) is None
    x0, y0, x1, y1 = COUNTER_BAND
    inside = [token('4/5', (int(1920 * (x0 + x1) / 2), int(1080 * (y0 + y1) / 2), 60, 30))]
    assert counter_state({'size': list(SIZE), 'ocr': inside}) == {'chosen': 4, 'required': 5}


def test_a_frame_without_a_counter_reads_as_nothing_picked():
    assert counter_state({'size': list(SIZE), 'ocr': [token('Confirm', (1130, 766, 164, 45))]}) is None
    assert counter_state({'size': list(SIZE)}) is None
    assert counter_state({}) is None
    assert counter_state({'size': None,
                          'ocr': [token('Selectable', (1326, 176, 174, 50))]}) is None


def test_the_floor_gift_counter_lives_in_its_own_band():
    # evidence/runtime/window-20261006-043102/frame-0003.json: Select 0/2 sits at
    # the bottom right, outside the reward card's band, so the caller picks the
    # band instead of the reader guessing.
    record = {'size': list(SIZE),
              'ocr': [token('Select', (1620, 851, 100, 36)),
                      token('0/2', (1740, 841, 62, 50))]}
    assert counter_state(record, band=GIFT_COUNTER_BAND) == {'chosen': 0, 'required': 2}
    assert counter_state(record) is None
    x0, y0, x1, y1 = COUNTER_BAND
    reward_frame = {'size': list(SIZE),
                    'ocr': [token('1/2', (int(1920 * (x0 + x1) / 2),
                                          int(1080 * (y0 + y1) / 2), 60, 30))]}
    assert counter_state(reward_frame, band=GIFT_COUNTER_BAND) is None
    assert counter_state(reward_frame) == {'chosen': 1, 'required': 2}


def frame_with(value, box=SELECT_BOX, size=SIZE):
    width, height = size
    image = np.zeros((height, width, 3), dtype='uint8')
    x, y, w, h = box
    image[y:y + h, x:x + w] = value
    return image


def test_the_select_button_reads_its_own_brightness():
    # Live: "Select 0/2" disabled mean 20.2 / max 64 and "Select 2/2" enabled mean
    # 73.7 / max 233 (evidence/runtime/window-20261006-043440/frame-0001/0003.png);
    # the counterless three-card round sits at mean 13.5 / max 64.
    assert select_ready(frame_with(0), SELECT_BOX) is False
    assert select_ready(frame_with(20), SELECT_BOX) is False
    assert select_ready(frame_with(64), SELECT_BOX) is True
    assert select_ready(frame_with(233), SELECT_BOX) is True
    assert select_ready(frame_with(0, box=(10, 10, 40, 20)), SELECT_BOX) is False


def test_an_unreadable_button_is_unknown_not_dark():
    assert button_mean(None, SELECT_BOX) is None
    assert select_ready(None, SELECT_BOX) is None
    # A box outside the frame, an empty box, and a junk box all read as unknown.
    assert button_mean(frame_with(200), (2000, 1100, 100, 36)) is None
    assert button_mean(frame_with(200), (10, 10, 0, 20)) is None
    assert button_mean(frame_with(200), None) is None
    assert select_ready(frame_with(200), (10, 10, 0, 20)) is None
    assert SELECT_READY_MEAN == 45.0


def test_floor_gift_cards_come_from_the_frames_own_plates():
    """The card's size follows how many gifts are offered, so the plate places it.

    Four-card round evidence/runtime/window-20261006-051524/frame-0036.json hangs its
    plates at [778,232,150,28] and [1176,232,146,28] with the cards' titles centred at
    758 and 1155; the single-card round
    evidence/runtime/window-20261006-103855/frame-0113.json hangs one plate at
    [976,228,150,28] with nothing but "Rebate Token" under it, and the anchored slots
    [337,300,240,200] miss that card entirely.
    """
    from pathlib import Path
    import json
    from maalimbus.reward_vision import gift_cards
    root = Path(__file__).resolve().parents[1]
    cases = {
        'window-20261006-051524/frame-0036.json': [361, 758, 1154, 1551],
        'window-20261006-103855/frame-0113.json': [956],
    }
    for name, centres in cases.items():
        path = root / 'evidence/runtime' / name
        if not path.exists():
            pytest.skip('retained live floor-gift evidence is not present')
        data = json.loads(path.read_text(encoding='utf-8'))
        records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
        cards = gift_cards(records, tuple(data['size']))
        assert [box[0] + box[2] // 2 for box in cards] == centres, name
        assert all(box[2:] == [240, 200] for box in cards)


def test_a_derived_gift_card_is_used_before_the_anchored_slot():
    from maalimbus.window import plan_step
    plan = plan_step('GIFT_PICK', gift={'chosen': 0, 'required': None, 'ready': False},
                     cards=[[836, 248, 240, 200]],
                     controls={'gift_pick.card_01': [337, 300, 240, 200],
                               'gift_pick.card_02': [732, 300, 240, 200],
                               'gift_pick.select_button': [1620, 851, 100, 36]})
    assert plan['action'] == 'click'
    assert plan['target'] == [836, 248, 240, 200]
    assert plan['reason'] == 'the_floor_gift_card_must_be_picked_before_select'
    # Without a derived card the anchored slot is still the fallback.
    fallback = plan_step('GIFT_PICK',
                         gift={'chosen': 0, 'required': None, 'ready': False},
                         controls={'gift_pick.card_01': [337, 300, 240, 200],
                                   'gift_pick.card_02': [732, 300, 240, 200],
                                   'gift_pick.select_button': [1620, 851, 100, 36]})
    assert fallback['target'] == [337, 300, 240, 200]


def test_the_starting_gift_column_names_the_icon_under_it():
    # Live: evidence/runtime/window-20261006-194741/frame-0001.json reads 'Bleed'
    # [510,236,64,32], while the icons under it carry no text at all — the first one
    # sits at (503,360), which is what the planner clicks.
    from maalimbus.reward_vision import INITIAL_COUNTER_BAND, keyword_panel_point
    assert INITIAL_COUNTER_BAND == (0.82, 0.76, 0.98, 0.89)
    records = [Text('Bleed', (510, 236, 64, 32), 1.0),
               Text('Burn', (294, 238, 52, 28), 1.0)]
    assert keyword_panel_point(records, SIZE, 'bleed') == (503, 360)
    assert keyword_panel_point(records, SIZE, 'Bleed') == (503, 360)
    assert keyword_panel_point(records, SIZE, 'slash') is None
    assert keyword_panel_point(records, SIZE, '') is None


def test_the_starting_gift_tray_prefers_the_rotation_names():
    # Live: evidence/runtime/window-20261006-194741/frame-0001.json lists 'Wound
    # Clerid' [1298,333,176,34] and 'Little and To-be-Naughty Plushie' [1298,488,430,38]
    # in the tray, each above its own description line.
    from maalimbus.reward_vision import initial_gift_box
    tray = [Text('Wound Clerid', (1298, 333, 176, 34), 1.0),
            Text('When hitting an enemy with a Skill that inflicts Bleed',
                 (1298, 367, 442, 26), .96),
            Text('Little and To-be-Naughty Plushie', (1298, 488, 430, 38), 1.0),
            Text('Deal +10% damage against enemies with Bleed', (1300, 528, 426, 25), .95)]
    assert initial_gift_box(tray, SIZE) == [1298, 333, 176, 34]
    # With none of our names on screen the topmost row is the game's own first offer.
    plain = [Text('Some Other Gift', (1298, 488, 300, 34), 1.0),
             Text('Another Gift Here', (1298, 333, 300, 34), 1.0)]
    assert initial_gift_box(plain, SIZE) == [1298, 333, 300, 34]
    assert initial_gift_box([], SIZE) is None
