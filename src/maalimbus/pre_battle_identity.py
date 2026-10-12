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
"""
import re
import unicodedata

from .storage import SINNERS

CARD_ORIGIN = (350, 225)
CARD_STEP = (198, 298)
CARD_SIZE = (185, 273)
TITLE_BAND = (0, 180, 190, 105)
CORNER_BADGE = (140, 4, 44, 44)
LEVEL_WINDOW = (150, 205)
CAPTION_WINDOW = (185, 280)
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


def sinner_name(sinner_index):
    if type(sinner_index) is not int or not 1 <= sinner_index <= len(SINNERS):
        raise ValueError('Invalid sinner index')
    return SINNERS[sinner_index - 1]
