"""Saved-team labels stay independent of identity art and preset numbers."""
import re
from .vision import find


BADGE_PATTERN = r'^\s*(SELECTED|BACKUP)\s*$'
CARD_COUNT = 12


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
