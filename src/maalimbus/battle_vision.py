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


def dial_control(image, *, roi=(0.58, 0.60, 0.82, 0.93), min_area=4000, min_side=100,
                 max_side=160, max_aspect=1.25, min_fill=0.28):
    """The battle's lit turn dial: the large warm disc that submits the turn, or None.

    Some boards draw the START word so small under their dial that OCR never returns
    it: live frame evidence/runtime/window-20261007-004730/frame-0326.png (floor 3, turn
    6/25) has no 'START' token at all, so start_button found nothing, the driver fell
    back to re-assigning skills, and the fight stood still through 140 clicks
    (build/window-run95.json, build/window-run96.json). The dial itself is a warm blob at
    1920 (1327,741,125,154) area 6646, left of the Win Rate button, so it is read by
    colour inside a band that excludes those buttons, and only when no readable START
    word exists.

    The dial has two warm variants and only the lit one is the control. Live
    window-20261007-194201 clicked the dim variant (1455,800,81,79) area 1913 seven
    times as if it were START and never submitted a turn: the board draws that variant
    while a turn is still unassigned, and it only lights up (1439,772,121,133) area 5512,
    fill 0.34, aspect 1.10 after the Win Rate auto-assignment is pressed -- proven live on
    both boards, e.g. window-20261007-175552 pressed Win Rate at 22:43:44 and the START
    banner appeared on frame-1010.json at 22:43:46. So the shape of the lit disc is what
    is read: side 100..160, aspect at most 1.25, and at least 28% of its own box filled.
    That keeps the disc and drops both the dim variant (side 79-81) and the wide warm
    highlights of the skill board that share this band -- measured on
    window-20261007-175552/frame-0307.png (decoy (1180,732,200,145) area 5949, aspect
    1.38, fill 0.21 beside the real (1436,770,121,133)) and frame-0083.png ((1113,676,172,
    264) area 13468). The old band's right edge (0.78*1920 = 1497) cut the disc's centre x
    about 1500 off, which is why the wide band stays; the Win Rate/Damage captions start at
    x=1584, outside the right edge (0.82*1920 = 1574), so they cannot be mistaken for it.
    """
    height, width = image.shape[:2]
    x0, y0 = int(width * roi[0]), int(height * roi[1])
    x1, y1 = int(width * roi[2]), int(height * roi[3])
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    blue, green, red = (crop[:, :, 0].astype(int), crop[:, :, 1].astype(int),
                        crop[:, :, 2].astype(int))
    mask = ((red > 150) & (green > 90) & (blue < 110)).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for index in range(1, count):
        bx, by, bwidth, bheight, area = stats[index]
        if area < min_area or bwidth < min_side or bheight < min_side:
            continue
        if max(bwidth, bheight) > max_side:
            continue
        if max(bwidth, bheight) > max_aspect * min(bwidth, bheight):
            continue
        if area < min_fill * bwidth * bheight:
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
    # The band is read by the label's centre, and the banner sits right of the middle
    # gears: live evidence/runtime/window-20261006-103550/frame-0044.json puts "START"
    # at [1518,738,60,28], whose centre is x=0.806, just outside the old 0.80 edge.
    # That made the control appear on some frames and vanish on others, and the driver
    # then fell back to re-assigning skills instead of submitting the turn.
    matches = find(records, r'^START$', (.40, .63, .88, .80), size, .85)
    if len(matches) != 1:
        # No readable START word: this board keeps it too small under its own dial
        # (live build/live-battle2.png), so the dial is read by colour instead of
        # re-assigning skills for a turn that never gets submitted.
        return None if image is None else dial_control(image)
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

    The TURN caption must appear exactly once in the top-left band, and the WAVE
    caption must be readable there or, when this OCR drops the whole word, its own
    ``n/m`` value standing in the same band. Their rendered values are gold bitmap
    glyphs that this OCR often misses, so a missing value is recorded as None rather
    than treated as a different page. Damage/Win-Rate readouts are diagnostics, never
    victory evidence.
    """
    # The W stays readable, but the red battlefield backdrop makes the OCR drop a
    # stroke off it: live evidence/runtime/window-20261006-053000/frame-0030.json reads
    # "NAVE" [28,41,38,24] beside a clean "TURN", and the whole page then fell back to
    # UNKNOWN for a full turn. On window-20261006-053923/frame-0056.json the caption is
    # gone altogether ("WS" is the left skill column) while "0/10" [78,37,58,32] and
    # "TURN" [20,97,42,22] are both read, so the value stands in for the caption. The
    # two captions live in neighbouring bands of the same corner, and no other page
    # puts a turn counter with a wave counter there, so neither form promotes a
    # different page.
    wave = find(records, r'^[WN]AVE$', (.0, .02, .06, .08), size, .85)
    if not wave:
        # The value itself can lose its leading digit to the red backdrop: live
        # evidence/runtime/window-20261007-151655/frame-0529.json reads "/10"
        # [98,39,34,24] 0.99 beside a clean "TURN" [20,97,42,22] 1.0 while START, Win,
        # Rate and Damage are all readable, and the page still fell back to UNKNOWN --
        # the window then waited the battle out and stopped. The counter shares the
        # corner with TURN and no other page draws a counter there, so the missing
        # digit is allowed.
        wave = find(records, r'^\d{0,2}\s*/\s*\d{1,2}$', (.0, .02, .09, .08), size, .85)
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
