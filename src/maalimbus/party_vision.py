"""The page that stands between a map node and a fight (2026-10-22).

Reaching an enemy node opens a participant screen whose only exits are "fill the
party" and "To Battle!".  A loop that does not know this page walks into it,
leaves `Total Participants 0 / 12` untouched, and then sits in front of a battle
HUD that never advances (`WAVE 0/10`, `TURN 1`) — which reads like a stalled
fight and is really an unfilled party.

Everything here is read from what the page prints about itself: the bordered
counter, and the fixed 6x2 card field the game draws for this preset.
"""
import re

LABEL = r'Total\s*Participants'
LABEL_ROI = (0.83, 0.69, 0.98, 0.78)
COUNTER_ROI = (0.83, 0.69, 0.99, 0.78)
COLUMNS = (.234, .344, .453, .563, .672, .781)
ROWS = (.333, .597)
CARD = (.100, .215)
TO_BATTLE_ROI = (0.845, 0.790, 0.985, 0.850)


def _inside(record, roi, size):
    w, h = size
    x, y, bw, bh = record.box
    cx, cy = (x + bw / 2) / w, (y + bh / 2) / h
    return roi[0] <= cx <= roi[2] and roi[1] <= cy <= roi[3]


def is_page(records, size, threshold=.75):
    """The page names itself with a two-word label above its counter."""
    from .vision import close_to
    return any(_inside(r, LABEL_ROI, size) and r.score >= threshold
               and close_to(r.text, 'Total Participants', 2) for r in records)


def participants(records, size, threshold=.6):
    """`(selected, total)` as the page prints it, or None when it is unreadable.

    The counter is drawn as one `n / 12` read on some frames and as two separate
    numbers on others, so both shapes are accepted; anything else is None rather
    than a guess.
    """
    picked = []
    for record in records:
        if record.score < threshold or not _inside(record, COUNTER_ROI, size):
            continue
        text = record.text.strip()
        pair = re.fullmatch(r'(\d{1,2})\s*[/|]\s*(\d{1,2})', text)
        if pair:
            return int(pair.group(1)), int(pair.group(2))
        if re.fullmatch(r'\d{1,2}', text):
            picked.append((record.box[0], int(text)))
    if len(picked) >= 2:
        picked.sort()
        return picked[0][1], picked[1][1]
    return None


def cards(size):
    """The 12 slots of this preset's card field, in reading order."""
    w, h = size
    out = []
    for row in ROWS:
        for column in COLUMNS:
            out.append((int((column - CARD[0] / 2) * w), int((row - CARD[1] / 2) * h),
                        int(CARD[0] * w), int(CARD[1] * h)))
    return out


def to_battle(size):
    w, h = size
    return (int(TO_BATTLE_ROI[0] * w), int(TO_BATTLE_ROI[1] * h),
            int((TO_BATTLE_ROI[2] - TO_BATTLE_ROI[0]) * w),
            int((TO_BATTLE_ROI[3] - TO_BATTLE_ROI[1]) * h))


def plan(records, size, chosen=0):
    """What this page wants next: a card to select, or the button that leaves it.

    A party that is already full is never re-clicked: on a full preset the cards
    read BACKUP and clicking one would swap a deployed identity out.
    """
    if not is_page(records, size):
        return None
    counted = participants(records, size)
    if counted is None:
        return None
    selected, total = counted
    if total <= 0:
        return None
    if selected < total:
        slots = cards(size)
        return dict(action='select', target=slots[min(chosen, len(slots) - 1)],
                    reason='a_party_that_is_not_full_cannot_start_the_fight',
                    selected=selected, total=total)
    return dict(action='click', target=to_battle(size),
                reason='a_full_party_leaves_by_its_own_button',
                selected=selected, total=total)
