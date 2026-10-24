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
    # The dial is an annulus whose own dark hub splits the warm mask into an upper arc
    # and a lower disc. On the board of live run packaged-mirror-20261022-015843 those
    # two pieces are all that exists -- (1326,771,113,58) area 1646 and (1341,799,88,79)
    # area 1935 -- and neither clears the area gate, so the dial was never found, the
    # driver re-assigned, and TURN stood at 6 for four rounds. Their boxes overlap, and
    # their union (121x137) is the same shape the lit variant is measured at, so pieces
    # that overlap are folded into one candidate before the gates are applied.
    # Pressing this control is safe in either state: proven live on that same board, a
    # tap on the dial with the turn still unassigned changed only the animation, and the
    # same tap right after Win Rate submitted the turn (TURN 6 -> attack sequence). The
    # gates below are unchanged; only how a fragmented disc is assembled is new.
    pieces = []
    for index in range(1, count):
        bx, by, bwidth, bheight, area = stats[index]
        if area < 400 or bwidth < 20 or bheight < 20:
            continue
        pieces.append([int(bx), int(by), int(bwidth), int(bheight), int(area)])
    merged = True
    while merged:
        merged = False
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                a, b = pieces[i], pieces[j]
                if (a[0] - 6 < b[0] + b[2] and b[0] - 6 < a[0] + a[2]
                        and a[1] - 6 < b[1] + b[3] and b[1] - 6 < a[1] + a[3]):
                    x = min(a[0], b[0]); y = min(a[1], b[1])
                    pieces[i] = [x, y,
                                 max(a[0] + a[2], b[0] + b[2]) - x,
                                 max(a[1] + a[3], b[1] + b[3]) - y,
                                 a[4] + b[4]]
                    pieces.pop(j)
                    merged = True
                    break
            if merged:
                break
    best = None
    for bx, by, bwidth, bheight, area in pieces:
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


def dial_beside_caption(records, size, image):
    """The dial when it is still fragmented: the brightest warm piece left of `Win Rate`.

    Live run packaged-mirror-20261022-015843 (frame-0020, WAVE 1/1, TURN 6) draws the
    dial as an annulus whose hub splits the warm mask into (1326,771,113,58) area 1646
    and (1341,799,88,79) area 1935 -- neither clears the disc gates, so the dial was
    never found, the driver re-assigned, and TURN stood at 6 through four rounds. The
    board still prints Win/Rate under it, so the control is read from that caption's own
    position instead of from a shape: the largest warm piece whose centre lies left of
    the caption's middle and inside its vertical span. Unassignable turns are safe here:
    a tap on this dial with the turn unassigned changed only the animation, and the same
    tap right after Win Rate submitted the turn (TURN 6 -> attack sequence), so reading
    it cannot cause a wrong submit -- the runner presses auto-assign first regardless.
    """
    if image is None:
        return None
    buttons = auto_assign_buttons(records, size)
    if buttons is None:
        return None
    label = buttons['win_rate']
    height, width = image.shape[:2]
    x0, y0 = int(width * 0.55), int(height * 0.55)
    x1, y1 = int(width * 0.82), int(height * 0.95)
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
        if area < 1200:
            continue
        centre_x, centre_y = bx + x0 + bwidth / 2, by + y0 + bheight / 2
        if centre_x >= label[0] + label[2] * 0.5:
            continue
        if not (label[1] - 40 <= centre_y <= label[1] + label[3] + 90):
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
        if image is None:return None
        fixed=dial_control(image)
        if fixed is not None:return fixed
        buttons=auto_assign_buttons(records,size)
        hud = battle_hud(records,size)
        if hud is None:return None
        # D107: a board whose turn caption this OCR cannot read keeps the ring as the
        # authority for the dial, because the toggle captions that would narrow the
        # search band were never read either (they stand in as fixed points, and a
        # fixed point cannot say where a *moving* dial is).
        if hud.get('turn') is None:
            ring = submit_dial(image)
            if ring is not None:return ring
        if buttons is not None:
            # The rightmost dial moves when the number of active sinners changes.
            # Derive its search band from the two native assignment captions; keep the
            # exact same lit-disc area/shape/fill gate and reject dim controls.
            #
            # D107: a fixed point may stand in for a toggle, but it cannot say where a
            # *moving* dial is, so only a toggle read from its own caption may anchor
            # this band (live
            # `tests/test_battle_dynamic_dial.py::test_shifted_lit_dial_is_bound_to_the_actual_assignment_captions`).
            width,height=size;x,y,w,h=buttons['win_rate'];sx,sy=width/1920,height/1080
            if not buttons.get('positional'):
                moving=dial_control(image,roi=((x-180*sx)/width,(y-55*sy)/height,
                                           (x-10*sx)/width,(y+145*sy)/height))
                if moving is not None:return moving
                # Still fragmented after both bands -- read it from the `Win Rate` caption
                # it sits left of; that is what the board of live run
                # packaged-mirror-20261022-015843 needs (see dial_beside_caption).
                captured=dial_beside_caption(records,size,image)
                if captured is not None:return captured
        # D101: on a board whose turn caption this OCR cannot read -- the D99/D100 case,
        # where `battle_hud` says `turn is None` -- every caption-anchored reading above
        # is unavailable by construction, and the dial is the gold ring itself (two live
        # frames, identical box).  A board that does read its turn keeps the caption
        # gates: a missing `Damage` there still means the reading is not trusted.
        if hud.get('turn') is None:
            return submit_dial(image)
        # D151: a readable `TURN` is not evidence that the dial can be found by its
        # captions.  Measured 2026-10-24 (operator screenshot, TURN 7, MAX, every slot
        # assigned, `Win Rate` ticked): the board reads its turn, the captions resolve,
        # and the dial's band was still empty -- `moving` and `captured` both refused, so
        # the loop never pressed START and re-planned the turn until the run ended.
        # The ring is the control; a caption is only how it was located, so the ring gets
        # a last look -- but only inside the band its own captions define, because a free
        # ring would accept any other lit disc (the guard that keeps a shifted dial from
        # being blessed still applies).
        ring = submit_dial(image)
        if ring is not None and buttons is not None:
            width,height=size;sx,sy=width/1920,height/1080
            x,y,w,h=buttons['win_rate']
            cx,cy=ring[0]+ring[2]/2,ring[1]+ring[3]/2
            if (x-230*sx)<=cx<=(x-10*sx) and (y-75*sy)<=cy<=(y+165*sy):
                return ring
        return None
    label = matches[0].box
    if image is None:
        return label
    control = warm_control(image, label)
    return label if control is None else control


