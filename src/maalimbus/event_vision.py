"""The event page's "Choices" column: which rows are options, and which to take.

Live page (``evidence/runtime/window-20261006-044943/frame-0015.json``): the
abnormality event covers the screen with a ``Choices`` heading and two to four
option rows in the right-hand column, each one a line of spoken text, for example
``I think we will smile.`` / ``Don't make any expression.`` / ``Cry and cry until
you sink.``. A row may also carry a reward line underneath it::

    Don't make any expression.              [1098, 464, 376, 28]
    Select to gain a Blunt E.G.O Gift       [1096, 500, 322, 26]

That line announces what the row above it grants, so it is a hint rather than a
fourth choice, and the hinted row is the one worth taking. The rows are read from
the frame instead of being anchored, because their number changes the layout.
"""
from __future__ import annotations

import re

#: x0, y0, x1, y1 fractions of the frame the option rows live in.
OPTION_BAND = (0.52, 0.24, 0.99, 0.72)

#: a reward announcement under an option, not an option itself.
HINT_PATTERN = re.compile(r'^Select to gain a .+ E\.?G\.?O Gift$', re.IGNORECASE)

#: how far below a row its reward line may sit, in pixels of a 1080-tall frame.
HINT_GAP = 90


def _text(item):
    return str(getattr(item, 'text', None) or (item.get('text') if isinstance(item, dict) else '') or '').strip()


def _box(item):
    raw = getattr(item, 'box', None) or (item.get('box') if isinstance(item, dict) else None) or ()
    try:
        return tuple(int(value) for value in raw)
    except (TypeError, ValueError):
        return ()


def _centre(box, size):
    return ((box[0] + box[2] / 2) / size[0], (box[1] + box[3] / 2) / size[1])


def _in_band(box, size, band):
    if len(box) != 4 or len(size) != 2:
        return False
    centre_x, centre_y = _centre(box, size)
    x0, y0, x1, y1 = band
    return x0 <= centre_x <= x1 and y0 <= centre_y <= y1


def choice_options(records, size, *, band=OPTION_BAND, min_length=8):
    """The option rows, top to bottom, as ``[(box, text), ...]``.

    A row is a spoken line rather than a two-word label, so short tokens (the
    ``Choices`` heading, the ``REC`` badge, a counter) are dropped by length, and a
    reward announcement is dropped by :data:`HINT_PATTERN`.
    """
    size = tuple(size or ())
    rows = []
    for item in records or []:
        text = _text(item)
        box = _box(item)
        binary=bool(re.fullmatch(r'(?:Yes|No|Accept|Refuse)[.!]?',text,re.I))
        if ((len(text) < min_length and not binary) or HINT_PATTERN.match(text)
                or re.fullmatch(r'Press the button to (?:proceed|stop)\.',text,re.I)):
            continue
        if not _in_band(box, size, band):
            continue
        rows.append((box[1], box, text))
    rows.sort(key=lambda row: (row[0], row[1][0]))
    return [(box, text) for _, box, text in rows]


def garden_refusal_choice(records,size,options):
    """Bounded refusal of the independently identified garden offer.

    No healing/reward benefit is inferred from the portrait or this dialogue.
    Other Accept/Refuse questions remain unsupported rather than using row zero.
    """
    short=[i for i,(_,text) in enumerate(options)
           if re.fullmatch(r'(?:Accept|Refuse)[.!]?',text,re.I)]
    if not short:return None
    from .vision import Text,find
    texts=[r if isinstance(r,Text) else Text(_text(r),_box(r),r.get('score',0)) for r in records or []]
    def unique(pattern,band):return len(find(texts,pattern,band,size,.9))==1
    if (len(options)!=2 or len(short)!=2
            or not unique(r'^Choices$',(.53,.13,.66,.22))
            or not unique(r'^Refuse\.$',OPTION_BAND)
            or not unique(r'^Accept\.$',OPTION_BAND)
            or not unique(r'''^["']?Our only wish is that our garden will bloom full of flowers\.["']?$''',(.04,.56,.49,.65))
            or not unique(r'''^["']?Now, what will you do\?["']?$''',(.04,.63,.49,.71))):
        raise ValueError('Accept/Refuse garden event identity is not independently proven')
    return next(i for i,(_,text) in enumerate(options) if text=='Refuse.')


