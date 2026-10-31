"""我方站在格上：一次确认，之后以格心为准；走了一步才重新确认。"""
from __future__ import annotations

import maalimbus.map_vision as vision

BOXES = [[100, 100, 190, 190], [290, 100, 190, 190], [100, 290, 190, 190]]


def test_a_near_reading_snaps_to_the_node_centre():
    point, node = vision.lock_party_to_node((205, 190), BOXES)
    assert point == (195, 195) and node == (195.0, 195.0)


def test_a_confirmed_node_survives_a_drifting_reading():
    first, node = vision.lock_party_to_node((205, 190), BOXES)
    second, node2 = vision.lock_party_to_node((150, 240), BOXES, previous=node)
    assert second == first and node2 == node


def test_a_step_away_only_happens_when_the_reading_moves_a_node():
    _, node = vision.lock_party_to_node((195, 195), BOXES)
    point, node2 = vision.lock_party_to_node((385, 195), BOXES, previous=node)
    assert point == (385, 195) and node2 == (385.0, 195.0)


def test_a_reading_far_from_every_node_is_not_confirmed():
    point, node = vision.lock_party_to_node((900, 900), BOXES)
    assert point == (900, 900) and node is None


def test_no_boxes_changes_nothing():
    assert vision.lock_party_to_node((10, 20), []) == ((10, 20), None)
