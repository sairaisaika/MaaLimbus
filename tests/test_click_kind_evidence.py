"""The click order is the measured one, and a kind with no evidence is not spent (D127).

`python tools/audit_map_clicks.py` over the archived corpus: 102 of 506 click verdicts
name a candidate kind, and their acceptance rates are lit_icon 7/22, bright_lit_icon 2/9,
gold_badge_node 2/21, lit_node 3/31, badge_mark 1/9, lit_ring 0/6, lattice_step 0/3.  A
ring or a lattice tile has never moved the party; clicking one is clicking the empty floor
between two nodes, and every refusal it earns feeds the streak that abandons the floor.
"""
import maalimbus.runner as runner


def test_the_order_follows_the_measured_acceptance():
    order = runner.CLICK_KIND_ORDER
    assert order.index('lit_icon') < order.index('gold_badge_node')
    assert order.index('bright_lit_icon') < order.index('lit_node')
    assert order.index('badge_mark') < order.index('lit_ring')


def test_a_kind_with_no_evidence_is_named_and_sorts_last():
    assert set(runner.CLICK_KINDS_WITHOUT_EVIDENCE) == {'lit_ring', 'lattice_step'}
    for kind in runner.CLICK_KINDS_WITHOUT_EVIDENCE:
        assert runner._kind_rank(kind) >= runner._kind_rank('badge_mark')


def test_a_frame_that_offers_only_rings_offers_nothing():
    kinds = {'1,1,40,40': 'lit_ring', '2,2,40,40': 'lattice_step'}
    assert runner.order_candidates([[1, 1, 40, 40], [2, 2, 40, 40]], kinds) == []


def test_a_frame_that_offers_both_keeps_the_useful_one():
    kinds = {'1,1,40,40': 'lit_ring', '2,2,40,40': 'lit_icon'}
    boxes = [[1, 1, 40, 40], [2, 2, 40, 40]]
    assert runner.order_candidates(boxes, kinds) == [[2, 2, 40, 40]]


def test_the_order_inside_the_list_is_the_measured_one():
    kinds = {'1,1,40,40': 'gold_badge_node', '2,2,40,40': 'lit_icon',
             '3,3,40,40': 'badge_mark'}
    boxes = [[1, 1, 40, 40], [2, 2, 40, 40], [3, 3, 40, 40]]
    assert runner.order_candidates(boxes, kinds) == [[2, 2, 40, 40], [1, 1, 40, 40],
                                                     [3, 3, 40, 40]]


def test_an_unknown_kind_is_kept_and_sorted_last():
    kinds = {'1,1,40,40': 'a_new_glyph', '2,2,40,40': 'lit_icon'}
    boxes = [[1, 1, 40, 40], [2, 2, 40, 40]]
    assert runner.order_candidates(boxes, kinds) == [[2, 2, 40, 40], [1, 1, 40, 40]]
