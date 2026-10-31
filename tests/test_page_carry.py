from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from maalimbus.page_carry import carry_page


def test_the_same_bytes_keep_the_map():
    assert carry_page('UNKNOWN', 'MAP', 'abc', 'abc') == 'MAP'


def test_a_different_picture_is_still_unknown():
    assert carry_page('UNKNOWN', 'MAP', 'abc', 'def') == 'UNKNOWN'


def test_a_named_page_is_never_overridden():
    assert carry_page('SHOP', 'MAP', 'abc', 'abc') == 'SHOP'


def test_only_a_map_is_carried():
    assert carry_page('UNKNOWN', 'SHOP', 'abc', 'abc') == 'UNKNOWN'


def test_missing_hashes_carry_nothing():
    assert carry_page('UNKNOWN', 'MAP', None, 'abc') == 'UNKNOWN'
    assert carry_page('UNKNOWN', 'MAP', 'abc', None) == 'UNKNOWN'


def test_an_unreadable_page_is_reread_once():
    from maalimbus.page_carry import unknown_needs_reread
    assert unknown_needs_reread('UNKNOWN') is True


def test_a_named_page_is_not_reread():
    from maalimbus.page_carry import unknown_needs_reread
    for page in ('MAP', 'SHOP', 'BATTLE_HUD'):
        assert unknown_needs_reread(page) is False


def test_observe_only_never_rereads():
    from maalimbus.page_carry import unknown_needs_reread
    assert unknown_needs_reread('UNKNOWN', observe_only=True) is False


def test_several_node_boxes_are_a_map_even_without_text():
    from maalimbus.page_carry import map_by_structure
    boxes = [[100 + 200 * i, 200, 190, 190] for i in range(6)]
    assert map_by_structure(boxes) is True


def test_one_box_is_not_a_map():
    from maalimbus.page_carry import map_by_structure
    assert map_by_structure([[100, 200, 190, 190]]) is False


def test_badges_and_buttons_are_not_nodes():
    from maalimbus.page_carry import map_by_structure
    # 界面页上的小控件（40×40 徽章、180×80 按钮）不该被当成节点框
    boxes = [[10, 10, 40, 40], [20, 20, 40, 40], [30, 30, 180, 80], [40, 40, 40, 40]]
    assert map_by_structure(boxes) is False


def test_the_structure_floor_sits_between_ui_and_map():
    from maalimbus.page_carry import MAP_STRUCTURE_FLOOR
    assert 1 < MAP_STRUCTURE_FLOOR < 6   # 界面页 0–1 个，地图页最少 6 个（实测）
