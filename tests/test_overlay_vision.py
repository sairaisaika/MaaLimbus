import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.overlay_vision import page_turn_arrows, triangle_box  # noqa: E402

GOLD = (60, 200, 240)  # BGR


def frame():
    return np.zeros((720, 1280, 3), np.uint8)


def test_blank_frame_has_no_arrows():
    assert page_turn_arrows(frame()) == {'previous': None, 'next': None}


def test_next_arrow_is_the_right_hand_triangle():
    image = frame()
    image[300:360, 1130:1190] = GOLD
    arrows = page_turn_arrows(image)
    assert arrows['next'] == [1130, 300, 60, 60]
    assert arrows['previous'] is None


def test_previous_arrow_is_the_left_hand_triangle():
    # Live proof: on the book's last page only the left triangle is left
    # (evidence/runtime/window-20261006-030152/frame-0014.png, box 93,519,40,44
    # in the 1920x1080 frame the window actually captures).
    image = np.zeros((1080, 1920, 3), np.uint8)
    image[519:563, 93:133] = GOLD
    arrows = page_turn_arrows(image)
    assert arrows['previous'] == [93, 519, 40, 44]
    assert arrows['next'] is None


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
