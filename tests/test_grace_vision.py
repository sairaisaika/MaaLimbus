"""The Grace of the Star page: board order, costs and what the run can afford."""
from maalimbus.grace_vision import (COSTS, available_starlight, card_index, cost_of,
                                    plan_purchases, plus_points)
from maalimbus.vision import Text


def test_the_board_order_and_costs_match_the_live_frame():
    # Live: evidence/runtime/window-20261006-193843/frame-0004.json, ten cards with
    # their starlight prices under the title.
    assert COSTS == (10, 10, 20, 20, 30, 30, 40, 40, 50, 60)
    assert card_index('Star of the Beginning') == 1
    assert card_index('Moon Star-shop') == 6
    assert card_index('Perfected Possibility') == 10
    # The season's "Starlight" comes back as "Starloud" and hyphens get dropped.
    assert card_index('Cumulating Starloud') == 2
    assert card_index('Chance Comet') == 9
    assert card_index('Starlight Bonus') is None
    assert cost_of(5) == 30


def test_the_plus_button_sits_under_its_own_title():
    # Live: title 'Star of the Beginning' [296,273,186,22] with its neighbour '++'
    # [384,518,42,27] puts the + button at about (270,530).
    records = [Text('Star of the Beginning', (296, 273, 186, 22), .99),
               Text('Moon Star-shop', (294, 627, 188, 30), 1.0),
               Text('Shop', (100, 100, 40, 20), .99)]
    assert plus_points(records, (1920, 1080)) == {1: (271, 534), 6: (270, 892)}


def test_the_available_counter_is_read_only_from_its_own_band():
    # '300' is the other currency on the far right: outside the band, so not the answer.
    records = [Text('Available', (1000, 40, 100, 30), .99),
               Text('60', (1140, 40, 60, 30), .90),
               Text('300', (1678, 45, 90, 38), 1.0)]
    assert available_starlight(records, (1920, 1080)) == 60
    assert available_starlight([Text('Available', (1000, 40, 100, 30), .99)],
                               (1920, 1080)) is None


def test_the_purchase_plan_follows_the_asked_order_within_the_budget():
    # The player asked for 1,3,5,6,8 while testing, and the live page offered 60
    # starlight: 10 + 20 + 30 fits, 30 and 40 do not.
    assert plan_purchases([1, 3, 5, 6, 8], 60) == [1, 3, 5]
    assert plan_purchases([1, 3, 5, 6, 8], 60, bought={1}) == [3, 5]
    # The asked order is kept even when a later card would have fitted.
    assert plan_purchases([6, 3], 40) == [6]
    assert plan_purchases([1, 2, 3], 25) == [1, 2]
    assert plan_purchases([10], 59) == []
    assert plan_purchases([3, 3, 3], 20) == [3]
    assert plan_purchases([], 60) == []
