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


#: The end-of-run summary, measured on live `build/after-defeat.png` (1280x720):
#: left column holds `Exploration Complete`, then `Dungeon Progress`, then the
#: floors, then `Last Reached` and `Total Progress NN%`.
SUMMARY_ROI = (0.05, 0.08, 0.95, 0.95)
SUMMARY_TITLE = re.compile(r'Exploration', re.I)
SUMMARY_TAIL = re.compile(r'Complete', re.I)
REACHED = re.compile(r'^\s*(.+?)\s*$')
TOTAL = re.compile(r'(\d{1,3})\s*%')


def exploration_summary(records, size):
    """Read the run's own receipt, or None when that page is not on screen.

    ``Exploration Complete`` is the only screen that states, after the fact, how
    far a run got: the floors it reached, the last one with its ``4/6``, and
    ``Total Progress 13%``. The frames the loop used to stop on said none of it,
    which is why a lost run looked like a map that refused clicks.
    """
    title = find(records, SUMMARY_TITLE.pattern, SUMMARY_ROI, size, threshold=.7)
    if not title:
        return None
    # The client draws the two words on two lines, so the pair -- not one merged
    # token -- is what identifies the screen.
    head = title[0].box
    tail = find(records, SUMMARY_TAIL.pattern,
                (head[0] / size[0], head[1] / size[1],
                 (head[0] + head[2]) / size[0], head[1] / size[1] + .12), size, threshold=.7)
    if not tail:
        return None
    title = [title[0]]
    payload = {'title': title[0].text, 'floor': None, 'steps': None, 'of': None,
               'last_reached': None, 'total_percent': None}
    floor = find(records, FLOOR.pattern, SUMMARY_ROI, size, threshold=.6)
    if floor:
        match = FLOOR.search(floor[0].text)
        payload['floor'] = int(match.group(1)) if match else None
    stepped = find(records, STEPS.pattern, SUMMARY_ROI, size, threshold=.6)
    if stepped:
        match = STEPS.search(stepped[0].text)
        if match:
            payload['steps'], payload['of'] = int(match.group(1)), int(match.group(2))
    total = find(records, r'\d{1,3}\s*%', SUMMARY_ROI, size, threshold=.6)
    if total:
        match = TOTAL.search(total[0].text)
        if match:
            payload['total_percent'] = int(match.group(1))
    # `Last Reached` is followed by the dungeon's name and the floor it stopped on;
    # the label is the anchor and the two rows under it are its value.
    anchor = find(records, r'Last\s*Reached', SUMMARY_ROI, size, threshold=.6)
    if anchor:
        box = anchor[0].box
        band = (SUMMARY_ROI[0], (box[1] + box[3]) / size[1], SUMMARY_ROI[2], .92)
        under = find(records, r'\S', band, size, threshold=.6)
        rows = [r.text for r in sorted(under, key=lambda r: r.box[1])][:2]
        payload['last_reached'] = ' / '.join(rows) if rows else None
    if payload['steps'] is None or not payload['of']:
        payload['reason'] = 'the_summary_is_on_screen_but_its_step_count_was_not_read'
    return payload
