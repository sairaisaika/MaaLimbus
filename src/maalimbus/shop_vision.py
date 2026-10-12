"""What the mirror-dungeon shop is offering, read off the page (offline, pure).

The shop is a 2 x 4 grid of offers.  Each card carries its art, a price badge under
the art and the name under the price, and both badges are centred on the column, so
the column centre can be taken from either badge.  The countdown and the shop's own
currency sit in the header ("Super Shop On Next Floor?" and the number under the
"Shop" tab) and the two refresh buttons -- regular and keyword -- sit on the right.

Live shape: ``evidence/runtime/window-20261012-024300/frame-0173.json`` -- six
offers at column centres 934/1163/1392/1624, price rows at y=476 and y=706, name
rows 34px under them, currency 1008, refreshes 15 and 90.  Nothing here sends
input: it answers what the page shows so a plan can decide about it.

An offer's click box is the art above its own price badge, at a measured offset:
the price is what a purchase identifies itself by, so a target is never invented
from nowhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REFERENCE = (1920, 1080)

# The offers live in the right-hand panel; the header above it (tab, currency,
# countdown, refreshes) and the Leave button below it are outside this window.
PANEL_X = (820, 1860)
PANEL_Y = (290, 800)

# The currency sits under the "Shop" tab, left of the countdown.
CURRENCY_X = (820, 1000)
CURRENCY_Y = (150, 245)

# The two refresh buttons and the cost badges under them.
REFRESH_Y = (140, 260)
REFRESH_X = (1440, 1620)
KEYWORD_REFRESH_X = (1640, 1820)
COST_ROW_Y = 200

PRICE_PATTERN = re.compile(r'^\s*(\d{1,4})\s*$')

# The game draws the coin mark immediately left of every price and OCR sometimes
# reads that mark as its own glyph ("①211") or drops it into a stray space (" 77").
# The badge is still a price badge, so allow up to two leading marks that are
# neither a digit nor a letter -- a title that merely ends in a number keeps its
# letters in front of it and is never read as a price.
PRICE_GLYPH_PATTERN = re.compile(r'^[^0-9A-Za-z]{1,2}([0-9]{1,4})\s*$')

# Titles print near 1.0; a price badge beside them does not always.  On five retained
# live shop frames every one of the six titles was read at >=.962 while badge scores
# fell to .835 (" 77") and .874 ("①211"), so the .9 cut reported a six-slot shelf as
# four or five offers.  That made the same shelf, read twice, look like a change and
# stopped a real refresh, and it left the purchase receipt's "complete successor
# shelf" comparison without the completeness it assumes.  Only the shelf's own price
# badges use this floor: the currency and the refresh costs keep the stricter .9.
SHELF_PRICE_FLOOR = .8

# A name badge sits this far under the price badge of the same offer, and both are
# centred on the column, so they pair up by their own printed geometry.  Two price
# rows are 230px apart, so a row tolerance well under that keeps them apart.
NAME_ROW_OFFSET = 34
NAME_ROW_TOLERANCE = 20
COLUMN_TOLERANCE = 60
ROW_TOLERANCE = 30

# The art sits above the price badge; this is where a purchase is aimed.  Measured
# on the live page: the art's centre is 58px over the top of the price badge, both
# rows (row 1 art 379-425 under the y=460 badge, row 2 art 580-680 under y=688).
ART_OFFSET_FROM_PRICE_TOP = 58
ART_HALF = (60, 45)


@dataclass(frozen=True)
class Offer:
    """One shop offer: what it is called, what it costs and where it is."""

    index: int
    name: str
    name_box: tuple
    price: int | None
    price_box: tuple | None
    click: tuple | None


@dataclass(frozen=True)
class Refresh:
    """A refresh button: the button itself and the cost badge under it."""

    box: tuple | None
    cost: int | None
    cost_box: tuple | None


def _scales(size):
    width, height = size or REFERENCE
    return width / float(REFERENCE[0]), height / float(REFERENCE[1])


def _center(box):
    x, y, w, h = box
    return x + w / 2.0, y + h / 2.0


def _inside(box, x_range, y_range, sx, sy):
    cx, cy = _center(box)
    return (x_range[0] * sx <= cx <= x_range[1] * sx
            and y_range[0] * sy <= cy <= y_range[1] * sy)


def click_box(price_box, size=None):
    """The art box above a price badge, which is what a purchase aims at."""
    sx, sy = _scales(size)
    x, y, w, h = price_box
    cx = x + w / 2.0
    half_w, half_h = ART_HALF[0] * sx, ART_HALF[1] * sy
    centre_y = y - ART_OFFSET_FROM_PRICE_TOP * sy
    return (int(round(cx - half_w)), int(round(centre_y - half_h)),
            int(round(2 * half_w)), int(round(2 * half_h)))


def price_value(text):
    """The integer a price badge prints, or ``None`` when the token is not a price.

    The coin mark in front of the number is not part of the price, so a badge the
    reader saw as ``"①211"`` prices at 211 rather than being filed as a title.
    """
    match = PRICE_PATTERN.match(text or '') or PRICE_GLYPH_PATTERN.match(text or '')
    return int(match.group(1)) if match else None


def shelf_tokens(records):
    """The tokens a shelf read may use out of a frame's OCR.

    Every confident token, plus a price badge that only scored below the usual floor.
    The exception is deliberately one-sided: a faint *number* beside a confident title
    is still that title's price, while a faint *title* is not a title at all -- the
    page's own price mark and the reader's confidence are not the same thing, and a
    shelf must never gain a card because its name was read badly.
    """
    return [token for token in records
            if token.score >= .9
            or (token.score >= SHELF_PRICE_FLOOR and price_value(token.text) is not None)]


def offers(records, size=None):
    """Every offer on the page, top row first, left to right inside a row.

    An offer whose price the page did not print is still reported, by its name,
    with ``price`` ``None``, so a plan can refuse it by name instead of silently
    skipping a card that is on screen.
    """
    sx, sy = _scales(size)
    prices = []
    names = []
    for record in records:
        box = tuple(record.box)
        if not _inside(box, PANEL_X, PANEL_Y, sx, sy):
            continue
        price = price_value(record.text)
        if price is None:
            names.append((str(record.text).strip(), box))
        else:
            prices.append((price, box))

    pairs = []
    for price, box in prices:
        px, py = _center(box)
        best = None
        for name, name_box in names:
            nx, ny = _center(name_box)
            dx = abs(nx - px)
            dy = abs((ny - py) - NAME_ROW_OFFSET * sy)
            if dx > COLUMN_TOLERANCE * sx or dy > NAME_ROW_TOLERANCE * sy:
                continue
            if best is None or (dx, dy) < best[0]:
                best = ((dx, dy), name, name_box)
        if best is not None:
            pairs.append((price, box, best[1], best[2]))

    lines = []
    for pair in sorted(pairs, key=lambda row: _center(row[1])[1]):
        cy = _center(pair[1])[1]
        if lines and abs(lines[-1][0] - cy) <= ROW_TOLERANCE * sy:
            lines[-1][1].append(pair)
        else:
            lines.append((cy, [pair]))

    ordered = []
    for _, line in lines:
        for price, box, name, name_box in sorted(line, key=lambda row: _center(row[1])[0]):
            ordered.append((name, name_box, price, box))
    return [Offer(index=index, name=name, name_box=name_box, price=price,
                  price_box=box, click=click_box(box, size))
            for index, (name, name_box, price, box) in enumerate(ordered, start=1)]


def currency(records, size=None):
    """The shop's own currency, as printed under the "Shop" tab."""
    sx, sy = _scales(size)
    for record in records:
        if not _inside(tuple(record.box), CURRENCY_X, CURRENCY_Y, sx, sy):
            continue
        match = PRICE_PATTERN.match(record.text or '')
        if match:
            return int(match.group(1))
    return None


