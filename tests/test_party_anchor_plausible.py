"""A party reading that stands on no node is not the anchor (D280).

Live `packaged-mirror-20261025-075247` read (162, 430) of 1920x1080: inside the board
fractions, so every earlier gate passed, while no node was anywhere near it.  The
adjacency filter then kept nothing and the run ended `no_candidate_node_observed`.
"""
from maalimbus import runner


def test_a_party_standing_on_a_node_is_accepted():
    assert runner.party_on_a_node((100, 100), [[10, 10, 190, 190]]) is True


def test_a_party_far_from_every_node_is_refused():
    assert runner.party_on_a_node((162, 430), [[700, 300, 190, 190]]) is False


def test_the_reach_follows_the_box_side_not_a_pixel_constant():
    small = [[0, 0, 60, 60]]
    big = [[0, 0, 190, 190]]
    assert runner.party_on_a_node((55, 55), small) is True
    assert runner.party_on_a_node((120, 120), small) is False
    assert runner.party_on_a_node((120, 120), big) is True


def test_no_boxes_or_no_party_is_not_an_anchor():
    assert runner.party_on_a_node(None, [[0, 0, 190, 190]]) is False
    assert runner.party_on_a_node((10, 10), []) is False


def test_a_malformed_box_is_skipped_not_raised():
    assert runner.party_on_a_node((90, 90), ['junk', [0, 0, 190, 190]]) is True
