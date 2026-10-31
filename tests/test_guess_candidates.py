"""读不出我方时，页面画的金徽章就是有依据的候选。"""
from __future__ import annotations

import sys
import pathlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from maalimbus import runner


def _frame():
    return np.zeros((1080, 1920, 3), np.uint8)


def test_only_node_kinds_at_node_size_become_guesses():
    clicks = [
        {'kind': 'gold_badge_node', 'box': [100, 100, 190, 190]},
        {'kind': 'lattice_step', 'box': [500, 100, 190, 190]},
        {'kind': 'lit_ring', 'box': [900, 100, 40, 40]},
        {'kind': 'neutral_outline_candidate', 'box': [1300, 100, 190, 190]},
    ]
    boxes = runner.guess_candidates(_frame(), clicks)
    assert boxes == [[100, 100, 190, 190]]


def test_the_nearest_to_the_frame_centre_is_tried_first():
    clicks = [{'kind': 'gold_badge_node', 'box': [0, 0, 190, 190]},
              {'kind': 'gold_badge_node', 'box': [860, 440, 190, 190]}]
    boxes = runner.guess_candidates(_frame(), clicks)
    assert boxes[0] == [860, 440, 190, 190]


def test_a_frame_with_nothing_marked_guesses_nothing():
    assert runner.guess_candidates(_frame(), []) == []
    assert runner.guess_candidates(_frame(), [{'kind': 'water', 'box': [0, 0, 190, 190]}]) == []
