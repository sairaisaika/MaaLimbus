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
                                   price_value, purchase_confirm_target, refreshes,
                                   shelf_tokens, wanted_offers)
from maalimbus.vision import Text  # noqa: E402

SHOP_FRAME = ROOT / 'evidence/runtime/window-20261012-024300/frame-0173.json'
SHOP_NAMES = ['Replace Heathciffs Skill', 'Uncapped Defibrilator', 'Polarization',
              'Scalpel', 'Curriculum Vitae', 'Prejudice']
SHOP_PRICES = [77, 147, 158, 155, 155, 152]

# The 12:39 live run met the shop with the same six card slots as the shelf above,
# but scored two of its price badges below the reader's usual floor: ``' 77'`` at
# .835 and ``'①211'`` at .874.  Cutting every token at .9 dropped both, so this
# six-slot shelf read as four offers.  Both frames are retained verbatim.
LIVE_SHELF_FRAME = ROOT / 'evidence/runtime/pi-20261012-123906/frame-0064.json'
LIVE_SHELF_COINS = 1647
LIVE_SHELF_NAMES = ["Replace Gregor's Skill", 'Melted Paraffin', 'Thorny Path',
                    'Wobbling Keg', 'Resolution', 'UPS System']
LIVE_SHELF_PRICES = [77, 150, 160, 211, 207, 156]

# The shelf one frame after a real purchase in the 20:37 window: the bought card is
# still there under its own ``Purchased`` badge, and its neighbour's badge read at
# .763 -- below the floor that used to price a shelf.
SUCCESSOR_FRAME = ROOT / 'evidence/runtime/window-20261012-203743/frame-0149.json'


def live_shelf_page():
    """The 12:39 shelf as the reader sees it: size plus its OCR tokens."""
    if not LIVE_SHELF_FRAME.exists():
        pytest.skip('retained live shop evidence is not present')
    record = json.loads(LIVE_SHELF_FRAME.read_text(encoding='utf-8'))
    records = [Text(token['text'], tuple(token['box']), token['score'])
               for token in record['ocr']]
    return records, tuple(record.get('size') or (1920, 1080))


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


@pytest.mark.parametrize('text,value', [
    (' 77', 77), ('①211', 211), ('158', 158), ('45', 45), ('1200', 1200),
    ('①②211', 211), ('Oracle', None), ('Lv. 60', None), ('3%', None), ('12345', None)])
def test_the_pages_own_coin_mark_is_not_part_of_a_price(text, value):
    assert price_value(text) == value


def test_a_faint_number_is_a_price_but_a_faint_title_is_not():
    # One-sided on purpose: the page's price mark and the reader's confidence are
    # different things.  A shelf that gains a card because its name was read badly
    # would offer a purchase the page never printed.
    records, size = shop_page()
    faint_number = Text('211', (1586, 458, 70, 36), .85)
    faint_title = Text('Wobbling Keg', (1556, 494, 142, 32), .85)
    kept = shelf_tokens(records + [faint_number, faint_title])
    assert faint_number in kept
    assert faint_title not in kept
    # A badge can read fainter than that and still be the card's own price: the
    # successor shelf of a real purchase printed one at .763.  What the reader's own
    # strays look like is a *single* digit, which never prices a card.
    assert Text('211', (1586, 458, 70, 36), .79) in shelf_tokens(
        records + [Text('211', (1586, 458, 70, 36), .79)])
    assert Text('7', (1586, 458, 20, 36), .79) not in shelf_tokens(
        records + [Text('7', (1586, 458, 20, 36), .79)])


def test_the_successor_shelf_keeps_the_card_whose_badge_read_faint():
    # ``frame-0149`` of ``window-20261012-203743`` is the shelf just after a real
    # purchase.  It holds the same six cards as ``frame-0144`` one frame earlier, but
    # the Gemstone Oscillator's badge read ``'④ 153'`` at .763 where 0144 read
    # ``'⊕153'`` at .823.  The .8 floor dropped that card, and the purchase receipt
    # then refused a purchase the page had already completed.
    if not SUCCESSOR_FRAME.exists():
        pytest.skip('retained live shop evidence is not present')
    record = json.loads(SUCCESSOR_FRAME.read_text(encoding='utf-8'))
    records = [Text(token['text'], tuple(token['box']), token['score'])
               for token in record['ocr']]
    found = offers(shelf_tokens(records), tuple(record.get('size') or (1920, 1080)))
    assert [(offer.name, offer.price) for offer in found] == [
        ("Replace Yi Sang's Skill", 77), ('Gemstone Oscillator', 153),
        ('Lightning Rod', 247), ("Hellterfly's Dream", 198),
        ('Perversion', 157), ('Ragged Umbrella', 211)]
    assert [offer.name for offer in found if offer.purchased] == ['Ragged Umbrella']



def test_the_live_shelf_that_broke_the_refresh_reads_all_six_offers():
    # The run of 12:39 read this shelf as four offers, stored a four-row pending
    # shelf, and then refused its own successor.  Both badges the reader dropped
    # are real cards: ' 77' scored .835 and '①211' scored .874.
    records, size = live_shelf_page()
    found = offers(shelf_tokens(records), size)
    assert [offer.name for offer in found] == LIVE_SHELF_NAMES
    assert [offer.price for offer in found] == LIVE_SHELF_PRICES
    assert currency(records, size) == LIVE_SHELF_COINS


def test_the_plain_confidence_floor_is_what_dropped_them():
    # Keep the failure legible: without the price-badge exception the very same
    # frame reads short, which is exactly what the stored 12:39 run contains.
    records, size = live_shelf_page()
    plain = offers([token for token in records if token.score >= .9], size)
    assert [offer.name for offer in plain] == ['Melted Paraffin', 'Thorny Path',
                                               'Resolution', 'UPS System']


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
