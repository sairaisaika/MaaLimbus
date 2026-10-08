"""The encounter reward page's pick counter, read from one frame's OCR tokens.

The page ("Select Encounter Reward Card") opens at ``Selectable 0/1`` and its
Confirm button stays inert until a card is picked, so the window driver hands the
planner the counter instead of clicking blind.

OCR reports the label and the counter as two tokens while nothing is picked, and
merges them into one token once a card is selected:

* ``evidence/runtime/window-20261006-034714/frame-0022.json`` — ``Selectable``
  plus a separate ``0/1``;
* ``evidence/runtime/window-20261006-035257/frame-0002.json`` — a single
  ``Selectable 1/1``, which is why the first attempt at this page fell through to
  the generic unknown-dialog veto.

The counter is therefore searched for inside a band rather than matched whole, so
an unrelated ratio elsewhere on the page can never be mistaken for it.
"""
from __future__ import annotations

import re

#: the pick counter, as its own token or inside the label's token.
COUNTER = re.compile(r'(\d{1,2})\s*/\s*(\d{1,2})')

#: the plate every offered floor gift card hangs at its own top-right corner.
PLATE = re.compile(r'^Acq\S{2,4}re E\.?G\.?O Gift?$', re.IGNORECASE)

#: how far the plate's centre sits to the right of the card's own content, in pixels.
#: Measured at 1920 wide on both live floor-gift layouts: the four-card round
#: (evidence/runtime/window-20261006-051524/frame-0036.json) plate [778,232,150,28]
#: over the card whose title centre is 758, and the single-card round
#: (evidence/runtime/window-20261006-103855/frame-0113.json) plate [976,228,150,28]
#: over the card whose title centre is 955.
PLATE_TO_BODY = 95

#: the card body under a plate, as width and height at 1920 wide.
CARD_SIZE = (240, 200)

#: x0, y0, x1, y1 fractions of the frame the counter lives in.
COUNTER_BAND = (0.60, 0.05, 1.0, 0.30)

#: the floor gift page's pick counter ("Select 0/2") sits at the bottom right.
#: Live evidence evidence/runtime/window-20261006-043102/frame-0003.json.
GIFT_COUNTER_BAND = (0.84, 0.74, 1.0, 0.90)

#: the starting E.G.O Gift page's pick counter ("0/1") sits under its Select button.
#: Live evidence evidence/runtime/window-20261006-195104/frame-0001.json: '0/1'
#: [1684,851,62,52] floating over the page's DANGER! strip, with Select
#: [1524,859,110,42].
INITIAL_COUNTER_BAND = (0.82, 0.76, 0.98, 0.89)

#: from a keyword panel's title centre to the first gift icon under it, in 1920-wide
#: pixels. Live: 'Bleed' [510,236,64,32] with the first icon of its column at (503,360)
#: and the second at (503,510) on evidence/runtime/window-20261006-195104/frame-0001.json.
KEYWORD_TO_ICON = (-39, 108)


def keyword_panel_point(records, size, keyword):
    """Centre of the first gift icon under ``keyword``'s panel, or ``None``.

    The starting page shows eight keyword columns (Burn, Bleed, Tremor, Rupture,
    Sinking, Poise, Charge, Slash) whose titles OCR reads reliably while the icons
    themselves carry no text at all, so the rotation's keyword is what locates the
    gift to take.
    """
    wanted = (keyword or '').strip().lower()
    if not wanted:
        return None
    for record in records or []:
        if (getattr(record, 'text', '') or '').strip().lower() != wanted:
            continue
        box = list(getattr(record, 'box', None) or [])
        if len(box) != 4:
            continue
        return (int(box[0] + box[2] / 2 + KEYWORD_TO_ICON[0]),
                int(box[1] + box[3] / 2 + KEYWORD_TO_ICON[1]))
    return None


#: the tray on the right of the starting page, where the gifts it offers are listed
#: by name once a keyword column has been opened.
INITIAL_TRAY_BAND = (0.60, 0.26, 0.95, 0.80)

#: the gifts the rotation asks for by name, best first: the player named Wound Clerid
#: and Little and To-be-Naughty Plushie for the Bleed team.
INITIAL_GIFT_PREFERENCE = ('Wound Clerid', 'Little and To-be-Naughty Plushie')


