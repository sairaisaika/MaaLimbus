"""The shop's own way back for a dead key Sinner.

The shop's left panel prints its services as buttons, and ``Heal Sinner`` is the one
that opens the Sinner list a revive is chosen from.  The operator described the rest
on 2026-10-12: "Heal Sinner 100 ... inside there will be three options, the third one
is it", and the standing rule that goes with it: a Sinner in the first seven slots of
the saved order who cannot be deployed has to come back.

Nothing here clicks by position.  The service is read from its own two label tokens
and the click box is the union of exactly those tokens, so a panel that prints
something else leaves the plan without a target, and the cost is the badge the panel
itself prints under that button.  Whether a revive is owed is decided from the
deployment page's own proof: ``rejected_unavailable_inputs`` in the deployment
transaction store names the cards that proof excluded, and only the ones the saved
order ranks inside ``KEY_POSITIONS`` are worth a step.
"""
from dataclasses import dataclass
import re

from .shop_vision import _center, _inside, _scales, price_digits, price_value

#: How many slots of the saved order the run must bring back (operator, 2026-10-12).
KEY_POSITIONS = 7

#: The label and its badge are read at the same confidence the shop's own currency
#: and refresh costs use: a faint token is not a service button.
FLOOR = .9

#: Reference-pixel box of the shop's service panel: shown on every retained shop
#: frame (evidence/runtime/window-20261012-024300/frame-0173.json prints
#: Enhance/Gifts at y 561-587, Heal Sinner at 688-704 with its badge at 742,
#: Team at 696, all inside x 180-660).
SERVICE_X = (180, 660)
SERVICE_Y = (540, 800)

#: The label's own words, exactly as the panel prints them.
LABEL = 'Heal Sinner'


@dataclass(frozen=True)
class Service:
    """The panel's Heal Sinner button: its own label tokens and the badge below."""

    label: str
    box: tuple
    cost: int | None
    cost_box: tuple | None


def _label_tokens(records, size):
    """The panel's own ``Heal``/``Sinner`` pair, or ``None`` when it prints neither."""
    sx, sy = _scales(size)
    words = {}
    for row in records or ():
        if row.score < FLOOR:
            continue
        key = row.text.strip().casefold()
        if key in ('heal', 'sinner') and _inside(row.box, SERVICE_X, SERVICE_Y, sx, sy):
            words.setdefault(key, []).append(row)
    if len(words.get('heal', [])) != 1 or len(words.get('sinner', [])) != 1:
        return None
    return words['heal'][0], words['sinner'][0]


def _cost_below(records, band, size):
    """The price badge the panel prints under ``band``, or ``(None, None)``."""
    sx, sy = _scales(size)
    x0, y0, w, h = band
    x1, y1 = x0 + w, y0 + h
    found = None
    for row in records or ():
        value = price_value(row.text)
        if value is None or price_digits(row.text) < 2 or row.score < FLOOR:
            continue
        cx, cy = _center(row.box)
        if not (x0 - 40 * sx <= cx <= x1 + 20 * sx):
            continue
        if not (y1 <= cy <= y1 + 70 * sy):
            continue
        if found is None or row.box[1] < found.box[1]:
            found = row
    return (price_value(found.text), tuple(found.box)) if found is not None else (None, None)


def heal_sinner(records, size=None):
    """The panel's own ``Heal Sinner`` service, or ``None`` when it prints none.

    A panel that printed the words twice, or that printed them outside the service
    panel, is not a service this project will aim at: no target is the safe answer.
    """
    size = size or (1920, 1080)
    pair = _label_tokens(records, size)
    if pair is None:
        return None
    left, right = pair
    x0 = min(left.box[0], right.box[0])
    y0 = min(left.box[1], right.box[1])
    x1 = max(left.box[0] + left.box[2], right.box[0] + right.box[2])
    y1 = max(left.box[1] + left.box[3], right.box[1] + right.box[3])
    band = (x0, y0, x1 - x0, y1 - y0)
    cost, cost_box = _cost_below(records, band, size)
    return Service(label=LABEL, box=band, cost=cost, cost_box=cost_box)


#: The option list is drawn in the modal's right half: the live frames
#: window-20261012-211311/frame-0015.json and window-20261012-212047/frame-0012.json
#: print 'I. Greatly heal a single Sinner.' (the OCR's own reading of the first ordinal)
#: at [1256,246,380,33], '2. Moderately heal every ...' at [1246,432,332,28] and
#: '3. Revive a single Sinner.' at [1246,611,326,34], each with its own '100' badge at
#: x 1764-1818 on the same row, over the shop page.
OPTION_X = (1150, 1860)
OPTION_Y = (150, 1000)
COST_X = (1700, 1860)

#: An ordinal the modal prints in front of an option.  The live frame reads the first
#: one as 'I' rather than '1', so the glyph run is matched loosely and the rows are then
#: taken in reading order -- which is what makes the third one the revive.
ORDINAL = re.compile(r'^\s*[0-9Il|]{1,2}\s*[.,:]\s*\S')


@dataclass(frozen=True)
class Options:
    """The modal's three numbered ways: their own boxes, as the modal prints them."""

    rows: tuple
    costs: tuple
    revive_box: tuple


