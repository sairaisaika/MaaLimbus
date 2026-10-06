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

from .vision import Text, find

HEADER_PATTERN = r'^(?:Exploring|Before\s+Entry)\s+Floor\s*([1-5])?\s*$'
#: the same header in the shapes the game really renders on the floor-1 map page. OCR
#: has produced all three: 'Exploring Floor 1' as one token, 'Exploring' [56,127,202,53]
#: plus 'Floor' [236,133,122,43] as two (evidence/runtime/window-20261006-033107),
#: and 'Exploring Floor' [60,133,330,41] with the stylised digit dropped by the
#: recogniser (evidence/runtime/window-20261006-040651). So the floor digit is
#: optional and the label may or may not carry the word "Floor"; the pack line below
#: is what keeps an unrelated page from being promoted into MAP.
HEADER_LABEL_PATTERN = r'^(?:Exploring|Before\s+Entry)(?:\s+Floor)?$'
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
    if found:
        return found
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
    """The four lattice steps around the player; ordering is the caller's job."""
    if player is None:
        return []
    pitch = LATTICE_PITCH if pitch is None else pitch
    return [(player[0] + pitch[0], player[1]), (player[0] - pitch[0], player[1]),
            (player[0], player[1] + pitch[1]), (player[0], player[1] - pitch[1])]


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


def map_clicks(image, *, template=None, node_side=190):
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
    # The highlighted node is the step the game will accept, so it goes first; the
    # chevron only points along the path towards it, and the badge nodes are the
    # ordinary case where nothing on the page is marked at all.
    for point in highlighted:
        add(point, 'highlighted_node', CLICK_SIDE)
    for point in chevrons:
        add(point, 'chevron_target', node_side)
    # A step away from the player on the lattice is connected to the player by a path
    # in the live game, and a click on an unconnected node only does nothing, so the
    # four lattice steps are offered before the badge nodes when there is a player.
    for point in lattice_neighbours(player):
        if 0 <= point[0] < width and 0 <= point[1] < height:
            add(point, 'lattice_step', node_side)
    for marker in advance_candidates(markers, player):
        add((marker.node[0] + marker.node[2] // 2,
             marker.node[1] + marker.node[3] // 2), 'node_away_from_player', node_side)
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


def route_decision(header, size, *, current=None, cleared=(), candidates=()):
    """Decide a next node or refuse; never invents a target.

    `current` is the proven current-position node; `cleared` and `candidates` are
    node identifiers observed on this page. Stage one has no proven node reader,
    so callers must pass the evidence they actually hold; an absent current
    position or candidate list yields an explicit refusal reason.
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
        return dict(next_node=None, reason='ambiguous_unvisited_candidates')
    return dict(next_node=unvisited[0], reason='single_unvisited_candidate')
