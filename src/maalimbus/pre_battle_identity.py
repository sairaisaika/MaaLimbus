"""Independent identity teachers for a real pre-battle team screen.

The neural shadow may not approve its own labels, so every identity claim used
for correctness here comes from a teacher that never reads the detector:

* the native OCR caption plus its level band, resolved against the revisioned
  public catalogue index by exact normalised alias, and by character
  subsequence only while the match stays unique;
* the card-corner sinner emblem, matched with native template matching against
  references whose labels were fixed by the caption teacher on a reference
  capture.

Two rules are structural, not conventions:

* a caption that does not resolve stays unknown - an unresolved caption is
  evidence of a gap, never a licence to guess or to copy the model;
* a grid slot with no measured card is reported missing, never as an empty or
  unknown card, because the team screen always seats twelve sinners.

``identity_report`` assembles one such reading per grid slot into a single
report that states both counts and both slot lists, so the twelve-slot invariant
travels with the evidence instead of living in the caller's head.
"""
import re
import unicodedata

from .storage import SINNERS

CARD_ORIGIN = (350, 225)
CARD_STEP = (198, 298)
CARD_SIZE = (185, 273)
TITLE_BAND = (0, 180, 190, 105)
CORNER_BADGE = (140, 4, 44, 44)
# Measured over 1878 retained PRE_BATTLE_TEAM frames: the skill line's centre sits
# 183..196 below the card origin, the printed title 204..230, and a level band either
# 161..199 or 218..219. The caption therefore starts above the skill line and the level
# window has to reach the lower row's band, or those cards report no level at all.
LEVEL_WINDOW = (150, 222)
CAPTION_WINDOW = (200, 280)
LINE_TOLERANCE = 12
LEVEL_PATTERN = re.compile(r'^lv\.?(\d{1,3})$', re.I)
SUBSEQUENCE_MINIMUM = 12
UNRESOLVED_RATIO = .6
SLOTS = 12
SLOT_STATES = ('measured', 'missing')
CARD_STATES = ('measured_card', 'missing_grid_slot')


def normalized(value):
    """Whitespace-free NFKC casefold, identical to the ownership reconciler."""
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).casefold()


def card_origin(grid_slot):
    if type(grid_slot) is not int or not 0 <= grid_slot < SLOTS:
        raise ValueError('Invalid grid slot')
    column, row = grid_slot % 6, grid_slot // 6
    return CARD_ORIGIN[0] + column * CARD_STEP[0], CARD_ORIGIN[1] + row * CARD_STEP[1]


def card_box(grid_slot):
    x, y = card_origin(grid_slot)
    return [x, y, CARD_SIZE[0], CARD_SIZE[1]]


def title_band_roi(grid_slot):
    """Absolute frame ROI holding both the printed title and its Lv. band."""
    x, y = card_origin(grid_slot)
    return [x + TITLE_BAND[0], y + TITLE_BAND[1], TITLE_BAND[2], TITLE_BAND[3]]


def corner_badge_roi(grid_slot):
    """Absolute frame ROI of the card-corner sinner emblem."""
    x, y = card_origin(grid_slot)
    return [x + CORNER_BADGE[0], y + CORNER_BADGE[1], CORNER_BADGE[2], CORNER_BADGE[3]]


def level_value(text):
    """The printed level, or None when the token is not a level band reading."""
    match = LEVEL_PATTERN.fullmatch(normalized(text))
    return int(match.group(1)) if match else None


def _centre(box):
    return box[0] + box[2] / 2, box[1] + box[3] / 2


def _reading_order(tokens):
    lines = []
    for token in sorted(tokens, key=lambda t: _centre(t['box'])[1]):
        centre = _centre(token['box'])[1]
        if not lines or abs(centre - lines[-1][0]) > LINE_TOLERANCE:
            lines.append((centre, [token]))
        else:
            lines[-1][1].append(token)
    return [t for _, line in lines for t in sorted(line, key=lambda t: t['box'][0])]


