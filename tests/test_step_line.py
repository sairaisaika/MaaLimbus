"""The line between the party and a tile is judged by its share of lit pixels (D331).

Measured on `packaged-mirror-20261025-160619/frame-0005.png`: the frame's grey median is 4
and its p90 is 22, so the old `grey > 90` never fired; the tiles a line connects carry lit
pixels on 54-85% of the segment and the tiles without one on 9-16%.
"""
import pathlib

import cv2
import pytest

from maalimbus import map_vision

REPO = pathlib.Path(__file__).resolve().parent.parent
FRAME = REPO / 'evidence' / 'runtime' / 'packaged-mirror-20261025-160619' / 'frame-0005.png'


def _frame():
    image = cv2.imread(str(FRAME))
    if image is None:
        pytest.skip('the retained frame is not in this checkout')
    return image


def _boxes(image, party):
    return [list(c['box']) for c in map_vision.map_clicks(image, player=party)]


def test_the_nearest_tile_with_a_lit_line_is_the_step():
    image = _frame()
    party = map_vision.party_point(image)
    assert party == (1091, 252)
    chosen = map_vision.neighbour_by_line(image, party, _boxes(image, party))
    assert chosen['box'] == [1152, 169, 190, 190]
    assert chosen['score'] >= 0.5


def test_a_tile_without_a_line_is_not_the_step():
    image = _frame()
    party = map_vision.party_point(image)
    answer = map_vision.neighbour_by_line(image, party, [[960, 329, 190, 190]])
    assert answer['box'] is None
    assert answer['scored'][0]['score'] < 0.5


def test_the_lit_share_is_derived_from_the_frame_and_not_from_ninety():
    image = _frame()
    party = map_vision.party_point(image)
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    import numpy as np
    expected = max(26.0, float(np.percentile(grey, 90)) + 8.0)
    assert 26.0 <= expected <= 40.0
    assert map_vision.line_share(image, party, (1247, 264)) == map_vision.line_share(
        image, party, (1247, 264), lit=expected)
    assert map_vision.line_share(image, party, (1247, 264)) >= 0.5
