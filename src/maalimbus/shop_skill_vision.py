"""Read the shop's skill-replacement offer and its subpage off the page (offline).

Two independent things live here and neither one spends anything:

``read_shelf`` answers what the shop shelf is showing.  A skill-replacement offer
announces itself in its own printed words -- ``Replace <sinner>'s Skill`` -- so the
sinner is taken from that text and from nothing else.  The card's column, grid slot
or index never decide who the offer is for; they only pair the announced offer with
the price badge printed under it on the same column.  The canonical spelling comes
from ``storage.SINNERS``; a text that does not name exactly one of them is reported
as unreadable with its OCR confidence, never repaired or rounded onto a neighbour.

``read_subpage`` answers what an opened replacement subpage shows.  No live capture
of that page has been retained in this repository, so its layout is NOT known and
this reader does not assume one: it matches only the values a caller already holds
(a skill bound to the identity by ``identity-catalog.json``, a price, a replacement
slot), requires every field to be unambiguous at the caller's confidence, and says
which fields are missing when they are.  It never invents a skill id or a slot, and
it cannot approve a purchase: ``authorized`` is always ``False`` and
``would_spend`` is always ``False``.  Durable intents and input stay in
``shop_transaction.ShopTransaction`` / the runner.

No Maa controller, no screen capture, no input, no private budget or ledger write,
and no threshold is tuned here.  Evidence paths are only ever read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from .storage import SINNERS
from .vision import Text, find

REFERENCE = (1920, 1080)
READER_VERSION = 1
SUBPAGE_VERSION = 1
OVERLAY_VERSION = 1

#: The shelf's own reading confidence, used for pairing and for reporting.
DEFAULT_THRESHOLD = .9

#: ``Replace <sinner>'s Skill``.  Both the apostrophe and the whole possessive are
#: frequently dropped or mangled by OCR -- the retained frame reads ``Replace
#: Heathciffs Skill`` and a dropped ``'s`` was measured to make a canonical offender
#: like ``Replace Ryoshu Skill`` vanish from the shelf entirely -- so the possessive
#: is optional here.  The captured token is still matched against ``storage.SINNERS``
#: and never against an approximate spelling of its own, so widening the pattern can
#: only turn a silent miss into an honest ``sinner_text_not_a_canonical_name`` row.
REPLACE_PATTERN = re.compile(
    r"^\s*replace\s+(?P<sinner>[A-Za-z][A-Za-z' -]*?)\s*(?:['\u2019\u02bc]s)?\s+skill\s*[.!:]?\s*$",
    re.IGNORECASE)

PRICE_PATTERN = re.compile(r'^\s*(\d{1,5})\s*$')

#: The name badge and the price badge of one offer are printed in the same column:
#: 198px apart across the grid, both rows 230px apart, so these tolerances keep
#: offers apart while surviving the shelves' few pixels of jitter.
COLUMN_TOLERANCE = 90
PRICE_ROW_BAND = 90

#: Matches used by the retained shelf frame (window-20261012-024300/frame-0173):
#: names at y=496..530, price badges at y=458..494 and y=688..724.
SHELF_BAND_Y = (280, 830)
SHELF_BAND_X = (820, 1860)

#: The native ``E.G.O Gift GET!`` notice.  Its identity is already proved twice over
#: in this project: ``assets/resource/en/locale.json`` carries the pattern
#: ``^E\.?G\.?O Gift GET!$`` and ``assets/resource/base/anchors.json`` id ``gift_get``
#: carries the title band, the single Confirm band and their measured boxes.  The
#: title itself is the literal notice text, so it is the same in every locale.
GIFT_GET_TITLE = 'E.G.O Gift GET!'
GIFT_GET_CONFIRM = r'^Confirm$'
GIFT_GET_TITLE_ROI = (.40, .21, .62, .29)
GIFT_GET_CONFIRM_ROI = (.44, .70, .58, .78)
GIFT_GET_TITLE_BOX = (828, 250, 258, 41)
GIFT_GET_CONFIRM_BOX = (922, 774, 136, 45)


@dataclass(frozen=True)
class SkillOffer:
    """One ``Replace <sinner>'s Skill`` offer: who, what price, where, and how sure."""

    sinner: str
    sinner_known: bool
    announced: str
    announced_confidence: float
    name_box: tuple | None
    price: int | None
    price_confidence: float | None
    price_box: tuple | None
    column: int | None
    reasons: tuple
    ambiguity: tuple


