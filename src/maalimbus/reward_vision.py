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


def counter_state(record):
    """``{'chosen': n, 'required': m}`` for a reward-card frame, else ``None``.

    ``record`` is one window observation: it needs ``size`` and the ``ocr`` token
    list. A missing counter returns ``None``, which the planner reads as "nothing
    picked yet" — never as "confirm now".
    """
    size = tuple(record.get('size') or ())
    x0, y0, x1, y1 = COUNTER_BAND
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
