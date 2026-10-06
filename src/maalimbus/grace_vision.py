"""Reading the Grace of the Star page: which cards exist, what they cost, and what the
run can afford.

The page lists ten grace cards in a fixed 2x5 grid. Every card carries a title, a
starlight cost and a ``+`` / ``++`` pair under it. Only the titles come out of OCR
reliably: the cost numbers and the "Available" counter are small, low contrast and
frequently missed, so this module treats the season's cost table as the source of
truth and keeps the on-screen counter as a best-effort override.

Live evidence: evidence/runtime/window-20261006-193843/frame-0004.json (1920x1080)
reads the card titles at x≈296/518/740/962/1184 and the ``++`` pair at
[384,518,42,27], which puts each card's ``+`` button at the title centre plus
(-118, +250).
"""
import re

#: Season 7 ("Mirror of Names and Spiders") grace cards in board order, with the
#: starlight each one costs, read off the live frame above (Owned 7541 -> Available 60).
CARDS = (
    ('Star of the Beginning', 10),
    ('Cumulating Starloud', 10),
    ('Interstellar Travel', 20),
    ('Star-shower', 20),
    ('Binary Star-shop', 30),
    ('Moon Star-shop', 30),
    ('Favor of the Nebulae', 40),
    ('Starlight Guidance', 40),
    ('Chance Comet', 50),
    ('Perfected Possibility', 60),
)

TITLES = tuple(name for name, _ in CARDS)
COSTS = tuple(cost for _, cost in CARDS)

#: Card titles, with the OCR's common slips tolerated (it reads "Starloud" for
#: "Starlight" and drops hyphens).
TITLE_PATTERN = re.compile(
    r'^(Star\s+of\s+the\s+Beginning|Cumulating\s+Star\w*|Interstellar\s+Travel|'
    r'Star\s*-?\s*shower|Binary\s+Star\s*-?\s*shop|Moon\s+Star\s*-?\s*shop|'
    r'Favor\s+of\s+the\s+Nebulae|Starlight\s+Guidance|Chance\s+Comet|'
    r'Perfected\s+Possibility)$', re.I)

#: The page's own Enter control, and the starlight counter next to "Available".
#: (maalimbus.vision.find hands the pattern to re.search with its own flags, so this
#: one stays a plain string.)
AVAILABLE_BAND = (0.52, 0.02, 0.80, 0.12)
AVAILABLE_PATTERN = r'^\d{1,5}$'

#: from a card title's centre to its ``+`` button centre, in 1920x1080 pixels.
PLUS_OFFSET = (-118, 250)
PLUS_SIZE = (90, 46)


def card_index(title):
    """1-based board position of ``title``, or None when the token is not a card."""
    match = TITLE_PATTERN.match((title or '').strip())
    if match is None:
        return None
    words = re.split(r'[^a-z]+', match.group(1).lower())
    for index, name in enumerate(TITLES, start=1):
        if re.split(r'[^a-z]+', name.lower()) == words:
            return index
    return None


def cost_of(index):
    """Starlight a 1-based card index costs."""
    if not 1 <= index <= len(CARDS):
        raise ValueError('card index out of range: %r' % (index,))
    return COSTS[index - 1]


def available_starlight(records, size, *, band=AVAILABLE_BAND):
    """The number beside "Available", or None when this frame does not read it."""
    import maalimbus.vision as vision

    hits = vision.find(list(records), AVAILABLE_PATTERN, band, size, .60)
    values = [int(hit.text) for hit in hits]
    return max(values) if values else None


def plus_points(records, size):
    """``{card index: (x, y)}`` for every card title this frame reads."""
    points = {}
    for record in records or []:
        index = card_index(getattr(record, 'text', None))
        if index is None:
            continue
        box = list(getattr(record, 'box', None) or [])
        if len(box) != 4:
            continue
        points.setdefault(index, (int(box[0] + box[2] / 2 + PLUS_OFFSET[0]),
                                  int(box[1] + box[3] / 2 + PLUS_OFFSET[1])))
    return points


def plan_purchases(wanted, available, *, bought=(), costs=COSTS):
    """Which cards to buy, in the order the caller asked for them.

    ``wanted`` is a sequence of 1-based card indices, ``available`` the starlight the
    run may still spend, ``bought`` the ones already bought this visit. A card is
    skipped when it is unaffordable or already bought; the scan continues rather than
    stopping, so a cheap card after an expensive one is still picked up.
    """
    bought = set(bought)
    spend = sum(costs[index - 1] for index in bought)
    picked = []
    for index in wanted:
        if index in bought or index in picked:
            continue
        if not 1 <= index <= len(costs):
            continue
        cost = costs[index - 1]
        if spend + cost > available:
            continue
        spend += cost
        picked.append(index)
    return picked