@dataclass(frozen=True)
class Shelf:
    """What one shelf frame shows, with every honesty caveat attached."""

    source: str | None
    size: tuple
    image_sha256: str | None
    image_sha256_source: str
    threshold: float
    skill_offers: tuple
    gift_names: tuple
    unreadable: tuple
    missing: tuple
    low_confidence: tuple
    ambiguous: tuple
    scene: str | None
    authorized: bool
    would_spend: bool


def _texts(records):
    """Accept ``vision.Text`` records, frame dicts, or the raw frame ``ocr`` rows."""
    result = []
    for row in records:
        if isinstance(row, Text):
            result.append(row)
        elif isinstance(row, dict):
            try:
                result.append(Text(str(row['text']), tuple(row['box']), float(row['score'])))
            except (KeyError, TypeError, ValueError):
                raise ValueError('Invalid OCR record')
        else:
            try:
                result.append(Text(str(row.text), tuple(row.box), float(row.score)))
            except AttributeError:
                raise ValueError('Invalid OCR record')
    return result


def _size(size):
    """The frame shape, required to match the reference layout at some scale.

    Every region this module reads is a normalized box over 1920x1080, so a shape with
    a different aspect ratio would silently shift those regions down the page; a frame
    that is not the reference layout scaled is refused instead of read crooked.
    """
    if size is None:
        return REFERENCE
    if (not isinstance(size, (list, tuple)) or len(size) != 2
            or any(type(n) is not int or n <= 0 for n in size)):
        raise ValueError('Invalid frame size')
    shape = (int(size[0]), int(size[1]))
    ratio = shape[0] / float(REFERENCE[0])
    # A 0.5px rounding allowance: 1000x562 is a legitimate rescale, 1920x1079 is not.
    if not 0 < ratio <= 4 or abs(shape[1] - REFERENCE[1] * ratio) > .5:
        raise ValueError('Frame must be the 1920x1080 reference layout or an integer scale')
    return shape


def _center(box):
    x, y, w, h = box
    return x + w / 2.0, y + h / 2.0


def _inside_band(box, size):
    sx = size[0] / float(REFERENCE[0])
    sy = size[1] / float(REFERENCE[1])
    cx, cy = _center(box)
    return (SHELF_BAND_X[0] * sx <= cx <= SHELF_BAND_X[1] * sx
            and SHELF_BAND_Y[0] * sy <= cy <= SHELF_BAND_Y[1] * sy)


def _normalised_text(cell):
    """Whitespace-collapsed, case-folded text; ``''`` when there is nothing to read."""
    return ' '.join(cell.split()).casefold() if isinstance(cell, str) else ''


def _canonical(cell):
    """The canonical sinner a printed text names, or ``None``.

    Whitespace is collapsed and case is folded; the printed token must then equal a
    sinner's name exactly.  ``Heathciffs`` therefore stays unreadable instead of
    becoming ``Heathcliff``.
    """
    wanted = _normalised_text(cell)
    if not wanted:
        return None
    for sinner in SINNERS:
        if sinner.casefold() == wanted:
            return sinner
    return None


def _png_hash(source):
    """The retained PNG's own SHA256 beside the frame JSON, or ``None``.

    The retained pair is ``<name>.json`` + ``<name>.png``, so the suffix is replaced
    on the *name* and never on a dotted stem (``frame-0173.200.300.json`` keeps its
    ``frame-0173.200.300.png``) -- the naive ``Path.with_suffix`` would silently look
    at a different file and report a hash of the wrong bytes.
    """
    if source is None:
        return None, 'absent'
    path = Path(source)
    candidates = (path.parent / (path.stem + '.png'), path.parent / (path.name + '.png'))
    for candidate in candidates:
        if candidate.is_file():
            return hashlib.sha256(candidate.read_bytes()).hexdigest(), 'retained_png'
    return None, 'absent'