def heal_sinners_options(records, size=None):
    """The numbered option list a shop's Heal Sinners modal prints, or ``None``.

    Only the shape is read -- three ordinally numbered rows, the third with its own
    printed cost badge on the same row -- so the modal's own language does not have to be
    known.  The revive row is the third one, in reading order, and its box is that row's
    own title token: a modal that prints anything else leaves the plan with no target.
    """
    size = size or (1920, 1080)
    sx, sy = _scales(size)
    rows = []
    for row in records or ():
        if row.score < FLOOR or ORDINAL.match(row.text.strip()) is None:
            continue
        if not _inside(row.box, OPTION_X, OPTION_Y, sx, sy):
            continue
        rows.append(row)
    rows.sort(key=lambda row: (row.box[1], row.box[0]))
    if len(rows) != 3:
        return None
    costs = []
    for row in rows:
        x0, y0, w, h = row.box
        found = None
        for other in records or ():
            value = price_value(other.text)
            if value is None or price_digits(other.text) < 2 or other.score < FLOOR:
                continue
            cx, cy = _center(other.box)
            if not (COST_X[0] * sx <= cx <= COST_X[1] * sx):
                continue
            if not (y0 - 6 * sy <= cy <= y0 + h + 6 * sy):
                continue
            found = value
            break
        costs.append(found)
    if costs[2] is None:
        return None
    return Options(rows=tuple(tuple(row.box) for row in rows),
                   costs=tuple(costs), revive_box=tuple(rows[2].box))


#: The picker's own party bar: live frame
#: evidence/runtime/window-20261012-213008/frame-0002.json draws twelve hexagonal
#: portraits along the bottom of the screen, the second slot's HP printed at
#: [222,996,38,26] and the twelfth's at [1378,996,...], a 115 px pitch from the first
#: slot's centre at x 112.  The sixth -- deck card 6, the one the deployment store calls
#: unavailable -- carries the dead Sinner's own red '0' and the game's highlight, and its
#: number is the one this OCR never reads, so the dead slot is taken from the deck the
#: page was drawn with and never from the look of a portrait.
BAR_FIRST_CENTER = 112
BAR_PITCH = 115
BAR_TOP = 880
BAR_SIDE = 90
BAR_HEIGHT = 120


def slot_box(card, size=None):
    """The picker's own party bar box for deck ``card`` (1..12), or ``None``."""
    if not isinstance(card, int) or not 1 <= card <= 12:
        return None
    sx, sy = _scales(size or (1920, 1080))
    center = BAR_FIRST_CENTER + BAR_PITCH * (card - 1)
    return [int((center - BAR_SIDE / 2) * sx), int(BAR_TOP * sy),
            int(BAR_SIDE * sx), int(BAR_HEIGHT * sy)]


def picker_slot(unavailable, saved_order, size=None):
    """The picker's portrait box for the first dead key Sinner, or ``None``.

    The picker asks for the Sinner itself; which one is dead is the deployment page's own
    proof, so a run whose proof names nothing lost has nothing to click and the bar is
    never searched by appearance.
    """
    lost = key_losses(unavailable, saved_order)
    if not lost:
        return None
    return slot_box(lost[0], size)


#: The modal's own bottom-right control: the three-way step prints it 'Return'
#: [1610,941,172,55], the pick step 'Select' [1614,937,166,61] and the step that has just
#: revived somebody 'Leave' [1622,943,150,53] (live window-20261012-213008/frame-0002.json,
#: window-20261012-214635/frame-0006.json and window-20261012-214803/frame-0001.json).  The
#: option rows above it are drawn the same in every state and answer nothing: only these
#: words are the modal's own input, so each state is read by the word it prints.
CONFIRM_X = (1560, 1860)
CONFIRM_Y = (900, 1010)


def modal_bottom_control(records, patterns, size=None):
    """The modal's own bottom-right control, read from the word it prints, or ``None``.

    Exactly one token inside the band has to match one of ``patterns``: a modal that
    prints none of them, or prints two, leaves the plan without a target.
    """
    size = size or (1920, 1080)
    sx, sy = _scales(size)
    hits = [row for row in records or ()
            if row.score >= FLOOR and _inside(row.box, CONFIRM_X, CONFIRM_Y, sx, sy)
            and any(re.match(pattern, row.text.strip()) is not None for pattern in patterns)]
    if len(hits) != 1:
        return None
    return list(hits[0].box)


def unavailable_sinners(store):
    """The cards the deployment page's own proof excluded, read from its store.

    The proof is what the deployment page printed, not a guess: the store's own
    ``unavailable`` list is the exclusion its ``prepare`` accepted with an accepted
    availability proof, and every rejected input carries the availability record that
    refused it.  Between a deployment and the next shop a battle can kill more than
    this, which only makes the list a lower bound: a Sinner excluded here was already
    unfieldable when the run submitted its saved order.  A card whose revive the shop
    itself has already been paid for is not one of them any more: those receipts
    (``revives``, booked from the shop's own currency delta) name the slots that came back.
    """
    data = store or {}
    cards = [int(card) for card in (data.get('unavailable') or ()) if isinstance(card, int)]
    for row in data.get('rejected_unavailable_inputs') or ():
        proof = row.get('proof') or {}
        cards.extend(int(card) for card in proof.get('unavailable') or ()
                     if isinstance(card, int))
        card = (row.get('intent') or {}).get('card')
        if isinstance(card, int):
            cards.append(card)
    revived = {row['card'] for row in data.get('revives') or ()
               if isinstance(row, dict) and isinstance(row.get('card'), int)}
    return sorted({card for card in cards if 1 <= card <= 12} - revived)


def saved_order(store):
    """The saved order the deployment page's own store holds, newest shape first."""
    data = store or {}
    order = data.get('saved_order') or data.get('order') or ()
    return [int(card) for card in order if isinstance(card, int)]


def key_losses(unavailable, saved_order, positions=KEY_POSITIONS):
    """The unavailable Sinners whose saved slot is one of the first ``positions``."""
    key = set(list(saved_order or ())[:positions])
    return sorted(set(unavailable or ()) & key)
