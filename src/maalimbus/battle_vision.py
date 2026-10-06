"""Experimental planning-page anchors; no turn submission or victory inference."""
import cv2
import numpy as np

from .theme_vision import ThemeCatalog
from .vision import find


class BattleCatalog(ThemeCatalog):
    def __init__(self, root):
        super().__init__(root, 'battle-catalog.json')


def planning_anchors(image, catalog, locale='en'):
    # Only the retained English label is available. Do not silently reuse it
    # as Japanese text validation. Lix locates skill glyphs at reference y560..600.
    if locale != 'en' or abs(image.shape[1]/image.shape[0]-16/9) > .02:
        return None
    buttons=catalog.matches(image,'win_rate',(.60,.65,1.,1.))
    if len(buttons)!=1:return None
    skills=[]
    width=image.shape[1]
    for kind in ('skill_slash','skill_pierce','skill_blunt'):
        for box in catalog.matches(image,kind,(0.,470/720,1.,625/720)):
            cx,cy=box[0]+box[2]/2,box[1]+box[3]/2
            if not 560/720<=cy/image.shape[0]<=600/720 or cx>=buttons[0][0]:continue
            if any(abs(cx-(b[0]+b[2]/2))<20*width/1280 for _,b in skills):
                return None
            skills.append((kind,box))
    if not 1<=len(skills)<=12:return None
    return {'win_rate':buttons[0],'skill_glyphs':sorted(skills,key=lambda s:s[1][0]),
            'scope':'pinned small English label and damage glyphs; experimental ROI, not full skill coverage'}


def preview_labels(records, size):
    # These are the upstream classifier's categories; text sightings are only
    # diagnostic. No coverage/assignment/survival proof follows from a few labels.
    result=[]
    for label in ('hopeless','struggling','neutral','favored','dominating'):
        for text in find(records,'^'+label+'$',(0.,.64,.90,.92),size,.85):
            result.append({'label':label,'box':text.box,'score':text.score,
                           'attention':label in ('hopeless','struggling','neutral')})
    return sorted(result,key=lambda t:t['box'][0])


def warm_control(image, label_box, *, min_area=2000, window=(60, 20, 60, 150)):
    """The warm (gold/orange) control blob just under a text label, or None.

    The battle's `START` action draws its word in a banner above the actual button,
    so the label box alone is not the control. This reads the control's own geometry
    from the frame; nothing is clicked here.
    """
    height, width = image.shape[:2]
    x, y, bw, bh = label_box
    left, top, right, bottom = window
    x0, y0 = max(0, x - left), max(0, y + top)
    x1, y1 = min(width, x + bw + right), min(height, y + top + bottom)
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    blue, green, red = crop[:, :, 0].astype(int), crop[:, :, 1].astype(int), crop[:, :, 2].astype(int)
    mask = ((red > 150) & (green > 90) & (blue < 110)).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for index in range(1, count):
        bx, by, bwidth, bheight, area = stats[index]
        if area < min_area or bwidth < 40 or bheight < 40:
            continue
        if best is None or area > best[0]:
            best = (int(area), int(bx + x0), int(by + y0), int(bwidth), int(bheight))
    return None if best is None else tuple(best[1:])


def start_button(records, size, image=None):
    """The battle's `START` action box: its control when the frame is available.

    Falls back to the label box, which is recorded rather than silently trusted.
    The banner sits above whichever gear the board layout puts it over, so the band
    spans the middle of the row rather than one fixed x.
    """
    matches = find(records, r'^START$', (.45, .63, .80, .79), size, .85)
    if len(matches) != 1:
        return None
    label = matches[0].box
    if image is None:
        return label
    control = warm_control(image, label)
    return label if control is None else control


def begin_turn_plan(records, size, image=None):
    """Plan one bounded turn-submission click, or refuse with an explicit reason."""
    hud = battle_hud(records, size)
    if hud is None:
        return dict(target=None, reason='battle_hud_not_identified')
    box = start_button(records, size, image)
    if box is None:
        return dict(target=None, reason='turn_start_not_present')
    return dict(target=box, reason='submit_turn', wave=hud['wave'], turn=hud['turn'])


def auto_assign_buttons(records, size):
    """The battle's `Win Rate` and `Damage` auto-assignment buttons.

    Each button is the union of its two caption words in its own band. These are
    read-only targets; this function never clicks and never infers a turn result.
    """
    win = find(records, r'^Win$', (.58, .70, .95, .84), size, .85)
    rate = find(records, r'^Rate$', (.58, .70, .95, .84), size, .85)
    damage = find(records, r'^Damage$', (.58, .77, .95, .90), size, .85)
    if len(win) != 1 or len(rate) != 1 or len(damage) != 1:
        return None
    union = (min(win[0].box[0], rate[0].box[0]), min(win[0].box[1], rate[0].box[1]),
             max(win[0].box[0] + win[0].box[2], rate[0].box[0] + rate[0].box[2])
             - min(win[0].box[0], rate[0].box[0]),
             max(win[0].box[1] + win[0].box[3], rate[0].box[1] + rate[0].box[3])
             - min(win[0].box[1], rate[0].box[1]))
    return {'win_rate': union, 'damage': damage[0].box,
            'scope': 'auto-assignment button geometry from their own captions; no input'}


def auto_assign_plan(records, size):
    """Plan one bounded auto-assignment click, or refuse with an explicit reason."""
    hud = battle_hud(records, size)
    if hud is None:
        return dict(target=None, reason='battle_hud_not_identified')
    buttons = auto_assign_buttons(records, size)
    if buttons is None:
        return dict(target=None, reason='auto_assign_buttons_not_present')
    return dict(target=buttons['win_rate'], damage=buttons['damage'],
                reason='win_rate_auto_assign', wave=hud['wave'], turn=hud['turn'])


def battle_hud(records, size):
    """Identify the combat HUD from its own WAVE/TURN captions.

    Both captions must appear exactly once in the top-left band. Their rendered
    values are gold bitmap glyphs that this OCR often misses, so a missing value is
    recorded as None rather than treated as a different page. Damage/Win-Rate
    readouts are diagnostics, never victory evidence.
    """
    wave = find(records, r'^WAVE$', (.0, .02, .06, .08), size, .85)
    turn = find(records, r'^TURN$', (.0, .06, .06, .13), size, .85)
    if len(wave) != 1 or len(turn) != 1:
        return None
    corner = [t for t in records
              if t.score >= .85 and t.text.strip()
              and .0 <= (t.box[0] + t.box[2] / 2) / size[0] <= .12
              and .0 <= (t.box[1] + t.box[3] / 2) / size[1] <= .16]
    wave_value = next((t.text.strip() for t in sorted(corner, key=lambda t: (t.box[1], t.box[0]))
                       if '/' in t.text), None)
    turn_value = next((t.text.strip() for t in sorted(corner, key=lambda t: (t.box[1], t.box[0]))
                       if t.text.strip().isdigit()), None)
    diagnostics = sorted(t.text.strip() for t in records
                         if t.score >= .85 and t.text.strip() in ('Win', 'Rate', 'Damage'))
    return {'wave': wave_value, 'turn': turn_value, 'wave_box': wave[0].box,
            'turn_box': turn[0].box, 'diagnostics': diagnostics,
            'scope': 'HUD identity only; no turn submission, coverage or victory claim'}