def read_shelf(records, size=None, *, source=None, threshold=DEFAULT_THRESHOLD):
    """Every skill-replacement offer on the shelf, read from the announced text.

    Callers pass a retained local frame: either the frame's ``ocr`` rows, or its
    already-converted records.  ``size`` defaults to 1920x1080.  ``source`` is the
    path of the retained JSON whose sibling PNG hash is carried as evidence.
    """
    if not isinstance(threshold, (int, float)) or not 0 < threshold <= 1:
        raise ValueError('Invalid OCR threshold')
    shape = _size(size)
    rows = _texts(records)
    if source is not None and not isinstance(source, (str, Path)):
        raise ValueError('Invalid retained frame path')
    digest, digest_source = _png_hash(source)

    prices = []
    names = []
    for row in rows:
        if not _inside_band(row.box, shape):
            continue
        match = PRICE_PATTERN.match(row.text or '')
        if match:
            prices.append((int(match.group(1)), row.box, float(row.score), row.text))
        elif len((row.text or '').strip()) >= 3:
            # One- and two-character fragments are OCR debris (the retained frame has a
            # stray 'C' inside the panel); they are not gift titles and not announcements.
            names.append((row.text.strip(), row.box, float(row.score)))

    skill_offers = []
    gift_names = []
    unreadable = []
    ambiguous = []
    low_confidence = []

    for name, name_box, confidence in names:
        match = REPLACE_PATTERN.match(name)
        if match is None:
            gift_names.append(name)
            continue
        announced_sinner = ' '.join(match.group('sinner').split())
        sinner = _canonical(announced_sinner)
        reasons = []
        offered = []
        for price, price_box, price_score, price_text in prices:
            nx, ny = _center(name_box)
            px, py = _center(price_box)
            tolerance = COLUMN_TOLERANCE * (shape[0] / float(REFERENCE[0]))
            band = PRICE_ROW_BAND * (shape[1] / float(REFERENCE[1]))
            if abs(px - nx) <= tolerance and py < ny and 0 < ny - py <= band:
                offered.append((abs(px - nx), -py, price, price_box, price_score, price_text))
        if not offered:
            # The announcement names the offer; a missing badge is reported as a missing
            # badge, because its absence is not a price of zero.
            reasons.append('price_pair_missing')
            reasons.append('price_unknown')
            price = None
            price_box = None
            price_score = None
            price_text = None
        else:
            offered.sort()
            if len(offered) > 1:
                # A second badge in the same column under the same announcement is two
                # claims about one price; never pick the nicer one silently.
                reasons.append('price_pair_ambiguous')
                ambiguous.append(dict(name=name, candidates=[
                    dict(price=row[2], box=list(row[3]), confidence=row[4], text=row[5])
                    for row in offered]))
            price, price_box, price_score, price_text = (
                offered[0][2], offered[0][3], offered[0][4], offered[0][5])
            if price_score < threshold:
                low_confidence.append(dict(field='price', text=price_text, confidence=price_score))
                reasons.append('price_confidence_below_threshold')
        if confidence < threshold:
            low_confidence.append(dict(field='announcement', text=name, confidence=confidence))
            reasons.append('announcement_confidence_below_threshold')
        if sinner is None:
            unreadable.append(dict(text=name, box=list(name_box), confidence=confidence,
                                   expected=list(SINNERS)))
            reasons.append('sinner_text_not_a_canonical_name')
        skill_offers.append(SkillOffer(
            sinner=sinner, sinner_known=sinner is not None, announced=name,
            announced_confidence=confidence, name_box=tuple(name_box), price=price,
            price_confidence=price_score, price_box=tuple(price_box) if price_box else None,
            column=None, reasons=tuple(reasons), ambiguity=tuple()))

    gift_names.sort()
    return Shelf(
        source=str(Path(source)) if source is not None else None,
        size=shape, image_sha256=digest, image_sha256_source=digest_source,
        threshold=float(threshold), skill_offers=tuple(skill_offers),
        gift_names=tuple(gift_names), unreadable=tuple(unreadable),
        missing=tuple(dict(field='price', announced=offer.announced)
                      for offer in skill_offers if offer.price is None),
        low_confidence=tuple(low_confidence), ambiguous=tuple(ambiguous),
        scene=None, authorized=False, would_spend=False)