# D106: the skill row sits along the bottom of the battle board (measured on
# `evidence/runtime/packaged-mirror-20261024-073605/frame-0003.png`: cards from x 470 to
# 1300, y 900 to 1030).  Tapping a slot is harmless -- the game opens or closes that
# slot's detail -- which is why the overlay is dismissed here rather than on the board.
SKILL_ROW_POINT = (560, 960)


def begin_turn_plan(records, size, image=None):
    """Plan one bounded turn-submission click, or refuse with an explicit reason."""
    hud = battle_hud(records, size)
    if hud is None:
        return dict(target=None, reason='battle_hud_not_identified')
    box = start_button(records, size, image)
    if box is None:
        return dict(target=None, reason='turn_start_not_present')
    return dict(target=box, reason='submit_turn', wave=hud['wave'], turn=hud['turn'])


#: The two auto-assignment toggles (D107, corrected by D114): D107 measured the caption
#: union on 544 frames and read its spread as an arrow glyph; re-measuring 1,655 frames
#: showed the spread is the *row* moving, so only the vertical place is a constant.
# The toggles' *vertical* place is fixed; their horizontal place is not. Over 1,655
# archived battle frames the `Win` caption sits at x 1,508-1,797 (median 1,510) and at
# y 803-807, and `Damage` is exactly 70 px below it. The row ends where the last living
# sinner's card ends, so the pair slides left as the party shrinks; D107's single point
# (1,622) was the average of that spread and missed both ends by up to 100 px.
TOGGLE_POINTS = {'win_rate': (1510, 806), 'damage': (1510, 876)}
TOGGLE_X_RANGE = (1450, 1830)   # every archived `Win` caption, plus the button's own width
TOGGLE_Y = {'win_rate': 806, 'damage': 876}
TOGGLE_HALF = (60, 22)


def toggle_boxes(size, *, records=None):
    """The measured toggle boxes, scaled to this frame.

    A click target is a box, so the measured centre is given a half-size large enough to
    absorb the caption height and small enough to stay clear of the skill row directly
    below (the row's top edge is at y 900 on a 1080 screen, 84 px below the centre).
    """
    width, height = float(size[0]), float(size[1])   # `find` reads size as (width, height)
    half_width, half_height = TOGGLE_HALF
    points = dict(TOGGLE_POINTS)
    if records:
        anchor = _caption_x(records, size)
        if anchor is not None:
            points = {name: (anchor, TOGGLE_Y[name]) for name in TOGGLE_POINTS}
    boxes = {}
    for name, (x, y) in points.items():
        boxes[name] = (int(round(x * width / 1920.0 - half_width)),
                       int(round(y * height / 1080.0 - half_height)),
                       2 * half_width, 2 * half_height)
    return boxes


