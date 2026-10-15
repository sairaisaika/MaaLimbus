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

#: The label, with the OCR's slips tolerated: the same header reads cleanly as
#: "Available" in window-20261008-033202/frame-0001.json but comes back as
#: "Avallable" (doubled l, score .99) in window-20261012-012943/frame-0012.json, and
#: an l/i/digit-1 swap is the same family of slip.
AVAILABLE_LABEL = r'^Ava[l1i]{1,3}ab[l1i]e$'

#: The counter keeps the starlight glyph glued to its digits, so the digits are picked
#: out of the token instead of the whole token being the number: the same live frame
#: reads '本60' (score .82) where the 20261008 frame read a clean '116'. The glued form
#: also scores lower — the live card costs read .75 to .86 that way against 1.0 clean —
#: so a token that proves its digits through this pattern is accepted from DIGIT_FLOOR.
AVAILABLE_PATTERN = r'^[^\d]{0,3}\d{1,5}[^\d]{0,2}$'
AVAILABLE_DIGITS = re.compile(r'\d{1,5}')
DIGIT_FLOOR = 0.70

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


#: A card's cost is read through its own tight box, and the OCR can hand the same glyph
#: back twice in one frame: the click that buys a card re-renders its price, and the
#: number is then read once through the box and once with the starlight icon glued to it
#: (live evidence/runtime/window-20261012-015054/frame-0005.json reads card 4's 20 at
#: [1336,229,42,32] and again at [1306,230,60,28], both at score 1.0). Both readings sit
#: inside the box only because vision.find judges by centre point, so a lone reading was
#: never stronger proof than two readings that agree: readings that agree are one glyph
#: read twice, and readings that disagree are two different numbers and prove nothing.
#: A cost is those digits, with up to the two glyphs the badge may draw beside them:
#: the 2026-10 client puts the starlight icon inside the same OCR box (live frame
#: runtime/packaged-mirror-20261015-070250/frame-0010 reads card 1 as '本10' at .86),
#: and the same box is what the tight cost_roi hands back. The digits are the plan.
COST_PATTERN = r'^\D{0,2}\s*(\d{1,3})$'
#: The glyph sharing the badge lowers the reading: live 2026-10 frames score the
#: glued costs .82-.87 against .99+ for the clean ones, so the floor admits them and
#: the agreeing-readings rule still refuses a box that reads as two numbers.
COST_FLOOR = 0.80


def agreeing_number(values):
    """The number a group of OCR readings of one glyph agrees on, or None."""
    values = list(values)
    if not values or len(set(values)) != 1:
        return None
    return values[0]


def read_cost(records, box, size):
    """The starlight a card's cost box proves this frame, or None."""
    import maalimbus.vision as vision

    x, y, w, h = box
    region = (x / size[0], y / size[1], (x + w) / size[0], (y + h) / size[1])
    values = []
    for item in vision.find(records, COST_PATTERN, region, size, COST_FLOOR):
        match = re.fullmatch(COST_PATTERN, (item.text or '').strip())
        if match:
            values.append(int(match.group(1)))
    return agreeing_number(values)


def available_starlight(records, size, *, band=AVAILABLE_BAND):
    """The number beside "Available", or None when this frame does not read it."""
    import maalimbus.vision as vision

    records=list(records)
    labels=vision.find(records,AVAILABLE_LABEL,band,size,.85)
    if len(labels)!=1:return None
    x,y,w,h=labels[0].box
    scale=size[0]/1920
    hits=[]
    for item in records:
        bx,by,bw,bh=item.box
        if (item.score>=DIGIT_FLOOR and re.fullmatch(AVAILABLE_PATTERN,item.text or '')
            and bx>=x+w-10*scale and bx+bw/2<=x+w+200*scale
            and abs((by+bh/2)-(y+h/2))<=25*scale):
            hits.append(int(AVAILABLE_DIGITS.search(item.text).group()))
    return agreeing_number(hits)


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


def observed_board(image, records, wanted):
    """Current card costs and base-only body targets, independent of buff titles."""
    from . import star_vision
    from .vision import find
    boxes=star_vision.grid(image)
    if boxes is None:return None
    height,width=image.shape[:2]
    costs=[0]*10;points={}
    for index in wanted:
        if not 1<=index<=10:return None
        box=boxes[index-1]
        x,y,w,h=star_vision.cost_roi(box)
        cost=read_cost(records,(x,y,w,h),(width,height))
        if cost is None or cost<=0:return None
        costs[index-1]=cost
        x,y,w,h=star_vision.target_box(box)
        points[index]=(x+w//2,y+h//2)
    return {'costs':costs,'points':points}


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


def conversion_state(image, records, template_dir):
    """Current modal checkbox and displayed conversion cost, with no title/art anchor.

    The 2026-10 redesign kept the box in place but redrew it, so the old artwork
    still scores 0.83 when the box is ticked and 0.15 when it is not: too close to
    the old 0.92 proof gate, and low enough that an exact-match reader calls the
    ticked box unknown and refuses the run. The state is therefore read from two
    independent channels -- the retained template and the bright stroke inside the
    box, which is 0.17 when ticked and 0.00 when empty -- and only accepted when
    they agree; a disagreement refuses instead of guessing at a purchase the run
    may not make. Live evidence: evidence/runtime/packaged-mirror-20261015-071416/
    frame-0011.png (ticked) and evidence/runtime/star-confirm-20261015/README.md
    (ticked and unticked captures of the same dialog).
    """
    import cv2
    from .vision import find
    if image is None or image.shape[:2]!=(1080,1920):return {}
    crop=image[516:581,1060:1116]
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    bright=gray>170
    best,corner=0.0,(1060,516)
    for y in range(0,max(1,gray.shape[0]-33)):
        for x in range(0,max(1,gray.shape[1]-33)):
            value=float(bright[y:y+34,x:x+34].mean())
            if value>best:best,corner=value,(1060+x,516+y)
    scores={}
    for state in ('checked','unchecked'):
        candidates=[template_dir / ('star-convert-'+state+'.png')]
        if state=='unchecked':candidates.append(template_dir/'star-convert-unchecked-current.png')
        for path in candidates:
            template=cv2.imread(str(path))
            if template is None or template.shape[0]>crop.shape[0] or template.shape[1]>crop.shape[1]:continue
            score=float(cv2.matchTemplate(crop,template,cv2.TM_CCOEFF_NORMED).max())
            scores[state]=max(scores.get(state,0),score)
    marked=scores.get('checked',0)>=.60
    filled=best>=.05
    conversion='checked' if marked or filled else 'unchecked'
    if marked!=filled:conversion=None
    costs=find(records,r'^\D{0,2}\s*(\d{1,4})$',(.67,.415,.735,.473),(1920,1080),.80)
    cost=None
    if len(costs)==1:
        digits=re.fullmatch(r'^\D{0,2}\s*(\d{1,4})$',costs[0].text)
        cost=int(digits.group(1)) if digits else None
    box=[corner[0],corner[1],34,34] if best>=.02 else [1072,530,34,34]
    return dict(conversion=conversion,conversion_box=box,cost=cost,scores=scores,
                stroke=round(best,4))