def _shelf_dict(shelf, scene=None, declared=None):
    return dict(
        version=READER_VERSION, source=shelf.source, size=list(shelf.size), scene=scene,
        image_sha256=shelf.image_sha256, image_sha256_source=shelf.image_sha256_source,
        image_sha256_declared=declared, threshold=shelf.threshold,
        skill_offers=[dict(sinner=o.sinner, sinner_known=o.sinner_known,
                           announced=o.announced, announced_confidence=o.announced_confidence,
                           name_box=list(o.name_box) if o.name_box else None,
                           price=o.price, price_confidence=o.price_confidence,
                           price_box=list(o.price_box) if o.price_box else None,
                           column=o.column, reasons=list(o.reasons),
                           ambiguity=list(o.ambiguity)) for o in shelf.skill_offers],
        gift_names=list(shelf.gift_names), unreadable=list(shelf.unreadable),
        missing=list(shelf.missing), low_confidence=list(shelf.low_confidence),
        ambiguous=list(shelf.ambiguous), authorized=False, would_spend=False,
        model_trained=False, input_sent=False, game_controller=False)


#: Fields the retained frame's own OCR rows must carry.  A frame missing one of
#: these is refused, because a partial read could look like a clean shelf.
FRAME_FIELDS = ('scene', 'size', 'image_sha256', 'ocr')


def _overlay_dict(overlay, size, source, scene, *, reason=None):
    """One uniform result card for the gift-get notice, readable or not.

    ``available`` is True only when the notice's own title was proven on this frame;
    ``complete`` is True only when the notice also carries exactly one Confirm, so an
    unread notice is never clicked and a frame that is not the notice is never
    reported as a missing notice.
    """
    overlay = overlay or {}
    return dict(
        version=OVERLAY_VERSION, kind='ego_gift_get_notice',
        source=str(source) if source is not None else None, size=list(size), scene=scene,
        available=bool(overlay.get('title_box')), complete=bool(overlay.get('confirm_box')),
        title=overlay.get('title'), title_box=overlay.get('title_box'),
        confirm=overlay.get('confirm'), confirm_box=overlay.get('confirm_box'),
        target=overlay.get('confirm_box'), title_roi=list(overlay.get('title_roi') or GIFT_GET_TITLE_ROI),
        confirm_roi=list(overlay.get('confirm_roi') or GIFT_GET_CONFIRM_ROI),
        threshold=overlay.get('threshold', DEFAULT_THRESHOLD),
        proved_title=GIFT_GET_TITLE, refused=[reason] if reason else [], reason=reason,
        layout_known=True,
        evidence='assets/resource/en/locale.json gift_get + anchors.json id gift_get; '
                 'live evidence/runtime/window-20261006-042640/frame-0066.json',
        note='The notice proves no purchase by itself; only the shelf that returns with '
             'the exact coin delta and the removed offer does.',
        authorized=False, would_spend=False, input_sent=False, game_controller=False,
        model_trained=False)