def _battle_chrome(records, size):
    """Whether this frame draws the battle's own chrome (`MAX`, `WAVE` or `TURN`).

    Used only to decide whether the measured toggle points may stand in for a caption
    that could not be read -- a page without this chrome is not the battle board.
    """
    for pattern in (r'^MAX$', r'^WAVE$', r'^TURN$'):
        if find(records, pattern, (.0, .0, 1.0, .25), size, .85):
            return True
    return False


def _caption_x(records, size):
    """The x the toggles are at, read from whichever of their captions this frame shows.

    The two labels are drawn one above the other at the row's right end, so a single
    readable word locates both. Returns None when no caption is readable at all, and then
    the measured median stands in.
    """
    for pattern, band in ((r'^Win$', (.60, .70, .98, .80)),
                          (r'^Rate$', (.60, .70, .98, .80)),
                          (r'^Damage$', (.60, .77, .98, .88))):
        found = find(records, pattern, band, size, .85)
        if len(found) == 1:
            box = found[0].box
            centre = int(round(box[0] + box[2] / 2.0))
            if TOGGLE_X_RANGE[0] <= centre <= TOGGLE_X_RANGE[1]:
                return centre
    return None


def auto_assign_buttons(records, size, *, positional=True):
    """The battle's `Win Rate` and `Damage` auto-assignment buttons.

    Each button is the union of its two caption words in its own band.  When a caption
    cannot be read the measured fixed points stand in for it (D107): the operator asked
    for the toggle to be pressed rather than rediscovered, and the two are the same place
    to within a few pixels on every archived frame.

    These are read-only targets; this function never clicks and never infers a turn result.
    """
    win = find(records, r'^Win$', (.58, .70, .95, .84), size, .85)
    rate = find(records, r'^Rate$', (.58, .70, .95, .84), size, .85)
    damage = find(records, r'^Damage$', (.58, .77, .95, .90), size, .85)
    if len(win) != 1 or len(rate) != 1 or len(damage) != 1:
        # Only a frame that shows battle chrome may borrow the fixed point: a non-battle
        # page must keep getting None, or the caller would click a toggle that is not
        # drawn there (live `tests/test_battle_touch.py::test_auto_assign_refuses_without_the_battle_page`).
        # A *fixed point* is not evidence that anything is drawn, so the page-identity
        # gate asks for `positional=False` and keeps requiring the captions themselves
        # (live `tests/test_theme_vision.py::test_regular_battle_requires_numeric_turn_and_both_controls`).
        if not positional or not _battle_chrome(records, size):
            return None
        fixed = toggle_boxes(size, records=records)
        return {'win_rate': fixed['win_rate'], 'damage': fixed['damage'],
                'positional': True,
                'scope': 'auto-assignment toggles anchored on whichever caption this '
                         'frame shows, else their measured median (D114)'}
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


def submit_dial(image):
    """The turn-submission dial, found by the gold ring it is drawn with.

    Live evidence `evidence/runtime/packaged-mirror-20261024-064826/frame-0009.png` and
    `...-063942/frame-0001.png` both read the WAVE caption, `MAX`, `Win` and `Damage`
    and **no** `START` word, and `dial_control`'s lit-disc gate rejected this dial: the
    frame is a battle whose turn can be submitted and whose control the reader could not
    name, so the window refused with `battle_has_no_proven_control` and sent no input.

    The dial is the largest warm-gold near-square ring right of the skill bar; both
    frames put it at exactly (1323, 768, 123, 133).  Returns a box or None.
    """
    height, width = image.shape[:2]
    if width < 200 or height < 200:
        return None
    import cv2
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # A dim dial (the board before the turn is assigned) must not qualify: live
    # `tests/test_battle_dynamic_dial.py::test_unassigned_dim_dial_stays_unavailable`.
    mask = cv2.inRange(hsv, (12, 120, 160), (34, 255, 255))
    mask[:, :int(width * 0.57)] = 0
    mask[:int(height * 0.60), :] = 0
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        if bw < 60 or bh < 60 or bw * bh < 6000:
            continue
        # The dial is a disc (123x133 on both live frames, ratio 0.92).  A wide blob is
        # the skill row: live `packaged-mirror-20261024-065736` offered (1099,790,190,149)
        # for one frame, ratio 1.28, and clicking a card is not submitting a turn.
        if not 0.7 <= bw / float(bh) <= 1.25:
            continue
        if best is None or bw * bh > best[0]:
            best = (bw * bh, [int(x), int(y), int(bw), int(bh)])
    return None if best is None else best[1]


