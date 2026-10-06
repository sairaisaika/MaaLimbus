import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.overlay_vision import (carousel_dots, page_turn_arrows,
                                      triangle_box)  # noqa: E402

GOLD = (60, 200, 240)  # BGR


def frame():
    return np.zeros((720, 1280, 3), np.uint8)


def add_triangle(image, x, y, width, height, *, pointing='right'):
    """Paste a solid page-turn triangle, the way the game draws its own glyph.

    About half of its bounding box is gold and one horizontal quarter of it is much
    fuller than the other. A solid rectangle is *not* a page-turn control: the
    pre-battle page's warm ``Details`` button is one, and a live run clicked it
    twelve times believing it turned a page.
    """
    for column in range(width):
        ratio = ((column + 1) / width if pointing == 'right'
                 else (width - column) / width)
        extent = max(1, int(round(height * ratio)))
        top = y + (height - extent) // 2
        image[top:top + extent, x + column] = GOLD


def test_blank_frame_has_no_arrows():
    assert page_turn_arrows(frame()) == {'previous': None, 'next': None}


def test_next_arrow_is_the_right_hand_triangle():
    image = frame()
    add_triangle(image, 1130, 300, 60, 60)
    arrows = page_turn_arrows(image)
    assert arrows['next'] == [1130, 300, 60, 60]
    assert arrows['previous'] is None


def test_previous_arrow_is_the_left_hand_triangle():
    # Live proof: on the book's last page only the left triangle is left
    # (evidence/runtime/window-20261006-030152/frame-0014.png, box 93,519,40,44
    # in the 1920x1080 frame the window actually captures).
    image = np.zeros((1080, 1920, 3), np.uint8)
    add_triangle(image, 93, 519, 40, 44, pointing='left')
    arrows = page_turn_arrows(image)
    assert arrows['previous'] == [93, 519, 40, 44]
    assert arrows['next'] is None


def test_a_solid_warm_button_is_not_a_page_turn_triangle():
    # Live false positive: the pre-battle page's Details button sits in the next
    # band and was read as a 47x41 "triangle"
    # (evidence/runtime/window-20261006-034009/frame-0004.png, box 1670,640,47,41).
    image = np.zeros((1080, 1920, 3), np.uint8)
    image[640:681, 1670:1717] = GOLD
    assert page_turn_arrows(image) == {'previous': None, 'next': None}


def test_speck_of_gold_scenery_is_not_a_control():
    image = frame()
    image[300:305, 1140:1145] = GOLD  # 25 warm pixels
    assert page_turn_arrows(image)['next'] is None


def test_large_gold_artwork_is_not_a_control():
    image = frame()
    image[280:420, 1100:1270] = GOLD  # wider than the 9% control limit
    assert triangle_box(image, (0.87, 0.35, 1.0, 0.68)) is None


def test_warm_pixels_outside_the_side_bands_are_ignored():
    image = frame()
    image[300:360, 600:660] = GOLD  # centre of the frame
    assert page_turn_arrows(image) == {'previous': None, 'next': None}


def test_a_tall_gold_column_is_not_a_page_turn_triangle():
    # Live false positive: the battle HUD's E.G.O resource column is gold and sits
    # in the next band, and it was read as a 49x156 control box
    # (evidence/runtime/window-20261006-030152/frame-0014.json).
    image = frame()
    image[378:534, 1220:1269] = GOLD
    assert page_turn_arrows(image)['next'] is None


def test_a_wide_gold_strip_is_not_a_page_turn_triangle():
    image = frame()
    image[400:450, 1120:1276] = GOLD  # 156x50, aspect far from square
    assert page_turn_arrows(image)['next'] is None


def test_the_tallest_gold_pixel_column_does_not_mask_the_real_triangle():
    image = frame()
    image[378:534, 1240:1260] = GOLD  # the icon column
    add_triangle(image, 1191, 380, 26, 44)  # as measured live
    assert page_turn_arrows(image)['next'] == [1191, 380, 26, 44]


class Token:
    def __init__(self, text, box):
        self.text = text
        self.box = box


def test_the_book_carousel_dots_are_read_from_the_bottom_band():
    dots = Token('000000000000000\u25cf0', (692, 909, 532, 28))
    assert carousel_dots([dots], (1920, 1080)) == [dots]


def test_a_short_or_non_dot_run_is_not_the_carousel():
    short = Token('0000', (692, 909, 120, 28))
    words = Token('Select the door', (692, 909, 400, 28))
    assert carousel_dots([short, words], (1920, 1080)) == []


def test_dots_outside_the_band_do_not_identify_the_book():
    digits = Token('000000000000000', (900, 300, 400, 28))  # mid screen
    assert carousel_dots([digits], (1920, 1080)) == []