def read_frame(path, *, threshold=DEFAULT_THRESHOLD):
    """Read one retained local frame JSON.  Read-only; nothing here touches a device."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Retained local frame required')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or any(key not in data for key in FRAME_FIELDS):
        raise ValueError('Invalid retained shop frame')
    shape = _size(data['size'])
    ratio = shape[0] / float(REFERENCE[0])
    if not 0 < ratio <= 4 or shape[1] != int(round(REFERENCE[1] * ratio)):
        raise ValueError('Frame must be the 1920x1080 reference layout or an integer scale')
    rows = data['ocr']
    if not isinstance(rows, list):
        raise ValueError('Invalid retained shop frame OCR')
    texts = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('text'), str)
                or type(row.get('score')) not in (int, float)
                or not 0 <= row['score'] <= 1
                or not isinstance(row.get('box'), list) or len(row['box']) != 4
                or any(type(n) is not int for n in row['box'])):
            raise ValueError('Invalid retained OCR row')
        x, y, width, height = row['box']
        if min(x, y) < 0 or min(width, height) <= 0 or x + width > shape[0] or y + height > shape[1]:
            raise ValueError('Retained OCR box outside image')
        texts.append(Text(row['text'], tuple(row['box']), float(row['score'])))
    shelf = read_shelf(texts, shape, source=path, threshold=threshold)
    declared = data.get('image_sha256')
    if shelf.image_sha256 is not None and declared is not None and declared != shelf.image_sha256:
        raise ValueError('Retained frame PNG hash differs from its own record')
    if shelf.image_sha256 is None and not isinstance(declared, str):
        raise ValueError('Retained frame carries no image hash')
    return _shelf_dict(shelf, scene=data.get('scene'), declared=declared)


def read_overlay(records, size=None, *, locale=None, source=None,
                 title_pattern=None, confirm_pattern=None, expected_title=None,
                 require_scene=None, scene=None, threshold=DEFAULT_THRESHOLD):
    """Recognise the native ``E.G.O Gift GET!`` notice that covers a shop shelf.

    A shop purchase is paid at its card, but the game then raises this notice over the
    shelf, so the shelf that proves the coin delta is not readable until the notice is
    cleared.  The notice is identified by the two texts the project already proved
    (``assets/resource/base/anchors.json`` id ``gift_get``): the title in its own band
    and the notice's single Confirm.  Its Confirm box is returned as the click target,
    so the notice's own control is clicked and no free-hand position is invented.

    ``available is False`` means the frame is simply not this notice, which is a
    tolerated read.  ``complete is False`` means the notice is up but unread: the
    title is not proven, or it does not carry exactly one Confirm, and nothing may be
    clicked from this frame.  The notice proves no purchase by itself; a shop receipt
    still needs the shelf that comes back with the exact coin delta.
    """
    rows = _texts(records)
    shape = _size(size)
    patterns = locale or {}
    title = title_pattern or patterns.get('gift_get') or GIFT_GET_TITLE
    confirm = confirm_pattern or patterns.get('gift_confirm') or GIFT_GET_CONFIRM
    for pattern, label in ((title, 'gift get title'), (confirm, 'gift get confirm')):
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError('Invalid ' + label + ' pattern')
        re.compile(pattern)
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0 <= threshold <= 1:
        raise ValueError('Invalid OCR threshold')
    if expected_title is not None and _normalised_text(expected_title) != _normalised_text(GIFT_GET_TITLE):
        raise ValueError('Expected overlay title is not the proved notice title')
    if require_scene is not None and scene != require_scene:
        return _overlay_dict(None, shape, source, scene,
                             reason='overlay_scene_not_' + str(require_scene).casefold())
    hits = find(rows, title, GIFT_GET_TITLE_ROI, shape, threshold)
    if len(hits) != 1:
        return _overlay_dict(None, shape, source, scene,
                             reason='overlay_absent' if not hits else 'overlay_title_ambiguous')
    title_hit = hits[0]
    if _normalised_text(title_hit.text) != _normalised_text(GIFT_GET_TITLE):
        # The locale pattern is allowed to be wider than the proved title; a wider
        # match still has to print this exact notice, or the frame is not the notice.
        return _overlay_dict(None, shape, source, scene,
                             reason='overlay_title_differs_from_proved_notice')
    controls = find(rows, confirm, GIFT_GET_CONFIRM_ROI, shape, threshold)
    if len(controls) != 1:
        return _overlay_dict(dict(title=title_hit.text, title_box=list(title_hit.box),
                                  confirm=None, confirm_box=None, title_roi=GIFT_GET_TITLE_ROI,
                                  confirm_roi=GIFT_GET_CONFIRM_ROI, threshold=threshold),
                             shape, source, scene,
                             reason='overlay_confirm_not_proven' if not controls
                             else 'overlay_confirm_ambiguous')
    control = controls[0]
    return _overlay_dict(dict(title=title_hit.text, title_box=list(title_hit.box),
                              confirm=control.text, confirm_box=list(control.box),
                              title_roi=GIFT_GET_TITLE_ROI, confirm_roi=GIFT_GET_CONFIRM_ROI,
                              threshold=threshold),
                         shape, source, scene)


def frame_overlay(path, *, locale=None, require_scene=None, threshold=DEFAULT_THRESHOLD):
    """Read the notice out of one retained frame JSON; read-only, no device touched.

    The frame's declared scene and size are carried into the result so a caller can
    anchor an acknowledgement to the frame it was read from, and the frame's own PNG
    hash is re-verified against the retained PNG exactly as the shelf reader does.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Retained local frame required')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or any(key not in data for key in FRAME_FIELDS):
        raise ValueError('Invalid retained shop frame')
    shape = _size(data['size'])
    rows = data['ocr']
    if not isinstance(rows, list):
        raise ValueError('Invalid retained shop frame OCR')
    texts = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('text'), str)
                or type(row.get('score')) not in (int, float)
                or not 0 <= row['score'] <= 1
                or not isinstance(row.get('box'), list) or len(row['box']) != 4
                or any(type(n) is not int for n in row['box'])):
            raise ValueError('Invalid retained OCR row')
        x, y, width, height = row['box']
        if min(x, y) < 0 or min(width, height) <= 0 or x + width > shape[0] or y + height > shape[1]:
            raise ValueError('Retained OCR box outside image')
        texts.append(Text(row['text'], tuple(row['box']), float(row['score'])))
    result = read_overlay(texts, shape, locale=locale, source=path, scene=data.get('scene'),
                          require_scene=require_scene, threshold=threshold)
    declared = data.get('image_sha256')
    actual, digest_source = _png_hash(path)
    if declared is not None and actual is not None and declared != actual:
        raise ValueError('Retained frame PNG hash differs from its own record')
    result['declared_image_sha256'] = declared
    result['image_sha256'] = actual
    result['image_sha256_source'] = digest_source
    return result


