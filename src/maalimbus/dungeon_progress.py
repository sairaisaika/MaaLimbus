"""How far the run actually got, read from the game's own Dungeon Progress panel.

The panel is the only place the client states progress in words and digits:
it names each floor, tags the floor the party is standing on with its
difficulty, and prints that floor's step count under it.

Live evidence (2026-10-22, `build/r8-menu2.png`, 1280x720): the panel reads
``Dungeon Progress``, then ``Floor 1 (HARD)`` over ``4/5``, and the floors the
party has not reached print a level pair instead (``22/25``, ``23/25``), so the
fraction is only progress where the difficulty tag sits. That is why this
reader anchors on the tag and never on the first fraction it sees.

Without it the loop infers progress from clicks that failed, which is how a
floor at 4/5 was reported as a page that refused input.
"""
import re

from .vision import find

#: The panel's own band, normalized. It is drawn centred while the run is
#: paused, so nothing outside it belongs to the panel. The bottom reaches .70
#: because the panel's button row (Progress / Forfeit / Continue / To Window /
#: Config) sits under the floor labels -- live `build/r8-menu2.png` puts Continue
#: at y 452 of 720, i.e. .63.
PANEL_ROI = (0.20, 0.25, 0.80, 0.70)

TAG = re.compile(r'\(?\s*(HARD|NORMAL)\s*\)?', re.I)
FLOOR = re.compile(r'Floor\s*(\d+)', re.I)
STEPS = re.compile(r'(\d{1,2})\s*/\s*(\d{1,2})')
TITLE = re.compile(r'Dungeon\s*Progress', re.I)

#: How far under the tag its step count may be printed, in pixels at 1280x720,
#: and how far sideways. Measured on the live panel: the tag and its count share
#: a column ~30 px apart, and the next floor's level pair sits ~77 px to the
#: right -- so the sideways budget must stay under half that pitch, or the
#: neighbour's ``22/25`` is read as this floor's progress.
BELOW = (6, 60)
SIDEWAYS = 45


def dungeon_progress(records, size, *, roi=PANEL_ROI):
    """Read the panel: ``{'floor', 'difficulty', 'steps', 'of', 'title'}`` or None.

    None means the panel is not on screen at all -- which the caller must not
    confuse with a panel that is on screen and unreadable, so an unreadable
    panel is reported as a dict carrying ``reason`` instead of as None.
    """
    w, h = size
    tagged = find(records, TAG.pattern, roi, size, threshold=.6)
    if not tagged:
        return None
    title = find(records, TITLE.pattern, roi, size, threshold=.6)
    if not title and not find(records, FLOOR.pattern, roi, size, threshold=.6):
        return None
    tag = tagged[0]
    tx, ty = (tag.box[0] + tag.box[2] / 2) / w, (tag.box[1] + tag.box[3] / 2) / h
    floor = None
    for record in find(records, FLOOR.pattern, (tx - .12, ty - .05, tx + .12, ty + .05),
                       size, threshold=.6):
        match = FLOOR.search(record.text)
        if match:
            floor = int(match.group(1))
            break
    steps = of = None
    band = ((tx * w - SIDEWAYS) / w, (ty * h + BELOW[0]) / h,
            (tx * w + SIDEWAYS) / w, (ty * h + BELOW[1]) / h)
    nearest = None
    for record in find(records, STEPS.pattern, band, size, threshold=.6):
        match = STEPS.search(record.text)
        if not match:
            continue
        dx = abs((record.box[0] + record.box[2] / 2) / w - tx)
        if nearest is None or dx < nearest[0]:
            nearest = (dx, int(match.group(1)), int(match.group(2)))
    if nearest is not None:
        steps, of = nearest[1], nearest[2]
    payload = {
        'difficulty': tag.text.upper().strip('() ').strip() if tag.text else None,
        'floor': floor,
        'steps': steps,
        'of': of,
        'title': title[0].text if title else None,
    }
    if steps is None or of is None or not of:
        payload['reason'] = 'the_floor_tag_is_on_screen_but_its_step_count_was_not_read'
    elif steps > of:
        payload['reason'] = 'the_step_count_is_not_a_count_within_its_own_floor'
        payload['steps'] = payload['of'] = None
    return payload


def steps_left(payload):
    """How many steps that floor still offers, or None when it was not read."""
    if not payload or payload.get('reason'):
        return None
    return max(0, payload['of'] - payload['steps'])
