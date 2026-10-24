"""Saved-team labels stay independent of identity art and preset numbers."""
import re
from .vision import find


BADGE_PATTERN = r'^\s*(SELECTED|BACKUP)\s*$'
#: The page's own participant counter, e.g. '11/11' (live frame
#: evidence/runtime/window-20261007-0030xx reads it at 1920 [1702,754,122,57] score .99).
PARTICIPANT_PATTERN = r'^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$'
PARTICIPANT_ROI = (0.86, 0.66, 0.97, 0.78)
CARD_COUNT = 12


#: The page names the saved team two ways. Both live wordings are the same
#: header in the same column; the reader understood only the first one, so the
#: team check that shipped for it never fired once (`Preset #1` at
#: [150,254,84,21] score .9098 on every pre-battle frame of
#: packaged-mirror-20261024-042500 / -001120 / -001939, while the old band
#: started at x=0.16 and the word was not `TEAMS`).
TEAM_HEADER_PATTERN = r'^\s*(TEAMS?|Preset)\s*#\s*([1-9]|[1-3][0-9]|40)\s*$'
#: Both wordings sit in the page's top-left column; the pattern is specific
#: enough that the wider band cannot pick up a button caption.
TEAM_HEADER_ROI = (0.02, 0.10, 0.50, 0.32)
TEAM_HEADER_SCORE = 0.85
#: The word alone, used to decide whether a page speaks "TEAMS" at all.
TEAMS_ONLY_PATTERN = r'^\s*TEAMS?\s*#'


def saved_team_header(records, size):
    """The saved-team header the page shows, with the word it used.

    ``TEAMS #N`` is the header the page has always had; ``Preset #N`` is what the
    current build prints in the same column (four archived frames, three runs).
    Both share the top-left band, so the *word* decides: a page that shows a
    ``TEAMS`` header reads that one, and ``Preset`` is only accepted when no
    ``TEAMS`` header is on the page at all. Anything else — two headers of the
    same word, or none — is a question, not a guess.
    """
    hits = find(records, TEAM_HEADER_PATTERN, TEAM_HEADER_ROI, size, TEAM_HEADER_SCORE)
    parsed = []
    boxes = {}
    for hit in hits:
        match = re.fullmatch(TEAM_HEADER_PATTERN, hit.text, re.I)
        if match is not None:
            word = match.group(1).lower()
            parsed.append((word, int(match.group(2))))
            # The header is also the control: pressing it opens the preset column, so a
            # run whose board shows another saved team can pick the right one instead of
            # stopping (D117's first live effect was a stop at 14 s with 0 clicks).
            boxes[word] = tuple(int(value) for value in hit.box)
    teams = [slot for word, slot in parsed if word.startswith('team')]
    presets = [slot for word, slot in parsed if word == 'preset']
    # A page that shows any TEAMS header at all speaks that language: its
    # preset number is a preset, not the team (the loadout picker lists
    # several). Only a page with no TEAMS header anywhere is read by the
    # preset column the current pre-battle page prints.
    if not teams and find(records, TEAMS_ONLY_PATTERN, (0.0, 0.0, 1.0, 1.0), size, TEAM_HEADER_SCORE):
        return None
    if len(teams) == 1:
        return {'slot': teams[0], 'word': 'teams', 'box': boxes.get('team')}
    if not teams and len(presets) == 1:
        return {'slot': presets[0], 'word': 'preset', 'box': boxes.get('preset')}
    return None


def selected_saved_team(records, size):
    """Read the selected loadout's header, whichever word the page used."""
    header = saved_team_header(records, size)
    return None if header is None else header['slot']


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
