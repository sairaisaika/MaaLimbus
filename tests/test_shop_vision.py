"""Tests for reading a mirror shop page off its own frame.

Every number here comes from a live shop frame: ``frame-0173`` of
``evidence/runtime/window-20261012-024300`` is the page the run met at 02:58, and
its six offers, their prices and the shelf's own currency are what the reader has
to return.  The purchase dialog itself has not been met live yet, so its Confirm
is only ever claimed when a frame prints one Confirm beside one Cancel over the
shop's own offers.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.shop_vision import (Offer, click_box, currency, offers,  # noqa: E402
                                   purchase_confirm_target, refreshes,
                                   wanted_offers)
from maalimbus.vision import Text  # noqa: E402

SHOP_FRAME = ROOT / 'evidence/runtime/window-20261012-024300/frame-0173.json'
SHOP_NAMES = ['Replace Heathciffs Skill', 'Uncapped Defibrilator', 'Polarization',
              'Scalpel', 'Curriculum Vitae', 'Prejudice']
SHOP_PRICES = [77, 147, 158, 155, 155, 152]


def shop_page():
    """The live shop frame as the reader sees it: size plus its OCR tokens."""
    if not SHOP_FRAME.exists():
        pytest.skip('retained live shop evidence is not present')
    record = json.loads(SHOP_FRAME.read_text(encoding='utf-8'))
    records = [Text(token['text'], tuple(token['box']), token['score'])
               for token in record['ocr']]
    return records, tuple(record.get('size') or (1920, 1080))


def dialog_page(records, size, *, confirm='Confirm', cancel='X Cancel', extra=()):
    """The shop page with a purchase question drawn over it."""
    drawn = list(records)
    if confirm is not None:
        drawn.append(Text(confirm, (1040, 760, 120, 34), .99))
    if cancel is not None:
        drawn.append(Text(cancel, (700, 760, 120, 34), .99))
    drawn.extend(extra)
    return drawn, size


def test_the_shelf_prints_its_own_currency_and_six_offers():
    records, size = shop_page()
    assert currency(records, size) == 1008
    found = offers(records, size)
    assert [offer.name for offer in found] == SHOP_NAMES
    assert [offer.price for offer in found] == SHOP_PRICES
    assert [offer.index for offer in found] == [1, 2, 3, 4, 5, 6]


def test_an_offer_is_clicked_on_its_own_card_not_on_its_price_label():
    records, size = shop_page()
    found = offers(records, size)
    # The card art sits above its price label, so the click is above it too, and the
    # first row's four cards are clicked on the same row: the labels were drawn a
    # couple of pixels apart, and the click follows the label rather than a constant.
    first_row = [click_box(offer.price_box, size) for offer in found[:4]]
    assert len({box[1] for box in first_row}) == 1 or max(box[1] for box in first_row) \
        - min(box[1] for box in first_row) <= 4
    assert all(box[0] < offer.price_box[0] for box, offer in zip(first_row, found))
    assert [offer.click[0] for offer in found] == [870, 1101, 1330, 1561, 870, 1101]
    assert all(offer.click[2:] == (120, 90) for offer in found)


def test_the_shelf_prices_a_plain_and_a_keyword_refresh():
    records, size = shop_page()
    buttons = refreshes(records, size)
    assert buttons['regular'].cost == 15
    assert buttons['keyword'].cost == 90
    assert buttons['regular'].box is not None and buttons['keyword'].box is not None


def test_a_plan_is_bought_in_its_own_order_and_never_twice():
    records, size = shop_page()
    found = offers(records, size)
    ranked = wanted_offers(found, ['Prejudice', 'Uncapped Defibrilator'])
    assert [offer.name for offer in ranked] == ['Prejudice', 'Uncapped Defibrilator']
    scanned = wanted_offers(found, ['Uncapped Defibrilator', 'Prejudice'])
    assert [offer.name for offer in scanned] == ['Uncapped Defibrilator', 'Prejudice']
    again = wanted_offers(found, ['Prejudice'], bought=['Prejudice'])
    assert again == []


def test_the_shop_itself_is_never_read_as_a_purchase_question():
    records, size = shop_page()
    assert purchase_confirm_target(records, size) is None


def test_a_question_over_the_offers_is_the_shops_purchase_confirm():
    records, size = shop_page()
    drawn, size = dialog_page(records, size)
    assert purchase_confirm_target(drawn, size) == [1040, 760, 120, 34]


@pytest.mark.parametrize('confirm,cancel', [(None, 'X Cancel'), ('Confirm', None),
                                            ('Confirm', 'Cancel')])
def test_half_a_question_is_not_a_purchase_confirm(confirm, cancel):
    records, size = shop_page()
    if confirm is None and cancel is None:
        pytest.skip('a frame with neither control is the shop itself')
    drawn, size = dialog_page(records, size, confirm=confirm,
                              cancel='' if cancel is None else cancel)
    if (confirm, cancel) == ('Confirm', 'Cancel'):
        # A Cancel without the X the game draws beside it is still a Cancel: the
        # marker is optional, the word is not.
        assert purchase_confirm_target(drawn, size) == [1040, 760, 120, 34]
    else:
        assert purchase_confirm_target(drawn, size) is None


def test_two_confirms_over_the_offers_are_not_a_purchase_confirm():
    records, size = shop_page()
    drawn, size = dialog_page(records, size, extra=[Text('Confirm', (1200, 780, 100, 30), .99)])
    assert purchase_confirm_target(drawn, size) is None


def test_a_question_that_covers_the_offers_is_not_read_as_a_purchase():
    # A frame that cannot show the shop behind the question is not this dialog: the
    # reader has to see the offers it is about to pay for.
    records, size = shop_page()
    drawn = [token for token in records if token.text.strip() not in SHOP_NAMES]
    drawn.append(Text('Confirm', (1040, 760, 120, 34), .99))
    drawn.append(Text('X Cancel', (700, 760, 120, 34), .99))
    assert purchase_confirm_target(drawn, size) is None


def test_an_offer_without_a_price_is_not_bought_on_a_guessed_number():
    records, size = shop_page()
    stripped = [token for token in records if token.text.strip() != '147']
    found = offers(stripped, size)
    assert all(offer.price != 147 for offer in found)
    assert len(found) == 5


def test_a_shop_frame_is_scaled_to_its_own_resolution():
    records, size = shop_page()
    half_size = (size[0] // 2, size[1] // 2)
    half = offers([Text(token.text, tuple(int(value / 2) for value in token.box), token.score)
                   for token in records], half_size)
    full = offers(records, size)
    assert [offer.name for offer in half] == SHOP_NAMES
    # The click follows the frame it was read from, so a half-size frame is clicked at
    # half the coordinates and with half the card: rounding may move it a pixel.
    for scaled, original in zip(half, full):
        x, y, w, h = original.click
        assert scaled.click[2:] == (w // 2, h // 2)
        assert abs(scaled.click[0] - x // 2) <= 2 and abs(scaled.click[1] - y // 2) <= 2
    assert isinstance(half[0], Offer)
