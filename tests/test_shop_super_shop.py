"""The shop node's other title: `Super Shop`.

`evidence/runtime/packaged-mirror-20261023-235553` (authorised live run, 2026-10-23
23:55) walked to a shop node, clicked its panel's Enter, and landed on a screen that
`classify` called UNKNOWN eleven times until the budget ended.  The frame says why:
the title reads `Super Shop` [282,154,202,54] 0.96, while `assets/resource/en/locale.json`
anchors the shop as `^Shop$`.  `Leave` [1622,945,150,53] 1.0 sits exactly where the shop
rule looks, so one unanchored word cost the run its remaining reads.

These tests pin the title pair, the Leave requirement, the ROI and the recorded frames.
"""
import json
import pathlib

import pytest

from maalimbus import vision
from maalimbus.vision import Text

ROOT = pathlib.Path(__file__).resolve().parents[1]
SIZE = (1920, 1080)
LIVE = ROOT / 'evidence/runtime/packaged-mirror-20261023-235553'


def _locale():
    return json.loads((ROOT / 'assets/resource/en/locale.json').read_text(encoding='utf-8'))


def _records(*pairs):
    return [Text(text, tuple(box), score) for text, box, score in pairs]


def _shop(super_=True, *, leave=True):
    title = 'Super Shop' if super_ else 'Shop'
    pairs = [(title, (282, 154, 202, 54), 0.96)]
    if leave:
        pairs.append(('Leave', (1622, 945, 150, 53), 1.0))
    return _records(*pairs)


def test_the_super_shop_title_is_the_same_page():
    assert vision.classify(_shop(), _locale(), SIZE) == 'SHOP'


def test_the_plain_shop_title_still_is():
    assert vision.classify(_shop(super_=False), _locale(), SIZE) == 'SHOP'


def test_a_title_without_a_leave_is_not_the_shop():
    """Every input the shop plan sends comes from a control this page did not show."""
    assert vision.classify(_shop(leave=False), _locale(), SIZE) == 'UNKNOWN'


def test_a_super_shop_word_outside_the_title_band_is_not_the_shop():
    """The band is what separates the title from the same words inside the shelf."""
    records = _records(('Super Shop', (900, 620, 200, 40), 0.99),
                       ('Leave', (1622, 945, 150, 53), 1.0))
    assert vision.classify(records, _locale(), SIZE) == 'UNKNOWN'


def test_the_live_frames_that_were_unknown_now_name_the_shop():
    if not (LIVE / 'frame-0022.json').exists():
        pytest.skip('the 2026-10-23 23:55 run is not retained here')
    locale = _locale()
    for name in ('frame-0022.json', 'frame-0026.json'):
        record = json.loads((LIVE / name).read_text(encoding='utf-8'))
        assert record.get('scene') == 'UNKNOWN', 'the run recorded what this test explains'
        records = [Text(t['text'], tuple(t['box']), t['score']) for t in record['ocr']]
        assert vision.classify(records, locale, tuple(record['size'])) == 'SHOP'


def test_the_neighbouring_pages_are_not_pulled_into_the_shop():
    """The check pages either side of the shop keep their own names."""
    if not (LIVE / 'frame-0009.json').exists():
        pytest.skip('the 2026-10-23 23:55 run is not retained here')
    locale = _locale()
    for name, expected in (('frame-0008.json', 'EVENT_CHECK_RESULT'),
                           ('frame-0009.json', 'EVENT_CHECK_READY')):
        record = json.loads((LIVE / name).read_text(encoding='utf-8'))
        records = [Text(t['text'], tuple(t['box']), t['score']) for t in record['ocr']]
        assert vision.classify(records, locale, tuple(record['size'])) == expected
