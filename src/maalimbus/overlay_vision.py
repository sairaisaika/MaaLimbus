"""Reading the guide overlay's own controls off a live frame.

The book that covers the Mirror Dungeon walks through dozens of pages. Its
page-turn triangle is the one control that never changes, but its position does:
it sits on the right edge while a next page exists and on the left edge once only
a previous page is left. A single fixed box therefore clicks into empty space as
soon as the book reaches its last page (measured live: the fixed right-edge box
missed the triangle, the click changed nothing, and the overlay never moved), so
the box is derived from the frame instead.

The band rois below are plain ``x0, y0, x1, y1`` fractions of the frame, not the
centre-normalised boxes :mod:`maalimbus.vision` uses for OCR records.
"""

from __future__ import annotations

import numpy as np

#: a page-turn triangle is a solid gold shape: bright red, strong green, weak
#: blue, and clearly warmer than it is blue.
MIN_RED = 185
MIN_GREEN = 130
MAX_BLUE = 170
MIN_WARMTH = 55

#: smallest number of gold pixels that counts as a control rather than a speck of
#: scenery.
MIN_PIXELS = 200

#: a control is small; anything bigger is artwork that happens to be gold.
MAX_SIDE = 0.09

#: a narrow strip down each side, at the height the book draws its arrows.
PREVIOUS_BAND = (0.0, 0.35, 0.12, 0.68)
NEXT_BAND = (0.87, 0.35, 1.0, 0.68)


def _band(size, roi):
    width, height = size
    x0, y0, x1, y1 = roi
    return int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height)


def triangle_box(image, roi):
    """Bounding box of the solid gold triangle inside ``roi``, or ``None``.

    ``image`` is an OpenCV BGR frame. The box is in pixels.
    """
    if image is None:
        return None
    height, width = image.shape[:2]
    x0, y0, x1, y1 = _band((width, height), roi)
    band = image[y0:y1, x0:x1]
    if band.size == 0:
        return None
    blue = band[:, :, 0].astype(int)
    green = band[:, :, 1].astype(int)
    red = band[:, :, 2].astype(int)
    mask = ((red > MIN_RED) & (green > MIN_GREEN) & (blue < MAX_BLUE)
            & (red - blue > MIN_WARMTH))
    if int(mask.sum()) < MIN_PIXELS:
        return None
    ys, xs = np.nonzero(mask)
    box = [x0 + int(xs.min()), y0 + int(ys.min()),
           int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
    if box[2] > MAX_SIDE * width or box[3] > MAX_SIDE * width:
        return None
    return box


def page_turn_arrows(image):
    """``{'previous': box, 'next': box}`` for the guide overlay, ``None`` when absent.

    ``next`` is the right-hand triangle, the control a window clicks to walk the
    book forward. A missing ``next`` on a page that still shows ``previous`` means
    the book sits on its last page: turning a page can no longer dismiss it, so a
    window must not pretend a click there did anything.
    """
    if image is None:
        return {'previous': None, 'next': None}
    return {'previous': triangle_box(image, PREVIOUS_BAND),
            'next': triangle_box(image, NEXT_BAND)}
