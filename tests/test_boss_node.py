"""The floor's last node is a red room outside the walk's band (D244).

Measured on `evidence/runtime/packaged-mirror-20261025-040555/frame-0004.png`: party
(482,347), boss box (1026,306,324,248) at 710.9 px, while `adjacent_to` keeps 245-406 px
-- so the last node of every floor was dropped from the candidate list and the walk
could not finish a floor.
"""
from __future__ import annotations

import pathlib

import cv2
import pytest

from maalimbus import map_vision, runner

REPO = pathlib.Path(__file__).resolve().parents[1]
BOSS_FRAME = REPO / "evidence/runtime/packaged-mirror-20261025-040555/frame-0004.png"
PLAIN_FRAME = REPO / "evidence/runtime/packaged-mirror-20261025-045045/frame-0009.png"


def _clicks(path):
    image = cv2.imread(str(path))
    assert image is not None, path
    return map_vision.map_clicks(image, template=runner.node_badge_template())


def _boss_boxes(clicks):
    return [list(item["box"]) for item in clicks if item["kind"] == "boss_node"]


@pytest.mark.skipif(not BOSS_FRAME.exists(), reason="retained frame is not in this checkout")
def test_the_red_room_is_a_candidate():
    boxes = _boss_boxes(_clicks(BOSS_FRAME))
    assert boxes == [[1026, 306, 324, 248]]


@pytest.mark.skipif(not PLAIN_FRAME.exists(), reason="retained frame is not in this checkout")
def test_a_frame_without_a_red_room_offers_none():
    assert _boss_boxes(_clicks(PLAIN_FRAME)) == []


def test_a_part_of_the_room_is_not_a_duplicate_of_it():
    """A tile drawn inside the room must not erase it (the first rule did exactly that)."""
    covered = [list(v) for v in
               [(1026, 306, 324, 248), (1106, 374, 190, 190), (1171, 538, 40, 40)]]
    kept = [box for box in covered
            if not any(map_vision._cover(box, other) >= .5
                       and (other[2] * other[3]) >= .5 * (box[2] * box[3])
                       for other in covered if other is not box)]
    assert kept == [[1026, 306, 324, 248]]


def test_the_band_still_decides_the_walkable_steps(two_box_record=None):
    """The boss is appended after the band, never in place of a nearby step."""
    party = (482, 347)
    near = (594, 497, 190, 190)
    boss = (1026, 306, 324, 248)
    kept = map_vision.adjacent_to(party, [near, boss])
    assert list(map(list, kept)) == [list(near)]
