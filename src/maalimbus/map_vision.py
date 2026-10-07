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
HEADER_FLOOR_PATTERN = r'^Floor\s*([1-5])?$'
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
    """
    enters = find(records, ENTER_PATTERN, ENTER_ROI, size, .8)
    if len(enters) != 1:
        return None
    rewards = find(records, REWARDS_PATTERN, REWARDS_ROI, size, .8)
    if len(rewards) != 1 and map_header(records, size) is None:
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
    blue = image[:, :, 0].astype(int)
    green = image[:, :, 1].astype(int)
    red = image[:, :, 2].astype(int)
    mask = ((red > 180) & (green > 150) & (blue < 120)).astype(np.uint8)
    mask[round(bottom * height):] = 0
    mask[:, round(right * width):] = 0
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    blobs = []
    for index in range(1, count):
        x, y, box_w, box_h, area = (int(value) for value in stats[index])
        if area < min_area:
            continue
        blobs.append(dict(x=x, y=y, w=box_w, h=box_h, area=area,
                          cx=int(round(centroids[index][0])),
                          cy=int(round(centroids[index][1]))))
    best = None
    for flame in blobs:
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


def map_clicks(image, *, template=None, node_side=190, player=None):
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
        player = (train_player(image)
                  or yellow_flame_player(markers, image) or flame_player(markers, image)
                  or likely_player(markers))
    clicks = []

    def add(point, kind, side):
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
        if player and (centre[0] - player[0]) ** 2 + (centre[1] - player[1]) ** 2 <= 70 * 70:
            continue
        fill = area / float(max(1, box_w * box_h))
        ratio = box_w / float(max(1, box_h))
        # A highlighted hexagon is a compact ring (live fill 0.12-0.21); the path glow
        # that shares this mask is a large sparse wash (fill 0.03) and the chevron is a
        # flat bar (ratio above 3), so neither can pass for the marked node.
        if box_w >= 90 and ratio <= 3.0 and fill >= 0.08:
            highlighted.append(centre)
        elif ratio > 3.0:
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
    walk = path_end(image, player)
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
    for point in icons:
        add(point, 'lit_icon', CLICK_SIDE)
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
    for point in lattice_neighbours(player):
        if 0 <= point[0] < width and 0 <= point[1] < height:
            add(point, 'lattice_step', node_side)
    return clicks


# The page's own captions drift between runs: the live frames read the button as
# "Battle!" while it is disabled and as "To" + "Battle!" (with a Chain badge over
# it) once a team is picked, and the clear action as " Clear Selection" with a
# leading space. Anchoring the captions loosely keeps this page recognisable in
# both states; both captions are still required together, so a looser pattern
# cannot promote an unrelated page.
BATTLE_PATTERN = r'^\s*(?:Chain\s+)?(?:To\s+)?Battle!?\s*$'
BATTLE_ROI = (.83, .77, .97, .87)
CLEAR_SELECTION_PATTERN = r'^\s*Clear\s+Selection\s*$'
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


def pre_battle_team_page(records, size):
    """Return the pre-battle team page, or None when this is not that page."""
    battle = find(records, BATTLE_PATTERN, BATTLE_ROI, size, .8)
    clear = find(records, CLEAR_SELECTION_PATTERN, CLEAR_SELECTION_ROI, size, .8)
    if len(battle) != 1 or len(clear) != 1:
        return None
    participants = tuple(t.text.strip() for t in
                         find(records, PARTICIPANTS_PATTERN, (.80, .66, .98, .76), size, .8))
    return TeamPage(battle[0], clear[0], participants)


def battle_target(page):
    """The bounded click box for `Battle!`, or None when the page is not current."""
    if page is None or page.battle is None:
        return None
    return page.battle.box


def map_header(records, size):
    """Return the map header only when floor text and the pack line both parse.

    The pack line is required so an unrelated page carrying similar wording cannot
    be promoted into MAP; it is never used as an artwork or season anchor. The
    header is accepted either as one token or as the two the game really renders
    (see :data:`HEADER_LABEL_PATTERN`); the floor number stays ``None`` when the
    stylised digit is not read, and the label alone is enough when OCR also drops
    the separate "Floor" token.
    """
    floor = None
    text = None
    matches = find(records, HEADER_PATTERN, HEADER_ROI, size, .85)
    if len(matches) == 1:
        text = matches[0]
        digit = re.match(HEADER_PATTERN, text.text.strip(), re.I).group(1)
        floor = int(digit) if digit else None
    else:
        labels = [r for r in find(records, HEADER_LABEL_PATTERN, HEADER_ROI, size, .85)]
        for label in labels:
            same_line = [r for r in find(records, HEADER_FLOOR_PATTERN, HEADER_ROI, size, .85)
                         if r.box[0] > label.box[0]
                         and abs((r.box[1] + r.box[3] / 2) / size[1]
                                 - (label.box[1] + label.box[3] / 2) / size[1]) <= .03]
            same_line.sort(key=lambda r: r.box[0])
            text = label
            if same_line:
                digit = re.match(HEADER_FLOOR_PATTERN, same_line[0].text.strip(), re.I).group(1)
                floor = int(digit) if digit else None
            # The stylised "Floor" token is dropped by OCR on roughly half of the
            # live map frames (evidence/runtime/window-20261006-033259/frame-0002.json),
            # so the label alone is accepted; the pack line below still gates it.
            break
    if text is None:
        return None
    pack_candidates = [r for r in records
                       if r.score >= .8 and r.box[1] > text.box[1]
                       and PACK_ROI[0] <= (r.box[0] + r.box[2] / 2) / size[0] <= PACK_ROI[2]
                       and PACK_ROI[1] <= (r.box[1] + r.box[3] / 2) / size[1] <= PACK_ROI[3]
                       and not re.match(HEADER_PATTERN, r.text.strip(), re.I)
                       and not re.match(HEADER_LABEL_PATTERN, r.text.strip(), re.I)
                       and not re.match(HEADER_FLOOR_PATTERN, r.text.strip(), re.I)]
    pack_candidates.sort(key=lambda r: (r.box[1], r.box[0]))
    pack = pack_candidates[0] if pack_candidates else None
    if pack is None:
        return None
    return MapHeader(floor, pack.text.strip(), text, pack)


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
