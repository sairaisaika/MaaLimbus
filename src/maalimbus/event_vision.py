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