def speed_toggle(records, size):
    """The battle's own speed/auto caption, `MAX`, at the top-right of the board.

    Measured over 2,025 archived battle frames: the caption is present in every one,
    its centre within x 1661-1667 and y 55-59 on 1920x1080 -- a genuinely fixed
    control, unlike the Win Rate toggle whose x follows the party (D114).  The loop
    never pressed it, so every fight ran at the game's default speed.
    """
    import types
    rows = [r if hasattr(r, 'box')
            else types.SimpleNamespace(text=(r or {}).get('text', ''),
                                       box=list((r or {}).get('box') or []),
                                       score=(r or {}).get('score', 0.0))
            for r in (records or [])]
    for record in find(rows, r'^MAX$', (.84, .03, .95, .08), size, .85):
        return record.box
    return None


def hud_controls(records, size):
    """How many of the HUD's own corner controls this frame reads, each in its band.

    Speed (`MAX`), the Win/Rate toggle and the Damage readout are drawn by no other
    page.  They are counted, never used as victory evidence.
    """
    bands = ((r'^MAX$', (.80, .02, .99, .13)),
             (r'^Win$', (.74, .70, .84, .78)),
             (r'^Rate$', (.74, .72, .86, .80)),
             (r'^Damage$', (.74, .77, .86, .85)))
    seen = 0
    for pattern, roi in bands:
        if find(records, pattern, roi, size, .85):
            seen += 1
    return seen


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
    if len(wave) == 1 and not turn:
        # The TURN caption is drawn in the same corner and this OCR drops it often: live
        # evidence/runtime/packaged-mirror-20261024-063400/frame-0024 reads a clean
        # "WAVE" (score 0.9999) beside "MAX", "Win" and "Damage" and no TURN at all, so
        # a whole battle sat UNKNOWN (D99).  When the wave caption is readable, two of
        # the HUD's own controls are read in their own bands, and no other page draws
        # those together, the turn caption is allowed to be the part the OCR lost.
        controls = hud_controls(records, size)
        if controls >= 2:
            # The caption is not the value: `WAVE` says this is the battle, `1/1` would
            # say which wave.  Reporting the caption as the wave would hand the loop a
            # signature that can never move, and the stall guard would then end a healthy
            # fight (live `063942`, `battle_progress_stalled` after one turn).  Both
            # values stay None, which `battle_progress` already knows is blindness and
            # not staleness (D100).
            return dict(wave=None, turn=None, wave_box=wave[0].box, turn_box=None,
                        diagnostics=controls and ['Win', 'Rate', 'Damage', 'MAX'],
                        scope='HUD identity from the wave caption plus its own controls; '
                              'turn caption unreadable, no turn submission or victory claim')
    if not wave and len(turn)==1 and auto_assign_buttons(records,size,positional=False) is not None:
        # Regular encounters omit WAVE entirely. A local numeric turn and both
        # independent assignment controls identify this variant; wave stays None.
        values=find(records,r'^\d{1,3}$',(.035,.077,.081,.121),size,.9)
        if len(values)==1 and int(values[0].text)>0:
            return dict(wave=None,turn=values[0].text,wave_box=None,turn_box=turn[0].box,
                        diagnostics=['Win','Rate','Damage'],scope='regular HUD identity; wave absent, no turn submission or victory claim')
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

TURN_BADGE = (0.050, 0.074, 0.014, 0.026)   # the digit inside the TURN badge, 1920x1080
TURN_CHANGED = 4.0                          # mean abs difference that means "a new turn"


def turn_signature(image, box=None):
    """A small, comparable picture of the turn badge's digit.

    Measured on `evidence/runtime/packaged-mirror-20261024-095825`: within one turn the
    crop varies by <= 0.06 (mean absolute difference) and across a turn boundary by 13.56
    -- a two-hundredfold margin, so the badge answers "did the turn advance" without any
    OCR (the caption itself reads `TURN` and its digit is not recognised at all).
    """
    if image is None:
        return None
    height, width = image.shape[:2]
    fx, fy, fw, fh = box or TURN_BADGE
    x, y = int(round(fx * width)), int(round(fy * height))
    w, h = max(8, int(round(fw * width))), max(8, int(round(fh * height)))
    crop = image[y:y + h, x:x + w]
    if crop.size == 0:
        return None
    small = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (8, 8), interpolation=cv2.INTER_AREA)
    return [int(v) for v in small.reshape(-1)]


def turn_changed(before, after, *, limit=TURN_CHANGED):
    """True when the badge picture moved far enough to mean a new turn (D113)."""
    if not before or not after or len(before) != len(after):
        return False
    total = sum(abs(int(a) - int(b)) for a, b in zip(before, after))
    return total / float(len(before)) > limit