def load_identity_skills(path):
    """``{identity_id: set(skill_id)}`` from the shipped identity catalog.

    The catalogue is the only source of skill ids here; no second numbering and no
    invented id.  ``identity-catalog.json`` is a list of identities under
    ``identities``.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Identity catalogue required')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported identity catalogue version')
    rows = data.get('identities')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Identity catalogue has no identities')
    catalog = {}
    for row in rows:
        if not isinstance(row, dict) or type(row.get('id')) is not int:
            raise ValueError('Identity catalogue row needs an integer id')
        skills = row.get('skills')
        if not isinstance(skills, list) or not skills or any(type(s) is not int for s in skills):
            raise ValueError('Identity catalogue row needs integer skills')
        catalog[row['id']] = set(skills)
    return catalog


@dataclass(frozen=True)
class Subpage:
    """A bounded reading of an opened replacement subpage: what is proven, what is not."""

    version: int
    complete: bool
    authorized: bool
    would_spend: bool
    skill_id: int | None
    skill_name: str | None
    replaces: int | None
    price: int | None
    price_box: tuple | None
    confirm: tuple | None
    cancel: tuple | None
    missing: tuple
    refused: tuple
    evidence: tuple
    synthetic: bool
    threshold: float
    live_subpage_evidence: bool


def _field(records, wanted, threshold, label, missing, refused):
    """The single confident record whose text equals ``wanted``, else ``None``."""
    hits = [row for row in records if row.score >= threshold and row.text.strip() == wanted]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        missing.append(label)
    else:
        refused.append(label + '_ambiguous')
    return None


def _controls(rows, size, confirm_roi=None, cancel_roi=None):
    """The Confirm of the replacement subpage, when a unique pair sits in its regions.

    No live subpage capture is retained, so the regions default to the shop's own
    dialog regions (``shop_vision.CONFIRM_ROI`` / ``CANCEL_ROI``) and the pair must be
    unique there; anything else is reported unproven rather than clicked.
    """
    from .vision import find
    from .shop_vision import CANCEL_ROI, CONFIRM_ROI

    confirm_roi = confirm_roi or CONFIRM_ROI
    cancel_roi = cancel_roi or CANCEL_ROI
    confirm = find(rows, r'^Confirm$', confirm_roi, size, .9)
    cancel = find(rows, r'^[X\u00d7]?\s*Cancel$', cancel_roi, size, .9)
    if len(confirm) != 1 or len(cancel) != 1:
        return None, None, 'confirm_cancel_pair_unproven'
    return tuple(confirm[0].box), tuple(cancel[0].box), None


def read_subpage(records, size=None, *, identity_id, skills, skill_id, name,
                 skill_names=(), replaces=(), price=None, threshold=DEFAULT_THRESHOLD,
                 confirm_roi=None, cancel_roi=None):
    """Read an opened replacement subpage without assuming a layout nobody retained.

    One call answers the one skill the shelf already announced: ``skill_id`` is that
    id, ``name`` is the name it is printed under, ``replaces`` is the skill the offer
    would displace and ``skill_names`` resolves the *displaced* skill's printed name.
    A name that simply is not on the page is a missing field -- never evidence about
    some other skill's row.  Every resolved id must be bound to the identity by the
    shipped catalogue, so a page can only ever confirm ids that already exist.  With
    no retained live subpage capture this returns ``complete=False`` on any real
    frame, by design, and it never authorizes anything.
    """
    if not isinstance(threshold, (int, float)) or not 0 < threshold <= 1:
        raise ValueError('Invalid OCR threshold')
    shape = _size(size)
    rows = _texts(records)
    if type(identity_id) is not int:
        raise ValueError('Identity id must be an integer')
    if not isinstance(skills, (set, frozenset, list, tuple)):
        raise ValueError('Identity skills must be supplied')
    bound = set(skills)
    if not bound or any(type(s) is not int for s in bound):
        raise ValueError('Identity skills must be integer ids')
    if type(skill_id) is not int:
        raise ValueError('The announced skill id must be an integer')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('The announced skill name must be printed text')
    name = name.strip()
    if price is not None and (type(price) is not int or price < 0):
        raise ValueError('Price must be a non-negative integer')
    names = {}
    for other_id, printed in dict(skill_names or {}).items():
        if type(other_id) is not int or not isinstance(printed, str) or not printed.strip():
            raise ValueError('Skill names must map integer ids to printed names')
        names[other_id] = printed.strip()
    replaceable = set(replaces or ())

    missing = []
    refused = []
    evidence = []

    # The announced name is the skill the shelf already said is being offered, so it
    # is the one name this page has to print.  No other skill name is searched for; an
    # absent one would say nothing about the page and must not block the reading.
    announced_hit = _field(rows, name, threshold, 'skill_name', missing, refused)

    slot_hits = []
    for displaced_id in sorted(replaceable):
        if names.get(displaced_id) is None:
            continue
        row = _field(rows, names[displaced_id], threshold,
                     'replacement_slot:' + str(displaced_id), missing, refused)
        if row is not None:
            slot_hits.append((displaced_id, names[displaced_id], row))

    price_box = None
    seen = {row.text.strip() for row in rows if row.score >= threshold}
    if price is None:
        printed = [row for row in rows if row.score >= threshold and PRICE_PATTERN.fullmatch(row.text)]
        if len(printed) == 1:
            price = int(PRICE_PATTERN.fullmatch(printed[0].text).group(1))
            price_box = tuple(printed[0].box)
        elif not printed:
            missing.append('price')
        else:
            refused.append('price_ambiguous')
    elif str(price) not in seen:
        missing.append('price')

    confirm, cancel, control_refusal = _controls(rows, shape, confirm_roi, cancel_roi)
    if control_refusal is not None:
        refused.append(control_refusal)

    resolved_skill = skill_id if announced_hit is not None else None
    if resolved_skill is not None and resolved_skill not in bound:
        refused.append('skill_not_bound_to_identity')
        resolved_skill = None
    replaced = slot_hits[0][0] if len(slot_hits) == 1 else None
    if replaceable and len(slot_hits) != 1:
        # A replacement is only bounded when the page says which skill it displaces; an
        # unresolved slot is a missing field, never a licence to displace anything.
        missing.append('replacement_slot')
    if replaced is not None and replaced not in bound:
        refused.append('replacement_slot_not_bound_to_identity')
        replaced = None
    if replaced is not None and replaced == resolved_skill:
        refused.append('replacement_slot_is_the_new_skill')
        replaced = None

    if announced_hit is not None:
        evidence.append(dict(field='skill_name', text=name,
                             box=list(announced_hit.box),
                             confidence=float(announced_hit.score)))
    if len(slot_hits) == 1:
        evidence.append(dict(field='replacement_slot', text=slot_hits[0][1],
                             box=list(slot_hits[0][2].box),
                             confidence=float(slot_hits[0][2].score)))
    if price is not None:
        evidence.append(dict(field='price', text=str(price),
                             box=list(price_box) if price_box else None))
    complete = (resolved_skill is not None and replaced is not None and price is not None
                and not refused and not missing)
    return Subpage(version=SUBPAGE_VERSION, complete=complete, authorized=False,
                   would_spend=False, skill_id=resolved_skill,
                   skill_name=name if announced_hit is not None else None,
                   replaces=replaced, price=price, price_box=price_box, confirm=confirm,
                   cancel=cancel, missing=tuple(missing), refused=tuple(refused),
                   evidence=tuple(evidence), synthetic=False, threshold=float(threshold),
                   live_subpage_evidence=False)


def subpage_dict(subpage, *, synthetic=None):
    """The JSON-safe reading.  ``synthetic`` may only be *raised*, never cleared:
    a fixture cannot become live evidence by asking for it."""
    if synthetic is True and not subpage.synthetic:
        subpage = replace(subpage, synthetic=True)
    return dict(version=subpage.version, complete=subpage.complete, authorized=False,
                would_spend=False, skill_id=subpage.skill_id,
                skill_name=subpage.skill_name, replaces=subpage.replaces,
                price=subpage.price,
                price_box=list(subpage.price_box) if subpage.price_box else None,
                confirm=list(subpage.confirm) if subpage.confirm else None,
                cancel=list(subpage.cancel) if subpage.cancel else None,
                missing=list(subpage.missing), refused=list(subpage.refused),
                evidence=list(subpage.evidence), synthetic=subpage.synthetic,
                threshold=subpage.threshold,
                live_subpage_evidence=subpage.live_subpage_evidence)


#: What a caller must supply and what the reader refuses to guess.  Declared so the
#: runner can state the protocol before a subpage exists, and so a synthetic test
#: cannot be mistaken for a validated layout.
SUBPAGE_PROTOCOL = dict(
    version=SUBPAGE_VERSION,
    live_subpage_evidence=False,
    layout_known=False,
    required=[
        'identity_id: an integer id from identity-catalog.json',
        'skills: the skill-id set bound to that identity by the same catalogue',
        'skill_names: {skill_id: printed name} for the names that may appear',
        'replaces: the skill ids that may be displaced on this subpage',
        'price: the integer price already read off the shelf, or exactly one printed price',
        'threshold: the caller\'s confidence; never lowered to make a field appear',
    ],
    refuses=[
        'a skill id that the identity catalogue does not bind to the identity',
        'a replacement slot equal to the new skill',
        'a missing, duplicated or below-threshold field, reported by name',
        'approval: authorized and would_spend are always False',
    ],
    never=['invent a skill id', 'infer a slot from geometry or slot index',
           'promote a synthetic fixture to live evidence', 'lower the threshold',
           'approve a purchase or a spend of any budget'],
)


def main(argv=None):
    """Local read-only replay of one retained frame.  Prints JSON; sends nothing."""
    parser = argparse.ArgumentParser(description='Read a retained shop frame offline')
    parser.add_argument('--frame', required=True, help='Retained local frame JSON')
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument('--out', default=None)
    parser.add_argument('--print-protocol', action='store_true')
    args = parser.parse_args(argv)
    if args.print_protocol:
        print(json.dumps(SUBPAGE_PROTOCOL, ensure_ascii=False, indent=2))
        return 0
    reading = read_frame(args.frame, threshold=args.threshold)
    text = json.dumps(reading, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
