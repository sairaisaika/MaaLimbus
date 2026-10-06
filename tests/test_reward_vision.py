"""The encounter reward page's pick counter (no device, no image)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.reward_vision import (COUNTER_BAND, GIFT_COUNTER_BAND,
                                     SELECT_READY_MEAN, button_mean,
                                     counter_state,
                                     select_ready)  # noqa: E402

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
