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

import re

import cv2
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

#: ... and a control is compact. The battle HUD's E.G.O resource column is gold,
#: sits in the same right-hand band, and covered 156 px of height in the live
#: frame that made the triangle alone report a tutorial over the battle page.
MAX_PIXELS = 4000
MIN_ASPECT = 0.5
MAX_ASPECT = 1.7

#: ... and a page-turn triangle is *pointed*. A solid triangle fills about half of
#: its bounding box and one horizontal quarter of it holds far more gold than the
#: other. The pre-battle page draws a warm rounded ``Details`` button inside the
#: same right-hand band, which is evenly filled and therefore not a control: the
#: live run window-20261006-034009 clicked it twelve times as if it turned a page.
MIN_FILL = 0.28
MAX_FILL = 0.72
MIN_LEAN = 1.8

#: a narrow strip down each side, at the height the book draws its arrows.
PREVIOUS_BAND = (0.0, 0.35, 0.12, 0.68)
NEXT_BAND = (0.87, 0.35, 1.0, 0.68)

#: the book's carousel dots: a long run of ring glyphs, read as digits by OCR.
#: They exist only under the book, which makes them the dependable identity.
DOTS_PATTERN = re.compile(r'^[0-9Oo\u25cf\u2022\u00b7]+$')
DOTS_BAND = (0.28, 0.80, 0.72, 0.90)
MIN_DOTS = 6


def _band(size, roi):
    width, height = size
    x0, y0, x1, y1 = roi
    return int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height)


def _points_sideways(component):
    """True when a compact gold component is a sideways-pointing triangle.

    ``component`` is a boolean mask cropped to the component's own box. A page-turn
    arrow fills about half of that box and is lopsided: one horizontal quarter
    carries far more gold than the other. A rounded button fills most of its box
    evenly, and a resource icon is not compact, so neither is mistaken for a page
    turn when it happens to sit in the same band.
    """
    height, width = component.shape
    if width < 3 or height < 3:
        return False
    fill = float(component.sum()) / float(width * height)
    if not MIN_FILL <= fill <= MAX_FILL:
        return False
    quarter = max(1, width // 4)
    left = float(component[:, :quarter].sum())
    right = float(component[:, -quarter:].sum())
    return max(left, right) / max(1.0, min(left, right)) >= MIN_LEAN


def triangle_box(image, roi):
    """Pixel box of the solid gold page-turn triangle inside ``roi``, or ``None``.

    ``image`` is an OpenCV BGR frame. The biggest *compact, pointed* gold component
    wins: a column of resource icons or a wide button strip can be gold too, and
    taking the bounding box of every gold pixel in the band turned those into a
    fake control.
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
            & (red - blue > MIN_WARMTH)).astype(np.uint8)
    if int(mask.sum()) < MIN_PIXELS:
        return None
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best = None
    for index in range(1, count):
        x, y, w, h, area = (int(value) for value in stats[index])
        if not MIN_PIXELS <= area <= MAX_PIXELS:
            continue
        if w > MAX_SIDE * width or h > MAX_SIDE * height:
            continue
        if not MIN_ASPECT <= w / max(1, h) <= MAX_ASPECT:
            continue
        if not _points_sideways(labels[y:y + h, x:x + w] == index):
            continue
        if best is None or area > best[0]:
            best = (area, [x0 + x, y0 + y, w, h])
    return None if best is None else best[1]


def carousel_dots(records, size, *, band=DOTS_BAND, minimum=MIN_DOTS):
    """The book's carousel dot row as OCR records, or ``[]`` when it is absent.

    ``records`` are :class:`maalimbus.vision.Text`-like objects. The row is drawn
    under every book page and nowhere else, so it separates the book from the pages
    it covers; the live battle page has no such row.
    """
    width, height = size
    found = []
    for record in records:
        text = (getattr(record, 'text', '') or '').strip().replace(' ', '')
        if len(text) < minimum or not DOTS_PATTERN.match(text):
            continue
        x, y, w, h = record.box
        centre = ((x + w / 2) / width, (y + h / 2) / height)
        if band[0] <= centre[0] <= band[2] and band[1] <= centre[1] <= band[3]:
            found.append(record)
    return found


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
