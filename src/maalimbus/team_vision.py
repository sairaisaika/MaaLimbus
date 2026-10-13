"""Saved-team labels stay independent of identity art and preset numbers."""
import re
from .vision import find


BADGE_PATTERN = r'^\s*(SELECTED|BACKUP)\s*$'
#: The page's own participant counter, e.g. '11/11' (live frame
#: evidence/runtime/window-20261007-0030xx reads it at 1920 [1702,754,122,57] score .99).
PARTICIPANT_PATTERN = r'^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$'
PARTICIPANT_ROI = (0.86, 0.66, 0.97, 0.78)
CARD_COUNT = 12


def selected_saved_team(records, size):
    """Read the selected loadout's header, never its separate Preset number."""
    pattern=r'^\s*TEAMS\s*#\s*([1-9]|[1-3][0-9]|40)\s*$'
    hits=find(records,pattern,(.16,.13,.42,.22),size,.9)
    if len(hits)!=1:return None
    return int(re.fullmatch(pattern,hits[0].text,re.I).group(1))


def card_states(records, boxes, size):
    """Read every pre-battle card's participation badge, in reading order.

    ``boxes`` are the twelve card boxes in pixel space; the answer is one of
    ``'selected'``, ``'backup'`` or ``None`` (no badge yet, so the card is not in
    the team). The caption is what proves it: on the live frames every badge reads
    ``SELECTED``/``BACKUP`` at score 1.0, while the badge's *colour* is not usable
    because several identities wear exactly the same red as the SELECTED band
    (evidence/runtime/window-20261006-030750/frame-0001.json: cards 3, 5, 8 and 11
    would look picked while the page says 0/12).
    """
    width, height = size
    states = []
    for box in boxes:
        if not box:
            states.append(None)
            continue
        x, y, w, h = box
        roi = (x / width, y / height, (x + w) / width, (y + h) / height)
        found = find(records, BADGE_PATTERN, roi, size, .85)
        states.append(found[-1].text.strip().lower() if found else None)
    return states


def participants(records, size, roi=PARTICIPANT_ROI):
    """The page's participant counter as ``(picked, capacity)``, or ``None``.

    The badge columns alone cannot tell a full team from an unread slot: live frame
    build/live-prebattle.png (window-20261007-001439) shows eleven cards wearing their
    badges, a twelfth slot that this encounter simply does not have, and a bright
    'To Battle!'. Tapping the missing slot over and over is what build/window-run94.json
    spent fifty-seven steps on, so the counter -- which reads '11/11' at score .99 --
    is what says the team is already complete.
    """
    found = find(records, PARTICIPANT_PATTERN, roi, size, .85)
    if not found:
        return None
    match = re.match(PARTICIPANT_PATTERN, found[-1].text.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def team_pattern(team, locale='en'):
    if team.name:
        return r'^\s*' + re.escape(team.name).replace(r'\ ', r'\s*') + r'\s*$'
    prefix = r'TEAMS?' if locale == 'en' else r'(?:チーム|TEAMS?)'
    return rf'^\s*{prefix}\s*#?\s*{team.slot}\s*$'


def team_row(records, team, locale, size):
    matches = find(records, team_pattern(team, locale), (.04, .28, .19, .80), size, .8)
    return matches[0] if len(matches) == 1 else None


def team_header(records, team, locale, size):
    matches = find(records, team_pattern(team, locale), (.16, .07, .40, .18), size, .8)
    return matches[0] if len(matches) == 1 else None


#: Every card that is in the team prints its place in the deployment order as one
#: big glyph. The page keeps the order of the previous encounter, so reading those
#: glyphs is what lets the driver verify an inherited order instead of clearing and
#: re-picking it. Live evidence/runtime/window-20261012-023229/frame-0068.json reads
#: card 7's '6' inside card-relative (0.41,0.25) and card 10's '8' at (0.37,0.25),
#: and no other bare number on a card sits in this band.
ASSIGNMENT_BAND = (0.28, 0.10, 0.78, 0.44)
ASSIGNMENT_PATTERN = r'^\s*(\d{1,2})\s*$'


def assignment_box(box):
    """The pixel box that holds one card's printed order number, or ``None``."""
    if not box:
        return None
    x, y, w, h = box
    left, top, right, bottom = ASSIGNMENT_BAND
    return (x + round(left * w), y + round(top * h),
            max(1, round((right - left) * w)), max(1, round((bottom - top) * h)))


def assignment_numbers(records, boxes, size, threshold=.6):
    """Each card's printed deployment number, in card order (``None`` = unread).

    The driver compares this with the saved deployment: a page that already carries
    the saved order needs no ``Clear Selection`` before ``Battle!``.
    """
    width, height = size
    numbers = []
    for box in boxes:
        pixel = assignment_box(box)
        if pixel is None:
            numbers.append(None)
            continue
        x, y, w, h = pixel
        roi = (x / width, y / height, (x + w) / width, (y + h) / height)
        found = [item for item in find(records, ASSIGNMENT_PATTERN, roi, size, threshold)
                 if re.fullmatch(ASSIGNMENT_PATTERN, item.text.strip())]
        numbers.append(int(found[-1].text.strip()) if found else None)
    return numbers


def carries_saved_order(numbers, order, count):
    """Whether the page itself already shows ``order`` as positions 1..picked.

    ``numbers`` is ``assignment_numbers`` output, ``order`` the saved deployment
    (card index per position) and ``count`` the page's ``(picked, capacity)``.
    """
    picked = count[0] if count else 0
    if not numbers or not order or picked <= 0 or picked > len(order):
        return False
    for position in range(1, picked + 1):
        card = order[position - 1]
        if not 1 <= card <= len(numbers) or numbers[card - 1] != position:
            return False
    return True