def cyborg_city_choice(records,size,options):
    """Only this exact factory question may select No; never infer from a portrait."""
    question=[r for r in records or [] if
              re.fullmatch(r'<?DO YOU LOVE THE CITY YOU LIVE IN\?>?',_text(r),re.I)
              and _in_band(_box(r),size,(.03,.40,.51,.75))
              and float(getattr(r,'score',r.get('score',0) if isinstance(r,dict) else 0))>=.9]
    binary=[(i,text) for i,(box,text) in enumerate(options)
            if re.fullmatch(r'(?:Yes|No)[.!]?',text,re.I)
            and any(_box(r)==box and float(getattr(r,'score',r.get('score',0) if isinstance(r,dict) else 0))>=.9
                    for r in records or [])]
    if not binary:return None
    if len(question)!=1:raise ValueError('Binary event question is not independently identified')
    yes=[i for i,text in binary if re.fullmatch(r'Yes[.!]?',text,re.I)]
    no=[i for i,text in binary if re.fullmatch(r'No[.!]?',text,re.I)]
    if len(yes)!=1 or len(no)!=1:raise ValueError('Factory question Yes/No controls are ambiguous')
    return no[0]


def factory_result_panel(records,size):
    from .vision import Text,find
    texts=[r if isinstance(r,Text) else Text(_text(r),_box(r),r.get('score',0)) for r in records or []]
    if (len(find(texts,r'^Result$',(.53,.13,.66,.22),size,.9))!=1
            or len(find(texts,r'^No\.$',(.53,.26,.64,.36),size,.9))!=1
            or len(find(texts,r'^After a short notice, the factory exploded with a massive bang\.$',
                        (.04,.49,.49,.60),size,.9))!=1):return None
    content=find(texts,r'^All (?:Identities lose \d+ HP\.|the Cyborgs have lost their \[Upgrade)$',
                 (.54,.40,.91,.54),size,.9)
    return content[0].box if len(content)==1 else None


def gift_hints(records, size, *, band=OPTION_BAND):
    """The y coordinate of every reward announcement in the option column."""
    size = tuple(size or ())
    hints = []
    for item in records or []:
        text = _text(item)
        box = _box(item)
        if not HINT_PATTERN.match(text) or not _in_band(box, size, band):
            continue
        hints.append(box[1])
    return sorted(hints)


def preferred_choice(options, hints, *, gap=HINT_GAP):
    """The index of the option a reward announcement sits under, else ``0``.

    The fallback is only a generic preference, not proof that a choice advances
    the run. Callers reject unsupported binary questions and enforce progress.
    """
    if not options:
        return 0
    for index, (box, _text) in enumerate(options):
        bottom = box[1] + box[3] if len(box) == 4 else box[1]
        if any(0 <= hint - box[1] <= gap or 0 <= hint - bottom <= gap for hint in hints):
            return index
    return 0


def event_result_content(records,size):
    """Meaningful story/result text; the changing REC clock is not progress."""
    values=[]
    for r in records or []:
        box=_box(r)
        if (_in_band(box,size,(.04,.44,.51,.75)) or _in_band(box,size,(.54,.40,.91,.60))):
            text=re.sub(r'\W+','',_text(r).casefold())
            if any(c.isalpha() for c in text):values.append((box[1],box[0],text))
    return tuple(text for _,_,text in sorted(values))


#: The skill check ("Who should do it?" / "Choose a character to perform the check
#: with:") prints an odds caption over each identity slot. The captions are the same
#: UI text every time, so they are matched as templates instead of read as OCR: the
#: live frame merges the whole row into one token
#: (evidence/runtime/window-20261006-204421/frame-0001.json reads
#: "VeryHigh Very Low Very High Very HighHighHighVery tow ..." in a single box), and
#: "High" is a substring of "Very High", so the longer captions are tried first and a
#: caption is only trusted at ODDS_MIN_SCORE.
ODDS_TEMPLATE_DIR = 'assets/resource/base/image/event'

#: captions from the best odds down; the order is also the matching order.
ODDS_TIERS = ('very_high', 'high', 'normal', 'very_low')

#: how good each caption is; the best caption an identity shows is the one to send.
ODDS_RANK = {'very_high': 3, 'high': 2, 'normal': 1, 'very_low': 0}

#: live scores on window-20261006-204421/frame-0001.png, read at the slot centres
#: below: every slot's own caption scores 0.94-1.00 and the runner-up scores at most
#: 0.73, so 0.92 separates them with room to spare.
ODDS_MIN_SCORE = 0.92

#: x0, y0, x1, y1 fractions of the frame the odds captions live in.
CHECK_ROW_BAND = (0.0, 0.828, 1.0, 0.866)