def initial_gift_box(records, size, *, wanted=INITIAL_GIFT_PREFERENCE,
                     band=INITIAL_TRAY_BAND):
    """Box of the tray row to take, preferring the rotation's own gift names.

    Live: evidence/runtime/window-20261006-194741/frame-0001.json lists 'Wound Clerid'
    [1298,333,176,34] above its description and 'Little and To-be-Naughty Plushie'
    [1298,488,430,38] below it. With no name of ours on screen the topmost row of the
    tray wins, which is the game's own first offer.
    """
    rows = []
    for record in records or []:
        box = list(getattr(record, 'box', None) or [])
        text = (getattr(record, 'text', '') or '').strip()
        if len(box) != 4 or len(text) < 6:
            continue
        centre = ((box[0] + box[2] / 2) / size[0], (box[1] + box[3] / 2) / size[1])
        if band[0] <= centre[0] <= band[2] and band[1] <= centre[1] <= band[3]:
            rows.append((box, text))
    if not rows:
        return None
    for name in wanted:
        key = (name or '').strip().lower()
        for box, text in rows:
            if key and key in text.lower():
                return box
    rows.sort(key=lambda row: row[0][1])
    return rows[0][0]

#: grayscale mean over the floor gift page's Select button that counts as lit.
#:
#: The three-card round prints no counter at all (a bare ``Select``), so the button's
#: own pixels decide when the next input is the confirm rather than another card.
#: Live: "Select 0/2" disabled mean 20.2 / max 64 and "Select 2/2" enabled mean 73.7
#: / max 233 in evidence/runtime/window-20261006-043440/frame-0001.png and
#: ``frame-0003.png``; the counterless round sits at mean 13.5 / max 64.
SELECT_READY_MEAN = 45.0


def button_mean(image, box):
    """The grayscale mean over ``box`` (x, y, w, h) in a BGR frame, else ``None``.

    ``None`` means the frame could not answer — no image, or a box outside it —
    which callers read as "unknown" rather than "dark".
    """
    if image is None:
        return None
    try:
        x, y, width, height = (int(value) for value in box)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    height_px, width_px = image.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width_px, x + width), min(height_px, y + height)
    if x1 <= x0 or y1 <= y0:
        return None
    crop = image[y0:y1, x0:x1]
    gray = crop.mean(axis=2) if crop.ndim == 3 else crop
    return float(gray.mean())


def select_ready(image, box, *, min_mean=SELECT_READY_MEAN):
    """``True``/``False`` when the Select button is lit/dim, ``None`` when unreadable."""
    mean = button_mean(image, box)
    if mean is None:
        return None
    return mean >= min_mean


def counter_state(record, *, band=COUNTER_BAND):
    """``{'chosen': n, 'required': m}`` for a pick counter, else ``None``.

    ``record`` is one window observation: it needs ``size`` and the ``ocr`` token
    list. A missing counter returns ``None``, which the planner reads as "nothing
    picked yet" — never as "confirm now". ``band`` is x0, y0, x1, y1 as frame
    fractions; the encounter reward card uses :data:`COUNTER_BAND` and the floor
    gift page :data:`GIFT_COUNTER_BAND`.
    """
    size = tuple(record.get('size') or ())
    x0, y0, x1, y1 = band
    for item in record.get('ocr') or []:
        match = COUNTER.search(str(item.get('text') or ''))
        if not match:
            continue
        box = tuple(item.get('box') or ())
        if len(size) == 2 and len(box) == 4:
            centre_x = (box[0] + box[2] / 2) / size[0]
            centre_y = (box[1] + box[3] / 2) / size[1]
            if not (x0 <= centre_x <= x1 and y0 <= centre_y <= y1):
                continue
        return {'chosen': int(match.group(1)), 'required': int(match.group(2))}
    return None


def gift_cards(records, size, *, threshold=.85):
    """One clickable box per offered floor gift card, read from the frame itself.

    The card's own frame is not a fixed size: the round that offers a single gift
    draws one card about 390x585 at [760,240] while the four-card round draws 240x200
    slots, so the anchored slots only ever fit the latter. Every card hangs its
    "Acquire E.G.O Gift" plate at its top-right corner, and clicking the card's body
    is what selects it, so the box is placed ``PLATE_TO_BODY`` left of the plate.

    :param records: the frame's OCR tokens.
    :param size: the frame's ``(width, height)``.
    """
    width, height = size
    boxes = []
    for record in records:
        if record.score < threshold or not PLATE.match(record.text.strip()):
            continue
        x, y, w, h = record.box
        cx = x + w / 2
        card_w, card_h = CARD_SIZE
        left = int(cx - PLATE_TO_BODY - card_w / 2)
        top = int(y + 20)
        if left < 0 or top + card_h > height:
            continue
        boxes.append([max(0, left), top, card_w, card_h])
    return sorted(boxes, key=lambda box: box[0])