def read_caption(tokens, grid_slot):
    """Split one card's native OCR tokens into a printed caption and a level band.

    Only tokens whose centre sits inside this card's own cell and inside either
    the level window or the caption window are considered, so a neighbouring
    card or an ornament can never contribute to this card's caption.
    """
    x, y, width, height = card_box(grid_slot)
    captions, levels, rejected = [], [], []
    for token in tokens:
        text = (token.get('text') or '').strip()
        if not text:
            continue
        cx, cy = _centre(token['box'])
        inside = x <= cx <= x + width and y <= cy <= y + height
        offset = cy - y
        if not inside or not (LEVEL_WINDOW[0] <= offset <= CAPTION_WINDOW[1]):
            rejected.append(text)
            continue
        level = level_value(text)
        if level is not None:
            if LEVEL_WINDOW[0] <= offset <= LEVEL_WINDOW[1]:
                levels.append(dict(text=text, box=list(token['box']), level=level,
                                   score=token.get('score')))
            else:
                rejected.append(text)
            continue
        if not re.search(r'[0-9A-Za-z]', text) or offset < CAPTION_WINDOW[0]:
            rejected.append(text)
            continue
        captions.append(dict(text=text, box=list(token['box']), score=token.get('score')))
    ordered = _reading_order(captions)
    scores = [t['score'] for t in ordered if isinstance(t['score'], (int, float))]
    return dict(grid_slot=grid_slot, card_box=card_box(grid_slot), slot_state='measured',
        card_state='measured_card',
        caption=' '.join(t['text'] for t in ordered) if ordered else None,
        caption_tokens=ordered, rejected_tokens=rejected,
        caption_score=min(scores) if scores else None,
        level=levels[0]['level'] if len(levels) == 1 else None,
        level_tokens=levels)


def alias_index(index, locales=('en', 'jp')):
    """Every revisioned catalogue title that names one identity, per locale."""
    rows = []
    for entry in index['identities']:
        for locale in locales:
            title = (entry.get('titles') or {}).get(locale)
            if not title:
                continue
            rows.append(dict(identity_id=entry['id'], sinner_index=entry['sinner_index'],
                sinner=entry['sinner'], locale=locale, title=title,
                alias=normalized(title)))
    return rows


def _subsequence(needle, haystack):
    stream = iter(haystack)
    return all(character in stream for character in needle)


def resolve_caption(caption, aliases, *, exact_only=False):
    """Resolve a printed caption, or refuse it; a refusal is never a guess."""
    alias = normalized(caption)
    if len(alias) < 4:
        return dict(resolved=False, alias=alias, reason='caption_too_short')
    exact = [row for row in aliases if row['alias'] == alias]
    candidates, method = exact, 'exact_alias'
    if not exact and not exact_only:
        if len(alias) >= SUBSEQUENCE_MINIMUM:
            contained = [row for row in aliases if _subsequence(alias, row['alias'])
                         and len(alias) >= UNRESOLVED_RATIO * len(row['alias'])]
            if contained:
                candidates, method = contained, 'unique_subsequence'
    if not candidates:
        return dict(resolved=False, alias=alias, reason='no_catalogue_alias_matches')
    identities = {row['identity_id'] for row in candidates}
    if len(identities) != 1:
        return dict(resolved=False, alias=alias, reason='ambiguous_catalogue_alias',
            identity_ids=sorted(identities))
    return dict(resolved=True, alias=alias, method=method,
        identity_id=candidates[0]['identity_id'], sinner_index=candidates[0]['sinner_index'],
        sinner=candidates[0]['sinner'], matched_titles=sorted({row['title'] for row in candidates}),
        locales=sorted({row['locale'] for row in candidates}),
        candidate_count=len(candidates))


def badge_sample(pixels, box, size=(32, 32)):
    """Blurred normalised luminance of one emblem; framing and level removed."""
    import cv2
    x, y, width, height = box
    patch = pixels[max(0, y):y + height, max(0, x):x + width]
    if patch.size == 0 or patch.shape[0] < 8 or patch.shape[1] < 8:
        return None, 0.0
    grey = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype('float32')
    grey = cv2.resize(grey, size, interpolation=cv2.INTER_AREA)
    grey -= grey.mean()
    deviation = float(grey.std())
    return (grey / deviation if deviation > 1e-6 else grey), deviation


def nearest_badge(sample, references):
    """Rank labelled emblem references by mean absolute difference."""
    if sample[0] is None or sample[1] < 6.0:
        return None
    ranked = []
    for reference in references:
        if reference['sample'][0] is None:
            continue
        ranked.append((float(abs(sample[0] - reference['sample'][0]).mean()),
                       reference['sinner_index'], reference['sinner'], reference['source']))
    if not ranked:
        return None
    ranked.sort(key=lambda row: (row[0], row[1]))
    best = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    return dict(sinner_index=best[1], sinner=best[2], distance=round(best[0], 4),
        runner_up_sinner_index=None if runner is None else runner[1],
        runner_up=None if runner is None else runner[2],
        runner_up_distance=None if runner is None else round(runner[0], 4),
        margin=None if runner is None else round(runner[0] - best[0], 4))


