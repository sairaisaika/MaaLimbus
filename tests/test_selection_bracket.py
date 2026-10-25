"""The bracket is a pair of thin bars, and one bar is not a selection (D205)."""
import sys
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src')]

from maalimbus.map_vision import selection_bracket  # noqa: E402

ORANGE = (30, 200, 255)  # BGR of the measured HSV 14/253/239
DARK = (20, 18, 16)


def _frame(width=1920, height=1080):
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = DARK
    return image


def _bar(image, x, y, w=18, h=50):
    image[y:y + h, x:x + w] = ORANGE


def test_the_measured_pair_is_found():
    image = _frame()
    _bar(image, 1162, 648, 18, 50)
    _bar(image, 1237, 654, 18, 52)
    box = selection_bracket(image)
    assert box is not None
    x, y, w, h = box
    assert (x, y) == (1162, 648)
    assert x + w == 1237 + 18
    assert h >= 50


def test_one_bar_is_not_a_selection():
    image = _frame()
    _bar(image, 1162, 648)
    assert selection_bracket(image) is None


def test_bars_too_far_apart_are_not_a_pair():
    image = _frame()
    _bar(image, 900, 648)
    _bar(image, 1237, 654)
    assert selection_bracket(image) is None


def test_bars_on_different_rows_are_not_a_pair():
    image = _frame()
    _bar(image, 1162, 500)
    _bar(image, 1237, 700)
    assert selection_bracket(image) is None


def test_a_wide_block_is_not_a_bar():
    image = _frame()
    _bar(image, 1100, 648, 120, 50)
    _bar(image, 1237, 654, 18, 52)
    assert selection_bracket(image) is None


def test_the_same_pair_is_found_at_the_operator_scale():
    image = _frame(963, 532)
    _bar(image, 583, 319, 9, 25)
    _bar(image, 620, 322, 9, 26)
    assert selection_bracket(image) is not None
