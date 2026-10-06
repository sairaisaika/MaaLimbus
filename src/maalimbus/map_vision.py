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

HEADER_PATTERN = r'^(?:Exploring|Before\s+Entry)\s+Floor\s*([1-5])\b'
HEADER_ROI = (.0, .06, .30, .22)
PACK_ROI = (.0, .14, .30, .28)


@dataclass(frozen=True)
class MapHeader:
    floor: int
    pack: str | None
    exploring_text: Text
    pack_text: Text | None


def map_header(records, size):
    """Return the map header only when floor text and the pack line both parse.

    The pack line is required so an unrelated page carrying similar wording cannot
    be promoted into MAP; it is never used as an artwork or season anchor.
    """
    floor_matches = find(records, HEADER_PATTERN, HEADER_ROI, size, .85)
    if len(floor_matches) != 1:
        return None
    text = floor_matches[0]
    match = re.match(HEADER_PATTERN, text.text.strip(), re.I)
    if match is None:
        return None
    pack_candidates = [r for r in records
                       if r.score >= .8 and r.box[1] > text.box[1]
                       and PACK_ROI[0] <= (r.box[0] + r.box[2] / 2) / size[0] <= PACK_ROI[2]
                       and PACK_ROI[1] <= (r.box[1] + r.box[3] / 2) / size[1] <= PACK_ROI[3]
                       and not re.match(HEADER_PATTERN, r.text.strip(), re.I)]
    pack_candidates.sort(key=lambda r: (r.box[1], r.box[0]))
    pack = pack_candidates[0] if pack_candidates else None
    if pack is None:
        return None
    return MapHeader(int(match.group(1)), pack.text.strip(), text, pack)


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