def refreshes(records, size=None):
    """The regular and keyword refresh buttons, each with the cost it shows."""
    sx, sy = _scales(size)
    answer = {}
    for key, x_range in (('regular', REFRESH_X), ('keyword', KEYWORD_REFRESH_X)):
        button = None
        cost = None
        cost_box = None
        for record in records:
            box = tuple(record.box)
            if not _inside(box, x_range, REFRESH_Y, sx, sy):
                continue
            match = PRICE_PATTERN.match(record.text or '')
            if match and _center(box)[1] > COST_ROW_Y * sy:
                if cost is None or box[3] > cost_box[3]:
                    cost, cost_box = int(match.group(1)), box
            elif not match and (button is None or box[3] > button[3]):
                button = box
        answer[key] = Refresh(box=button, cost=cost, cost_box=cost_box)
    return answer


def wanted_offers(found, names, bought=()):
    """The offers whose name the plan asked for, in the plan's own order.

    A name already bought in this run is left out: the page can hold the same
    offer again after a refresh, and the plan must not pay for it twice.
    """
    order = [str(name).strip().lower() for name in names or []]
    spent = {str(name).strip().lower() for name in bought or []}
    ranked = []
    for offer in found:
        key = offer.name.strip().lower()
        if key in order and key not in spent:
            ranked.append((order.index(key), offer))
    ranked.sort(key=lambda row: (row[0], row[1].index))
    return [offer for _, offer in ranked]


