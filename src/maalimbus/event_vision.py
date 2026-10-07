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
        if len(text) < min_length or HINT_PATTERN.match(text):
            continue
        if not _in_band(box, size, band):
            continue
        rows.append((box[1], box, text))
    rows.sort(key=lambda row: (row[0], row[1][0]))
    return [(box, text) for _, box, text in rows]


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

    Falls back to the first row so the page always has one bounded input: every
    option continues the run, so picking one is never a guess about coordinates.
    """
    if not options:
        return 0
    for index, (box, _text) in enumerate(options):
        bottom = box[1] + box[3] if len(box) == 4 else box[1]
        if any(0 <= hint - box[1] <= gap or 0 <= hint - bottom <= gap for hint in hints):
            return index
    return 0


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
