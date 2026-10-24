"""D131: the reader reads the button; the caller's box is a cross-check.

`evidence/runtime/packaged-mirror-20261024-153418` was the three-free page with
`Select` at [1654,847,108,42] and `Refuse Gift` at [1350,851,150,34]; the run stopped
with `three_free_gift_controls_missing` only because the caller had not named the
button, which made a hand-over a precondition.
"""
import json
import pathlib

import cv2
import pytest

from maalimbus.floor_gifts import observe_three_free
from maalimbus.reward_vision import gift_cards
from maalimbus.gift_vision import GiftCatalog
from maalimbus.vision import Text

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAME = ROOT / "evidence/runtime/packaged-mirror-20261024-153418/frame-0001"


def _inputs():
    data = json.loads(FRAME.with_suffix(".json").read_text(encoding="utf-8"))
    image = cv2.imread(str(FRAME.with_suffix(".png")))
    size = tuple(data.get("size") or (1920, 1080))
    records = [Text(r["text"], tuple(r["box"]), r["score"]) for r in data["ocr"]]
    return records, size, image, gift_cards(records, size)


def test_the_frame_is_present():
    assert FRAME.with_suffix(".png").exists(), "retained evidence missing"


def test_the_reader_finds_the_button_the_caller_did_not_name():
    records, size, image, boxes = _inputs()
    catalog = GiftCatalog(ROOT / 'assets/resource/base')
    offers, count = observe_three_free(records, size, catalog, boxes, image, None)
    assert count == dict(chosen=1, required=1)
    assert len(offers) == 3


def test_a_page_without_the_button_still_refuses():
    records, size, image, boxes = _inputs()
    without = [r for r in records if r.text.strip() != "Select"]
    with pytest.raises(ValueError, match="three_free_gift_controls_missing"):
        observe_three_free(without, size, GiftCatalog(ROOT / 'assets/resource/base'), boxes, image, None)
