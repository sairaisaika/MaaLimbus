"""目标抖动不算替换（D422）。"""
from maalimbus.pages import superseded_click


def test_a_few_pixels_are_the_same_tile():
    assert superseded_click([1035, 318, 190, 190], [1040, 320, 190, 190]) is False


def test_half_a_tile_away_is_still_the_same_tile():
    assert superseded_click([1035, 318, 190, 190], [1040, 318, 190, 190]) is False


def test_a_real_move_is_a_replacement():
    assert superseded_click([1035, 318, 190, 190], [1344, 447, 190, 190]) is True


def test_no_pending_click_is_not_a_replacement():
    assert superseded_click(None, [1035, 318, 190, 190]) is False


def test_points_without_a_side_still_compare_exactly():
    assert superseded_click([10, 20], [11, 20]) is True