def missing_slot(grid_slot, reason):
    """A slot with no measured card: explicitly missing, never empty or unknown."""
    return dict(grid_slot=grid_slot, card_box=card_box(grid_slot), slot_state='missing',
        card_state='missing_grid_slot', caption=None, caption_tokens=[], rejected_tokens=[],
        caption_score=None, level=None, level_tokens=[], missing_reason=reason)


REPORT_SCHEMA = 1
TEACHER = 'native_caption_alias_plus_corner_emblem'
ABSENT_REASON = 'no_card_border_measured'


def slot_row(grid_slot, tokens, *, present=True, pixels=None, aliases=None, references=None,
             missing_reason=ABSENT_REASON):
    """One of the twelve slots, with both teachers' reading of it.

    ``present`` is the caller's own measurement that a card stands in this cell.
    This teacher never infers presence from OCR, so a slot the caller did not
    measure becomes an explicitly missing row instead of an empty reading.
    """
    if not present:
        row = missing_slot(grid_slot, missing_reason)
        row['resolution'] = dict(resolved=False, reason='slot_missing')
        row['badge'] = None
        row['badge_reason'] = 'slot_missing'
        return row
    row = read_caption(tokens, grid_slot)
    caption = row['caption']
    if aliases is None:
        row['resolution'] = dict(resolved=False, reason='no_catalogue_index')
    elif caption is None:
        row['resolution'] = dict(resolved=False, reason='caption_not_read')
    else:
        row['resolution'] = resolve_caption(caption, aliases)
    if pixels is None:
        row['badge'], row['badge_reason'] = None, 'no_frame_pixels'
    elif references is None:
        row['badge'], row['badge_reason'] = None, 'no_corner_emblem_references'
    else:
        row['badge'] = nearest_badge(badge_sample(pixels, corner_badge_roi(grid_slot)),
                                     references)
        row['badge_reason'] = None if row['badge'] else 'corner_emblem_not_measurable'
    return row


def identity_report(tokens, *, present_slots, pixels=None, aliases=None, references=None,
                    presence_source=ABSENT_REASON):
    """Assemble all twelve grid slots of one real team screen into one report.

    The twelve-slot invariant is structural rather than conventional: the report
    always holds twelve rows, every row is either ``measured`` or ``missing``,
    and both counts and both slot lists are stated, so a grid position that was
    not measured can never be read as an empty or unknown card. A card that was
    measured but whose caption does not resolve stays an unresolved row with a
    named reason, which is the honest gap the emblem teacher exists to cover.

    ``present_slots`` is the caller's own pixel measurement. Nothing in this
    report consults a detector, and nothing here may be used to claim one did.
    """
    slots_hint = list(present_slots)
    if any(type(slot) is not int or not 0 <= slot < SLOTS for slot in slots_hint):
        raise ValueError('Present slots must be grid slots 0..11')
    if len(set(slots_hint)) != len(slots_hint):
        raise ValueError('Present slots must be unique')
    measured = set(slots_hint)
    slots = [slot_row(slot, tokens, present=slot in measured, pixels=pixels,
                      aliases=aliases, references=references,
                      missing_reason=presence_source)
             for slot in range(SLOTS)]
    reasons = {}
    for row in slots:
        reason = row['resolution'].get('reason')
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
    return dict(schema_version=REPORT_SCHEMA, teacher=TEACHER, detector_read=False,
        slot_count=SLOTS, presence_source=presence_source,
        slot_states={'measured': len(measured), 'missing': SLOTS - len(measured)},
        measured_slots=sorted(measured),
        missing_slots=sorted(set(range(SLOTS)) - measured),
        resolved_slots=[row['grid_slot'] for row in slots
                        if row['resolution'].get('resolved') is True],
        unresolved_slots=[row['grid_slot'] for row in slots
                          if row['resolution'].get('resolved') is not True],
        identity_ids={row['grid_slot']: row['resolution']['identity_id'] for row in slots
                      if row['resolution'].get('resolved') is True},
        unresolved_reasons=reasons, slots=slots,
        all_slots_accounted_for=len(slots) == SLOTS)


