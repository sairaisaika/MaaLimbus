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

#: x0, y0, x1, y1 fractions of the frame the counter lives in.
COUNTER_BAND = (0.60, 0.05, 1.0, 0.30)

#: the floor gift page's pick counter ("Select 0/2") sits at the bottom right.
#: Live evidence evidence/runtime/window-20261006-043102/frame-0003.json.
GIFT_COUNTER_BAND = (0.84, 0.74, 1.0, 0.90)

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
