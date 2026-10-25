"""Mirror Dungeon map page identity and bounded route reading.

The map is identified by text: the localized `Exploring Floor <n>` /
`Before Entry Floor <n>` header with the selected theme pack name beneath it. Node
artwork, cover art, seasonal icons and currency amounts are never identity anchors.

Route reading stays conservative on purpose. A node may only be planned when the
page identifies as the map, a single current-position marker is proven, and every
neighbour of the chosen node other than a single unvisited candidate already has
positive cleared evidence. Anything else returns an explicit refusal instead of a
fabricated click target. No function here calls an input API.
"""
from dataclasses import dataclass
import re

from .route_plan import plan_route
from .vision import Text, find

HEADER_WORD = r'(?:Explori\w{0,3}|Before\s+Entry)'
HEADER_PATTERN = r'^' + HEADER_WORD + r'\s*(?:F\w{3,5}?|F\s*\d)\s*([1-5])?\s*$'
#: the same header in the shapes the game really renders on the floor-1 map page. OCR
#: has produced all three: 'Exploring Floor 1' as one token, 'Exploring' [56,127,202,53]
#: plus 'Floor' [236,133,122,43] as two (evidence/runtime/window-20261006-033107),
#: and 'Exploring Floor' [60,133,330,41] with the stylised digit dropped by the
#: recogniser (evidence/runtime/window-20261006-040651). The word itself also mangles:
#: window-20261006-104857/frame-0080 reads the whole line as 'Exploring Flaor'
#: [56,127,310,53] 0.99, so the word after the label is only required to open with F
#: and carry three to five more characters (or an F followed by the digit). So the
#: floor digit is optional and the label may or may not carry the word "Floor"; the
#: pack line below is what keeps an unrelated page from being promoted into MAP.
#: The label's tail also drops off: live run build/window-run111.json sat on floor 3
#: "To be Cleaved" while every frame read the label as 'Explorin' (no trailing g) and
#: the page stayed UNKNOWN for five rounds, so the word is matched by its opening six
#: letters plus at most three more. The space between the word and "Floor" also
#: disappears in live OCR: window-20261007-034308/frame-0198 read the whole floor-5
#: line as 'ExploringFloor5' [56,121,356,63] 0.95 and the page stayed UNKNOWN, so the
#: separator is optional too (greedy backtracking still splits it after "Exploring"),
#: and the floor word itself is matched lazily so its letters cannot swallow the digit
#: ('ExploringFloor5' would otherwise parse as the word "Floor5" with no floor number).
HEADER_LABEL_PATTERN = r'^' + HEADER_WORD + r'(?:\s*Floor)?$'
# One map variant splits its caption across two boxes and OCR sometimes returns only the
# second one: evidence/runtime/packaged-mirror-20261025-045045/frame-0009.json holds
# ('Floor', (246,135,120,35), 0.99) with no 'Exploring' anywhere, so the label alone kept
# the page UNKNOWN for a whole 300 s run.  The bare second half is accepted inside the
# header band only; the pack line is still required by map_header, so a stray 'Floor'
# elsewhere on a page cannot promote anything.
HEADER_TAIL_PATTERN = r'^Floor$'
HEADER_FLOOR_PATTERN = r'^Floor\s*([1-5])?$'
#: OCR sometimes renders the gap in "Exploring Floor" as a dot instead of a space
#: (live evidence/runtime/packaged-mirror-20261022-045608/frame-0006.json reads
#: 'Exploring·Floor' and the page consequently stayed UNKNOWN for 32 of 36 frames,
#: producing no map click at all).  Normalising the separator once, here, keeps the
#: header patterns readable instead of growing a tolerance per glyph.
HEADER_SEPARATORS = '\u00b7\u2022\u22c5\u0387\u30fb|'


def normalise_header_text(text):
    """The header's words with dot separators folded to a single space."""
    out = text or ''
    for separator in HEADER_SEPARATORS:
        out = out.replace(separator, ' ')
    return re.sub(r'\s+', ' ', out).strip()

HEADER_ROI = (.0, .06, .30, .22)
PACK_ROI = (.0, .14, .30, .28)

#: the crescent emblem every map node hangs under its hexagon, kept in 1280-space so
#: callers can scale it to the frame (assets/resource/base/image/map/node_badge.png).
NODE_BADGE_TEMPLATE = 'image/map/node_badge.png'
REFERENCE_WIDTH = 1280
BADGE_THRESHOLD = 0.90
#: the node's centre sits this far above its badge's centre. Measured on four archived
#: floor-1 frames: the orange path line, which is drawn through the node centres, runs
#: at y 428 while the badges hang at y 506 (evidence/runtime/window-20261006-035828).
BADGE_TO_CENTRE = 78
#: fallback only: a bright interior ornament sits near the top of the hexagon (the
#: live left-hand node's glyph at y 367 for a node centred at 429).
ORNAMENT_LIFT = 70
#: the player's locomotive burns a saturated yellow flame worth ~211 px; every other
#: node ornament measures 0-17 px there (four archived map frames).
PLAYER_FLAME = 60
#: The player readings are checked against the flame itself, because they disagree on
#: frames caught mid-fade and each one is right on the frames the others fail. Live
#: evidence/runtime/window-20261007-174525/frame-0002.png: the locomotive pair reads
#: (636,510) and the badge lift reads (751,425) while the flame burns at (694,384), so a
#: radius has to cover the flame's own height above its node (~70 px) plus the reading's
#: own error.
PLAYER_FLAME_RADIUS = 110


@dataclass(frozen=True)
class MapHeader:
    floor: int | None
    pack: str | None
    exploring_text: Text
    pack_text: Text | None


@dataclass(frozen=True)
class NodePanel:
    """The node info panel that opens after a map click, if it is on screen."""
    title: str | None
    clear_rewards: Text | None
    enter: Text | None
    cost_texts: tuple


REWARDS_PATTERN = r'^Clear\s*Rewards$'
REWARDS_ROI = (.50, .64, .68, .75)
ENTER_PATTERN = r'^Enter$'
ENTER_ROI = (.82, .68, .95, .80)
PANEL_TITLE_ROI = (.58, .33, .85, .48)
PANEL_TITLE_PATTERN = r'^[A-Za-z][A-Za-z\s\'&.\-]{2,40}$'


def node_panel(records, size):
    """Return the open node info panel, or None when the page is not a panel.

    Identity is the `Enter` action in its own band plus one of two things: the
    `Clear Rewards` caption that a reward panel carries, or the floor header that the
    panel does not hide. The game renders two panel shapes -- the reward panel
    (`Clear Rewards` above the reward icons) and the encounter panel, which only names
    the encounter and has no reward caption at all
    (evidence/runtime/window-20261006-041345/frame-0002.json, 'Thick Rumbling Hum' with
    its Enter at [1670,784,122,57]). Requiring `Clear Rewards` made the second shape
    read as MAP -- the header stays legible behind the panel -- so the click that
    opened it looked like a no-op. The Mirror-Dungeon entry page carries an `Enter` in
    the same slot but never a floor header, so it is still excluded. The theme name is
    used only as recorded context, never as identity.

    The panel accepts the floor header *label* alone, without the pack line that the
    map itself insists on: on the encounter shape the pack line is whatever small map
    text happens to survive OCR, and on evidence/runtime/packaged-mirror-20261014-065112
    frame-0250 it read as nothing at all while 'Exploring Floor 2' and the panel's
    `Enter` were both on screen. The frame went UNKNOWN, the window waited the run out
    and stopped with `page_unreadable_after_waiting`; an entry page still has no header,
    so this does not widen identity to the entry screen.
    """
    enters = find(records, ENTER_PATTERN, ENTER_ROI, size, .8)
    if len(enters) != 1:
        return None
    rewards = find(records, REWARDS_PATTERN, REWARDS_ROI, size, .8)
    if len(rewards) != 1 and map_header(records, size) is None and floor_label(records, size) is None:
        return None
    titles = find(records, PANEL_TITLE_PATTERN, PANEL_TITLE_ROI, size, .8)
    titles.sort(key=lambda t: (t.box[1], t.box[0]))
    costs = tuple(t.text for t in records
                  if re.fullmatch(r'\d{1,4}', t.text.strip()) and t.score >= .8
                  and .62 <= (t.box[1] + t.box[3] / 2) / size[1] <= .92)
    return NodePanel(titles[0].text.strip() if titles else None,
                     rewards[0] if rewards else None, enters[0], costs)


def enter_target(panel):
    """The bounded click box for the panel's Enter action, or None without it."""
    if panel is None or panel.enter is None:
        return None
    return panel.enter.box


@dataclass(frozen=True)
class NodeMarker:
    """A visible map node: the glyph that proves it, and the clickable hexagon.

    With the badge template the proof is the small emblem hanging under every
    hexagon, and the node body is a box centred exactly ``BADGE_TO_CENTRE`` pixels
    above it. With the bright-ornament fallback the proof is the node's own interior
    glyph, which sits near the top of the hexagon, so the box is lifted by
    ``ORNAMENT_LIFT``. Identity is that glyph's shape/brightness only; node *type* is
    never inferred from artwork.
    """
    ornament: tuple[int, int, int, int]
    node: tuple[int, int, int, int]