def learned_references(report, pixels, *, source='caption_teacher'):
    """Label a corner emblem only where the caption teacher already named it.

    A slot whose caption stayed unresolved, ambiguous or missing contributes no
    reference at all: a reference store may not be filled from a guess, and this
    is the only way a labelled emblem ever enters one.
    """
    if pixels is None:
        return []
    references = []
    for row in report['slots']:
        resolution = row.get('resolution') or {}
        if resolution.get('resolved') is not True:
            continue
        sample = badge_sample(pixels, corner_badge_roi(row['grid_slot']))
        if sample[0] is None:
            continue
        references.append(dict(sample=sample, sinner_index=resolution['sinner_index'],
            sinner=resolution['sinner'], source=source,
            identity_id=resolution['identity_id'], grid_slot=row['grid_slot'],
            caption=row['caption']))
    return references


def agrees_with_saved_team(report, saved_sinners):
    """Whether the twelve sinners this report read are the saved team's twelve.

    This is the claim a page can support without knowing its own card order, so
    it is the one the run may lean on when the order badges are unreadable. The
    verdict is only ``verified`` from twelve resolved identities whose multiset
    equals the saved one; any unresolved slot is a gap and leaves it unproven.
    """
    order = list(saved_sinners)
    if len(order) != SLOTS or any(type(value) is not int for value in order):
        raise ValueError('A saved deployment order seats twelve sinner indexes')
    read = {}
    for row in report['slots']:
        resolution = row.get('resolution') or {}
        if resolution.get('resolved') is True:
            read[row['grid_slot']] = resolution['sinner_index']
    unread = sorted(set(range(SLOTS)) - set(read))
    saved_counts, read_counts = {}, {}
    for value in order:
        saved_counts[value] = saved_counts.get(value, 0) + 1
    for value in read.values():
        read_counts[value] = read_counts.get(value, 0) + 1
    missing_from_page = sorted(value for value in set(order)
                               if read_counts.get(value, 0) < saved_counts[value])
    absent_from_saved = sorted(value for value in set(read.values())
                               if saved_counts.get(value, 0) < read_counts[value])
    verified = (not unread and not missing_from_page and not absent_from_saved
                and len(read) == SLOTS)
    return dict(verified=verified, read_slots=sorted(read),
        read_sinner_indexes={slot: read[slot] for slot in sorted(read)},
        unread_slots=unread, saved_sinner_indexes=order,
        saved_but_not_read=missing_from_page, read_but_not_saved=absent_from_saved,
        teacher=report['teacher'], detector_read=False)


def agrees_with_saved_order(report, saved_sinners, order_badges):
    """Whether the page already carries the saved order, slot by slot.

    ``order_badges`` is the printed 1-based deployment number of each grid slot,
    or ``None`` where that badge was not read - the same measurement the driver's
    own ``carries_saved_order`` uses. The badge, not the grid position, is what
    ties a card to a deployment position, so this refuses to answer without it
    rather than silently assuming the page is laid out in order.
    """
    order = list(saved_sinners)
    badges = list(order_badges)
    if len(order) != SLOTS or any(type(value) is not int for value in order):
        raise ValueError('A saved deployment order seats twelve sinner indexes')
    if len(badges) != SLOTS:
        raise ValueError('Order badges must cover the twelve grid slots')
    agreed, mismatched, unaligned, unread = [], [], [], []
    for row in report['slots']:
        slot = row['grid_slot']
        resolution = row.get('resolution') or {}
        badge = badges[slot]
        if resolution.get('resolved') is not True:
            unread.append(slot)
        elif badge is None:
            unaligned.append(slot)
        elif order[badge - 1] == resolution['sinner_index']:
            agreed.append(slot)
        else:
            mismatched.append(dict(grid_slot=slot, order_badge=badge,
                saved_sinner_index=order[badge - 1],
                read_sinner_index=resolution.get('sinner_index'),
                read_sinner=resolution.get('sinner'),
                identity_id=resolution.get('identity_id')))
    return dict(verified=len(agreed) == SLOTS, agreed_slots=agreed,
        agreed_identities={slot: report['identity_ids'][slot] for slot in agreed},
        mismatched=mismatched, unaligned_slots=unaligned, unresolved_slots=unread,
        saved_sinner_indexes=order, order_badges=badges,
        teacher=report['teacher'], detector_read=False)


def sinner_name(sinner_index):
    if type(sinner_index) is not int or not 1 <= sinner_index <= len(SINNERS):
        raise ValueError('Invalid sinner index')
    return SINNERS[sinner_index - 1]
