"""Adjacency comes from the lit edge the page draws, not from a distance band."""
import numpy as np

from maalimbus import map_vision as mv


def _page(beam=True):
    image = np.zeros((300, 420, 3), np.uint8)
    if beam:
        image[148:152, 100:230] = (255, 255, 255)
    return image


PARTY = (100, 150)


def test_the_node_at_the_end_of_the_beam_is_the_target():
    target = (200, 130, 40, 40)
    behind = (20, 130, 40, 40)
    assert mv.edge_target(_page(), PARTY, [behind, target]) == target


def test_without_a_beam_there_is_no_target():
    assert mv.edge_target(_page(beam=False), PARTY, [(200, 130, 40, 40)]) is None