def badge_nodes(image, template, *, threshold=BADGE_THRESHOLD, reference_width=REFERENCE_WIDTH,
                node_side=190):
    """Every node whose under-hexagon badge matches the template, best score first.

    The live map draws one identical crescent emblem under every reachable node, so
    matching it enumerates the whole page (3-6 nodes) where the bright-ornament scan
    found only the one node whose interior happens to be lit. Matching reports a
    cloud of hits per badge, so the best hit inside one node's radius wins.
    """
    if template is None or getattr(template, 'size', 0) == 0:
        return []
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    scale = width / reference_width
    size = (max(1, round(template.shape[1] * scale)), max(1, round(template.shape[0] * scale)))
    scaled = cv2.resize(template, size, interpolation=cv2.INTER_LINEAR)
    if scaled.shape[0] > height or scaled.shape[1] > width:
        return []
    result = cv2.matchTemplate(image, scaled, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= threshold)
    order = sorted(zip(xs.tolist(), ys.tolist()), key=lambda p: -result[p[1], p[0]])
    kept = []
    for x, y in order:
        cx = x + size[0] // 2
        cy = y + size[1] // 2 - BADGE_TO_CENTRE
        if any((cx - other[0]) ** 2 + (cy - other[1]) ** 2 <= (node_side // 2) ** 2
               for other in kept):
            continue
        kept.append((cx, cy, (x, y, size[0], size[1])))
    half = node_side // 2
    markers = []
    for cx, cy, badge in kept:
        nx = min(max(0, cx - half), max(0, width - node_side))
        ny = min(max(0, cy - half), max(0, height - node_side))
        markers.append(NodeMarker(badge, (nx, ny, node_side, node_side)))
    markers.sort(key=lambda m: (m.node[1], m.node[0]))
    return markers


def node_markers(image, *, template=None, threshold=175, band=(.18, .78), min_area=300,
                 max_area=4000, node_side=190):
    """Read the map's nodes from a frame; no input.

    The badge template is preferred because it sees every node; the bright-ornament
    scan is the fallback for callers that have no template at hand, and it can see as
    little as one node (live: the frame that stopped the run with
    ``no_candidate_node_observed`` -- evidence/runtime/window-20261006-035828).
    """
    found = badge_nodes(image, template, node_side=node_side)
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    gray = image.max(axis=2)
    mask = (gray >= threshold).astype(np.uint8)
    mask[:round(band[0] * height)] = 0
    mask[round(band[1] * height):] = 0
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    markers = []
    for index in range(1, count):
        x, y, box_w, box_h, area = stats[index]
        if not (min_area <= area <= max_area) or not (25 <= box_w <= 95) or not (18 <= box_h <= 75):
            continue
        if box_w < box_h * 0.8:
            continue
        cx, cy = int(centroids[index][0]), int(centroids[index][1]) + ORNAMENT_LIFT
        half = node_side // 2
        nx = min(max(0, cx - half), width - node_side)
        ny = min(max(0, cy - half), height - node_side)
        markers.append(NodeMarker((int(x), int(y), int(box_w), int(box_h)),
                                  (nx, ny, node_side, node_side)))
    # The two sources miss different nodes, so both are kept: on the floor-4 frame that
    # stopped run76 (evidence/runtime/window-20261006-212950/frame-0058.png) the badge
    # template matched the player's own crescent and one arc of the lit orange ring --
    # box (232,14,190,190), which is not a node at all and was the only candidate left
    # after the player's node was dropped, so the run clicked the same empty spot until
    # the map gave out -- while the ornament scan still saw the shop node at
    # (263,338,190,190). A node found by both keeps the badge's box, which is centred on
    # the hexagon rather than lifted from the interior glyph.
    merged = list(found)
    for marker in markers:
        centre = (marker.node[0] + marker.node[2] // 2, marker.node[1] + marker.node[3] // 2)
        if any((centre[0] - other.node[0] - other.node[2] // 2) ** 2
               + (centre[1] - other.node[1] - other.node[3] // 2) ** 2
               <= (node_side // 2) ** 2 for other in merged):
            continue
        merged.append(marker)
    markers = merged
    markers.sort(key=lambda m: (m.node[1], m.node[0]))
    return markers


def player_marker(image):
    """Approximate the red player icon's centre on a map page, or None."""
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    blue = image[:, :, 0].astype(int)
    green = image[:, :, 1].astype(int)
    red = image[:, :, 2].astype(int)
    red = red.copy()
    red[:round(.18 * height)] = 0
    red[round(.78 * height):] = 0
    mask = ((red > 130) & (red - green > 70) & (red - blue > 70)).astype(np.uint8)
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for index in range(1, count):
        area = stats[index][4]
        if area < 800:
            continue
        if best is None or area > best[0]:
            best = (int(area), int(centroids[index][0]), int(centroids[index][1]))
    return None if best is None else (best[1], best[2])


def likely_player(markers):
    """The marker most likely to be the player's own node.

    The player icon's bright part is the smallest ornament on the page (the flame tip
    of the train), while every other node carries a larger interior glyph. This is a
    coarse ordering, so callers record it instead of trusting it as identity.
    """
    if not markers:
        return None
    smallest = min(markers, key=lambda m: (m.ornament[2] * m.ornament[3], m.ornament[0]))
    return ((smallest.node[0] + smallest.node[2] // 2),
            (smallest.node[1] + smallest.node[3] // 2))


def flame_player(markers, image):
    """The node whose ornament is the player's bright yellow flame, or None."""
    if not markers:
        # A page with no markers is a page the player cannot be located on; the caller
        # already treats None as "unknown", and iterating None crashed the loop here
        # (evidence/runtime/packaged-mirror-20261022-063031, TypeError at this line).
        return None
    best = None
    for marker in markers:
        x, y, w, h = marker.ornament
        crop = image[y:y + h, x:x + w]
        if crop.size == 0:
            continue
        blue, green = float(crop[:, :, 0].mean()), float(crop[:, :, 1].mean())
        score = green - blue
        if green < 120:
            continue
        if best is None or score > best[0]:
            best = (score, (marker.node[0] + marker.node[2] // 2,
                            marker.node[1] + marker.node[3] // 2))
    return None if best is None else best[1]


EDGE_CYAN_HUE = (80, 112)
EDGE_CYAN_SATURATION = 140
EDGE_SAMPLE_HALF = 7


def bridge_strength(image, start, end, *, half=EDGE_SAMPLE_HALF):
    """How bright the edge between two map points is, in HSV value.

    Measured on `build/t94-now.png` (the floor-3 map live screenshot): every edge on the
    page is drawn in the same dark cyan, so counting cyan pixels cannot separate them --
    a perpendicular window along the party-to-node line scored 0.74-0.86 for all five
    nodes.  Their *brightness* does separate them: the one edge the game will accept read
    a mean value of 64.1 against 13.8-32.6 for the spent ones.  So the strength is the
    mean value of the cyan pixels the line crosses, and the floor compares a candidate
    against the others rather than against an absolute threshold.
    """
    import cv2
    import math

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    height, width = image.shape[:2]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    seen = []
    for step in range(int(length)):
        best = 0
        for offset in range(-half, half + 1):
            x = int(start[0] + ux * step + px * offset)
            y = int(start[1] + uy * step + py * offset)
            if not (0 <= x < width and 0 <= y < height):
                continue
            hue, saturation, value = hsv[y, x]
            if (EDGE_CYAN_HUE[0] <= hue <= EDGE_CYAN_HUE[1]
                    and saturation >= EDGE_CYAN_SATURATION):
                best = max(best, int(value))
        if best:
            seen.append(best)
    if not seen:
        return 0.0
    return float(sum(seen)) / len(seen)


PLAYER_RING_AREA = (120, 6000)
PLAYER_RING_BAND = (.12, .85)


def player_by_ring(image):
    """The party's own node, found by the ring the game draws around it.

    ``yellow_flame_player`` needs the crescent badges ``node_markers`` finds, and that
    template reads nothing on the paler floor palettes: live frame
    evidence/runtime/packaged-mirror-20261022-051350/frame-0010.png yields zero markers
    and therefore no player, which left the reachability ranking with no input at all.
    The party's node still carries the largest solid warm structure on the page -- the game
    rings it, unlike the small ring above an offered node -- so it is located by that, and
    ``None`` is returned when nothing meets the size gate rather than guessing a node.
    """
    import cv2

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (15, 120, 150), (40, 255, 255))
    height, width = image.shape[:2]
    mask[:int(PLAYER_RING_BAND[0] * height)] = 0
    mask[int(PLAYER_RING_BAND[1] * height):] = 0
    mask[:, :int(.03 * width)] = 0
    mask[:, int(.92 * width):] = 0
    count, _labels, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for index in range(1, count):
        area = int(stats[index, 4])
        if not PLAYER_RING_AREA[0] <= area <= PLAYER_RING_AREA[1]:
            continue
        box_w, box_h = int(stats[index, 2]), int(stats[index, 3])
        if not 8 <= box_w <= 200 or not 8 <= box_h <= 200:
            continue
        if best is None or area > best[0]:
            best = (area, int(centres[index][0]), int(centres[index][1]))
    return None if best is None else (best[1], best[2])


def yellow_flame_player(markers, image):
    """The node carrying the player's bright yellow flame, or None.

    The player is the locomotive: a saturated yellow flame burns above its node while
    every other node's ornament is painted in the pack's own colours. Counting those
    pixels separates it cleanly -- 211 against 0-17 on all four archived floor-1
    frames -- where red mass cannot (the map's red X event marker reached 4835).
    """
    if not markers:
        return None
    import numpy as np
    blue = image[:, :, 0].astype(int)
    green = image[:, :, 1].astype(int)
    red = image[:, :, 2].astype(int)
    flame = (red > 180) & (green > 150) & (blue < 120)
    best = None
    for marker in markers:
        x, y, w, h = marker.node
        cx, cy = x + w // 2, y + h // 2
        crop = flame[max(0, cy - 45):cy + 65, max(0, x):x + w]
        count = int(crop.sum())
        if count < PLAYER_FLAME:
            continue
        if best is None or count > best[0]:
            best = (count, (cx, cy))
    return None if best is None else best[1]


def flame_centroid(image, *, bottom=None, right=None, minimum=PLAYER_FLAME):
    """The player's flame found anywhere on the map, or None.

    `yellow_flame_player` can only score the nodes the badge scan already found, and
    on live floor-2 frames (evidence/runtime/window-20261006-045857, reproduced from
    build/live-now.png) that scan found a single node, so the player was never
    scored and its own glow was then mistaken for a marked node. The flame is the
    player's own feature, so it is looked for directly.
    """
    if image is None:
        return None
    import cv2
    import numpy as np
    bottom = MARKER_MAP_BOTTOM if bottom is None else bottom
    right = MARKER_MAP_RIGHT if right is None else right
    height, width = image.shape[:2]
    blue = image[:, :, 0].astype(int)
    green = image[:, :, 1].astype(int)
    red = image[:, :, 2].astype(int)
    mask = ((red > 180) & (green > 150) & (blue < 120)).astype(np.uint8)
    mask[round(bottom * height):] = 0
    mask[:, round(right * width):] = 0
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for index in range(1, count):
        area = int(stats[index][4])
        if area < minimum:
            continue
        if best is None or area > best[0]:
            best = (area, (int(round(centroids[index][0])), int(round(centroids[index][1]))))
    return None if best is None else best[1]


def flame_count(image, point, *, radius=PLAYER_FLAME_RADIUS, band=(.12, .80)):
    """How many of the player's own flame pixels sit within ``radius`` of ``point``.

    The count is taken inside the map band only: the header strip carries the sin
    counters, whose icons are saturated yellow too, and the whole-map centroid has
    already landed on one of them (live evidence/runtime/window-20261006-233633/frame-0001.png,
    where ``flame_centroid`` returns the counter at (1616,82) and that reading would
    otherwise outrank the player on the floor it was taken from).
    """
    if image is None or point is None:
        return 0
    import numpy as np
    height, width = image.shape[:2]
    x, y = int(point[0]), int(point[1])
    x0, x1 = max(0, x - radius), min(width, x + radius)
    y0, y1 = max(round(band[0] * height), y - radius), min(round(band[1] * height), y + radius)
    if x1 <= x0 or y1 <= y0:
        return 0
    crop = image[y0:y1, x0:x1].astype(int)
    blue, green, red = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
    return int(((red > 180) & (green > 150) & (blue < 120)).sum())


def player_readings(image, markers):
    """Every point a reader claims the player stands at, the flame's favourite first.

    Ordering them is only ever a guess -- see ``player_of`` for the frames where the
    readings disagree -- so this returns all of them and lets the caller check the guess
    against the page itself. The flame score is the tie-break because the flame is the
    one thing on the page that is certainly the player's, but a reader that put its point
    slightly off can still outscore the right one (the locomotive's own lamp is yellow
    too), which is why the caller may look at the rest.
    """
    readings = []
    for guess in (train_player(image), yellow_flame_player(markers, image),
                  flame_centroid(image), flame_player(markers, image),
                  likely_player(markers)):
        if guess and guess not in readings:
            readings.append(guess)
    return sorted(readings, key=lambda guess: -flame_count(image, guess))


def player_of(image, markers):
    """The player's point: the reading with the most of the flame under it, or None.

    No single reading is right on every frame, so ordering them cannot settle which one
    to believe. The badge lift needs the badge scan to have found the player's ornament,
    the locomotive pair needs the flame and its body to be picked out of the floor's own
    glow, and the whole-map centroid needs the largest yellow blob on the page to be the
    flame rather than a reward chip: live
    evidence/runtime/window-20261006-050106/frame-0003.json is a frame where only the
    locomotive finds it (one badge node on the page), while live
    evidence/runtime/window-20261007-174525/frame-0002.png -- caught mid-fade -- is a
    frame where the locomotive pair lands at (636,510) and the badge lift at (751,425)
    while the flame burns at (694,384); believing the locomotive first is what sent that
    run's first click to the hexagon between them. So each reading is scored against the
    flame itself and the reading with the most of it wins. A frame whose flame is not
    visible at all still returns its best reading rather than nothing, because a wrong
    point costs one candidate while no point costs the path reading.
    """
    readings = player_readings(image, markers)
    return readings[0] if readings else None


def train_player(image, *, bottom=None, right=None, min_area=60, max_side=32,
                 gap=(55, 115), drift=45):
    """The player's node found by its locomotive, or None.

    The locomotive is the only place on a map where a small yellow flame sits above
    another yellow blob: a live floor-2 frame (build/live-now.png, 1920) carries the
    flame as a 20x20 blob of 271 px at (702,300) with the lit body 156 px at
    (694,384) 84 px below it, while the node reward chips are 44x44 blobs of ~285 px
    whose only neighbour is the node's own icon. Pairing the small blob with the blob
    under it therefore names the player where neither the badge scan (one node found
    on that frame) nor a whole-map scan (the largest yellow blob was a reward chip)
    can.
    """
    if image is None:
        return None
    import cv2
    import numpy as np
    bottom = MARKER_MAP_BOTTOM if bottom is None else bottom
    right = MARKER_MAP_RIGHT if right is None else right
    height, width = image.shape[:2]

    # Every default above was measured on a 1920x1080 frame: the flame is 271 px there and
    # 45 px on a 1280x720 capture, where an unscaled min_area of 60 discards it (live
    # `evidence/runtime/lattice-probe/zoomed2.png`, torch blobs 45/27/23 px at
    # (703,253)/(699,281)/(703,324)).  The thresholds stay 1080p pixels and are scaled by
    # the frame's own height, so another camera size reads the same locomotive.
    scale = height / 1080.0
    min_area = max(8, int(round(min_area * scale * scale)))
    max_side = max(6, int(round(max_side * scale)))
    gap = (int(round(gap[0] * scale)), int(round(gap[1] * scale)))
    drift = max(8, int(round(drift * scale)))
    blue = image[:, :, 0].astype(int)
    green = image[:, :, 1].astype(int)
    red = image[:, :, 2].astype(int)
    mask = ((red > 180) & (green > 150) & (blue < 120)).astype(np.uint8)
    mask[round(bottom * height):] = 0
    mask[:, round(right * width):] = 0
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    blobs = []
    # A flame is the big yellow blob (271 px on the measured 1080p frame); the lit body
    # under it is smaller -- 53 px and 50 px on
    # `evidence/runtime/packaged-mirror-20261025-061838/frame-0001.png` -- so filtering
    # every blob at the flame's own floor left no body to pair with and the function
    # answered None on both retained frames.  Flames keep `min_area`; bodies only need to
    # exist (`body_area`).
    body_area = max(4, int(round(20 * scale * scale)))
    for index in range(1, count):
        x, y, box_w, box_h, area = (int(value) for value in stats[index])
        if area < min(min_area, body_area):
            continue
        blobs.append(dict(x=x, y=y, w=box_w, h=box_h, area=area,
                          cx=int(round(centroids[index][0])),
                          cy=int(round(centroids[index][1]))))
    best = None
    for flame in blobs:
        if flame['area'] < min_area:
            continue
        if flame['w'] > max_side or flame['h'] > max_side:
            continue
        for body in blobs:
            if body is flame:
                continue
            if abs(body['cx'] - flame['cx']) > drift:
                continue
            if not gap[0] <= body['cy'] - flame['cy'] <= gap[1]:
                continue
            weight = flame['area'] + body['area']
            if best is None or weight > best[0]:
                best = (weight, (body['cx'], body['cy']))
    return None if best is None else best[1]


def lattice_neighbours(player, pitch=None):
    """The lattice steps around the player; ordering is the caller's job.

    The hex rows are offset by half a column, so the steps that land on another node
    are the two horizontals and the four diagonals; a straight (0, +/-pitch) step falls
    between two rows and is kept only as the last resort it always was. Live: the player
    said the lower path was gone and the run had to go diagonally up (m10702), while
    every candidate list up to then held the orthogonal four first.
    """
    if player is None:
        return []
    pitch = LATTICE_PITCH if pitch is None else pitch
    half = pitch[0] // 2
    x, y = player
    return [(x + half, y - pitch[1]), (x - half, y - pitch[1]),
            (x + half, y + pitch[1]), (x - half, y + pitch[1]),
            (x + pitch[0], y), (x - pitch[0], y),
            (x, y + pitch[1]), (x, y - pitch[1])]


def advance_candidates(markers, player=None):
    """Ordered nodes to try: nearest to the player when known, else topmost.

    The player stands on one of the detected nodes and that node is never a
    candidate, so it is dropped by radius rather than by blindly dropping the nearest
    entry: with a single detected node (the old ornament scan's live failure mode)
    that shortcut handed the player's own node back as the only candidate.
    """
    ordered = list(markers)
    if player is not None:
        def distance(marker):
            x, y, w, h = marker.node
            return (x + w // 2 - player[0]) ** 2 + (y + h // 2 - player[1]) ** 2
        ordered.sort(key=distance)
        elsewhere = [m for m in ordered if distance(m) > 60 * 60]
        ordered = elsewhere or ordered
    else:
        ordered.sort(key=lambda m: (m.node[1], m.node[0]))
    return ordered


def advance_plan(markers, player=None, index=0):
    """Choose one node to try (never the player's own), or refuse explicitly."""
    if not markers:
        return dict(target=None, reason='no_node_marker_observed')
    ordered = advance_candidates(markers, player)
    chosen = ordered[index % len(ordered)]
    return dict(target=chosen.node, ornament=chosen.ornament, index=index,
                candidates=len(markers), player=list(player) if player else None,
                reason='nearest_node_away_from_player' if player else 'topmost_node_first')


#: The step the game will accept is drawn with a desaturated-bright glyph. Two shapes
#: were observed on the floor-1 map: the pale hexagon of a highlighted node
#: (evidence/runtime/window-20261006-040938/frame-0001.png, box 1016,40,142,127, which
#: opened the encounter panel when the ADB tap landed on it) and the wide grey double
#: chevron that sits on the path towards the reachable node (box 774,417,242,30 in
#: evidence/runtime/window-20261006-033107/frame-0005.png). Both are brighter than the
#: map's own lines and far less saturated than the orange path glow, which is what this
#: mask keeps. A hint for ordering clicks only, never an identity anchor.
MARKER_MIN_BRIGHTNESS = 105
MARKER_MAX_SATURATION = 50
MARKER_MIN_PIXELS = 400
MARKER_MAP_BOTTOM = .62
MARKER_MAP_RIGHT = .88
#: columns run 384 px apart and rows 320 px apart on a 1920 frame (LALC's 260/210 in
#: 1280-space, times 1.5). Used only to guess which node a chevron points at.
LATTICE_PITCH = (384, 320)
CLICK_SIDE = 40


#: The node the game is offering next is lit cyan on the live floor-1 page (the rest
#: of the map is dark blue); the wash along the path shares the colour but is sparse,
#: so a fill test separates the lit ring from it.
HIGHLIGHT_MIN_GREEN = 140
HIGHLIGHT_MIN_BLUE = 120
HIGHLIGHT_MAX_RED = 140
HIGHLIGHT_MIN_WARMTH = 50
HIGHLIGHT_MIN_PIXELS = 400
HIGHLIGHT_MIN_SIDE = 40
HIGHLIGHT_MAX_SIDE = 260
HIGHLIGHT_MIN_FILL = 0.08
#: The lit node is a *ring*, while the header strip above the map carries solid cyan
#: status icons: live window-20261006-052530/frame-0020 read one at (1164,180) with
#: fill 0.49 against the ring's 0.28. The band drops the header outright -- every lit
#: node seen live sat at y 0.39-0.68 -- and the fill cap is the backstop.
HIGHLIGHT_BAND = (.20, .95)
HIGHLIGHT_MAX_FILL = 0.60


def highlighted_nodes(image, *, min_green=HIGHLIGHT_MIN_GREEN, min_blue=HIGHLIGHT_MIN_BLUE,
                      max_red=HIGHLIGHT_MAX_RED, warmth=HIGHLIGHT_MIN_WARMTH,
                      min_pixels=HIGHLIGHT_MIN_PIXELS, min_side=HIGHLIGHT_MIN_SIDE,
                      max_side=HIGHLIGHT_MAX_SIDE, min_fill=HIGHLIGHT_MIN_FILL,
                      max_fill=HIGHLIGHT_MAX_FILL, band=HIGHLIGHT_BAND):
    """Centres of the cyan-lit nodes on a map page, densest first; no input.

    Live: evidence/runtime/window-20261006-201831/frame-0065.png -- the run stopped
    with ``no_candidate_node_observed`` because the node the game offered (1087,737,
    sitting between crescent-badge nodes that all refused the click) was never a
    candidate. The lit ring's own pixels name it directly, which is sturdier than any
    offset from the badge drawn under a node.
    """
    if image is None:
        return []
    import cv2
    import numpy as np
    height = image.shape[0]
    blue = image[:, :, 0].astype(np.int16)
    green = image[:, :, 1].astype(np.int16)
    red = image[:, :, 2].astype(np.int16)
    mask = ((green >= min_green) & (blue >= min_blue) & (red <= max_red)
            & ((green + blue) // 2 - red >= warmth)).astype(np.uint8)
    mask[:round(band[0] * height)] = 0
    mask[round(band[1] * height):] = 0
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    found = []
    for index in range(1, count):
        x, y, box_w, box_h, area = stats[index]
        if area < min_pixels:
            continue
        if not (min_side <= box_w <= max_side) or not (min_side <= box_h <= max_side):
            continue
        fill = area / float(max(1, box_w * box_h))
        if not (min_fill <= fill <= max_fill):
            continue
        found.append(((int(x + box_w // 2), int(y + box_h // 2)), int(area)))
    found.sort(key=lambda item: -item[1])
    return [point for point, _ in found]


#: The node the game offers next is drawn inside a saturated ring, and the ring's hue
#: follows the floor: cyan on floor 1 (evidence/runtime/window-20261006-200505/
#: frame-0081.png) and orange on floor 3 (evidence/runtime/window-20261006-214057/
#: frame-0025.png). Hue cannot carry the reading, so the ring is found by saturation
#: and brightness instead: the map behind it is a dark washed blue, while the ring is a
#: compact, strongly coloured loop wrapped around the node.
LIT_MIN_VALUE = 110
LIT_MIN_CHROMA = 70
LIT_MIN_PIXELS = 400
LIT_MIN_SIDE = 30
LIT_MAX_SIDE = 300
#: The sparse wash that runs along the paths is saturated too, but it is hollow: on
#: live window-20261006-214057/frame-0025 it measures fill 0.073-0.083, while the ring
#: itself fills 0.383 and a node's own icon 0.46-0.78.
LIT_MIN_FILL = 0.15
LIT_MAX_FILL = 0.85
LIT_MIN_RATIO = 0.45
#: A ring whose top is cut by the band reads wide: the live orange ring measured
#: 186x79, a ratio of 2.35.
LIT_MAX_RATIO = 3.2
#: The header strip and the team bar carry solid saturated icons of their own, so the
#: band keeps only the map proper: the sin counters sit above y 0.08 and the identity
#: cards start below y 0.78 on a 1920x1080 frame.
LIT_BAND = (.08, .78)
#: A ring opens around the node the game is offering; an ordinary node's own icon is
#: solid and compact. Live window-20261006-214057/frame-0025: the ring fills 0.383 over
#: 186x79 while the icons on the same page fill 0.46-0.78 over 47x47 or less.
LIT_RING_MAX_FILL = 0.42
LIT_RING_MIN_SIDE = 60
#: On a floor whose background is drawn in the same gold as the offer, the ring's pixels
#: merge with the web behind them at the general threshold and ``lit_rings`` reads nothing
#: at all: live evidence/runtime/window-20261007-175552/frame-0052.png (floor 3,
#: "Emotional Indolence") yields eight ordinary nodes' icons and no ring at 110, while 150
#: yields exactly the offered node's ring (centre 1147,443 -- box 1113,384,69,119, fill
#: .345). The run spent eight clicks on those icons before the offered node's own box
#: (1064,472,190,190) finally took one.
LIT_RING_MIN_VALUE = 150
#: The lit path leaving the player, read from live window-20261006-233633/frame-0001: the
#: line is dashed, so 21 px of closing merges its glow into one component, and the walk
#: stops well short of the 320 px that would let a merged graph reach another node.
PATH_MERGE = 41
PATH_REACH = 130
#: A floor-2 walk leaves the player for a hexagon one lattice step away: on live
#: evidence/runtime/window-20261007-172225/frame-0406.png the bright line runs from the
#: player at (694,384) to the node at (1054,124), about 470 px, while the old 320 px cap
#: stopped the walk in the middle of the line and left the run with nothing to click. A
#: click on a node the run cannot reach is a no-op and the caller tries its next
#: candidate, so a merged graph handing back the far end of a neighbouring line costs one
#: attempt rather than the run.
PATH_WALK_LIMIT = 560
#: Floors 1 and 3 draw the walkable path a bright violet; floor 2's "Automated Factory"
#: draws the same line bright cyan over a dim teal grid. The violet mask alone read
#: nothing there (live frame-0406, where ``path_end`` was None), the run clicked the
#: player's own node and one of its reward chips instead, and stopped with
#: ``no_candidate_node_observed``. The cyan reading is kept bright because the floor's
#: own grid is cyan too: at brightness 180 the line separates, at 120 the whole floor
#: merges into one blob.
PATH_CYAN_MIN_VALUE = 180
PATH_CYAN_MIN_GREEN = 140
PATH_CYAN_MIN_BLUE = 140
PATH_CYAN_MAX_RED = 150
PATH_CYAN_MIN_WARMTH = 40
#: The path names the node; the node's own ring names the pixel. On live
#: evidence/runtime/window-20261006-201831/frame-0065.png the line ends 66 px off the
#: centre of the ringed node, outside its hexagon, while the ring itself is the click that
#: opened the panel -- so a marked node this close to the path's far end takes its place.
PATH_SNAP = 70


def lit_components(image, *, min_value=LIT_MIN_VALUE, min_chroma=LIT_MIN_CHROMA,
                   min_pixels=LIT_MIN_PIXELS, min_side=LIT_MIN_SIDE, max_side=LIT_MAX_SIDE,
                   min_fill=LIT_MIN_FILL, max_fill=LIT_MAX_FILL, min_ratio=LIT_MIN_RATIO,
                   max_ratio=LIT_MAX_RATIO, band=LIT_BAND):
    """Saturated blobs on a map page as records, densest first; no input.

    ``highlighted_nodes`` reads the floor-1 cyan ring only, which is why the run walked
    floors 1 and 2 and then stopped dead on floor 3: there the same ring is drawn
    orange, no candidate named it, and every crescent badge and lattice guess around the
    player was a no-op (build/window-run78.json). The ring's own pixels name the node at
    any hue, which is sturdier than any offset from the badge drawn under it.
    """
    if image is None:
        return []
    import cv2
    import numpy as np
    height = image.shape[0]
    pixels = image.astype(np.int16)
    high = pixels.max(axis=2)
    low = pixels.min(axis=2)
    mask = ((high >= min_value) & (high - low >= min_chroma)).astype(np.uint8)
    mask[:round(band[0] * height)] = 0
    mask[round(band[1] * height):] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    found = []
    for index in range(1, count):
        x, y, box_w, box_h, area = stats[index]
        if area < min_pixels:
            continue
        if not (min_side <= box_w <= max_side) or not (min_side <= box_h <= max_side):
            continue
        ratio = box_w / float(max(1, box_h))
        if not (min_ratio <= ratio <= max_ratio):
            continue
        fill = area / float(max(1, box_w * box_h))
        if not (min_fill <= fill <= max_fill):
            continue
        found.append(dict(point=(int(x + box_w // 2), int(y + box_h // 2)),
                          box=(int(x), int(y), int(box_w), int(box_h)),
                          area=int(area), fill=round(fill, 3)))
    found.sort(key=lambda record: -record['area'])
    return found


def lit_nodes(image, **kwargs):
    """Centres of every saturated blob on a map page, densest first; no input."""
    return [record['point'] for record in lit_components(image, **kwargs)]


def lit_rings(image, **kwargs):
    """Centres of the ringed (offered) nodes only, densest first; no input.

    A ring is hollow and wide where the icon of an ordinary node is solid and compact:
    live window-20261006-214057/frame-0025 draws the offered ring at fill 0.383 over
    186x79, while the node icons on the same page fill 0.46-0.78 over boxes of 47x47 or
    less. Without the split, every icon on the page outranks the one node the game is
    actually offering (the 040938 and 050106 frames of tests/test_map_vision.py).
    """
    return [record['point'] for record in lit_components(image, **kwargs)
            if record['fill'] <= LIT_RING_MAX_FILL
            and max(record['box'][2], record['box'][3]) >= LIT_RING_MIN_SIDE]


def path_end(image, player, *, max_distance=PATH_WALK_LIMIT, reach=PATH_REACH,
             merge=PATH_MERGE):
    """The node at the far end of the lit path leaving the player, or None.

    The game draws the path a run may still walk as a bright violet line and the paths it
    has already spent as a dull grey one, so the walkable neighbour is the far end of the
    bright line that touches the player's node. This is the reading that finally moved the
    run on floor 3: live evidence/runtime/window-20261006-233633/frame-0001.png has the
    player at (960,672) with the bright line running down-right to (1036,711) and up to
    (1162,590), and an ADB tap on that far end (1920 1162,607) opened the node panel the
    lit ring and every badge candidate had refused -- the player had said the lower path
    was gone and the run had to go diagonally up (m10702).

    The line is drawn as a dashed glow, so the segments are merged before walking; the
    walk is capped at ``max_distance`` from the player so that a merged graph cannot hand
    back a node somewhere else on the floor. The cap has to clear one lattice step, and
    the mask has to read the hue the floor draws the line in -- floor 2's cyan line over a
    cyan grid is why the hue families below are a pair, not one.
    """
    if image is None or player is None:
        return None
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    blue = image[:, :, 0].astype(int)
    green = image[:, :, 1].astype(int)
    red = image[:, :, 2].astype(int)
    violet = (red > 110) & (blue > 110) & (green < 95) & (np.abs(red - blue) < 70)
    brightest = np.maximum(np.maximum(red, green), blue)
    cyan = ((green >= PATH_CYAN_MIN_GREEN) & (blue >= PATH_CYAN_MIN_BLUE)
            & (red <= PATH_CYAN_MAX_RED) & (green - red >= PATH_CYAN_MIN_WARMTH)
            & (brightest >= PATH_CYAN_MIN_VALUE))
    mask = (violet | cyan).astype(np.uint8)
    mask[round(.86 * height):] = 0
    mask[:round(.08 * height)] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((merge, merge), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    px, py = player
    limit = max_distance * max_distance
    far = None
    for index in range(1, count):
        if stats[index][4] < 20:
            continue
        ys, xs = np.nonzero(labels == index)
        d = (xs - px) ** 2 + (ys - py) ** 2
        if int(d.min()) > reach * reach:
            continue  # this line does not touch the player's node
        inside = d <= limit
        if not inside.any():
            continue
        pick = int(np.argmax(np.where(inside, d, -1)))
        if far is None or d[pick] > far[0]:
            far = (int(d[pick]), int(xs[pick]), int(ys[pick]))
    if far is None or far[0] < 40 * 40:
        return None
    return (far[1], far[2])

def marker_boxes(image, *, minimum=MARKER_MIN_BRIGHTNESS, saturation=MARKER_MAX_SATURATION,
                 min_pixels=MARKER_MIN_PIXELS, bottom=MARKER_MAP_BOTTOM, right=MARKER_MAP_RIGHT):
    """Bright desaturated glyph boxes on a map page, largest first; no input."""
    if image is None:
        return []
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    pixels = image.astype(np.int16)
    high = pixels.max(axis=2)
    low = pixels.min(axis=2)
    mask = ((high > minimum) & ((high - low) < saturation)).astype(np.uint8)
    mask[round(bottom * height):] = 0
    mask[:, round(right * width):] = 0
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    boxes = []
    for index in range(1, count):
        x, y, box_w, box_h, area = stats[index]
        if area < min_pixels or not (40 <= box_w <= 320) or not (24 <= box_h <= 220):
            continue
        boxes.append((int(x), int(y), int(box_w), int(box_h), int(area)))
    boxes.sort(key=lambda box: -box[4])
    return boxes


CHEVRON_SATURATION_MAX = 70
CHEVRON_VALUE_BAND = (100, 170)
CHEVRON_SIDE = ((14, 40), (6, 24))          # glyph width, height in 1080p pixels
CHEVRON_GAP = (16, 48)                       # centre-to-centre of the two glyphs


def chevron_glyph_pairs(image):
    """Centres of the paired low-saturation glyphs the game draws as a path chevron.

    Measured on `packaged-mirror-20261025-135349/frame-0005` (party (500,244)): the double
    chevron is two glyphs of about 22x12 at (844,215) and (885,223), HSV about [14,46,124].
    Brightness gates never see it (V is ~124, not the 175+ a badge carries), a flat-bar rule
    never sees it either (each glyph is 22x12, ratio 1.8), and both were assumed before this
    measurement.  What distinguishes it is being a *pair* of small low-saturation glyphs at
    the same height, side by side, near the party.
    """
    import cv2
    import numpy as np
    if image is None or getattr(image, 'ndim', 0) != 3:
        return []
    height, width = image.shape[:2]
    scale = width / 1920.0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    low, high = CHEVRON_VALUE_BAND
    mask = cv2.inRange(hsv, (0, 0, int(low)), (180, CHEVRON_SATURATION_MAX, int(high)))
    mask[:int(0.10 * height)] = 0
    mask[int(0.84 * height):] = 0
    mask[:, int(0.95 * width):] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, _labels, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
    glyphs = []
    (width_lo, width_hi), (height_lo, height_hi) = (
        (int(width_lo * scale), int(width_hi * scale)) for width_lo, width_hi in CHEVRON_SIDE)
    for index in range(1, count):
        area = int(stats[index][4])
        side_w, side_h = int(stats[index][2]), int(stats[index][3])
        if not (80 * scale * scale <= area <= 900 * scale * scale):
            continue
        if not (width_lo <= side_w <= width_hi and height_lo <= side_h <= height_hi):
            continue
        glyphs.append((int(centres[index][0]), int(centres[index][1]), side_w, side_h))
    pairs = []
    gap_lo, gap_hi = (int(v * scale) for v in CHEVRON_GAP)
    for first in range(len(glyphs)):
        for second in range(first + 1, len(glyphs)):
            ax, ay, aw, _ah = glyphs[first]
            bx, by, bw, _bh = glyphs[second]
            dx = abs(bx - ax)
            if abs(ay - by) > int(8 * scale):
                continue
            if not (gap_lo <= dx <= gap_hi):
                continue
            if not (0.5 <= aw / float(max(1, bw)) <= 2.0):
                continue
            pairs.append(((ax + bx) // 2, (ay + by) // 2))
    return pairs


def chevron_target(player, marker, pitch=LATTICE_PITCH):
    """The lattice node a desaturated glyph on the path points at, or None."""
    if player is None:
        return None
    dx, dy = marker[0] - player[0], marker[1] - player[1]
    if dx == 0 and dy == 0:
        return None
    if abs(dx) >= abs(dy):
        return (player[0] + (pitch[0] if dx > 0 else -pitch[0]), player[1])
    return (player[0], player[1] + (pitch[1] if dy > 0 else -pitch[1]))


def neutral_node_outlines(image):
    """Compact bright neutral outlines; proposed controls, never node identities.

    A free-gift cube can be white instead of gold. Its own local border survives
    the coloured map background; the successor panel still decides whether it
    was an available node. Header/roster regions are outside this search band.
    """
    import cv2,numpy as np
    h,w=image.shape[:2];scale=w/1920
    pixels=image.astype(np.int16)
    mask=((pixels.min(axis=2)>=75)&(pixels.max(axis=2)-pixels.min(axis=2)<=30)).astype(np.uint8)*255
    mask[:round(h*.18)]=0;mask[round(h*.80):]=0
    mask[:,:round(w*.025)]=0;mask[:,round(w*.90):]=0
    kernel=np.ones((max(1,round(9*scale)),)*2,np.uint8)
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel)
    n,labels,stats,centres=cv2.connectedComponentsWithStats(mask,8)
    points=[]
    for i in range(1,n):
        x,y,bw,bh,area=map(int,stats[i])
        if (45*scale<=bw<=170*scale and 40*scale<=bh<=165*scale
                and .5<=bw/bh<=2.2 and area>=160*scale*scale):
            points.append((x+bw//2,y+bh//2))
    return points


# The gold ring is the offer mark the game draws over a node it will let the run step
# to, and it is painted the same gold on every floor -- so it is read off the colour
# rather than off one stored badge bitmap, which is only ever one floor's art. Live
# evidence/runtime/pi-20261021-185251/frame-0119.png (floor 1) is why: five rings 24 px
# across sat on the offered nodes at (863,404), (1055,403), (1247,403), (1247,564) and
# (1055,723) while `node_badge_template` matched nothing on that floor, so the only
# candidates the page handed the runner were the player's own icon, a path chevron and
# two lattice guesses in the empty black panel beside the map. Every click was a no-op
# and the run stopped with `no_candidate_node_observed` after 48 inputs.
# The badge's own gold is BGR (21,140,223) -- OpenCV hue 13-16, saturation 231.
GOLD_MARK_HUE = (10, 40)
GOLD_MARK_MIN_SATURATION = 120
GOLD_MARK_MIN_VALUE = 140
GOLD_MARK_SIDE = (14, 46)
# A badge is drawn above the node it marks, not on it: on the same frame the ring at
# (863,404) sits over the node whose hexagon is centred at (863,448).
GOLD_MARK_DROP = 44
# One ring is not always one connected component: an icon inside the badge and a
# bright pixel row can split it.  Nearest marks closer than this are the same ring.
GOLD_MARK_MERGE = 25


def _node_below(image, x, y, drop):
    """The node the ring advertises is a dark hexagon; open board is not.

    A warm floor paints the whole map in gold wash, so brightness alone put rings on
    arrows and background.  What every real ring has is a dark node a fixed distance
    under it -- and that is true even on the orange floors.
    """
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    half = 20
    centre_y = int(y) + int(drop)
    y0, y1 = max(0, centre_y - half), min(height, centre_y + half)
    x0, x1 = max(0, int(x) - half), min(width, int(x) + half)
    if y1 - y0 < half or x1 - x0 < half:
        return False
    patch = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)[:, :, 2]
    return float(np.mean(patch)) <= 70.0


def gold_marks(image):
    """Centres of the gold rings the game draws over the nodes it offers; no input.

    Read off hue, saturation and brightness so a floor whose badge art the stored
    template does not match is still readable. The reward bar, the star count and the
    party strip are gold as well and are kept out by the canvas band here, and the
    right-hand command buttons by the width bound.
    """
    if image is None:
        return []
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    mask = ((hue >= GOLD_MARK_HUE[0]) & (hue <= GOLD_MARK_HUE[1])
            & (saturation >= GOLD_MARK_MIN_SATURATION)
            & (value >= GOLD_MARK_MIN_VALUE)).astype(np.uint8)
    mask[:int(.10 * height), :] = 0
    # The party strip starts at about .78 of the height and its frames are gold too.
    mask[int(.80 * height):, :] = 0
    mask[:, :int(.10 * width)] = 0
    mask[:, int(.84 * width):] = 0
    count, _, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
    shortest, longest = GOLD_MARK_SIDE
    marks = []
    for index in range(1, count):
        x, y, box_w, box_h, area = stats[index]
        if not shortest <= box_w <= longest or not shortest <= box_h <= longest:
            continue
        if area < shortest * shortest // 2:
            continue
        marks.append((int(round(centres[index][0])), int(round(centres[index][1]))))
    if marks:
        drop = gold_badge_drop(image)
        marks = [point for point in marks if _node_below(image, point[0], point[1], drop)]
    marks.sort(key=lambda point: (point[1], point[0]))
    merged = []
    for point in marks:
        close = [other for other in merged
                 if abs(other[0] - point[0]) <= GOLD_MARK_MERGE
                 and abs(other[1] - point[1]) <= GOLD_MARK_MERGE]
        if not close:
            merged.append(point)
    return lattice_consistent(merged, width)


# The map is drawn on a fixed lattice: two nodes side by side are 192 px apart on
# 1920-wide frames, two rows 160 px, and a diagonal neighbour 192x160.  Measured on
# `evidence/runtime/pi-20261021-185251/frame-0119.png` -- (863,404), (1055,403),
# (1247,403), (1247,564), (1055,723) -- and on the older floor in `pi-20261012-180805`.
LATTICE_STEPS = ((192, 0), (0, 160), (192, 160))
LATTICE_TOLERANCE = 0.09
# Below the tightest spacing two separate nodes can have, so two marks closer than this
# are one object the reader saw twice -- the player's own token is gold and answers twice.
TIGHT_MARK = 150


def lattice_consistent(marks, width=1920, tolerance=LATTICE_TOLERANCE):
    """Keep the gold rings that stand at this map's node spacing.

    Three things are decided here, in this order:

    * a mark within :data:`TIGHT_MARK` of another is one object read twice (the party
      marker is gold too), and *all* of that cluster's marks go;
    * a survivor counts when it stands at 1-3 whole lattice steps from another survivor
      in either axis: a row can skip nodes the floor is not offering, so the gap is a
      small multiple of the spacing, not exactly the spacing;
    * when no pair fits and geometry says nothing, everything that survived is handed on.
      Deleting every candidate is the failure this reader exists to prevent.
    """
    points = [(int(x), int(y)) for x, y in marks]
    if len(points) < 2:
        return points
    scale = float(width) / 1920.0
    tight = int(round(TIGHT_MARK * scale))

    def gaps_to(point, other):
        return abs(point[0] - other[0]), abs(point[1] - other[1])

    clustered = set()
    for index, point in enumerate(points):
        for other_index, other in enumerate(points):
            if other_index <= index:
                continue
            gap_x, gap_y = gaps_to(point, other)
            if max(gap_x, gap_y) < tight:
                clustered.add(index)
                clustered.add(other_index)
    survivors = [point for index, point in enumerate(points) if index not in clustered]
    if len(survivors) < 2:
        return survivors
    steps = [(int(round(dx * scale)), int(round(dy * scale))) for dx, dy in LATTICE_STEPS]
    kept = []
    for index, point in enumerate(survivors):
        for other_index, other in enumerate(survivors):
            if other_index == index:
                continue
            gap_x, gap_y = gaps_to(point, other)
            fits = False
            for want_x, want_y in steps:
                for kx in range(1, 4) if want_x else (0,):
                    for ky in range(1, 4) if want_y else (0,):
                        if not kx and not ky:
                            continue
                        if abs(gap_x - kx * want_x) <= max(8, int(round(kx * want_x * tolerance))) \
                                and abs(gap_y - ky * want_y) <= max(8, int(round(ky * want_y * tolerance))):
                            fits = True
                            break
                    if fits:
                        break
                if fits:
                    break
            if fits:
                kept.append(point)
                break
    return kept or survivors


def gold_badge_drop(image):
    """How far below a badge its node sits, at this frame's scale."""
    height, width = image.shape[:2]
    return int(round(GOLD_MARK_DROP * width / 1920.0))


GLOW_CONTRAST = 20.0
GLOW_SPAN = 60
GLOW_STEP = 10
GLOW_RADIUS = 15
GLOW_OFFSETS = (-30, -15, 0, 15, 30)


def _saturation(image, point, radius=GLOW_RADIUS):
    x, y = int(point[0]), int(point[1])
    patch = image[max(0, y - radius):y + radius, max(0, x - radius):x + radius]
    if not patch.size:
        return 0.0
    return float(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[:, :, 1].mean())


def saturation_contrast(image, point, *, span=GLOW_SPAN):
    """How much brighter the point is saturated than its neighbourhood.

    Measured on 203 retained verdicts (46 accepted, 157 rejected): accepted clicks sit
    on a flat node body (mean contrast 5.6), rejected ones sit on the glow between a
    gold badge and the node (mean contrast 89.0).  A threshold anywhere in 20..40 keeps
    every accepted click and drops 107 of the 157 rejected ones, so the separation is a
    plateau, not a knife edge.
    """
    here = _saturation(image, point)
    lowest = None
    for dx in (-span, -span // 2, 0, span // 2, span):
        for dy in (-span, -span // 2, 0, span // 2, span):
            value = _saturation(image, (point[0] + dx, point[1] + dy))
            if lowest is None or value < lowest:
                lowest = value
    if lowest is None:
        return 0.0
    return here - lowest


def is_glow(image, point, *, threshold=GLOW_CONTRAST):
    """A candidate whose point sits on a saturated glow is not a clickable node body."""
    return saturation_contrast(image, point) > threshold


BOSS_RED_LOW = ((0, 180, 140), (8, 255, 255))
BOSS_RED_HIGH = ((172, 180, 140), (180, 255, 255))
# Sized in *pixels of the frame itself*, not as constants: the map can be zoomed, and a
# palmed/zoomed board moves and resizes every box (operator, m16901: "这个会变化的，要考虑
# 缩放过地图").  The room is ~17% of the frame's width and ~0.9% of its area on the two
# retained 1920x1080 frames, so both floors are fractions of the frame.
BOSS_MIN_SIDE_FRACTION = 0.05
BOSS_MIN_AREA_FRACTION = 0.0018


def boss_nodes(image):
    """Red rooms on a MAP page: the floor's last node, drawn as a big red badge.

    Measured 2026-10-25 on `evidence/runtime/packaged-mirror-20261025-040555/frame-0004.png`:
    the boss sat at box (1026,306,324,248), centre (1188,430), while the party stood at
    (482,347) -- **710.9 px** away.  `adjacent_to` keeps only one pitch (245-406 px on
    that frame), so the last node of a floor was dropped from every candidate list, and
    a scan of 60 runs found **no** run that ever offered a box over a red blob.

    The operator's reading (m16784, paraphrased): the shop's colour changes with the
    pack but the boss room is red on every floor, and the reward tiles under it are the
    parts that change.  So the colour is the identity here, and the two small tiles are
    excluded by the minimum side length.

    Returns ``[(box, centre)]`` with ``box = (x, y, w, h)``.
    """
    import cv2
    if image is None:
        return []
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = (cv2.inRange(hsv, BOSS_RED_LOW[0], BOSS_RED_LOW[1])
            | cv2.inRange(hsv, BOSS_RED_HIGH[0], BOSS_RED_HIGH[1]))
    count, _, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
    frame_h, frame_w = image.shape[:2]
    min_side = BOSS_MIN_SIDE_FRACTION * frame_w
    min_area = BOSS_MIN_AREA_FRACTION * frame_w * frame_h
    found = []
    for index in range(1, count):
        x, y, w, h, area = [int(v) for v in stats[index]]
        if area < min_area or w < min_side or h < min_side:
            continue
        found.append(((x, y, w, h), (int(centres[index][0]), int(centres[index][1]))))
    return found


def _cover(a, b):
    """How much of the smaller of two boxes the other one covers."""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    smaller = min(a[2] * a[3], b[2] * b[3])
    return (w * h) / smaller if smaller else 0.0


def _with_bosses(image, clicks):
    """Append the red room to a candidate list, deduplicated against it.

    The floor's last node sits far outside one pitch, so the caller's adjacency band
    drops it; it is appended after the walk's own steps and never replaces one (D244).
    """
    taken = [list(item['box']) for item in clicks]
    for box, centre in boss_nodes(image):
        box = tuple(int(v) for v in box)
        # A reward tile or a badge drawn inside the room is a *part* of it, not a
        # duplicate destination: only a similarly sized box may stand in for it.
        if any(_cover(box, k) >= .5 and (k[2] * k[3]) >= .5 * (box[2] * box[3])
               for k in taken):
            continue
        clicks.append(dict(box=box, kind='boss_node', point=centre))
    return clicks


def relaxed_nodes(image, *, band=(.18, .78), node_side=190, min_side=12, area_floor=60,
                  max_area=4000):
    """Nodes on a page whose ornaments sit below every tuned cut (D257).

    Measured 2026-10-25 on one zoomed-out page: 7 ornaments at grey>=60, 1 at >=90 and
    none at the tuned >=175, so a page the tuned read cannot see at all is re-read with a
    cut taken from its own picture.  These are last-resort points: the caller offers them
    after every proven kind, so a loose read cannot displace a gold badge, a cyan step, a
    path node or the boss room.
    """
    import cv2
    if image is None:
        return []
    height, width = image.shape[:2]
    gray = image.max(axis=2)
    band_gray = gray[round(band[0] * height):round(band[1] * height)]
    if not band_gray.size:
        return []
    lit, _ = cv2.threshold(band_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cut = max(60, int(lit * .55))
    mask = (gray >= cut).astype('uint8')
    mask[:round(band[0] * height)] = 0
    mask[round(band[1] * height):] = 0
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    out = []
    for index in range(1, count):
        x, y, box_w, box_h, area = stats[index]
        if (not (area_floor <= area <= max_area) or not (min_side <= box_w <= 95)
                or not (min_side - 7 <= box_h <= 75)):
            continue
        if box_w < box_h * 0.8:
            continue
        cx, cy = int(centroids[index][0]), int(centroids[index][1]) + ORNAMENT_LIFT
        half = node_side // 2
        nx = min(max(0, cx - half), width - node_side)
        ny = min(max(0, cy - half), height - node_side)
        out.append(NodeMarker((int(x), int(y), int(box_w), int(box_h)), (nx, ny, node_side, node_side)))
    return out


def map_clicks(image, *, template=None, node_side=None, player=None):
    # The badge node's side is a fraction of the screen, not a 1080p constant: the
    # emulator has served both 1920x1080 and 1280x720 frames in one day, and on the
    # smaller one a 190 px box swallowed tiles and missed every node (D275).
    if node_side is None:
        node_side = max(40, round(BADGE_NODE_SIDE * image.shape[0] / 1080.0))
    """Ordered click boxes for a MAP page: the marked step first, then the nodes.

    Live run window-20261006-040751 is why the highlight is consulted first: four
    crescent-badge nodes around the player were all refused clicks while the
    highlighted, badge-less gate in the row above opened the encounter panel. Node
    connectivity is still not readable from a frame, so this only orders candidates --
    the caller tries them in turn and stops at the first one that opens the panel, and
    a click on an unreachable node is a harmless no-op.
    """
    if image is None:
        return []
    height, width = image.shape[:2]
    markers = node_markers(image, template=template, node_side=node_side)
    # A caller that already knows where the player stands (a live run that read the
    # locomotive on an earlier frame) hands the point in: on a zoomed-out page every
    # detector here fails -- live evidence/runtime/window-20261006-233633/frame-0001.png
    # where train_player is None and flame_centroid returns a header icon -- and the path
    # reading, which is the one proven to open the panel, would be lost with it.
    if player is None:
        readings = player_readings(image, markers)
        player = readings[0] if readings else None
    else:
        readings = []
    # The lit path is drawn from the player, so it is also the one reading on the page
    # that can settle which point really is the player: live
    # evidence/runtime/window-20261007-174525/frame-0002.png is a frame where the
    # flame-scored reading is the badge lift at (751,425) and the path off it lands on
    # the node the click really opened, while the locomotive pair reads (636,510) -- 137
    # px away, outside PATH_REACH -- and leaves the path with nothing to start from. So
    # when the best reading walks nowhere, the other readings are tried before the page
    # is given back without a path candidate at all.
    walk = path_end(image, player) if player else None
    if walk is None:
        for other in readings[1:]:
            walk = path_end(image, other)
            if walk:
                player = other
                break
    clicks = []

    # The right column of circular buttons (info, guide, party, help) is page furniture, not
    # map: live packaged-mirror-20261021-200907/frame-0053 had two guesses land on it at
    # (1791,324) and (1801,254) while the floor's three offered nodes sat at (1247,264),
    # (1439,264) and (1055,424).  A guess may not propose that column at all.
    def _furniture(point):
        return point[0] >= .88*width and point[1] < .45*height

    def add(point, kind, side):
        # Candidate probes belong to the map canvas, never the header or party.
        if not .10*height<=point[1]<.84*height or point[0]>=.94*width:return
        if (kind in ('neutral_outline_candidate','lit_icon','bright_lit_icon','lattice_step')
                and point[0]<.30*width and point[1]<.215*height):return
        if (kind in ('node_away_from_player','badge_mark','lattice_step',
                     'bright_lit_icon','neutral_outline_candidate') and _furniture(point)):
            return
        x = min(max(0, point[0] - side // 2), max(0, width - side))
        y = min(max(0, point[1] - side // 2), max(0, height - side))
        for item in clicks:
            box_x, box_y, box_w, box_h = item['box']
            if ((x + side // 2 - box_x - box_w // 2) ** 2
                    + (y + side // 2 - box_y - box_h // 2) ** 2 <= 50 * 50):
                return
        clicks.append(dict(box=(x, y, side, side), kind=kind, point=(point[0], point[1])))

    highlighted = []
    chevrons = []
    for box in marker_boxes(image):
        x, y, box_w, box_h, area = box
        centre = (x + box_w // 2, y + box_h // 2)
        fill = area / float(max(1, box_w * box_h))
        ratio = box_w / float(max(1, box_h))
        # The player's own glow sits where the party stands, and a compact bright ring
        # there is that glow, not a node.  A flat bar is not: the path chevron the game
        # draws starts right beside the party's tile, so excluding everything within
        # 70 px of the party also excluded the one mark that says which step the page
        # will accept -- live `packaged-mirror-20261025-135349` emitted no `chevron_target`
        # at all while the arrow stood one tile to the party's right.
        near_player = bool(player) and (
            (centre[0] - player[0]) ** 2 + (centre[1] - player[1]) ** 2) <= 70 * 70
        # A highlighted hexagon is a compact ring (live fill 0.12-0.21); the path glow
        # that shares this mask is a large sparse wash (fill 0.03) and the chevron is a
        # flat bar (ratio above 3), so neither can pass for the marked node.
        if box_w >= 90 and ratio <= 3.0 and fill >= 0.08:
            if near_player:
                continue
            highlighted.append(centre)
        elif ratio > 3.0:
            target = chevron_target(player, centre)
            if target:
                chevrons.append(target)
    if not chevrons:
        # The paired-glyph reader is the one that sees the chevron on the 720p reading; the
        # flat-bar rule above was calibrated on 1080p captures and never fires here.
        for centre in chevron_glyph_pairs(image):
            target = chevron_target(player, centre)
            if target:
                chevrons.append(target)
    if player:
        nearby = lambda point: (point[0] - player[0]) ** 2 + (point[1] - player[1]) ** 2
        highlighted.sort(key=nearby)
        chevrons.sort(key=nearby)
    else:
        # With no player on the page a compact bright ring cannot be told from the
        # player's own glow (live floor-2 probe: the locomotive's halo was the
        # "highlighted node" and the first click went to it), so nothing is claimed
        # as marked and the chevron/lattice candidates carry the step instead.
        highlighted = []
    # The ring is the game's own "this is the step" mark, so it outranks every reading
    # taken off a badge or the lattice, whichever hue the floor draws it in. The player's
    # own flame is saturated too and is dropped by radius; the node icons are kept for
    # later, because on this page they are the ordinary nodes rather than the offer.
    lit = [point for point in lit_nodes(image)
           if not player or (point[0] - player[0]) ** 2 + (point[1] - player[1]) ** 2 > 90 * 90]
    rings = [point for point in lit_rings(image)
             if not player or (point[0] - player[0]) ** 2 + (point[1] - player[1]) ** 2 > 90 * 90]
    icons = [point for point in lit if point not in rings]
    cyan = list(highlighted_nodes(image))
    # The lit path leaving the player is the direction the run may still walk, so its far
    # end is the strongest reading on the page: live evidence/runtime/
    # window-20261006-233633/frame-0001.png, where an ADB tap on it opened the node panel
    # after the ring and every badge candidate had been refused.
    if walk:
        # The path names which node the run may step to; the node's own ring names the
        # pixel the game accepts. Live evidence/runtime/window-20261006-201831/frame-0065.png
        # (floor 1): the line's far end lands at (1029,705), 66 px off the centre of the
        # ringed node at (1087,737) and outside its hexagon, while that ring is the click
        # the panel really opened on.
        marked = cyan + rings
        near = [point for point in marked
                if (point[0] - walk[0]) ** 2 + (point[1] - walk[1]) ** 2 <= PATH_SNAP * PATH_SNAP]
        if near:
            walk = min(near, key=lambda point: (point[0] - walk[0]) ** 2
                       + (point[1] - walk[1]) ** 2)
        add(walk, 'path_node', CLICK_SIDE)
    # The lit node is the step the game is offering, so it outranks everything else:
    # live evidence/runtime/window-20261006-200505/frame-0081.png -- the click that
    # opened the panel landed on the cyan node while the crescent-badge nodes around it
    # refused it, and the run had stopped with no_candidate_node_observed.
    for point in cyan:
        add(point, 'cyan_node', CLICK_SIDE)
    # The highlighted node is the step the game will accept, so it goes first; the
    # chevron only points along the path towards it, and the badge nodes are the
    # ordinary case where nothing on the page is marked at all.
    for point in highlighted:
        add(point, 'highlighted_node', CLICK_SIDE)
    for point in chevrons:
        add(point, 'chevron_target', node_side)
    # A floor that paints its background the same gold as the offer needs the brighter
    # threshold to see the ring at all: live evidence/runtime/window-20261007-175552/
    # frame-0052.png (floor 3) yields exactly one ring at 150 -- the node the game was
    # offering, box (1064,472,190,190) -- while the standard reading sees only the eight
    # ordinary nodes' icons that swallowed the next eight clicks.
    #
    # The radius filter only means something against a player the page has corroborated.
    # With no path walked, the reading it filters against is itself unproven: on that same
    # frame the flame-scored reading (1126,433) *is* the offered node's ring -- the ring is
    # painted in the flame's own orange -- so filtering by it discarded the one candidate
    # the game was actually offering.
    corroborated = player if walk else None
    bright_rings = [point for point in lit_rings(image, min_value=LIT_RING_MIN_VALUE)
                    if not corroborated or (point[0] - corroborated[0]) ** 2
                    + (point[1] - corroborated[1]) ** 2 > 90 * 90]
    for point in bright_rings:
        add(point, 'lit_ring', CLICK_SIDE)
    # The ring is the only reading that survives a floor which draws the offer in
    # another hue -- floor 3 draws it orange, where ``highlighted_nodes`` and the
    # chevrons read nothing at all (build/window-run78.json), so these come next.
    for point in rings:
        add(point, 'lit_node', CLICK_SIDE)
    # A node's own icon is saturated too, so the reader offers those blobs as well; they
    # are read off the frame, so they outrank the badge lift and the lattice. Live
    # evidence/runtime/window-20261007-023156/frame-0053.png ("The Forgotten", floor 1):
    # the only step the floor offered is the red "?" hexagon, whose icon the reader names
    # at (1087,409), while the four lifted badge boxes ((578,14)/(194,334)/(232,14)/
    # (1346,14)) are ordinary nodes and every click on them was swallowed -- the run
    # stopped after map_tries with the panel never opened. A manual 1920-space tap on
    # (1080,428) opened that node's panel, so the icon is the step. Live
    # 040938/frame-0001: the offered gate there is a paler hexagon, and the leftmost
    # node's icon was the only other thing the reader could name.
    bright_icons=lit_components(image, min_value=LIT_RING_MIN_VALUE)
    # A wide, dense icon is stronger evidence than small reward/buff badges.
    # Keep path/ring precedence while ensuring it fits the bounded candidates.
    for item in bright_icons:
        # Actual GUI frame0095 question glyph is54x54/.455; reward badges
        # are46px. This orders candidates only, never proves a node successor.
        if max(item['box'][2:])>=50 and item['fill']>=.4:
            point=item['point']
            if not corroborated or (point[0]-corroborated[0])**2+(point[1]-corroborated[1])**2>90*90:
                add(point,'bright_lit_icon',CLICK_SIDE)
    # The gold ring is the game's own offer mark, and it is the one reading that names a
    # node on a floor whose badge art the stored template does not match: live
    # pi-20261021-185251/frame-0119 above. It comes after the readings a live run has
    # proven opens the panel (the walked path, the lit ring, the lit icon) and before the
    # neutral outline, the badge lift and the lattice, which on that frame were a path
    # chevron, nothing and two guesses in the empty black panel.
    # It used to be consulted only when the badge scan found no node at all, and that gate
    # is what let a live run spend its click retries on the settings column: live
    # packaged-mirror-20261021-200907/frame-0053 prints three rings -- (1247,220),
    # (1439,220), (1055,380) -- while the badge scan still produced a path node and two
    # right-edge guesses at (1791,324) and (1801,254), so the one reading that names a
    # walkable node was skipped, the run tapped the UI column, and it stopped on
    # `unexpected_successor` after the recovery ladder ran out.  The gate is gone: rings
    # are always offered, still after the readings a live run has proven (walked path, lit
    # ring, lit icon) and still before the neutral outline, the badge lift and the lattice,
    # so a ring can take the place of a guess but never of a proven reading -- and the
    # earlier worry (window-20261006-212950/frame-0058, where the lit ring read as a badge
    # would have deduped the shop node away) cannot recur from this position.
    # The gold ring is the game's own offer mark: the one reading that names a node on a
    # floor whose badge art the stored template does not match, and the reading that keeps
    # a run off the settings column -- live packaged-mirror-20261021-200907/frame-0053 had
    # three rings at (1247,264), (1439,264), (1055,424) while the badge scan only guessed a
    # path node and two right-edge points, so nine click retries went to the UI and the run
    # stopped on `unexpected_successor`.  A ring is skipped when the badge/ornament readings
    # already name the node under it (window-20261006-212950/frame-0058: the lit ring node is
    # (318,140) and the lift lands (304,201), 62 px away -- two candidates, one node), which
    # is why those points are computed before the rings are added even though the readings
    # themselves are added after them.
    named = [(marker.node[0] + marker.node[2] // 2, marker.node[1] + marker.node[3] // 2)
             for marker in advance_candidates(markers, player)]
    named += [(marker.ornament[0] + marker.ornament[2] // 2,
               marker.ornament[1] + marker.ornament[3] // 2)
              for marker in advance_candidates(markers, player)]
    named += list(highlighted) + list(icons)
    lift = gold_badge_drop(image)
    for point in gold_marks(image):
        lifted = (point[0], point[1] + lift)
        if any((lifted[0]-x)**2 + (lifted[1]-y)**2 <= 90*90 for x, y in named):
            continue
        add(lifted, 'gold_badge_node', node_side)
    for point in neutral_node_outlines(image):
        add(point,'neutral_outline_candidate',CLICK_SIDE)
    for point in icons:
        add(point, 'lit_icon', CLICK_SIDE)
    # Vain Pride frame20261009-053703/0102 retains the offered icon at
    # (1087,409) only at the brighter threshold. Preserve existing path/ring/
    # icon precedence, then offer these before inferred badge/lattice points.
    for item in bright_icons:
        point=item['point']
        if point in bright_rings:
            continue
        if corroborated and (point[0]-corroborated[0])**2+(point[1]-corroborated[1])**2 <= 90*90:
            continue
        add(point, 'bright_lit_icon', CLICK_SIDE)
    # The badge nodes are read off the frame, so they outrank a guessed lattice step:
    # live run build/window-run35 clicked four lattice points around the player while
    # the one real node (center 1095,429) sat 48 px from the third guess and was
    # deduplicated away, which ended the run with no_candidate_node_observed. They sit
    # behind the icons because the lift is a guess from the badge and the icon is not.
    for marker in advance_candidates(markers, player):
        add((marker.node[0] + marker.node[2] // 2,
             marker.node[1] + marker.node[3] // 2), 'node_away_from_player', node_side)
    # The badge is drawn *under* an ordinary node, but the lit ring's own crescent sits
    # inside its ring, so a badge read is two candidate points, not one: the box lifted
    # to the hexagon, and the badge's own centre. Live floor-4 frame
    # evidence/runtime/window-20261006-212950/frame-0058.png: the crescent at
    # (310,173,34,28) hangs inside the orange ring whose node centre is (327,187) -- the
    # registered lift put that candidate at (232,14,190,190), off the top of the map,
    # while the badge's own centre is the node the game is offering.
    for marker in advance_candidates(markers, player):
        x, y, box_w, box_h = marker.ornament
        add((x + box_w // 2, y + box_h // 2), 'badge_mark', node_side)
    # A step away from the player on the lattice is connected to the player by a path
    # in the live game, and a click on an unconnected node only does nothing, so the
    # four lattice steps are the last resort, kept for floors whose badges are not
    # drawn (live: window-20261006-051323 read only one badge on the whole floor).
    # A lattice point is not a node: `frame-0057` of
    # evidence/runtime/packaged-mirror-20261022-080630 had the four lattice steps land in
    # empty space up to 173 px below the nodes they were meant to name, and the live run's
    # nine clicks were all rejected because the page never changed -- the badge centre is
    # the node the game offers (see the `badge_mark` comment above), the lattice guess is
    # not.  Snap each lattice point onto the nearest badge it is trying to name, and drop
    # it when there is no badge within reach rather than click bare background.
    anchors = [(marker.ornament[0] + marker.ornament[2] // 2,
                marker.ornament[1] + marker.ornament[3] // 2) for marker in markers]
    for point in lattice_neighbours(player):
        if not (0 <= point[0] < width and 0 <= point[1] < height):
            continue
        near = None
        best = 141
        for anchor in anchors:
            reach = max(abs(anchor[0] - point[0]), abs(anchor[1] - point[1]))
            if reach < best:
                best, near = reach, anchor
        add(near if near else point, 'lattice_step', node_side)
    # The game marks the steps it will accept with a gold ring; anything else on this
    # page is a guess (a lit ring, a bright icon, an outline read as a node).  Live run
    # evidence/runtime/packaged-mirror-20261022-050759 asked for the two 40x40 `lit_ring`
    # guesses first -- the player's own token and a chevron -- and every one of the six
    # clicks was rejected as `the_page_stayed_on_the_map_after_the_click`, while the three
    # real `gold_badge_node` boxes were in the same list, unclicked.  So the mark the game
    # itself draws now leads, and the inferred readings keep their relative order after it.
    # The gold mark says "this node can be entered", not "it can be reached from here".
    # Live run evidence/runtime/packaged-mirror-20261022-051350 offered four gold-marked
    # nodes from the top of the floor while the party stood two rows below them, and all
    # three clicks were rejected -- honestly, because the game only accepts the nodes the
    # lit edges connect to the party.  So the reachable ones lead; the rest stay in the
    # list rather than being dropped, so a floor whose party was not located still has
    # something to try and the verdict stays a measurement.
    here = (player if player is not None
            else yellow_flame_player(markers, image) or player_by_ring(image))
    reach_x, reach_y = 1.5 * LATTICE_PITCH[0], 1.5 * LATTICE_PITCH[1]

    def distant(click):
        if here is None:
            return 0
        px, py = click['point']
        near = ((px - here[0]) / reach_x) ** 2 + ((py - here[1]) / reach_y) ** 2 <= 1.0
        return 0 if near else 1

    def strength(click):
        if here is None:
            return 0.0
        return bridge_strength(image, here, click['point'])

    marks = sorted((c for c in clicks if c['kind'] == 'gold_badge_node'),
                   key=lambda c: (-distant(c), -strength(c)))
    # The ranking is one explicit table (D300).  Two retained frames constrain it and they do
    # not contradict each other once the levels are written down: `-050759` requires the gold
    # mark ahead of every ring/icon guess while the walked path leads; `-175552` requires the
    # ring first on a floor that has no gold mark at all, so the two rules only overlap where
    # neither applies.  The chevron sits between them: the game draws it (so it beats a guess)
    # but it names a direction, not a node that will open.
    KIND_WEIGHT = {'path_node': 0, 'cyan_node': 0, 'highlighted_node': 0,
                   'gold_badge_node': 1,
                   'chevron_target': 2,
                   'lit_ring': 3,
                   'bright_lit_icon': 4, 'lit_icon': 4,
                   'lit_node': 5,
                   'neutral_outline_candidate': 6, 'relaxed_node': 6,
                   'badge_mark': 7, 'lattice_step': 8}

    def by_kind(click):
        weighted = KIND_WEIGHT.get(click['kind'], 5)
        if click['kind'] == 'gold_badge_node':
            return (weighted, -distant(click), -strength(click))
        return (weighted, 0, 0)

    clicks = [c for c in clicks if c['kind'] == 'path_node'] + marks + [
        c for c in clicks if c['kind'] not in ('path_node', 'gold_badge_node')]
    clicks = sorted(clicks, key=by_kind)
    # A page nothing above could read is offered its dim ornaments here (D257): a loose
    # read only fills gaps, and it is offered before the boss room (which is a destination
    # the player may not yet be next to) but after every proven kind.
    if len(clicks) < 3:
        for marker in relaxed_nodes(image, node_side=node_side):
            add((marker.node[0] + marker.node[2] // 2,
                 marker.node[1] + marker.node[3] // 2), 'relaxed_node', CLICK_SIDE)
    return _with_bosses(image, clicks)


# The page's own captions drift between runs: the live frames read the button as
# "Battle!" while it is disabled and as "To" + "Battle!" (with a Chain badge over
# it) once a team is picked, and the clear action as " Clear Selection" with a
# leading space. Anchoring the captions loosely keeps this page recognisable in
# both states; both captions are still required together, so a looser pattern
# cannot promote an unrelated page.
#
# The clear action is also read as two words on the same line rather than one
# token: live evidence/runtime/window-20261008-030555/frame-0015.json reads
# 'Clear' [1640,706,74,22] and 'Selection' [1706,706,122,22] where every earlier
# frame read 'Clear Selection' whole. That single split left the page named
# TEAM_LIBRARY, whose only plan is the saved-team library's, so the window stopped
# on a page it drives perfectly well (frame-0014/frame-0015, run-continue-26). The
# whole caption and the pair are therefore both accepted, and the pair must sit on
# one line, left to right, with no more than a word-sized gap -- the same shape the
# game draws.
BATTLE_PATTERN = r'^\s*(?:Chain\s+)?(?:To\s+)?Battle!?\s*$'
BATTLE_ROI = (.83, .77, .97, .87)
CLEAR_SELECTION_PATTERN = r'^\s*Clear\s+Selection\s*$'
CLEAR_WORD_PATTERN = r'^\s*Clear\s*$'
SELECTION_WORD_PATTERN = r'^\s*Selection\s*$'
CLEAR_SELECTION_ROI = (.83, .62, .98, .70)
PARTICIPANTS_PATTERN = r'^\s*\d{1,2}\s*/\s*\d{1,2}\s*$'


@dataclass(frozen=True)
class TeamPage:
    """The pre-battle team / identity page reached from a node panel.

    Identity is two stable captions in their own bands: the `Clear Selection`
    action and the `Battle!` action. Participant counts are recorded context only.
    """
    battle: Text
    clear_selection: Text
    participants: tuple


def clear_selection_caption(records, size):
    """The page's clear action, as one token or as the two the game sometimes draws.

    Returns the token, or a synthesised :class:`Text` spanning the pair, or ``None``
    when neither reading is present. The pair has to be on one line and in reading
    order; any horizontal gap is allowed, because the recognised boxes of two words
    of one caption are never exactly adjacent.
    """
    whole = find(records, CLEAR_SELECTION_PATTERN, CLEAR_SELECTION_ROI, size, .8)
    if len(whole) == 1:
        return whole[0]
    words = find(records, CLEAR_WORD_PATTERN, CLEAR_SELECTION_ROI, size, .8)
    labels = find(records, SELECTION_WORD_PATTERN, CLEAR_SELECTION_ROI, size, .8)
    pairs = []
    for word in words:
        for label in labels:
            if label.box[0] < word.box[0]:
                continue
            middle = lambda box: (box[1] + box[3] / 2) / size[1]
            if abs(middle(word.box) - middle(label.box)) > .03:
                continue
            pairs.append((word, label))
    if len(pairs) != 1:
        return None
    word, label = pairs[0]
    left, top = word.box[0], min(word.box[1], label.box[1])
    right = max(word.box[0] + word.box[2], label.box[0] + label.box[2])
    bottom = max(word.box[1] + word.box[3], label.box[1] + label.box[3])
    return Text('Clear Selection', (left, top, right - left, bottom - top),
                min(word.score, label.score))


def pre_battle_team_page(records, size):
    """Return the pre-battle team page, or None when this is not that page."""
    battle = find(records, BATTLE_PATTERN, BATTLE_ROI, size, .8)
    clear = clear_selection_caption(records, size)
    if len(battle) != 1 or clear is None:
        return None
    participants = tuple(t.text.strip() for t in
                         find(records, PARTICIPANTS_PATTERN, (.80, .66, .98, .76), size, .8))
    return TeamPage(battle[0], clear, participants)


def battle_target(page):
    """The bounded click box for `Battle!`, or None when the page is not current."""
    if page is None or page.battle is None:
        return None
    return page.battle.box


class _folded_header:
    """One OCR row with its dot separators folded, so the header patterns stay simple."""

    __slots__ = ('text', 'box', 'score')

    def __init__(self, record):
        self.text = normalise_header_text(getattr(record, 'text', ''))
        self.box = record.box
        self.score = record.score


def floor_label(records, size):
    """The floor header's own words, whether or not its pack line could be read.

    The label is the part of the header the node panel cannot hide; a map page is still
    only a map once the pack line below it is read too (see :func:`map_header`).
    """
    folded = [_folded_header(r) for r in records]
    matches = find(folded, HEADER_PATTERN, HEADER_ROI, size, .85)
    if len(matches) == 1:
        return matches[0]
    labels = find(folded, HEADER_LABEL_PATTERN, HEADER_ROI, size, .85)
    if labels:
        return labels[0]
    tails = find(folded, HEADER_TAIL_PATTERN, HEADER_ROI, size, .85)
    return tails[0] if len(tails) == 1 else None


def map_header(records, size, pack_name=None):
    """Return the map header only when floor text and the pack line both parse.

    The pack line is required so an unrelated page carrying similar wording cannot
    be promoted into MAP; it is never used as an artwork or season anchor. The
    header is accepted either as one token or as the two the game really renders
    (see :data:`HEADER_LABEL_PATTERN`); the floor number stays ``None`` when the
    stylised digit is not read, and the label alone is enough when OCR also drops
    the separate "Floor" token.
    """
    floor = None
    text = floor_label(records, size)
    if text is None:
        return None
    whole = re.match(HEADER_PATTERN, normalise_header_text(text.text), re.I)
    if whole:
        digit = whole.group(1)
        floor = int(digit) if digit else None
    else:
        same_line = [r for r in find(records, HEADER_FLOOR_PATTERN, HEADER_ROI, size, .85)
                     if r.box[0] > text.box[0]
                     and abs((r.box[1] + r.box[3] / 2) / size[1]
                             - (text.box[1] + text.box[3] / 2) / size[1]) <= .03]
        same_line.sort(key=lambda r: r.box[0])
        # The stylised "Floor" token is dropped by OCR on roughly half of the live map
        # frames (evidence/runtime/window-20261006-033259/frame-0002.json), so the label
        # alone is accepted; the pack line below still gates it.
        if same_line:
            digit = re.match(HEADER_FLOOR_PATTERN, same_line[0].text.strip(), re.I).group(1)
            floor = int(digit) if digit else None
    # A caller that resolved a faint pack line hands its identity in (`pack_name`): the
    # row carries the faint pass's low score ('SunkClom' 0.551 on
    # evidence/runtime/packaged-mirror-20261025-044012/frame-0005), so the noise gate that
    # keeps fragments out would also keep the real line out.  With a resolved identity the
    # threshold admits it and `MapHeader.pack` carries the canonical name.
    floor_score = .5 if pack_name else .8
    pack_candidates = [r for r in records
                       if r.score >= floor_score and r.box[1] > text.box[1]
                       and PACK_ROI[0] <= (r.box[0] + r.box[2] / 2) / size[0] <= PACK_ROI[2]
                       and PACK_ROI[1] <= (r.box[1] + r.box[3] / 2) / size[1] <= PACK_ROI[3]
                       and not re.match(HEADER_PATTERN, r.text.strip(), re.I)
                       and not re.match(HEADER_LABEL_PATTERN, r.text.strip(), re.I)
                       and not re.match(HEADER_FLOOR_PATTERN, r.text.strip(), re.I)]
    # A pack line is a phrase drawn across the header, so a two-character fragment of a
    # few dozen pixels is not one: the node panel's noise was accepted as "Su" (26x18,
    # score .99) and the panel was promoted to MAP (evidence/runtime/
    # packaged-mirror-20261025-012549/frame-0001.json). Real pack lines measure
    # 114-118 px wide at 1920 (median 118, "Sunk Gloom" 114), so the candidate must be
    # at least 5% of the frame wide or a phrase of six characters or more.
    pack_candidates = [r for r in pack_candidates
                       if r.box[2] >= .05 * size[0] or len(r.text.strip()) >= 6]
    pack_candidates.sort(key=lambda r: (r.box[1], r.box[0]))
    pack = pack_candidates[0] if pack_candidates else None
    if pack is None:
        return None
    name = (pack_name or pack.text).strip()
    return MapHeader(floor, name, text, pack)


def map_page(records, size):
    """True only for an identified map page; the agent maps that to scene MAP."""
    return map_header(records, size) is not None


@dataclass(frozen=True)
class MapAsset:
    """Normalized light-pixel evidence actually visible on the retained page.

    Ratios are of the source height so 1280x720 and 1920x1080 agree. This is a
    structural read for offline work, not a node identity or a route decision.
    """
    components: int
    node_ratio: float
    link_ratio: float


def light_ratio(image, roi, threshold=190):
    """Fraction of pixels above `threshold` inside a normalized ROI."""
    h, w = image.shape[:2]
    x0, y0, x1, y1 = roi
    crop = image[round(y0 * h):round(y1 * h), round(x0 * w):round(x1 * w)]
    if crop.size == 0 or crop.ndim != 3:
        return 0.0
    gray = crop.max(axis=2)
    return float((gray >= threshold).mean())


def read_map_asset(image, roi=(.01, .22, .995, .80), threshold=190):
    """Count light structure without claiming any node identity."""
    import cv2
    import numpy as np
    h, w = image.shape[:2]
    x0, y0, x1, y1 = roi
    crop = image[round(y0 * h):round(y1 * h), round(x0 * w):round(x1 * w)]
    if crop.size == 0 or crop.ndim != 3:
        return MapAsset(components=0, node_ratio=0.0, link_ratio=0.0)
    mask = (crop.max(axis=2) >= threshold).astype(np.uint8)
    count, _ = cv2.connectedComponents(mask)
    return MapAsset(components=int(max(0, count - 1)), node_ratio=float(mask.mean()),
                    link_ratio=0.0)


def route_decision(header, size, *, current=None, cleared=(), candidates=(),
                   policy=None, kinds=None, context=None):
    """Decide a next node or refuse; never invents a target.

    `current` is the proven current-position node; `cleared` and `candidates` are
    node identifiers observed on this page. Stage one has no proven node reader,
    so callers must pass the evidence they actually hold; an absent current
    position or candidate list yields an explicit refusal reason.

    When several candidates are unvisited the answer is normally
    `ambiguous_unvisited_candidates`.  Passing `policy` (a table from
    `route_plan.load_policy`) with `kinds` (node id -> kind observed on this
    page) lets `route_plan.plan_route` order them instead; candidates whose kind
    nobody read are skipped, and when none can be scored the refusal is
    `route_kind_unknown` — still a refusal, never a guess.
    """
    if header is None:
        return dict(next_node=None, reason='map_header_not_identified')
    if not current:
        return dict(next_node=None, reason='current_position_not_proven')
    if not candidates:
        return dict(next_node=None, reason='no_unvisited_candidate_observed')
    unvisited = [node for node in candidates if node not in set(cleared)]
    if not unvisited:
        return dict(next_node=None, reason='no_unvisited_reachable_node')
    if len(unvisited) != 1:
        if policy is None:
            return dict(next_node=None, reason='ambiguous_unvisited_candidates')
        known_kinds = kinds or {}
        plan = plan_route(
            [dict(id=node, kind=known_kinds.get(node)) for node in unvisited],
            policy=policy,
            context=context,
        )
        if plan['refused'] is not None:
            return dict(next_node=None, reason=plan['refused'], plan=plan)
        return dict(next_node=plan['target'], reason='policy_ranked_candidate', plan=plan)
    return dict(next_node=unvisited[0], reason='single_unvisited_candidate')


def party_from_flame(image, boxes, *, top=0.10, right=0.80, bottom=0.86):
    """我方标记：一枚竖直细长的高亮火苗，站在某个已检出节点上方。

    颜色不参与：整条判定只在灰度图上做（局部对比 + 峰值 + 高宽比），所以主题包的
    背景红/绿/蓝都不影响（m18524 的批评：按颜色枚举是笨办法）。

    几何与尺寸都用**画面比例**表达，不写死像素：
      * 只看棋盘内（去掉顶部 HUD 带 `top`、右侧面板 `right`、底部卡槽 `bottom`）；
      * 局部对比 `灰度 - 大核模糊` 后二值化，找小连通块；
      * 火苗比徽章更细长：高宽比 >= 1.2，面积介于画面的 0.000007..0.00011；
      * 正下方 0.2..1.5 个节点高度内必须有一枚已检出框（我方站在节点上）。

    实测依据 `evidence/runtime/packaged-mirror-20261025-075711/frame-0002.png`：
    真值火苗中心 (663,452)，本函数给出 (670,468)，峰值 216；同帧徽章峰值 175-207
    且高宽比 < 1.2，被排除。
    """
    import cv2
    if image is None or not boxes:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    contrast = cv2.subtract(gray, cv2.GaussianBlur(gray, (0, 0), 9))
    _limit, mask = cv2.threshold(contrast, 55, 255, cv2.THRESH_BINARY)
    mask[:int(height * top), :] = 0
    mask[int(height * bottom):, :] = 0
    mask[:, int(width * right):] = 0
    area_low = 15
    area_high = max(area_low, int(0.00011 * width * height))
    found = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for index in range(1, found[0]):
        x, y, box_w, box_h, area = found[2][index]
        if not (area_low <= area <= area_high):
            continue
        if box_h < 6 or box_w < 3 or box_h > int(0.06 * height) or box_w > int(0.03 * width):
            continue
        if box_h / max(1, box_w) < 1.2:
            continue
        centre_x, centre_y = int(found[3][index][0]), int(found[3][index][1])
        peak = int(gray[y:y + box_h, x:x + box_w].max())
        below = 0
        for box in boxes:
            try:
                bx, by, bwid, bhei = [float(v) for v in box[:4]]
            except (TypeError, ValueError):
                continue
            side = max(bwid, bhei)
            if -0.2 * side <= (by + bhei / 2.0) - centre_y <= 1.5 * side and                     abs((bx + bwid / 2.0) - centre_x) <= 0.9 * side:
                below += 1
        if not below:
            continue
        score = (peak, int(area))
        if best is None or score > best[0]:
            best = (score, centre_x, centre_y)
    if best is None:
        return None
    # 返回普通元组：调用方普遍用 `if party:` 判断，numpy 数组的真值会抛
    # `ValueError: The truth value of an array ... is ambiguous`（本轮实机 6 事件即崩于此）。
    return (int(best[1]), int(best[2]))


FLAME_THRESHOLD = 170


def flame_point(image):
    """Where the player's flame is, judged by shape rather than brightness.

    Measured 2026-10-25 on two live frames: the flame is a filled blob of about 7x6 px
    peaking at grey 216, and a node's gold ring peaks at 207 -- nine levels apart, so
    brightness cannot separate them.  Shape can: the flame is solid (fill ratio well above
    half), the ring is hollow, and the ring is larger.  The board gate then keeps the
    answer inside the map, and a reading that is outside it is not the flame.
    """
    import cv2
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if getattr(image, 'ndim', 2) == 3 else image
    height, width = gray.shape[:2]
    _, mask = cv2.threshold(gray, FLAME_THRESHOLD, 255, cv2.THRESH_BINARY)
    count, _labels, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for index in range(1, count):
        x, y, side_w, side_h, area = (int(v) for v in stats[index][:5])
        if not (5 <= side_w <= 20 and 5 <= side_h <= 20):
            continue
        if area < 20 or area / float(side_w * side_h) < 0.55:
            continue
        if y < 0.10 * height or y > 0.90 * height:
            continue
        if x < 0.02 * width or x + side_w > 0.95 * width:
            # the right-hand chrome carries warm icons of its own
            continue
        point = (float(centres[index][0]), float(centres[index][1]))
        distance = abs(point[0] - width / 2.0) + abs(point[1] - height / 2.0)
        if best is None or distance < best[0]:
            best = (distance, point)
    if best is None:
        return None
    point = (int(round(best[1][0])), int(round(best[1][1])))
    return point if _on_the_board(point, image) else None


GLOW_BAND = (0.10, 0.84)


def glow_point(image):
    """The party's own selection glow, as a shape rather than a colour rule.

    Every theme rings the tile the party stands on with a warm glow far larger than the
    flame's 7x6 blob -- measured 961 px, 508x242 centre, on `packaged-mirror-20261025-134415`
    -- and no node badge carries it.  Size and place decide: a blot between 60 and 200 px a
    side, inside the board band, above the HUD.  Colour only says where to look, the accepted
    answer is the largest such blot, so a theme change moves the hue and not the rule.
    """
    import cv2
    import numpy as np
    if image is None or getattr(image, 'ndim', 0) != 3:
        return None
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (5, 120, 140), (32, 255, 255))
    mask[:int(GLOW_BAND[0] * height)] = 0
    mask[int(GLOW_BAND[1] * height):] = 0
    mask[:, int(0.95 * width):] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for index in range(1, count):
        area = int(stats[index][4])
        side_w, side_h = int(stats[index][2]), int(stats[index][3])
        if area < 400 or area > 20000 or not (40 <= side_w <= 400 and 40 <= side_h <= 400):
            continue
        if best is None or area > best[0]:
            best = (area, int(centroids[index][0]), int(centroids[index][1]))
    if best is None:
        return None
    return (best[1], best[2])


def _party_point_legacy(image):
    """The locomotive's position, read from its own torch, not from a badge.

    `player_marker` returns None on the live frames (`evidence/runtime/
    packaged-mirror-20261022-075450/frame-0034`: the party sits at (830,450) while
    only the six badge nodes are found), so the loop could not tell a reachable
    node from any node.  Measured on that frame, the torch is two small very bright
    warm blobs stacked vertically -- (832,418) area 56 and (826,461) area 23 -- and
    nothing else in the board carries that signature.  Two blobs rather than one
    because the flame sprite is drawn above and below the sprite's hood.
    """
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    # The board runs to the right-hand chrome, not to 0.79 of the width: a party that
    # has walked east stands at ~0.80-0.85 and was outside the old band, which made
    # every frame of `evidence/runtime/packaged-mirror-20261022-090550` read None and
    # silently disabled the adjacency filter (six rejected clicks, party unmoved).
    board = image[int(.10 * height):int(.86 * height), :int(.95 * width)]
    hsv = cv2.cvtColor(board, cv2.COLOR_BGR2HSV)
    # Measured on the live frame `build/r247.png`: the torch's bright pixels have HSV
    # median (13,251,223) with a few at value 223, so the old (15,120,235) floor excluded
    # both the hue (13 < 15) and the value (223 < 235) and the party read as None on a
    # board where it plainly stood at (1625,600).  The band below brackets the measured
    # colour; the area floor admits the sprite's lower flame (area 16).
    mask = cv2.inRange(hsv, (8, 150, 200), (45, 255, 255))
    count, _, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
    # The area band is a pixel count, so it has to follow the frame's scale: the packaged
    # agent's screenshots are not always 1920 wide, and at 1280 the lower flame's 16 px
    # becomes 7 and vanished under a fixed floor -- which read as "no party" and emptied
    # the candidate list (`packaged-mirror-20261022-092529`: three steps, no clicks).
    scale = (width / 1920.0) ** 2
    floor = max(4, int(round(15 * scale)))
    ceiling = max(60, int(round(900 * scale)))
    value = hsv[:, :, 2]
    blobs = [(int(stats[i, 4]), float(centres[i][0]), float(centres[i][1]),
              float(value[stats[i, 1]:stats[i, 1] + stats[i, 3],
                          stats[i, 0]:stats[i, 0] + stats[i, 2]].mean()))
             for i in range(1, count) if floor <= stats[i, 4] <= ceiling]
    if len(blobs) < 1:
        return None
    blobs.sort(reverse=True)
    # The torch is filled as well as bright; a badge ring is bright but hollow and an
    # enemy marker is filled but small.  Measured on one frame of
    # `evidence/runtime/packaged-mirror-20261023-055547` (180x180 crops, same mask):
    # badge (399 px, V 128), party (539 px, V 209), enemy (270 px, V 216) -- so neither
    # size nor brightness separates them alone, and both together do.  When exactly one
    # blob is filled *and* bright it is the flame, and it is tried first.
    solid = max(4, int(round(300 * scale)))
    anchor = [b for b in blobs if b[0] >= solid and b[3] >= 170]
    if anchor:
        # Several blobs can be filled and bright at once (a badge's ring at this size
        # reads 400+ px at V 200+ on `055547/frame-0005`, where the party also does), so
        # the largest filled-and-bright blob wins instead of requiring a unique one:
        # the torch is 539 px there against the badge's 399.
        anchor.sort(reverse=True)
        chosen = anchor[0]
        blobs = [chosen] + [b for b in blobs if b is not chosen]
    # A second, nearby blob makes it the flame: two bright specks a few pixels apart.
    # Every blob is tried as the upper speck, not just the largest: once the colour band
    # admits the map's own warm furniture (the chest icons on the right edge), the
    # largest blob is often not the torch and the pair was never even considered
    # (`build/r247.png`: the flame is (1630,537) area 60 above (1626,579) area 16).
    for index, top in enumerate(blobs):
        for other, mate in enumerate(blobs):
            if other == index:
                continue
            # Brightness gates the pair, not just the anchor: this loop only ever
            # checked geometry, so on `055547/frame-0005` -- where the torch's two
            # specks do not line up -- it fell through to a dim badge (V 128) and
            # answered the badge's position as the party's.  A pair with a dark half
            # is not a flame; better a `None` than a wrong anchor.
            if top[3] < 170 or mate[3] < 170:
                continue
            if abs(mate[1] - top[1]) <= 12 and abs(mate[2] - top[2]) <= 80:
                x = (top[1] + mate[1]) / 2.0
                y = (top[2] + mate[2]) / 2.0 + int(.10 * height)
                point = (int(x), int(y))
                # The colour channel cannot tell the torch from a node's gold ring
                # (both are warm and bright: measured 216 vs 207 grey).  When the two
                # readings disagree, the shape wins -- live
                # `packaged-mirror-20261025-101647` read (498,221), which is a node.
                flame = flame_point(image)
                if flame is not None and abs(point[0] - flame[0]) + abs(point[1] - flame[1]) > 60:
                    return flame
                return point
    return None

STEP_CENTRES = tuple(
    (sx * ax, sy * ay)
    for ax, ay in ((384, 0), (192, 110), (0, 220))
    for sx in (1, -1)
    for sy in (1, -1))


STEP_CENTRES = tuple(
    (sx * ax, sy * ay)
    for ax, ay in ((384, 0), (192, 110), (0, 220))
    for sx in (1, -1)
    for sy in (1, -1))




def pitch_of(party, boxes, *, floor=60.0, corroboration=2):
    """The lattice pitch this frame draws, as (across, down), or None if unprovable.

    Why not a constant: the measured step between two adjacent nodes is 219 px on
    `evidence/runtime/packaged-mirror-20261022-085428/frame-0008` and 396 px on the
    `evidence/runtime/packaged-mirror-20261023-05xxxx` runs -- the same offset is one
    step on one floor and two steps on another, so neither a scalar radius nor
    `STEP_CENTRES` can serve both.  The pitch is a property of the frame.

    The two axes are estimated separately (a hex lattice is anisotropic), each as the
    smallest offset along that axis that at least `corroboration` boxes agree with.
    One lone far box therefore cannot define the pitch, and a frame that cannot prove
    both axes yields None instead of an invented number.
    """
    if party is None:
        return None

    def axis(values):
        if len(values) < corroboration:
            return None
        smallest = min(values)
        agreeing = [v for v in values if abs(v - smallest) <= smallest * 0.25]
        if len(agreeing) < corroboration:
            return None
        return smallest

    xs, ys = [], []
    for box in boxes:
        x, y, w, h = [float(v) for v in box[:4]]
        dx, dy = (x + w / 2) - party[0], (y + h / 2) - party[1]
        if abs(dx) >= floor:
            xs.append(abs(dx))
        if abs(dy) >= floor:
            ys.append(abs(dy))
    across, down = axis(xs), axis(ys)
    if across is None or down is None:
        return None
    return across, down


def nearest_centre(point, boxes, *, dy_share=0.35, dx_share=1.0):
    """The node centre a party reading belongs to, or None.

    Measured on 18 live frames of three runs: the reading sits a *constant* (-156, -12) from
    the nearest 190 px node box -- the marker is drawn inside the node but the reader lands
    on its upper-left shoulder.  A distance gate of a fraction of the side therefore rejects
    the true node, and the caller then drops the anchor and falls back to a stale probe
    (`map_party_anchor source: probe` on every live run).

    The rule is geometric and in the boxes' own units: the reading is aligned by *row*
    first (|dy| <= `dy_share` of the side), then by *column* (|dx| <= `dx_share` of the
    side), admitting one node's width of lateral drift.  Smallest |dy| wins, so a reading
    cannot be pulled onto another row.  Boxes narrower than half the widest are badges.
    """
    if point is None or not boxes:
        return None
    widest = max(float(box[2]) for box in boxes if len(box) >= 3)
    px, py = float(point[0]), float(point[1])
    best, best_score = None, None
    for box in boxes:
        w, h = float(box[2]), float(box[3])
        if widest and w < 0.5 * widest:
            continue
        side = max(w, h)
        cx, cy = float(box[0]) + w / 2, float(box[1]) + h / 2
        dy, dx = abs(cy - py), abs(cx - px)
        if dy > dy_share * side or dx > dx_share * side:
            continue
        score = dy + 0.25 * dx
        if best_score is None or score < best_score:
            best, best_score = (int(cx), int(cy)), score
    return best


def adjacent_to(party, boxes, *, near=150.0, far=430.0, tolerance=0.34):
    """Keep the boxes one step from the party, using this frame's own pitch.

    One step is `pitch_of(...)`; a box is kept when its offset from the party is that
    pitch to within `tolerance`.  When the frame cannot prove a pitch the reading is
    *unknown*, not *nothing*: the fallback band is applied and the caller records it,
    so an unreadable frame cannot silently pass two-step boxes as neighbours.
    """
    if party is None:
        return list(boxes)
    pitch = pitch_of(party, boxes)
    keep = []
    for box in boxes:
        x, y, w, h = [float(v) for v in box[:4]]
        dx, dy = (x + w / 2) - party[0], (y + h / 2) - party[1]
        if pitch is None:
            distance = (dx * dx + dy * dy) ** 0.5
            if near <= distance <= far:
                keep.append(box)
            continue
        across, down = pitch
        # One step is either a lateral neighbour, a vertical one, or the diagonal the
        # hex grid draws; the box must sit on one of those three, within `tolerance`.
        options = ((across, down), (across, 0.0), (0.0, down))
        reach = max(across, down) * tolerance
        if any(((abs(dx) - ex) ** 2 + (abs(dy) - ey) ** 2) ** 0.5 <= reach
               for ex, ey in options):
            keep.append(box)
    return keep




VIEW_TOLERANCE = 12.0


def movement_between(before, after, *, tolerance=VIEW_TOLERANCE):
    """Did the party walk, or did the camera move the whole page?

    The measurement that forced this: in `evidence/runtime/packaged-mirror-20261023-055547`
    the party sat at (703,316) for the early frames and at (1052,439) for the late ones --
    a delta of (349,122) -- but the badges around it were a *different set*
    ((888,432),(318,680) before versus (671,290),(671,450),(288,610) after), and
    (888,432)+(349,122) appears nowhere in the later view.  A whole-page translation
    would carry the badges with it; a different badge set means the view changed.

    `before` / `after` are dicts with `party` and `badges`.  Returns one of
    `'moved'`, `'the_view_moved'`, `'the_view_changed'` or `'unknown'` -- never a guess:
    a missing reading on either side is `'unknown'`.
    """
    if not before or not after:
        return 'unknown'
    before_party, after_party = before.get('party'), after.get('party')
    if before_party is None or after_party is None:
        return 'unknown'
    dx = after_party[0] - before_party[0]
    dy = after_party[1] - before_party[1]
    if abs(dx) <= tolerance and abs(dy) <= tolerance:
        return 'unknown'
    marks_before = list(before.get('badges') or [])
    marks_after = list(after.get('badges') or [])
    if not marks_before or not marks_after:
        return 'unknown'
    carried = 0
    for x, y in marks_before:
        if any(abs((x + dx) - ax) <= tolerance and abs((y + dy) - ay) <= tolerance
               for ax, ay in marks_after):
            carried += 1
    if carried * 2 >= len(marks_before):
        return 'the_view_moved'
    if carried == 0 and not any(abs(x - ax) <= tolerance and abs(y - ay) <= tolerance
                                for x, y in marks_before for ax, ay in marks_after):
        return 'the_view_changed'
    return 'moved'


# --- channel-order tolerance for the party reader ---------------------------
# The torch mask is warm-hue under **BGR**, and the packaged agent hands readers the
# framework's `cached_image`, which is **RGB** (measured live 2026-10-23: six map
# frames carried `image_mean 126.8` and zero `map_player`, while 88 of 90 offline
# frames read fine).  A reader that returns None on an order it cannot see is the
# defect that cost three rounds of retracting "the reader is broken", so the second
# order is tried before giving up.
_bgr_party_point = _party_point_legacy   # the first generation, kept as the colour reader


def party_readings(image):
    """Each party reader's own answer, so a null party names the reader that failed (D294).

    `party_point` returns one point or None, and "None" has been the whole story for three
    rounds of live attempts: the loop could not say whether the torch reader, the marker
    reader or the ring reader was the one that came back empty.  The three are cheap and
    independent, so a failed read can carry all three answers instead of a shrug.
    """
    pair = _bgr_party_point(image)
    marker = player_marker(image)
    ring = player_by_ring(image)
    chosen = party_point(image)
    if pair is not None:
        why = 'pair'
    elif chosen is not None:
        why = 'two_readers_agreed'
    else:
        why = 'none'
    return {'pair': pair, 'marker': marker, 'ring': ring, 'chosen': chosen, 'why': why}


def _on_the_board(point, image):
    """A party reading outside the board band is chrome, not the train (D310).

    Measured 2026-10-25: two different drags left the reading at y=221 on a 1080-high
    frame while x jumped between 498 and 1458.  A moving object cannot keep its y through
    two drags, so that reading is a HUD icon -- and every downstream decision was built on
    it.
    """
    try:
        height = float(image.shape[0])
        y = float(point[1])
    except Exception:
        return True
    return 0.25 * height <= y <= 0.88 * height


def _flame_corroborated(image, marker, ring):
    """The flame, but only when nothing contradicts it.

    A colour reading that landed in the HUD or in the right chrome still says "something
    warm is here, just not the party", so a flame far from both of those readings is a
    different object and is refused.  When neither reader answered at all -- the live
    1080p case -- there is nothing to contradict, and the shape reading is the only fact
    (D293).
    """
    flame = flame_point(image)
    if flame is None:
        return None
    for other in (marker, ring):
        if other is None:
            continue
        if abs(int(other[0]) - flame[0]) + abs(int(other[1]) - flame[1]) <= 200:
            return flame
    if marker is None and ring is None:
        return flame
    return None


REFERENCE_WIDTH = 1920.0


def _at_reference_width(image, read):
    """Run a reader at the reference width, then map its answer back.

    Every reader below is written in absolute pixels measured on 1920x1080 frames, and the
    device itself renders 1280x720: `party_point` answered (1091,252) on the archived frame
    of `-150446` and `None` on the same picture scaled to 720p, so the agent (which reads
    the device frame) fell back to the probe while the repository (which reads the archived
    png) looked healthy -- six rounds of "the fix is in but nothing changes" (D309).  The
    readers meet one scale: the reference width.
    """
    import cv2  # imported here: this module keeps the heavy import out of module load
    height, width = image.shape[:2]
    if width >= REFERENCE_WIDTH - 1:
        return read(image)
    scale = REFERENCE_WIDTH / float(width)
    bigger = cv2.resize(image, (int(round(width * scale)), int(round(height * scale))),
                        interpolation=cv2.INTER_CUBIC)
    found = read(bigger)
    if found is None:
        return None
    if isinstance(found, (tuple, list)) and len(found) == 2 and all(
            isinstance(v, (int, float)) for v in found):
        return (int(round(found[0] / scale)), int(round(found[1] / scale)))
    return found


def party_point(image):
    """`party_point` for either channel order; BGR first, RGB(A) as the fallback."""

    if image.shape[1] < REFERENCE_WIDTH - 1:
        return _at_reference_width(image, party_point)
    found = _bgr_party_point(image)
    if found is not None and _on_the_board(found, image):
        flame = flame_point(image)
        if (flame is not None
                and abs(int(found[0]) - flame[0]) + abs(int(found[1]) - flame[1]) > 200):
            # Being inside the board band is not enough: on the red theme the same colour
            # mask answers a node's gold ring (`-101647` reads (498,221) where no flame
            # exists at all), and live `-133918` spent nine clicks from that anchor.  The
            # flame's filled shape is the only reading with a counter-example behind it, so
            # a flame that disagrees by more than a card's width overrules the colour
            # reading instead of being consulted only when colour is silent (D293).
            return flame
        return found
    import cv2
    if image is None or getattr(image, 'ndim', 0) != 3 or image.shape[2] not in (3, 4):
        return None
    swapped = cv2.cvtColor(image, cv2.COLOR_RGB2BGR if image.shape[2] == 3
                           else cv2.COLOR_RGBA2BGR)
    found = _bgr_party_point(swapped)
    if found is not None:
        return found
    # Two independent readers locate the party: the stacked-torch pair above, and
    # `player_marker`'s own flame.  A board can show one flame and not the pair
    # (`packaged-mirror-20261025-083025/frame-0001`: the torch reads at (1012,595)
    # while the pair never forms), and a missing anchor silently empties the whole
    # candidate list -- the run then stops as `no_candidate_node_observed` with no
    # hint that the party was the missing fact.  So the second reader is a fallback,
    # kept inside the board band: the HUD's own flames sit above it or in the right
    # chrome, and a marker read there is not the party.
    # A single reader is not evidence: live `packaged-mirror-20261025-084828` showed
    # `player_marker` answering (48,273) on one frame and (1795,834) on the next while
    # the party had not moved, so a lone marker is noise dressed as a fact.  Two
    # independent readers that agree to within a card's width are the party (D291).
    marker = player_marker(image)
    if marker is None:
        marker = player_marker(swapped)
    ring = player_by_ring(image)
    if ring is None:
        ring = player_by_ring(swapped)
    if (marker is None or ring is None
            or abs(int(marker[0]) - int(ring[0])) > 80
            or abs(int(marker[1]) - int(ring[1])) > 80):
        # Neither the pair nor the two agreeing readers found the party: the only reading
        # left is the flame's own shape (D293).  It is measured, not guessed -- live
        # `packaged-mirror-20261025-075711` answers (670,467) and the board without a flame
        # answers None, so an empty answer here means the party truly was not on screen.
        flame = _flame_corroborated(image, marker, ring)
        if flame is not None:
            return flame
        # A lone ring is noise (D291), but a ring reading that lands on a ring the page itself
        # drew is two independent readings agreeing: live `-143225/frame-0001` answers
        # `player_by_ring` (1091,252) while `lit_rings` puts its ring at (1056,246) -- 35 px on
        # a lattice whose step is 192 -- and with the marker absent every other reader was
        # silent, so `party_point` said None and the run offered no node at all
        # (`no_candidate_node_observed`, three frames of eight candidates each).  The
        # tolerance is a quarter of a step: enough for two readers disagreeing about one
        # ring's centre, far too small to reach a neighbouring node.
        if ring is not None:
            for centre in lit_rings(image):
                if (abs(int(centre[0]) - int(ring[0])) <= 48
                        and abs(int(centre[1]) - int(ring[1])) <= 48):
                    return (int(ring[0]), int(ring[1]))
        # Neither colour nor the flame answered: the tile's own glow is the last reading
        # with a shape behind it (D293/D294), and `packaged-mirror-20261025-134415` shows the
        # flame hidden behind the tile icon while the glow is measured at (508,242).
        return glow_point(image)
    height, width = image.shape[:2]
    x, y = int(marker[0]), int(marker[1])
    if not (0 <= x < int(.95 * width)) or not (int(.10 * height) <= y < int(.86 * height)):
        flame = _flame_corroborated(image, marker, ring)
        if flame is not None:
            return flame
        # Two independent readings that agree are the party (D291), and a ring reading that
        # lands on a ring the page itself drew is exactly that: live
        # `-143225/frame-0001` answers `player_by_ring` (1091,252) while `lit_rings` puts its
        # ring at (1056,246) -- 35 px apart on a lattice whose step is 192 -- and every other
        # reader was empty, so the run refused to offer any node at all
        # (`no_candidate_node_observed` with three frames of eight candidates each).  The
        # tolerance is a quarter of a step: large enough for two readers disagreeing about
        # the centre of one ring, far too small to match a neighbouring node.
        if ring is not None:
            for centre in lit_rings(image):
                if (abs(int(centre[0]) - int(ring[0])) <= 48
                        and abs(int(centre[1]) - int(ring[1])) <= 48):
                    return (int(ring[0]), int(ring[1]))
        return None
    return x, y

def selection_bracket(image):
    """The bracket the game draws around the step it has selected (D205).

    Calibrated on the operator's own screenshot of 2026-10-25 (scaled to 1920x1080): two
    thin saturated warm-orange bars, 18x50 and 18x52, 57 px apart, tops 6 px apart, in the
    map band.  Bands below are fractions of the picture's height so the same numbers hold
    at 963x532 and at 1920x1080 -- the device reports 1280x720 while the archive is
    1920x1080, so a fixed pixel band would be wrong on one of them.

    Returns (x, y, w, h) around the pair, or None.  One bar is not a selection: the map also
    draws orange capsules, numbers and the two slot pips, and a one-sided "selection" is
    exactly how a click ends up on empty floor.
    """
    import cv2

    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (5, 170, 180), (32, 255, 255))
    count, _labels, stats, _centres = cv2.connectedComponentsWithStats(mask, 8)
    bars = []
    for x, y, w, h, area in stats[1:]:
        if not (0.30 * height < y < 0.72 * height):
            continue
        if area < 0.00018 * width * height:
            continue
        if not (0.007 * height <= w <= 0.028 * height):
            continue
        if not (0.036 * height <= h <= 0.075 * height):
            continue
        bars.append((int(x), int(y), int(w), int(h)))
    bars.sort()
    for left, right in zip(bars, bars[1:]):
        gap = right[0] - (left[0] + left[2])
        if not (0.040 * height <= gap <= 0.075 * height):
            continue
        if abs(left[1] - right[1]) > 0.014 * height:
            continue
        x = left[0]
        y = min(left[1], right[1])
        w = right[0] + right[2] - x
        h = max(left[1] + left[3], right[1] + right[3]) - y
        return (int(x), int(y), int(w), int(h))
    return None

def cyan_step_boxes(image, party, *, near=120.0, far=400.0):
    """Cyan outlines near the party: the step the game is offering right now.

    `map_clicks(template=node_badge_template())` matches badge glyphs and misses the
    plain outlined hexagon that marks the reachable step, which is why a floor-5 run
    clicked a shop two hops away and three empty tiles
    (evidence/runtime/packaged-mirror-20261025-035558/frame-0019.png: party (861,209),
    the step at about (1030,220), the shop at about (1229,250)).

    Measured on that frame: the outline's pixels are H 95-96, S ~219, V ~115, they arrive
    as arcs of 200-450 px (the lower one is 48x23 at (1031,237)), and the horizontal path
    line is cyan too -- so a blob is a candidate only when it sits in the band between
    `near` and `far` from the party, which is exactly one step of the lattice.
    """
    import cv2
    import numpy as np
    if party is None:
        return []
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (92, 150, 85), (102, 255, 255))
    count, _labels, stats, _centres = cv2.connectedComponentsWithStats(mask, 8)
    boxes = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index][:5])
        if area < 60 or not (20 <= w <= 110 and 10 <= h <= 110):
            continue
        gap = ((x + w / 2 - party[0]) ** 2 + (y + h / 2 - party[1]) ** 2) ** 0.5
        if not (near <= gap <= far):
            continue
        if (y + h / 2) < 0.14 * image.shape[0]:
            continue  # the header bar is cyan too; a step is never up there
        boxes.append((gap, [x, y, w, h]))
    boxes.sort(key=lambda item: item[0])
    return [box for _gap, box in boxes]


BADGE_NODE_SIDE = 190


def node_class(boxes, *, share=0.1):
    """The boxes that look like nodes, chosen by this frame's own size distribution.

    `map_clicks` emits a badge, a tile and a chevron per node, so a raw list mixes three
    scales.  The node class is the modal side length (within ``share``), which makes the
    choice independent of both the pack's spacing and the screen resolution.
    """
    usable = [list(box) for box in boxes
              if box and len(box) >= 4 and box[2] > 0 and box[3] > 0]
    if not usable:
        return []
    sides = sorted(box[2] for box in usable)
    mode = sides[len(sides) // 2] if len(sides) % 2 else sides[len(sides) // 2]
    low, high = mode * (1.0 - share), mode * (1.0 + share)
    return [box for box in usable if low <= box[2] <= high]


def step_pitch(boxes, *, share=0.1):
    """One lattice step, measured on this frame's node class -- never assumed."""
    nodes = node_class(boxes, share=share)
    centres = [(box[0] + box[2] / 2.0, box[1] + box[3] / 2.0) for box in nodes]
    if len(centres) < 3:
        return None
    nearest = []
    for i, (x, y) in enumerate(centres):
        dists = [((x - x2) ** 2 + (y - y2) ** 2) ** 0.5
                 for j, (x2, y2) in enumerate(centres) if j != i]
        nearest.append(min(dists))
    nearest.sort()
    pitch = nearest[len(nearest) // 2]
    return pitch if pitch >= 40 else None


def one_step(party, boxes, *, pitch=None, ratio=0.45):
    """The boxes one step from the party, judged in pitches rather than in pixels."""
    if not party:
        return []
    pitch = pitch or step_pitch(boxes)
    if not pitch:
        return []
    out = []
    for box in node_class(boxes):
        cx, cy = box[0] + box[2] / 2.0, box[1] + box[3] / 2.0
        dist = ((cx - party[0]) ** 2 + (cy - party[1]) ** 2) ** 0.5
        if dist <= 0:
            continue
        if abs(dist / pitch - 1.0) <= ratio:
            out.append((dist, box))
    return [box for _, box in sorted(out, key=lambda item: item[0])]


def edge_target(image, party, boxes, *, reach=260.0, tube=0.28):
    """The node at the end of the lit edge leaving the party, or None.

    Distance cannot decide adjacency: both retained fixtures leave `pitch_of` at None,
    so the 150..430 px band kept a two-step box on the 192 px zoom
    (`packaged-mirror-20261025-073900`: party (1324,487), target (940,456) = 385 px)
    while the same 385 px is one step on the 384 px zoom
    (`packaged-mirror-20261022-085428`).  The page draws the reachable edge instead, so
    the edge is the reference: the brightest segment near the party gives a direction and
    the node whose centre sits closest to that ray wins.
    """
    if image is None or party is None or not boxes:
        return None
    import numpy as np

    height, width = image.shape[:2]
    scale = max(1.0, width / 1920.0)
    limit = reach * scale
    px, py = float(party[0]), float(party[1])
    x0, x1 = int(max(0, px - limit)), int(min(width, px + limit))
    y0, y1 = int(max(0, py - limit)), int(min(height, py + limit))
    window = image[y0:y1, x0:x1]
    if window.size == 0:
        return None
    hsv = np.asarray(__import__('cv2').cvtColor(window, __import__('cv2').COLOR_BGR2HSV))
    # The edge is drawn either as a saturated cyan beam or as a pale white one, so a
    # bright pixel qualifies when it is either saturated or nearly grey (measured: white
    # (255,255,255) has S=0 and was excluded by a `S>=40` test that only imagined cyan).
    lit = (hsv[:, :, 2] >= 200) & ((hsv[:, :, 1] >= 40) | (hsv[:, :, 1] <= 60))
    ys, xs = np.nonzero(lit)
    if len(xs) < 12:
        return None
    dx, dy = xs + x0 - px, ys + y0 - py
    far = int(np.argmax(dx * dx + dy * dy))
    ex, ey = float(dx[far]), float(dy[far])
    length = (ex * ex + ey * ey) ** 0.5
    if length < limit * 0.2:
        return None
    ux, uy = ex / length, ey / length
    best, best_miss = None, None
    for box in boxes:
        bx, by, bw, bh = [float(v) for v in box[:4]]
        cx, cy = bx + bw / 2 - px, by + bh / 2 - py
        along = cx * ux + cy * uy
        across = abs(-cx * uy + cy * ux)
        if along <= 0:
            continue
        gap = across - tube * along
        # A perfect hit is 0.0, which is falsy: `if gap:` silently skipped every node
        # that sat on the ray (found by the synthetic test in tests/test_edge_target.py).
        gap = 0.0 if gap <= 0 else gap
        if best_miss is None or gap < best_miss:
            best, best_miss = box, gap
    return best


def line_lit(image, start, end, *, sample=160, skip=0.18, lit=90):
    """Fraction of the segment between two points whose pixels are lit (a drawn edge).

    Measured on `evidence/runtime/packaged-mirror-20261025-160619/frame-0005.png`:
    the neighbour we actually clicked (1247,264) scored 0.00 while the two that share a drawn
    line with the party scored 0.07 and 0.13 -- distance said "nearest", the line said
    "unreachable".  The ends are skipped so the tile art is not counted as the line (D325).
    """
    import cv2
    import numpy as np

    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    xs = np.linspace(start[0], end[0], sample)
    ys = np.linspace(start[1], end[1], sample)
    h, w = grey.shape[:2]
    vals = []
    for x, y in zip(xs, ys):
        xi, yi = int(round(x)), int(round(y))
        if 0 <= yi < h and 0 <= xi < w:
            vals.append(int(grey[yi, xi]))
    if not vals:
        return 0.0
    core = vals[int(len(vals) * skip):int(len(vals) * (1 - skip))] or vals
    return round(sum(1 for value in core if value > lit) / float(len(core)), 3)


def tile_centre(image, box, *, lit=25):
    """The point inside a node box that the game accepts as that tile.

    A 190px node box wraps a badge and an arrow base, so its geometric centre is not the
    hexagon's centre -- and the offset differs by row: `-160619` measured the top-row box
    [1152,169] needing -34px while the bottom-row box [960,329] needed 0 (D326).  A uniform
    constant is therefore a local observation, not a rule; the lit-edge centroid inside the
    box is measured per box instead.
    """
    import cv2
    import numpy as np

    x, y, w, h = [int(v) for v in box[:4]]
    crop = image[max(0, y):y + h, max(0, x):x + w]
    if crop.size == 0:
        return (x + w // 2, y + h // 2)
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(grey, (9, 9), 0)
    lit_map = cv2.subtract(grey, blur)
    cv2.threshold(lit_map, lit, 255, cv2.THRESH_BINARY, lit_map)
    total = cv2.moments(lit_map)['m00']
    if total <= 0:
        return (x + w // 2, y + h // 2)
    m = cv2.moments(lit_map)
    cx = int(round(m['m10'] / total))
    cy = int(round(m['m01'] / total))
    cx = min(max(cx, int(w * 0.25)), int(w * 0.75))
    cy = min(max(cy, int(h * 0.20)), int(h * 0.80))
    return (x + cx, y + cy)
