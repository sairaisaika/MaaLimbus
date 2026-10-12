"""The Grace of the Star page: board order, costs and what the run can afford."""
import json
from pathlib import Path

import cv2
import pytest

from maalimbus.grace_vision import (COSTS, agreeing_number, available_starlight, card_index,
                                    cost_of, observed_board, plan_purchases, plus_points,
                                    read_cost)
from maalimbus.vision import Text

ROOT = Path(__file__).resolve().parents[1]

#: The run that stopped on this page with 'starlight_available_balance_not_proven'.
SLIPPED = ROOT / 'evidence/runtime/window-20261012-012943/frame-0012.json'

#: The run that stopped with 'configured_grace_costs_not_proven': its frame-0005 is the
#: one taken right after a purchase re-rendered a card's price.
REREAD = ROOT / 'evidence/runtime/window-20261012-015054'


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


def test_owned_stock_must_not_be_mistaken_for_the_available_pool():
    # Actual window-20261008-033202 header positions.
    records=[Text('Owned',(1138,55,60,24),.99),Text('7681',(1230,43,98,44),.99),
             Text('Available',(1396,55,94,24),.99),Text('116',(1488,47,74,38),.99),
             Text('580',(1716,45,70,40),.99)]
    assert available_starlight(records,(1920,1080))==116
    assert available_starlight([r for r in records if r.text!='Available'],(1920,1080)) is None


def test_the_live_header_reads_through_its_ocr_slips():
    # Live: evidence/runtime/window-20261012-012943/frame-0012.json, where the run
    # stopped with 'starlight_available_balance_not_proven': the label comes back as
    # "Avallable" (doubled l, .99) and the counter as '本60' (.82) with its starlight
    # glyph glued to the digits, so neither the old label match nor the old int() of
    # the whole token could produce the number the page prints.
    records = [Text('Ouned', (1134, 51, 50, 24), .76),
               Text('*7983', (1224, 43, 106, 42), .87),
               Text('Avallable', (1392, 49, 82, 30), .99),
               Text('本60', (1486, 47, 72, 38), .82),
               Text('300', (1678, 45, 90, 38), 1.0)]
    assert available_starlight(records, (1920, 1080)) == 60


def test_the_retained_live_grace_frame_reads_its_balance():
    """The same frame the live run stopped on, straight out of the evidence tree."""
    if not SLIPPED.exists():
        pytest.skip('retained live grace-page evidence is not present')
    data = json.loads(SLIPPED.read_text(encoding='utf-8'))
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in data['ocr']]
    assert data['scene'] == 'STAR_GRACES'
    assert available_starlight(records, tuple(data['size'])) == 60


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


def test_configured_four_graces_remain_affordable_after_two_purchases():
    costs=(0,10,0,20,30,0,40,0,0,0)
    assert plan_purchases([2,4,5,7],100,costs=costs)==[2,4,5,7]
    assert plan_purchases([2,4,5,7],100,bought={2,4},costs=costs)==[5,7]


def reread(name):
    """One frame of the window that stopped on 'configured_grace_costs_not_proven'."""
    image = cv2.imread(str(REREAD / f'{name}.png'))
    assert image is not None, name
    data = json.loads((REREAD / f'{name}.json').read_text(encoding='utf-8'))
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in data['ocr']]
    return image, records


def test_a_card_price_read_twice_in_one_frame_still_proves_itself():
    # Live: evidence/runtime/window-20261012-015054/frame-0005.json is the frame the
    # device handed back right after the click that bought card 2, and it reads card 4's
    # price '20' at [1336,229,42,32] and again at [1306,230,60,28] (the starlight glyph
    # glued to the digits), both at score 1.0. The old board required exactly one hit, so
    # this frame proved no cost at all and ended the run; both readings describe one
    # glyph, so the price is still proven.
    if not (REREAD / 'frame-0005.png').exists():
        pytest.skip('retained live grace-page evidence is not present')
    image, records = reread('frame-0005')
    board = observed_board(image, records, [2, 4, 5, 7])
    assert board is not None
    assert [board['costs'][index - 1] for index in (2, 4, 5, 7)] == [10, 20, 30, 40]


def test_the_price_of_a_card_read_once_is_unchanged():
    # frame-0001 is the page before any purchase: every wanted price reads exactly once.
    if not (REREAD / 'frame-0001.png').exists():
        pytest.skip('retained live grace-page evidence is not present')
    image, records = reread('frame-0001')
    board = observed_board(image, records, [2, 4, 5, 7])
    assert board is not None
    assert [board['costs'][index - 1] for index in (2, 4, 5, 7)] == [10, 20, 30, 40]


def test_readings_that_disagree_prove_nothing():
    """Two readings are one glyph read twice only while they agree."""
    box = (1336, 229, 42, 32)
    glued = (1306, 230, 60, 28)
    size = (1920, 1080)
    assert read_cost([Text('20', box, 1.0)], box, size) == 20
    assert read_cost([Text('20', box, 1.0), Text('20', glued, 1.0)], box, size) == 20
    assert read_cost([Text('20', box, 1.0), Text('30', glued, 1.0)], box, size) is None
    # The starlight cost reads .75 to .86 when the glyph stays glued, so an unproven
    # number is still unproven rather than guessed from a low-score token.
    assert read_cost([Text('20', box, .60)], box, size) is None
    assert read_cost([], box, size) is None
    assert agreeing_number([]) is None
    assert agreeing_number([20, 20]) == 20
    assert agreeing_number([20, 30]) is None


def test_the_available_counter_survives_a_duplicated_read():
    records = [Text('Available', (1000, 40, 100, 30), .99),
               Text('60', (1140, 40, 60, 30), .90),
               Text('60', (1180, 42, 64, 26), .88)]
    assert available_starlight(records, (1920, 1080)) == 60
    # A reading that disagrees with the counter is not a second opinion to average.
    disagreeing = records[:2] + [Text('600', (1180, 42, 64, 26), .88)]
    assert available_starlight(disagreeing, (1920, 1080)) is None
