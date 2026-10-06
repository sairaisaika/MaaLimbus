"""The encounter reward page's pick counter (no device, no image)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.reward_vision import COUNTER_BAND, counter_state  # noqa: E402

SIZE = (1920, 1080)


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