#: how far either side of a slot centre its caption may sit, as a fraction of width.
CHECK_WINDOW = 0.0286

#: the twelve identity slots' centres, as fractions of the frame width. Measured on the
#: live frame's 1920-wide pixels: the caption plates run 72-165, 174-269, 276-372, ...
#: i.e. a 118.5 px first centre with a 103.6 px step, which is 0.0617 + 0.0540 * i.
#: The cards themselves sit directly under their captions, so one centre serves both.
CHECK_CENTRES = tuple(round(0.0617 + 0.05398 * index, 4) for index in range(12))

#: half the width of one identity card, and the vertical band the cards occupy, as
#: fractions of the frame. Measured on the same live frame: the party row's bright
#: content runs y 922-1035 of 1080, and a card is about 93 px wide at 1920.
CHECK_CARD_HALF = 0.022
CHECK_CARD_BAND = (0.855, 0.960)


def check_box(index, size, *, centres=CHECK_CENTRES, half=CHECK_CARD_HALF,
              band=CHECK_CARD_BAND):
    """The pixel box of identity slot ``index`` (1-based) on a ``size`` frame."""
    width, height = size
    centre = centres[index - 1] * width
    return [int(round(centre - half * width)), int(round(band[0] * height)),
            int(round(2 * half * width)), int(round((band[1] - band[0]) * height))]


def odds_scores(image, *, directory=ODDS_TEMPLATE_DIR, centres=CHECK_CENTRES,
                band=CHECK_ROW_BAND, window=CHECK_WINDOW, tiers=ODDS_TIERS,
                min_score=ODDS_MIN_SCORE, reference_width=1920):
    """One record per identity slot: ``{'index', 'tier', 'score'}``.

    ``tier`` is ``None`` when no caption reaches ``min_score`` in that slot, which is
    what a fallen identity's dimmed caption looks like. Templates are stored from the
    1920-wide frames MaaFramework writes, so they match the live page exactly instead
    of carrying the resampling error of a downscaled screenshot; a narrower frame
    scales them down the way the anchor registry does.
    """
    from pathlib import Path

    import cv2

    height, width = image.shape[:2]
    row = image[int(band[1] * height):int(band[3] * height), :, :]
    scale = width / float(reference_width)
    results = []
    for index, centre in enumerate(centres, 1):
        left = max(0, int((centre - window) * width))
        right = min(width, int((centre + window) * width))
        column = row[:, left:right]
        chosen, best = None, 0.0
        for tier in tiers:
            template = cv2.imread(str(Path(directory) / ('odds_%s.png' % tier)))
            if template is None:
                continue
            size = (max(1, round(template.shape[1] * scale)),
                    max(1, round(template.shape[0] * scale)))
            template = cv2.resize(template, size, interpolation=cv2.INTER_LINEAR)
            if column.shape[0] < template.shape[0] or column.shape[1] < template.shape[1]:
                continue
            score = float(cv2.matchTemplate(column, template, cv2.TM_CCOEFF_NORMED).max())
            if score > best:
                best, chosen = score, tier if score >= min_score else None
        results.append({'index': index, 'tier': chosen, 'score': round(best, 3)})
    return results


def best_check_choice(scores, *, min_score=ODDS_MIN_SCORE):
    """The 1-based slot with the best trusted odds, else ``None``.

    Ties keep the leftmost slot, so the choice is stable rather than arbitrary.
    """
    best = None
    for item in scores or []:
        tier = item.get('tier')
        if tier not in ODDS_RANK or float(item.get('score', 0) or 0) < min_score:
            continue
        rank = ODDS_RANK[tier]
        if best is None or rank > best[1]:
            best = (item.get('index'), rank)
    return best[0] if best else None


#: The label the check page puts on the button that commits the chosen identity's roll
#: (locale key ``commence``). Live frame window-20261006-205435/frame-0002 reads it at
#: [1578,946,240,48] with score 1.0, next to 'Predicted Odds: Very High'.
COMMENCE_TEXT = 'Commence'


def check_stage(tokens):
    """``'commence'`` once a check page has an identity chosen and is asking to roll.

    Choosing a slot does not leave the page: the question and the odds row stay, and the
    bottom-right SKIP is replaced by Commence plus the prediction panel. Which of those
    two buttons the frame shows is the only thing that separates the stages, so the plan
    knows whether to aim at another identity or to commit the roll it already has.
    """
    for token in tokens or ():
        text = token.get('text') if isinstance(token, dict) else token
        if str(text or '').strip() == COMMENCE_TEXT:
            return 'commence'
    return None
