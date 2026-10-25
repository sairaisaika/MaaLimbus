"""One step is one pitch, measured on the frame's own node class."""
import pathlib

import pytest

from maalimbus import map_vision as mv
from maalimbus import runner

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAP_1080 = ROOT / 'evidence/runtime/packaged-mirror-20261025-040555/frame-0004.png'


def _lattice(pitch, count=5, side=190, y=300, start=100):
    return [[start + i * pitch, y, side, side] for i in range(count)]


def test_the_node_class_is_the_modal_side_length():
    boxes = _lattice(200) + [[10, 10, 40, 40], [50, 50, 40, 40]]
    assert len(mv.node_class(boxes)) == 5


def test_the_pitch_is_the_median_nearest_node_distance():
    assert mv.step_pitch(_lattice(200)) == 200
    assert mv.step_pitch(_lattice(137)) == 137


def test_two_nodes_are_not_a_lattice():
    assert mv.step_pitch(_lattice(200, count=2)) is None


def test_one_step_takes_the_neighbour_and_not_the_next():
    boxes = _lattice(200)
    party = (195, 395)                       # centre of the first node
    assert [box[0] for box in mv.one_step(party, boxes)] == [300]


def test_the_same_rule_holds_at_another_pitch():
    boxes = _lattice(137)
    party = (195, 395)
    assert [box[0] for box in mv.one_step(party, boxes)] == [237]


def test_an_immeasurable_lattice_calls_nothing_reachable():
    assert mv.one_step((195, 395), _lattice(200, count=2)) == []
    assert mv.one_step(None, _lattice(200)) == []


def test_the_live_floor_one_pitch_is_the_measured_192_and_the_boss_is_far():
    if not MAP_1080.exists():
        pytest.skip('retained live evidence is not present')
    import cv2
    image = cv2.imread(str(MAP_1080))
    clicks = mv.map_clicks(image, template=runner.node_badge_template())
    boxes = [item['box'] for item in clicks]
    assert mv.step_pitch(boxes) == 192
    party = runner.party_point(image)
    boss = [item['box'] for item in clicks if item['kind'] == 'boss_node']
    assert boss, 'the boss room is detected on this frame'
    centre = (boss[0][0] + boss[0][2] / 2, boss[0][1] + boss[0][3] / 2)
    distance = ((centre[0] - party[0]) ** 2 + (centre[1] - party[1]) ** 2) ** 0.5
    assert distance / 192 > 3                        # about 3.7 steps away
    assert centre not in [(box[0] + box[2] / 2, box[1] + box[3] / 2)
                          for box in mv.one_step(party, boxes)]