#: A purchase asks back before it is paid for.  The dialog sits over the shop, so
#: the offers stay readable behind it and the shop's own page keeps its name: the
#: pair of controls below is what tells the question apart from the shop itself.
CONFIRM_ROI = (0.50, 0.58, 0.70, 0.80)
CANCEL_ROI = (0.31, 0.58, 0.50, 0.80)


def native_purchase_dialog(records,size=None):
    """The real modal printed Purchase, not Confirm. Effects are not anchors."""
    from .vision import find
    size=size or REFERENCE
    title=find(records,r'^Purchase E\.G\.O Gifts$',(.32,.20,.55,.27),size,.9)
    buy=find(records,r'^Purchase$',CONFIRM_ROI,size,.9)
    cancel=find(records,r'^[X×]?\s*Cancel$',CANCEL_ROI,size,.9)
    return dict(title=title[0],purchase=buy[0],cancel=cancel[0]) if len(title)==len(buy)==len(cancel)==1 else None


def purchase_balances(records,size=None):
    from .vision import find
    size=size or REFERENCE
    before=find(records,r'^\d{1,4}$',(.639,.213,.672,.251),size,.9)
    after=find(records,r'^\d{1,4}$',(.679,.213,.711,.251),size,.9)
    if len(before)!=1 or len(after)!=1:return None
    return int(before[0].text),int(after[0].text)


def purchase_confirm_target(records, size=None, require_offers=True):
    """The Confirm of the shop's own purchase dialog, read off the frame.

    Live evidence is pending: the first purchase this project sends is the frame
    that names the question, so nothing here matches on wording -- it matches on a
    single Confirm beside a single Cancel *over the shop's own offers*, which only
    the purchase dialog puts there.  ``None`` means the page is the shop itself.

    ``require_offers`` is the shop page's own guard and stays on there: a plain shop
    bears no Confirm at all, so a stray one could only be something else.  The
    purchase page (maalimbus.vision naming it ``SHOP_PURCHASE``) has already matched
    the same pair over a shop, so it passes ``require_offers=False`` and still buys
    when the dialog covers the offers it sits on.
    """
    from .vision import find

    dialog=native_purchase_dialog(records,size)
    if dialog is not None:return list(dialog['purchase'].box)
    if require_offers and not offers(records, size):
        return None
    confirm = find(records, r'^Confirm$', CONFIRM_ROI, size, .9)
    cancel = find(records, r'^[X×]?\s*Cancel$', CANCEL_ROI, size, .9)
    if len(confirm) != 1 or len(cancel) != 1:
        return None
    return list(confirm[0].box)


def matching_purchase_question(records, name, price, size=None, threshold=.9, coins=None):
    """Return a Confirm only for a complete question naming the reserved offer.

    The older ``purchase_confirm_target`` is a scene detector, not authorization.
    This reader requires a full named/quoted purchase sentence including its
    integer price. Standalone title/price text may belong to the shelf behind a
    modal, so a generic question must never borrow those tokens. These
    conservative English schemas need retained live verification before use;
    an unfamiliar purchase layout remains pending rather than using generic Confirm.
    """
    from .vision import find

    if not isinstance(name, str) or not name.strip() or type(price) is not int or price <= 0:
        return None
    size = size or REFERENCE
    dialog=native_purchase_dialog(records,size)
    if dialog is not None:
        normalized=lambda text:re.sub(r'\s+',' ',text).strip().casefold()
        names=find(records,r'.+',(.26,.51,.41,.59),size,threshold)
        names=[r for r in names if normalized(r.text)==normalized(name)]
        balances=purchase_balances(records,size)
        if (len(names)==1 and balances and balances[0]-balances[1]==price and balances[1]>=0
                and (coins is None or balances[0]==coins)):
            return list(dialog['purchase'].box)
        return None
    target = purchase_confirm_target(records, size, require_offers=False)
    if target is None:
        return None
    content = find(records, r'.+', (.25, .26, .75, .58), size, threshold)
    normalized = lambda text: re.sub(r'\s+', ' ', text).strip().casefold()
    title = normalized(name)
    named = re.compile(
        r'^(?:would you like to purchase|purchase) ["\']?' + re.escape(title)
        + r'["\']? for ' + str(price) + r'(?: (?:cost|currency))?\?$', re.I)
    questions = [row for row in content if re.match(
        r'^(?:would you like to purchase|purchase)\b', normalized(row.text))]
    if len(questions) == 1 and named.fullmatch(normalized(questions[0].text)):
        return target
    return None
