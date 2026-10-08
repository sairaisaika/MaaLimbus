"""Bind each observed gift to its own Mounting Trials; no positional default.

English trial grammar is deliberately finite. Updated/unknown text and Japanese
trials refuse until independently validated, rather than inheriting old artwork.
"""
from dataclasses import dataclass, asdict
import re

from .gift_vision import normalized
from .reward_vision import gift_cards, counter_state, GIFT_COUNTER_BAND, button_mean
from .vision import find


@dataclass(frozen=True)
class Trial:
    level: int
    kind: str
    amount: int
    components: tuple = ()

    @property
    def penalty(self):
        # Survival-first heuristic: offense can change clashes; defense/HP mainly
        # lengthen fights. These weights are policy, not game formulas.
        weights = {'offense': 90, 'defense': 10, 'damage_reduction': 3, 'hp': 1, 'none': 0, 'damage_dealt': 20}
        effects=self.components or ((self.kind,self.amount),)
        return self.level * 30 + sum(amount*weights[kind] for kind,amount in effects)


@dataclass(frozen=True)
class Offer:
    title: str
    canonical: str
    keywords: frozenset
    box: tuple
    trial: Trial
    owned: bool
    selection_source: str = 'counter'

    def identity(self):
        value = dict(title=self.title, canonical=self.canonical,
                     trial=asdict(self.trial), owned=self.owned)
        if not self.trial.components:value['trial'].pop('components')
        if self.selection_source != 'counter':
            value['selection_source'] = self.selection_source
        return value


GRAMMAR = ((r'Defense Level\s*\+\s*(\d+)', 'defense'),
           (r'Offense Level\s*\+\s*(\d+)', 'offense'),
           (r'Damage Taken\s*[-−]\s*(\d+(?:\.\d+)?)\s*%', 'damage_reduction'),
           (r'Max HP\s*\+\s*(\d+(?:\.\d+)?)\s*%', 'hp'),
           (r'Damage Dealt\s*\+\s*(\d+(?:\.\d+)?)\s*%', 'damage_dealt'))


def parse_trial(level, records):
    if len({r.box for r in records})!=len(records):
        raise ValueError('floor_gift_enemy_trial_not_unique')
    # Complete wrapped text, ordered by row then horizontal position. Each comma
    # separates an independently supported effect; no unknown fragment is dropped.
    rows=[]
    for record in sorted(records,key=lambda r:(r.box[1]+r.box[3]/2,r.box[0])):
        cy=record.box[1]+record.box[3]/2
        if rows and abs(cy-rows[-1][0])<=12:rows[-1][1].append(record)
        else:rows.append((cy,[record]))
    text=' '.join(' '.join(r.text.strip() for r in sorted(row,key=lambda r:r.box[0])) for _,row in rows)
    effects=[]
    remaining=text.strip()
    while remaining:
        matches=[(kind,float(m[1]),m.end()) for pattern,kind in GRAMMAR
                 if (m:=re.match(pattern+r'(?=\s|,|$)',remaining,re.I))]
        if len(matches)!=1 or not 0<matches[0][1]<=100:
            raise ValueError('floor_gift_enemy_trial_unknown')
        kind,amount,end=matches[0];effects.append((kind,amount))
        remaining=remaining[end:].strip()
        if remaining.startswith(','):
            remaining=remaining[1:].strip()
            if not remaining:raise ValueError('floor_gift_enemy_trial_unknown')
    if not 0<level<=30 or not 1<=len(effects)<=2 or len({kind for kind,_ in effects})!=len(effects):
        raise ValueError('floor_gift_enemy_trial_unknown')
    if len(effects)==1:return Trial(level,*effects[0])
    return Trial(level,'compound',0,tuple(effects))


def observe(records, size, catalog, *, image=None, select_box=None):
    """Require complete one-to-one title/card/trial correspondence and a counter."""
    state = counter_state({'ocr': [dict(text=r.text, box=r.box, score=r.score)
                                   for r in records], 'size': size}, band=GIFT_COUNTER_BAND)
    boxes = gift_cards(records, size)
    if state is None and len(boxes) == 1:
        return observe_single_free(records, size, catalog, boxes[0], image, select_box)
    if state is None or not 1 <= len(boxes) <= 6:
        raise ValueError('floor_gift_counter_or_cards_not_proven')
    centers = [b[0]+b[2]/2 for b in boxes]
    bounds = [0]+[(a+b)/2 for a,b in zip(centers,centers[1:])]+[size[0]]
    offers = []
    for index, box in enumerate(boxes):
        left, right = bounds[index]/size[0], bounds[index+1]/size[0]
        titles = find(records, r'.+', (left,.245,right,.30), size,.9)
        if len(titles) != 1:
            raise ValueError('floor_gift_title_not_unique')
        title = titles[0].text
        canonical = catalog.text_identity(title)
        if canonical is None:
            raise ValueError('floor_gift_identity_unknown')
        trials = find(records, r'^Mounting Trials$', (left,.57,right,.62),size,.9)
        levels = find(records, r'^\+\s*\d+$', (left,.62,right,.67),size,.85)
        effects = find(records, r'.+', (left,.68,right,.74),size,.9)
        if len(trials)!=1 or len(levels)!=1 or not effects:
            raise ValueError('floor_gift_enemy_trial_not_unique')
        level = int(re.findall(r'\d+', levels[0].text)[0])
        trial=parse_trial(level,effects)
        owned = bool(find(records,r'^Owned$',(left,.13,right,.25),size,.9))
        offers.append(Offer(title,canonical,frozenset(catalog.entries[canonical]['keywords']),
                            tuple(box),trial,owned))
    if len({normalized(o.title) for o in offers})!=len(offers):
        raise ValueError('floor_gift_duplicate_identity')
    if not 0 <= state['chosen'] <= state['required'] <= len(offers):
        raise ValueError('floor_gift_counter_out_of_range')
    return offers, state


