"""待处理目标：差一格以内算同一次决策（D423）。"""
from maalimbus.runner import _far_apart


def test_two_neighbours_160px_apart_are_the_same_decision():
    assert _far_apart([1344, 361, 190, 190], [1344, 521, 190, 190]) is False


def test_a_real_jump_is_a_different_decision():
    assert _far_apart([1035, 318, 190, 190], [1344, 447, 190, 190]) is True


def test_one_full_tile_counts_as_a_different_decision():
    assert _far_apart([1000, 300, 190, 190], [1190, 300, 190, 190]) is True


def test_the_575px_case_from_d337_is_still_rejected():
    assert _far_apart([578, 142, 40, 40], [1153, 143, 40, 40]) is True