def observe_single_free(records, size, catalog, box, image, select_box):
    """One centered free gift: button state replaces the absent pick counter.

    This narrow layout is independent of the multi-card Mounting Trials page.
    A dim→lit transition is selection evidence only; GET and its successor are
    still required by the durable transaction before claiming acquisition.
    """
    if not .44 <= (box[0]+box[2]/2)/size[0] <= .56:
        raise ValueError('single_free_gift_geometry_unknown')
    if any(re.search(r'Mounting|Trials|Enemy Level|Defense Level|Offense Level|Damage Taken|Max HP|Lunacy|Modules?|Purchase|Cost', r.text, re.I) for r in records):
        raise ValueError('single_free_gift_trial_or_cost_present')
    titles = find(records, r'.+', (.40,.245,.60,.30), size,.9)
    select = find(records, r'^Select$', (.84,.77,.94,.84), size,.9)
    refuse = find(records, r'^Refuse Gift$', (.68,.77,.80,.84), size,.9)
    if len(titles)!=1 or len(select)!=1 or len(refuse)!=1:
        raise ValueError('single_free_gift_identity_or_controls_missing')
    canonical = catalog.text_identity(titles[0].text)
    if canonical is None:
        raise ValueError('floor_gift_identity_unknown')
    # Require the configured button patch to belong to the freshly read Select.
    if select_box is None or not (select[0].box[0] <= select_box[0]+select_box[2]/2 <= select[0].box[0]+select[0].box[2]
        and select[0].box[1] <= select_box[1]+select_box[3]/2 <= select[0].box[1]+select[0].box[3]):
        raise ValueError('single_free_gift_select_geometry_unknown')
    mean = button_mean(image, select_box)
    edges = single_free_selection_edges(image, box, size)
    dim = mean is not None and mean <= 25 and edges and max(edges)<.05
    lit = mean is not None and mean >= 45 and edges and min(edges)>=.25
    if not (dim or lit):
        raise ValueError('single_free_gift_selection_ambiguous')
    offer = Offer(titles[0].text, canonical, frozenset(catalog.entries[canonical]['keywords']),
                  tuple(box), Trial(0,'none',0), False, 'single_free_select_button')
    return [offer], dict(chosen=int(lit), required=1)


def single_free_selection_edges(image, box, size):
    """Four orange UI outline segments, outside the gift artwork and description.

    Geometry measured from the actual unselected/selected Lightning Rod pair
    window-20261008-091114. Every segment must agree with the Select state.
    This identifies a UI selection, never the gift via its cover colors.
    """
    if image is None:return None
    import cv2
    scale=size[0]/1920;cx=box[0]+box[2]/2
    # Acquire's OCR box moves upward when selected. The centered card's UI
    # edges stay fixed; do not move the outline probes with that text box.
    patches=[(cx-195*scale,250*scale,12*scale,560*scale),
             (cx+184*scale,250*scale,12*scale,560*scale),
             (cx-175*scale,228*scale,350*scale,15*scale),
             (cx-175*scale,835*scale,350*scale,15*scale)]
    values=[]
    for patch in patches:
        x,y,w,h=map(round,patch)
        if x<0 or y<0 or x+w>image.shape[1] or y+h>image.shape[0]:return None
        hsv=cv2.cvtColor(image[y:y+h,x:x+w],cv2.COLOR_BGR2HSV)
        values.append(float(((hsv[:,:,0]>=10)&(hsv[:,:,0]<=40)&(hsv[:,:,1]>=160)&(hsv[:,:,2]>=180)).mean()))
    return values


def rank(offers, team, selected):
    selected = {normalized(n) for n in selected}
    ranking = []
    for offer in offers:
        if normalized(offer.title) in selected or offer.canonical in team.block:
            continue
        preferred = offer.canonical in team.allow or bool(offer.keywords & team.keywords)
        # Preference offsets a modest trial, but never unconditionally beats a
        # large clash penalty. Non-synergy gifts have no invented roster benefit.
        score = offer.trial.penalty - (40 if preferred else 0) + (60 if offer.owned else 0)
        ranking.append(dict(title=offer.title, canonical=offer.canonical,
                            score=score, trial=asdict(offer.trial),
                            preferred=preferred, owned=offer.owned))
    return sorted(ranking,key=lambda r:(r['score'],r['title']))
